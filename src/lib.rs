#![allow(clippy::manual_map)]

use fastblur::gaussian_blur;
use image::{imageops, io::Reader as ImageReader, RgbImage};
use rayon::prelude::*;
use pyo3::prelude::*;

mod resize;

const DEFAULT_WALLPAPER_PATH: &str = "images/default_wallpaper.jpg";
const GENERATED_WALLPAPER_PATH: &str = "images/generated_wallpaper.png";

// Define module
#[pymodule]
fn albumpaper_rs(_py: Python, module: &PyModule) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(generate_save_wallpaper, module)?)?;
    Ok(())
}

type Color = [u8; 3];

// Parameters used in all of these functions
#[derive(FromPyObject, Hash, PartialEq, Eq, Clone)]
pub struct RequiredArgs {
    background_type: String,
    foreground: Foreground,
    display_geometry: [u32; 2],
    available_geometry: [u32; 4],
}

#[derive(FromPyObject, Hash, PartialEq, Eq, Clone)]
pub struct Foreground {
    artwork_buffer: Vec<u8>,
    artwork_size: [u32; 2],
    artwork_resize: u32,
}

#[derive(FromPyObject, Hash, PartialEq, Eq, Clone)]
pub struct OptionalArgs {
    blur_radius: Option<u32>,
    color1: Option<Color>,
    color2: Option<Color>,
}

#[pyfunction]
pub fn generate_save_wallpaper(
    _py: Python,
    required_args: RequiredArgs,
    optional_args: OptionalArgs,
) {
    let image = generate_wallpaper(required_args, optional_args);
    image.save(GENERATED_WALLPAPER_PATH).unwrap();
}

// In seperate function for possible caching
fn generate_wallpaper(required_args: RequiredArgs, optional_args: OptionalArgs) -> RgbImage {
    let artwork = RgbImage::from_raw(
        required_args.foreground.artwork_size[0],
        required_args.foreground.artwork_size[1],
        required_args.foreground.artwork_buffer,
    )
    .unwrap();

    let background = match &required_args.background_type[..] {
        "DefaultWallpaper" => {
            let default_wallpaper = ImageReader::open(DEFAULT_WALLPAPER_PATH)
                .unwrap()
                .decode()
                .unwrap()
                .into_rgb8();
            image_background(
                &default_wallpaper,
                required_args.display_geometry,
                optional_args.blur_radius,
            )
        }
        "Artwork" => image_background(
            &artwork,
            required_args.display_geometry,
            optional_args.blur_radius,
        ),
        "SolidColor" => {
            RgbImage::from_pixel(
                required_args.display_geometry[0],
                required_args.display_geometry[1],
                image::Rgb(optional_args.color1.unwrap()),
            )
        }
        "LinearGradient" => {
            linear_gradient(
                required_args.display_geometry,
                optional_args.color1.unwrap(),
                optional_args.color2.unwrap(),
            )
        },
        "RadialGradient" => gen_radial_gradient(
            required_args.display_geometry,
            optional_args.color1.unwrap(),
            optional_args.color2.unwrap(),
            required_args.foreground.artwork_resize,
        ),
        _ => panic!("Unknown background type"),
    };

    let artwork_resized = resize::fast_resize(
        &artwork,
        required_args.foreground.artwork_resize,
        required_args.foreground.artwork_resize,
    );
    paste_images(
        &background,
        Some(artwork_resized),
        required_args.display_geometry,
        required_args.available_geometry,
    )
}

// Used by wallpaper and artwork backgrounds
fn image_background(
    background: &RgbImage,
    display_geometry: [u32; 2],
    blur_radius: Option<u32>,
) -> RgbImage {
    if let Some(blur) = blur_radius {
        add_blur(
            background,
            display_geometry[0],
            display_geometry[1],
            blur as f32,
        )
    } else {
        resize::fast_resize(background, display_geometry[0], display_geometry[1])
    }
}

fn add_blur(image: &RgbImage, nwidth: u32, nheight: u32, blur_radius: f32) -> RgbImage {
    // Downsize the image by a factor of `scale` for faster blurring and upscale back
    // to display_geometry for final image

    let scale = 4;
    let (scaled_width, scaled_height) = (nwidth / scale, nheight / scale);
    let downscaled_image = resize::fast_resize(image, scaled_width, scaled_height);

    let mut pixels: Vec<[u8; 3]> = downscaled_image
        .into_raw()
        .chunks_exact(3)
        .map(|pixel| pixel.try_into().unwrap())
        .collect();

    gaussian_blur(
        &mut pixels,
        scaled_width.try_into().unwrap(),
        scaled_height.try_into().unwrap(),
        blur_radius / scale as f32,
    );

    let buf = pixels.into_iter().flatten().collect();
    let blurred_image = RgbImage::from_raw(scaled_width, scaled_height, buf).unwrap();
    resize::fast_resize(&blurred_image, nwidth, nheight)
}

