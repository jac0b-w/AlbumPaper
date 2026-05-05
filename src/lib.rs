use geometrize::{SamplingParams, geometrize};
use image::{
    DynamicImage, GrayAlphaImage, ImageBuffer, ImageReader, LumaA, RgbImage, Rgba, RgbaImage,
    imageops,
};
use pyo3::prelude::*;
use rand::{RngExt, SeedableRng, rngs::SmallRng};
use std::path::PathBuf;

use crate::misc::seed_from_image;

pub mod gradient;
pub mod misc;
pub mod noise;

type Color = [u8; 3];
type Size = [u32; 2];
type Rect = [u32; 4];

const CORNER_RADIUS_FRACTION: f32 = 20.0 / 600.0;
const SPACING_DIVISOR: u32 = 100;
const DROP_SHADOW_BLUR_RADIUS: u32 = 120;

#[derive(FromPyObject, Hash, PartialEq, Eq, Clone)]
pub struct PythonImageBuffer {
    pub size: Size,
    pub buffer: Vec<u8>,
}

impl PythonImageBuffer {
    fn to_image(&self) -> RgbaImage {
        DynamicImage::from(
            RgbImage::from_raw(self.size[0], self.size[1], self.buffer.clone()).unwrap(),
        )
        .to_rgba8()
    }
}

#[derive(Debug)]
pub struct AppPaths {
    default_wallpaper: PathBuf,
    generated_wallpaper: PathBuf,
    drop_shadow: PathBuf,
}

impl From<String> for AppPaths {
    fn from(python_root: String) -> Self {
        let root = PathBuf::from(python_root);
        let images_cache_dir = root.join("cache").join("images");
        AppPaths {
            default_wallpaper: images_cache_dir.join("default_wallpaper.jpg"),
            generated_wallpaper: images_cache_dir.join("generated_wallpaper.png"),
            drop_shadow: images_cache_dir.join("drop_shadow.png"),
        }
    }
}

#[derive(FromPyObject, Hash, PartialEq, Eq, Clone)]
pub struct GenerationConfig {
    pub project_root: String,
    pub artwork: PythonImageBuffer,
    pub background: BackgroundConfig,
    pub foreground: ForegroundConfig,
    pub display_geometry: Size,
    pub available_geometry: Rect,
}

#[derive(FromPyObject, Hash, PartialEq, Eq, Clone)]
pub struct ForegroundConfig {
    pub show_artwork: bool,
    pub artwork_size: u32,
    pub drop_shadow: bool,
    pub rounded_corners: bool,
    pub spotify_code: Option<PythonImageBuffer>,
}

#[derive(FromPyObject, Hash, PartialEq, Eq, Clone)]
pub struct BackgroundConfig {
    pub background_type: String,
    pub blur_radius: Option<u32>,
    pub color1: Option<Color>,
    pub color2: Option<Color>,
    pub no_colors: Option<u16>,
    pub n_samples: Option<u32>,
}

#[pymodule]
fn albumpaper_rs(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(generate_save_wallpaper, module)?)?;
    Ok(())
}

#[pyfunction]
pub fn generate_save_wallpaper(config: GenerationConfig) {
    let app_paths = AppPaths::from(config.project_root.clone());
    let image = generate_wallpaper(config, &app_paths);
    image.save(app_paths.generated_wallpaper).unwrap();
}

pub fn generate_wallpaper(config: GenerationConfig, app_paths: &AppPaths) -> RgbaImage {
    let artwork = config.artwork.to_image();

    // for reproducability
    let mut rng = SmallRng::seed_from_u64(seed_from_image(&artwork));

    let mut base = RgbaImage::new(config.display_geometry[0], config.display_geometry[1]);

    let background = generate_background(
        &artwork,
        config.background,
        config.display_geometry,
        config.foreground.artwork_size,
        &mut rng,
        app_paths,
    );

    let drop_shadow = config.foreground.drop_shadow;

    // Background Paste
    let [x, y] = center_position(
        config.display_geometry,
        background.dimensions().into(),
        [0, 0],
    );
    imageops::overlay(&mut base, &background, x, y);

    if !config.foreground.show_artwork {
        return base;
    }

    let foreground = generate_foreground(
        artwork,
        config.foreground,
        config.display_geometry,
        config.available_geometry,
    );

    if drop_shadow {
        let drop_shadow_path = &app_paths.drop_shadow;
        let drop_shadow_image = ImageReader::open(drop_shadow_path)
            .ok()
            .and_then(|r| r.decode().ok())
            .map(|img| img.to_rgba8())
            .unwrap_or_else(|| {
                let shadow = generate_drop_shadow(&foreground, &mut rng);
                shadow.save(drop_shadow_path).unwrap();
                shadow
            });
        imageops::overlay(&mut base, &drop_shadow_image, 0, 0);
    }

    imageops::overlay(&mut base, &foreground, 0, 0);

    base
}

