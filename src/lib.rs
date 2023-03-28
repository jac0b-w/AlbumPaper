#![allow(clippy::manual_map)]
#![allow(clippy::too_many_arguments)]

use fastblur::gaussian_blur;
use image::{imageops, io::Reader as ImageReader, ImageBuffer, RgbImage};
use itertools::izip;
use rayon::prelude::*;

mod resize;
use pyo3::prelude::*;

const DEFAULT_WALLPAPER_PATH: &str = "images/default_wallpaper.jpg";
const GENERATED_WALLPAPER_PATH: &str = "images/generated_wallpaper.png";


// Define module
#[pymodule]
fn albumpaper_rs(_py: Python, module: &PyModule) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(linear_gradient, module)?)?;
    module.add_function(wrap_pyfunction!(radial_gradient, module)?)?;
    module.add_function(wrap_pyfunction!(artwork, module)?)?;
    module.add_function(wrap_pyfunction!(solid_color, module)?)?;
    Ok(())
}

#[derive(FromPyObject)]
pub enum Wallpaper {
    Wallpaper(DefaultWallpaper),
    Artwork(Artwork),
    SolidColor(SolidColor),
    LinearGradient(LinearGradient),
    RadialGradient(RadialGradient),
}

type Color = [u8; 3];
// Parameters used in all of these functions
#[derive(FromPyObject)]
pub struct DefaultArgs {
    foreground: Foreground,
    display_geometry: [u32; 2],
    available_geometry: [u32; 4],
}

#[derive(FromPyObject)]
pub struct Foreground {
    artwork_buffer: Vec<u8>,
    artwork_size: [u32; 2],
    artwork_resize: u32,
}

#[derive(FromPyObject)]
pub struct DefaultWallpaper {
    default_args: DefaultArgs,
    blur_radius: Option<u32>,
    default_wallpaper_path: String,
}

#[derive(FromPyObject)]
pub struct Artwork {
    default_args: DefaultArgs,
    blur_radius: Option<u32>
}

#[derive(FromPyObject)]
pub struct SolidColor {
    default_args: DefaultArgs,
    color: Color,
}

#[derive(FromPyObject)]
pub struct LinearGradient {
    default_args: DefaultArgs,
    from_color: Color,
    to_color: Color,
}

#[derive(FromPyObject)]
pub struct RadialGradient {
    default_args: DefaultArgs,
    inner_color: Color,
    outer_color: Color,
}

#[pyfunction]
pub fn generate_wallpaper(
    _py: Python,
    wallpaper: Wallpaper,
) {
    match wallpaper {
        Wallpaper::Artwork(args) => panic!(),
        _ => panic!(),
    }
}

const CHUNK_SIZE: usize = 128 * 128;