/// Returns the raw bytes of a linear gradient image
///
/// # Arguments
///
/// * `geometry` - A tuple of the width and height of generated image
/// * `from_color` - A list of rgb values for the left color of linear gradient
/// * `to_color` - A list of rgb values for the right color of linear gradient
///
/// # Examples (in python)
///
/// ```
/// import albumpaper_rs
/// from PIL import Image
///
/// raw = albumpaper_rs.linear_gradient(
///     (1920, 1080),
///     [255, 0, 0],
///     [0, 0, 255]
/// )
///
/// image =  Image.frombuffer('RGB', [1920, 1080], raw)
///
/// ```

fn linear_gradient(geometry: [u32; 2], from_color: Color, to_color: Color) -> RgbImage {
    let [width, height] = geometry;
    let tot = (width + height) as usize;

    let channel =
        |from: u8, to: u8, dist: f32| ((to as f32 * dist) + from as f32 * (1.0 - dist)) as u8;

    let all_colours: Vec<u8> = (0..tot)
        .flat_map(|dist| {
            let scaled = dist as f32 / tot as f32;
            [
                channel(from_color[0], to_color[0], scaled),
                channel(from_color[1], to_color[1], scaled),
                channel(from_color[2], to_color[2], scaled),
            ]
        })
        .collect();

    let mut image = RgbImage::new(width, height);
    image
        .par_chunks_exact_mut(3 * width as usize)
        .enumerate()
        .for_each(|(nrow, row)| {
            let start = nrow * 3;
            let end = start + 3 * width as usize;
            row.copy_from_slice(&all_colours[start..end]);
        });

    image
}

/// Returns the raw bytes of a radial gradient image
///
/// # Arguments
///
/// * `geometry` - A tuple of the width and height of generated image
/// * `inner_color` - A list of rgb values for the centre color of radial gradient
/// * `outer_color` - A list of rgb values for the outer color of radial gradient
///
/// # Examples (in python)
///
/// ```
/// import albumpaper_rs
/// from PIL import Image
///
/// raw = albumpaper_rs.radial_gradient(
///     (1920, 1080),
///     [255, 0, 0],
///     [0, 0, 255]
/// )
///
/// image =  Image.frombuffer('RGB', [1920, 1080], raw)
///
/// ```

#[inline]
fn lerp(pct: f32, a: f32, b: f32) -> f32 {
    pct.mul_add(b - a, a)
}

#[inline]
fn distance(x: i32, y: i32) -> f32 {
    ((x * x + y * y) as f32).sqrt()
}

fn gen_radial_gradient(
    geometry: [u32; 2],
    inner_color: [u8; 3],
    outer_color: [u8; 3],
    foreground_size: u32,
) -> RgbImage {
    let mut background: RgbImage = RgbImage::new(geometry[0], geometry[1]);

    // The background will adapt to the foreground size so that the inner_color will be at the edges of the art
    // and not just at the centre of the image
    let center = ((geometry[0] / 2) as i32, (geometry[1] / 2) as i32);
    let foreground_half = (foreground_size / 2) as f32;
    let max_dist = distance(center.0, center.1) - foreground_half;
    let one_over_max_dist = 1.0 / max_dist;

    let inner_color = inner_color.map(|el| el as f32);
    let outer_color = outer_color.map(|el| el as f32);

    background
        .par_chunks_exact_mut(3 * geometry[0] as usize)
        .enumerate()
        .for_each(|(pos_y, row)| {
            for pos_x in 0..geometry[0] {
                let dist_x = pos_x as i32 - center.0;
                let dist_y = pos_y as i32 - center.1;
                let scaled_dist = (distance(dist_x, dist_y) - foreground_half) * one_over_max_dist;

                let pixel_pos = (pos_x * 3) as usize;
                let pixel = &mut row[pixel_pos..(pixel_pos + 3)];

                pixel[0] = lerp(scaled_dist, inner_color[0], outer_color[0]) as u8;
                pixel[1] = lerp(scaled_dist, inner_color[1], outer_color[1]) as u8;
                pixel[2] = lerp(scaled_dist, inner_color[2], outer_color[2]) as u8;
            }
        });
    background
}

fn paste_images(
    background: &RgbImage,
    foreground: Option<RgbImage>,
    display_geometry: [u32; 2],
    available_geometry: [u32; 4],
) -> RgbImage {
    let mut base = RgbImage::new(display_geometry[0], display_geometry[1]);

    // Background Paste
    let x = (display_geometry[0] as i64 - background.width() as i64) / 2;
    let y = (display_geometry[1] as i64 - background.height() as i64) / 2;

    imageops::overlay(&mut base, background, x, y);

    // Foreground paste
    if let Some(foreground) = foreground {
        let x = (i64::from(available_geometry[0]) - i64::from(foreground.width())) / 2
            + i64::from(available_geometry[2]);
        let y = (i64::from(available_geometry[1]) - i64::from(foreground.height())) / 2
            + i64::from(available_geometry[3]);

        imageops::overlay(&mut base, &foreground, x, y)
    }
    base
}