fn generate_drop_shadow(foreground: &RgbaImage, rng: &mut SmallRng) -> RgbaImage {
    let (width, height) = foreground.dimensions();

    let mask = GrayAlphaImage::from_fn(width, height, |x, y| {
        let rgba_pixel = foreground.get_pixel(x, y);

        LumaA([0u8, rgba_pixel[3]])
    });

    let drop_shadow =
        misc::add_blur(DynamicImage::from(mask), DROP_SHADOW_BLUR_RADIUS).to_luma_alpha8();

    let dithered_drop_shadow =
        ImageBuffer::from_fn(drop_shadow.width(), drop_shadow.height(), |x: u32, y| {
            let pixel = drop_shadow.get_pixel(x, y);

            let alpha_8_floor = pixel[1] as i32;
            let noise = rng.random_range(-3..=3);
            let dithered = (alpha_8_floor + noise).clamp(0, 255);

            LumaA([0u8, dithered as u8])
        });

    DynamicImage::from(dithered_drop_shadow).to_rgba8()
}

fn generate_background(
    artwork: &RgbaImage,
    background_config: BackgroundConfig,
    display_geometry: Size,
    artwork_size: u32,
    rng: &mut SmallRng,
    app_paths: &AppPaths,
) -> RgbaImage {
    let [width, height] = display_geometry;
    let resized_artwork = || misc::fast_resize(artwork, width, height);

    let background = match background_config.background_type.as_ref() {
        "solidcolor" => {
            let [r, g, b] = background_config.color1.unwrap();
            RgbaImage::from_pixel(width, height, Rgba([r, g, b, 255]))
        }
        "lineargradient" => DynamicImage::from(gradient::linear(
            display_geometry,
            background_config.color1.unwrap(),
            background_config.color2.unwrap(),
        ))
        .to_rgba8(),
        "radialgradient" => DynamicImage::from(gradient::radial(
            display_geometry,
            background_config.color1.unwrap(),
            background_config.color2.unwrap(),
            artwork_size,
        ))
        .to_rgba8(),
        "colorednoise" => {
            let seed: u32 = rng.random();
            DynamicImage::from(noise::colored(
                display_geometry,
                background_config.color1.unwrap(),
                background_config.color2.unwrap(),
                background_config.no_colors.unwrap(),
                seed,
            ))
            .to_rgba8()
        }
        "lowpoly" => geometrize(
            DynamicImage::from(resized_artwork()),
            geometrize::Style::Lowpoly,
            background_config.n_samples.unwrap(),
            SamplingParams::default(),
        )
        .unwrap(),
        "pointillist" => geometrize(
            DynamicImage::from(resized_artwork()),
            geometrize::Style::Pointillist { noise: 0.3 },
            background_config.n_samples.unwrap(),
            SamplingParams::default(),
        )
        .unwrap(),
        "albumart" => resized_artwork(),
        "defaultwallpaper" => {
            let default_wallpaper = ImageReader::open(&app_paths.default_wallpaper)
                .unwrap()
                .decode()
                .unwrap()
                .to_rgba8();
            misc::resize_default_wallpaper(default_wallpaper, display_geometry, app_paths)
        }
        unknown => panic!("Unknown background type '{unknown}'"),
    };

    if let Some(radius) = background_config.blur_radius {
        misc::add_blur(DynamicImage::from(background), radius).to_rgba8()
    } else {
        background
    }
}

fn generate_foreground(
    artwork: RgbaImage,
    foreground_config: ForegroundConfig,
    display_geometry: Size,
    available_geometry: Rect,
) -> RgbaImage {
    let ForegroundConfig {
        artwork_size,
        rounded_corners,
        spotify_code,
        ..
    } = foreground_config;

    let apply_rounded_corners = |img: &mut RgbaImage| {
        if rounded_corners {
            misc::round_corners(img, CORNER_RADIUS_FRACTION);
        }
    };

    // create transparent base
    let mut base =
        RgbaImage::from_pixel(display_geometry[0], display_geometry[1], Rgba([0, 0, 0, 0]));

    let mut artwork_resized = misc::fast_resize(&artwork, artwork_size, artwork_size);

    apply_rounded_corners(&mut artwork_resized);

    let spacing = display_geometry[1] / SPACING_DIVISOR;

    let foreground_height = match spotify_code.as_ref() {
        Some(buffer) => artwork_size + spacing + buffer.size[1],
        None => artwork_size,
    };

    let [w, h, off_x, off_y] = available_geometry;
    let [x, y] = center_position(
        [w, h],
        [artwork_resized.width(), foreground_height],
        [off_x as i64, off_y as i64],
    );

    imageops::overlay(&mut base, &artwork_resized, x, y);

    if let Some(buffer) = spotify_code {
        let y_code = y + i64::from(artwork_size + spacing);
        let mut code_image = buffer.to_image();
        apply_rounded_corners(&mut code_image);
        imageops::overlay(&mut base, &code_image, x, y_code)
    }

    base
}

fn center_position(container: Size, content: [u32; 2], offset: [i64; 2]) -> [i64; 2] {
    [
        (container[0] as i64 - content[0] as i64) / 2 + offset[0],
        (container[1] as i64 - content[1] as i64) / 2 + offset[1],
    ]
}