#[pyfunction]
pub fn linear_gradient(
    _py: Python,
    artwork_buf: Vec<u8>,
    buf_size: (u32, u32),
    foreground_size: Option<u32>,
    display_geometry: (u32, u32),
    available_geometry: (u32, u32, u32, u32),
    inner_color: Vec<u8>,
    outer_color: Vec<u8>,
) {
    let geometry = [display_geometry.0, display_geometry.1.try_into().unwrap()];

    let background = gen_linear_gradient(
        geometry,
        inner_color.try_into().unwrap(),
        outer_color.try_into().unwrap(),
    );

    let artwork: RgbImage = RgbImage::from_raw(buf_size.0, buf_size.1, artwork_buf).unwrap();

    let foreground = if let Some(size) = foreground_size {
        Some(resize::fast_resize(&artwork, size, size))
    } else {
        None
    };

    let final_image = paste_images(background, foreground, display_geometry, available_geometry);

    // PyBytes::new(py, final_image.as_raw()).into()
    final_image.save(GENERATED_WALLPAPER_PATH).unwrap();
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

fn gen_linear_gradient(geometry: [u32; 2], from_color: [u8; 3], to_color: [u8; 3]) -> RgbImage {
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

#[pyfunction]
pub fn radial_gradient(
    _py: Python,
    artwork_buf: Vec<u8>,
    buf_size: (u32, u32),
    foreground_size: Option<u32>,
    display_geometry: (u32, u32),
    available_geometry: (u32, u32, u32, u32),
    inner_color: Vec<u8>,
    outer_color: Vec<u8>,
) {
    let geometry = (
        display_geometry.0.try_into().unwrap(),
        display_geometry.1.try_into().unwrap(),
    );

    let radius_size = match foreground_size {
        Some(size) => size.try_into().unwrap(),
        None => 0,
    };
    let background = gen_radial_gradient(geometry, inner_color, outer_color, radius_size);

    let foreground = if let Some(size) = foreground_size {
        let artwork: RgbImage = RgbImage::from_raw(buf_size.0, buf_size.1, artwork_buf).unwrap();
        Some(resize::fast_resize(&artwork, size, size))
    } else {
        None
    };

    let final_image = paste_images(background, foreground, display_geometry, available_geometry);

    // PyBytes::new(py, final_image.as_raw()).into()
    final_image.save(GENERATED_WALLPAPER_PATH).unwrap();
}

fn gen_radial_gradient(
    geometry: (i32, i32),
    inner_color: Vec<u8>,
    outer_color: Vec<u8>,
    foreground_size: i32,
) -> RgbImage {
    let mut background: RgbImage = RgbImage::new(geometry.0 as u32, geometry.1 as u32);

    let distance = |x: i32, y: i32| (((x).pow(2) + (y).pow(2)) as f64).sqrt();

    // The background will adapt to the foreground size so that the inner_color will be at the edges of the art
    // and not just at the centre of the image
    let max_dist =
        distance((geometry.0 / 2) as i32, (geometry.1 / 2) as i32) - (foreground_size / 2) as f64;

    background
        .par_chunks_exact_mut(3)
        .enumerate()
        .for_each(|(pixel_num, pixel)| {
            let x_dist: i32 = pixel_num as i32 % geometry.0 - geometry.0 / 2;
            let y_dist: i32 = pixel_num as i32 / geometry.0 - geometry.1 / 2;
            let scaled_dist = (distance(x_dist, y_dist) - (foreground_size / 2) as f64) / max_dist;

            for (subpixel, outer_sub, inner_sub) in izip!(pixel, &outer_color, &inner_color) {
                *subpixel = ((*outer_sub as f64 * scaled_dist)
                    + (*inner_sub as f64 * (1.0 - scaled_dist))) as u8
            }
        });
    background
}

#[pyfunction]
pub fn artwork(_py: Python, args: DefaultArgs, blur_radius: Option<f32>) {
    let [width, height] = args.display_geometry;
    let max_dim = std::cmp::max(width, height);

    let artwork: RgbImage = RgbImage::from_raw(
        args.foreground.artwork_size[0],
        args.foreground.artwork_size[0],
        args.foreground.artwork_buffer,
    )
    .unwrap();


    let background = if let Some(blur_radius) = blur_radius {
        let half_size: RgbImage = resize::fast_resize(&artwork, max_dim/4, max_dim/4);
        let half_size = add_blur(half_size, blur_radius/4.0);
        resize::fast_resize(&half_size, max_dim, max_dim)
    } else {
        resize::fast_resize(&artwork, max_dim, max_dim)
    };


    let foreground = Some(resize::fast_resize(
        &artwork,
        args.foreground.artwork_resize,
        args.foreground.artwork_resize,
    ));

    let final_image = paste_images(
        background,
        foreground,
        (args.display_geometry[0], args.display_geometry[1]),
        (
            args.available_geometry[0],
            args.available_geometry[1],
            args.available_geometry[2],
            args.available_geometry[3],
        ),
    );

    // PyBytes::new(py, final_image.as_raw()).into()
    final_image.save(GENERATED_WALLPAPER_PATH).unwrap();
}

fn paste_images(
    background: RgbImage,
    foreground: Option<RgbImage>,
    display_geometry: (u32, u32),
    available_geometry: (u32, u32, u32, u32),
) -> RgbImage {
    let mut base = RgbImage::new(display_geometry.0, display_geometry.1);

    // Background Paste
    let x = (display_geometry.0 as i64 - background.width() as i64) / 2;
    let y = (display_geometry.1 as i64 - background.height() as i64) / 2;

    imageops::overlay(&mut base, &background, x as u32,y as u32);

    // Foreground paste
    if let Some(foreground) = foreground {
        let x = (i64::from(available_geometry.0) - i64::from(foreground.width())) / 2
            + i64::from(available_geometry.2);
        let y = (i64::from(available_geometry.1) - i64::from(foreground.height())) / 2
            + i64::from(available_geometry.3);

        imageops::overlay(&mut base, &foreground, x as u32, y as u32)
    }
    base
}

fn add_blur(image: RgbImage, blur_radius: f32) -> RgbImage {
    let (width, height) = (image.width(), image.height());

    let mut pixels: Vec<[u8; 3]> = image
        .into_raw()
        .chunks_exact(3)
        .map(|pixel| pixel.try_into().unwrap())
        .collect();

    gaussian_blur(
        &mut pixels,
        width.try_into().unwrap(),
        height.try_into().unwrap(),
        blur_radius,
    );

    let buf = pixels.into_iter().flatten().collect();

    RgbImage::from_raw(width, height, buf).unwrap()
}

#[pyfunction]
pub fn solid_color(
    _py: Python,
    artwork_buf: Vec<u8>,
    buf_size: (u32, u32),
    foreground_size: Option<u32>,
    display_geometry: (u32, u32),
    available_geometry: (u32, u32, u32, u32),
    color: [u8; 3],
) {
    let (width, height) = display_geometry;
    let background = RgbImage::from_pixel(width, height, image::Rgb(color));

    let foreground = if let Some(size) = foreground_size {
        let artwork: RgbImage = RgbImage::from_raw(buf_size.0, buf_size.1, artwork_buf).unwrap();
        Some(resize::fast_resize(&artwork, size, size))
    } else {
        None
    };

    let final_image = paste_images(background, foreground, display_geometry, available_geometry);

    final_image.save(GENERATED_WALLPAPER_PATH).unwrap();
}

// #[pyfunction]
// pub fn wallpaper(
//     _py: Python,
//     artwork_buf: Vec<u8>,
//     buf_size: (u32, u32),
//     foreground_size: Option<u32>,
//     display_geometry: (u32, u32),
//     available_geometry: (u32, u32, u32, u32),
// ) {

//     let background = ImageReader::open(DEFAULT_WALLPAPER_PATH).unwrap().decode().unwrap().into_rgb8();

//     if let Some(size) = foreground_size {
//         let foreground = Some(resize::fast_resize(&RgbImage::from_raw(buf_size.0, buf_size.1, artwork_buf).unwrap(), size, size, imageops::Triangle));

//     }

//     paste_images(background, Some(foreground), display_geometry, available_geometry).save(GENERATED_WALLPAPER_PATH).unwrap()
// }
