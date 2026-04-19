#![allow(clippy::manual_map)]

use image::{
    DynamicImage, GrayAlphaImage, ImageBuffer, ImageReader, LumaA, RgbImage, Rgba, RgbaImage,
    imageops,
};
use libblur::{self, GaussianBlurParams};
use pyo3::prelude::*;
use rand::Rng;
use std::io::BufReader;
use std::path::PathBuf;
use std::{
    collections::hash_map::DefaultHasher,
    hash::{Hash, Hasher},
};
use zune_jpeg::JpegDecoder;

pub mod gradient;
pub mod noise;
pub mod resize;

#[pymodule]
fn albumpaper_rs(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(generate_save_wallpaper, module)?)?;
    Ok(())
}

type Color = [u8; 3];

#[derive(FromPyObject, Hash, PartialEq, Eq, Clone)]
pub struct PythonImageBuffer {
    pub size: [u32; 2],
    pub buffer: Vec<u8>,
}

impl PythonImageBuffer {
    fn to_image(&self) -> RgbImage {
        RgbImage::from_raw(self.size[0], self.size[1], self.buffer.clone()).unwrap()
    }
}

#[derive(Debug)]
pub struct AppPaths {
    default_wallpaper: PathBuf,
    generated_wallpaper: PathBuf,
    drop_shadow: PathBuf,
}

impl AppPaths {
    fn from(python_root: String) -> Self {
        let root = PathBuf::from(python_root);
        AppPaths {
            default_wallpaper: root.join("cache\\images\\default_wallpaper.jpg"),
            generated_wallpaper: root.join("cache\\images\\generated_wallpaper.png"),
            drop_shadow: root.join("cache\\images\\drop_shadow.png"),
        }
    }
}

#[derive(FromPyObject, Hash, PartialEq, Eq, Clone)]
pub struct GenerationConfig {
    pub python_root: String,
    pub artwork: PythonImageBuffer,
    pub background: BackgroundConfig,
    pub foreground: ForegroundConfig,
    pub display_geometry: [u32; 2],
    pub available_geometry: [u32; 4],
}

#[derive(FromPyObject, Hash, PartialEq, Eq, Clone)]
pub struct ForegroundConfig {
    pub show_artwork: bool,
    pub artwork_resize: u32,
    pub drop_shadow: bool,
    pub spotify_code: Option<PythonImageBuffer>,
}

#[derive(FromPyObject, Hash, PartialEq, Eq, Clone)]
pub struct BackgroundConfig {
    pub background_type: String,
    pub blur_radius: Option<u32>,
    pub color1: Option<Color>,
    pub color2: Option<Color>,
    pub no_colors: Option<u16>,
}

#[pyfunction]
pub fn generate_save_wallpaper(config: GenerationConfig) {
    let app_paths = AppPaths::from(config.python_root.clone());
    let image = generate_wallpaper(config, &app_paths);
    image.save(app_paths.generated_wallpaper).unwrap();
}

// In seperate function for possible caching
pub fn generate_wallpaper(config: GenerationConfig, app_paths: &AppPaths) -> RgbImage {
    let artwork = config.artwork.to_image();

    let background = match config.background.background_type.as_str() {
        "solidcolor" => RgbImage::from_pixel(
            config.display_geometry[0],
            config.display_geometry[1],
            image::Rgb(config.background.color1.unwrap()),
        ),
        "lineargradient" => gradient::linear(
            config.display_geometry,
            config.background.color1.unwrap(),
            config.background.color2.unwrap(),
        ),
        "radialgradient" => gradient::radial(
            config.display_geometry,
            config.background.color1.unwrap(),
            config.background.color2.unwrap(),
            config.foreground.artwork_resize,
        ),
        "colorednoise" => {
            let mut hasher = DefaultHasher::new();
            config.artwork.buffer.hash(&mut hasher);
            let seed: u32 = hasher.finish() as u32;
            let background = noise::colored(
                config.display_geometry,
                config.background.color1.unwrap(),
                config.background.color2.unwrap(),
                config.background.no_colors.unwrap(),
                seed,
            );

            if let Some(blur_radius) = config.background.blur_radius {
                add_blur(DynamicImage::ImageRgb8(background), blur_radius).to_rgb8()
            } else {
                background
            }
        }
        "albumart" => image_background(
            artwork.clone(),
            config.display_geometry,
            config.background.blur_radius,
        ),
        "defaultwallpaper" => {
            let default_wallpaper = decode_jpeg(app_paths.default_wallpaper.clone());
            resize_default_wallpaper(&default_wallpaper, config.display_geometry, app_paths);
            image_background(
                default_wallpaper,
                config.display_geometry,
                config.background.blur_radius,
            )
        }
        unknown => panic!("Unknown background type '{unknown}'"),
    };

    let mut base = RgbaImage::new(config.display_geometry[0], config.display_geometry[1]);

    // Background Paste
    let x = (config.display_geometry[0] as i64 - background.width() as i64) / 2;
    let y = (config.display_geometry[1] as i64 - background.height() as i64) / 2;

    let background = DynamicImage::ImageRgb8(background).to_rgba8();
    imageops::overlay(&mut base, &background, x, y);

    if !config.foreground.show_artwork {
        return DynamicImage::ImageRgba8(base).to_rgb8();
    }

    let foreground = generate_foreground(
        artwork,
        config.foreground.artwork_resize,
        config.foreground.spotify_code,
        config.display_geometry,
        config.available_geometry,
    );

    if config.foreground.drop_shadow {
        let drop_shadow_image = match ImageReader::open(app_paths.drop_shadow.clone()) {
            Ok(drop_shadow_data) => drop_shadow_data.decode().unwrap().to_rgba8(),
            Err(_e) => {
                let drop_shadow = generate_drop_shadow(&foreground);
                drop_shadow.save(app_paths.drop_shadow.clone()).unwrap();
                drop_shadow
            }
        };
        imageops::overlay(&mut base, &drop_shadow_image, 0, 0);
    }

    imageops::overlay(&mut base, &foreground, 0, 0);

    DynamicImage::ImageRgba8(base).to_rgb8()
}

