use image::{ImageBuffer, RgbImage};
use rayon::prelude::*;

use pyo3::{prelude::*, types::PyBytes};

// Define module
#[pymodule]
fn albumpaper_imagegen(_py: Python, module: &PyModule) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(linear_gradient, module)?)?;
    module.add_function(wrap_pyfunction!(radial_gradient, module)?)?;
    Ok(())
}

const CHUNK_SIZE: usize = 128 * 128;

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
/// import albumpaper_imagegen
/// from PIL import Image
///
/// raw = albumpaper_imagegen.linear_gradient(
///     (1920, 1080),
///     [255, 0, 0],
///     [0, 0, 255]
/// )
///
/// image =  Image.frombuffer('RGB', [1920, 1080], raw)
///
/// ```
#[pyfunction]
pub fn linear_gradient(
    py: Python,
    geometry: (i32, i32),
    from_color: Vec<u8>,
    to_color: Vec<u8>,
) -> PyObject {
    let mut background: RgbImage = ImageBuffer::new(geometry.0 as u32, geometry.1 as u32);

    let max_dist = (geometry.0 + geometry.1) as f64;

    background
        .par_chunks_mut(CHUNK_SIZE * 3)
        .enumerate()
        .for_each(|(chunk_num, block)| {
            for (pixel_num, pixel) in block.chunks_exact_mut(3).enumerate() {
                let x_dist = (chunk_num * CHUNK_SIZE + pixel_num) as i32 % geometry.0;
                let y_dist = (chunk_num * CHUNK_SIZE + pixel_num) as i32 / geometry.0;
                let scaled_dist = (x_dist + y_dist) as f64 / max_dist;

                for (i, subpix) in pixel.iter_mut().enumerate() {
                    *subpix = ((to_color[i] as f64 * scaled_dist)
                        + (from_color[i] as f64 * (1.0 - scaled_dist)))
                        as u8;
                }
            }
        });
    PyBytes::new(py, background.as_raw()).into()
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
/// import albumpaper_imagegen
/// from PIL import Image
///
/// raw = albumpaper_imagegen.radial_gradient(
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
    py: Python,
    geometry: (i32, i32),
    inner_color: Vec<u8>,
    outer_color: Vec<u8>,
    foreground_size: i32,
) -> PyObject {
    let mut background: RgbImage = ImageBuffer::new(geometry.0 as u32, geometry.1 as u32);

    let distance = |x: i32, y: i32| (((x).pow(2) + (y).pow(2)) as f64).sqrt();

    // The background will adapt to the foreground size so that the inner_color will be at the edges of the art
    // and not just at the centre of the image
    let max_dist =
        distance((geometry.0 / 2) as i32, (geometry.1 / 2) as i32) - (foreground_size / 2) as f64;

    background
        .par_chunks_mut(CHUNK_SIZE * 3)
        .enumerate()
        .for_each(|(chunk_num, block)| {
            for (pixel_num, pixel) in block.chunks_exact_mut(3).enumerate() {
                let x_dist =
                    ((chunk_num * CHUNK_SIZE + pixel_num) as i32 % geometry.0) - (geometry.0 / 2);
                let y_dist =
                    ((chunk_num * CHUNK_SIZE + pixel_num) as i32 / geometry.0) - (geometry.1 / 2);
                let scaled_dist =
                    (distance(x_dist, y_dist) - (foreground_size / 2) as f64) / max_dist;

                for (i, subpix) in pixel.iter_mut().enumerate() {
                    *subpix = ((outer_color[i] as f64 * scaled_dist)
                        + (inner_color[i] as f64 * (1.0 - scaled_dist)))
                        as u8
                }
            }
        });

    PyBytes::new(py, background.as_raw()).into()
}