// Used by wallpaper and artwork backgrounds
fn image_background(
    background: RgbImage,
    display_geometry: [u32; 2],
    blur_radius: Option<u32>,
) -> RgbImage {
    let resized_background =
        resize::fast_resize(&background, display_geometry[0], display_geometry[1]);

    if let Some(blur) = blur_radius {
        add_blur(DynamicImage::ImageRgb8(resized_background), blur).into_rgb8()
    } else {
        resized_background
    }
}

fn add_blur(image: DynamicImage, blur_radius: u32) -> DynamicImage {
    let sigma = blur_radius as f64 / 2.0;

    // use the maximum kernel size possible
    let max_dimension = std::cmp::max(image.width(), image.height());
    let kernel_size = max_dimension + max_dimension % 2 + 1;

    libblur::gaussian_blur_image(
        image,
        GaussianBlurParams::new(kernel_size, sigma),
        libblur::EdgeMode2D::new(libblur::EdgeMode::Clamp),
        libblur::ConvolutionMode::Exact,
        libblur::ThreadingPolicy::Adaptive,
    )
    .unwrap()
}

pub fn generate_drop_shadow(foreground: &RgbaImage) -> RgbaImage {
    let (width, height) = foreground.dimensions();

    let mut rng = rand::rng();

    let mask = GrayAlphaImage::from_fn(width, height, |x, y| {
        let rgba_pixel = foreground.get_pixel(x, y);

        LumaA([0u8, rgba_pixel[3]])
    });

    let drop_shadow = add_blur(DynamicImage::ImageLumaA8(mask), 120).to_luma_alpha8();

    // let dithered_vec = Vec::with_capacity((width*height) as usize);

    let dithered_drop_shadow =
        ImageBuffer::from_fn(drop_shadow.width(), drop_shadow.height(), |x, y| {
            let pixel = drop_shadow.get_pixel(x, y);

            let alpha_8_floor = pixel[1] as i32;
            let noise = rng.random_range(-3..=3);
            let dithered = (alpha_8_floor + noise).clamp(0, 255);

            LumaA([0u8, dithered as u8])
        });

    let drop_shadow = DynamicImage::ImageLumaA8(dithered_drop_shadow).to_rgba8();

    drop_shadow
}

fn decode_jpeg(path: PathBuf) -> RgbImage {
    let image = BufReader::new(std::fs::File::open(path).unwrap());
    let mut decoder = JpegDecoder::new(image);

    decoder.decode_headers().unwrap();
    let image_info = decoder.info().unwrap();

    let pixels = decoder.decode().unwrap();

    RgbImage::from_raw(image_info.width.into(), image_info.height.into(), pixels).unwrap()
}

// Easier to just replace cache/images/defefault_wallpaper ourselves for consitency with generated wallpapers
fn resize_default_wallpaper(
    default_wallpaper: &RgbImage,
    display_geometry: [u32; 2],
    app_paths: &AppPaths,
) {
    if default_wallpaper.dimensions() != display_geometry.into() {
        let resized_wallpaper =
            resize::fast_resize(default_wallpaper, display_geometry[0], display_geometry[1]);
        resized_wallpaper
            .save(app_paths.default_wallpaper.clone())
            .unwrap();
    };
}

fn generate_foreground(
    artwork: RgbImage,
    artwork_resize: u32,
    spotify_code: Option<PythonImageBuffer>,
    display_geometry: [u32; 2],
    available_geometry: [u32; 4],
) -> RgbaImage {
    // create transparent base
    let mut base =
        RgbaImage::from_pixel(display_geometry[0], display_geometry[1], Rgba([0, 0, 0, 0]));

    let artwork_resized = DynamicImage::ImageRgb8(resize::fast_resize(
        &artwork,
        artwork_resize,
        artwork_resize,
    ))
    .to_rgba8();

    let spacing = display_geometry[1] / 100;

    let foreground_height = match spotify_code.as_ref() {
        Some(buffer) => artwork_resize + spacing + buffer.size[1],
        None => artwork_resize,
    };

    let x: i64 = (i64::from(available_geometry[0]) - i64::from(artwork_resized.width())) / 2
        + i64::from(available_geometry[2]);
    let y = (i64::from(available_geometry[1]) - i64::from(foreground_height)) / 2
        + i64::from(available_geometry[3]);

    imageops::overlay(&mut base, &artwork_resized, x, y);

    if let Some(buffer) = spotify_code {
        let y_code = y + i64::from(artwork_resize + spacing);
        let code_image = DynamicImage::ImageRgb8(buffer.to_image()).to_rgba8();
        imageops::overlay(&mut base, &code_image, x, y_code)
    }

    base
}
