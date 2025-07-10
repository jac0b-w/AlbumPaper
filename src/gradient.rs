use image::RgbImage;
use rand::Rng;
use rayon::prelude::*;

type Color = [u8; 3];

#[inline]
fn lerp_color(a: [f32; 3], b: [f32; 3], t: f32) -> [f32; 3] {
    [
        t.mul_add(b[0] - a[0], a[0]),
        t.mul_add(b[1] - a[1], a[1]),
        t.mul_add(b[2] - a[2], a[2]),
    ]
}

#[inline]
fn quantize_color_channel(c: f32) -> u8 {
    c.round().clamp(0.0, 255.0) as u8
}

/**
Returns an `RgbImage` of dimentions `geometry` with a linear gradient between
`from_color` and `to_color`

# Arguments

* `geometry` - A tuple of the width and height of generated image
* `from_color` - A list of rgb values for the left color of linear gradient
* `to_color` - A list of rgb values for the right color of linear gradient

*/
pub fn linear(geometry: [u32; 2], from_color: Color, to_color: Color) -> RgbImage {
    use rand::Rng;
    let [width, height] = geometry;

    let from_color = from_color.map(|c| c as f32);
    let to_color = to_color.map(|c| c as f32);

    let mut image = RgbImage::new(width, height);

    image
        .par_chunks_exact_mut(3 * width as usize)
        .enumerate()
        .for_each(|(y, row)| {

            let mut rng = rand::rng();

            for x in 0..width {
                let t = (x as f32 + y as f32) / (width as f32 + height as f32);
                
                let base = lerp_color(from_color, to_color, t);
                let dither = (rng.random::<f32>() - 0.5) + (rng.random::<f32>() - 0.5);
                let pixel = &mut row[(x * 3) as usize..(x * 3 + 3) as usize];
                pixel[0] = quantize_color_channel(base[0] + dither);
                pixel[1] = quantize_color_channel(base[1] + dither);
                pixel[2] = quantize_color_channel(base[2] + dither);
            }
        });

    image
}

/*
Returns an `RgbImage` of dimentions `geometry` with a linear gradient between
`inner_color` and `outer_color`

# Arguments

* `geometry` - A tuple of the width and height of generated image
* `inner_color` - A list of rgb values for the centre color of radial gradient
* `outer_color` - A list of rgb values for the outer color of radial gradient

*/

#[inline]
fn distance(x: i32, y: i32) -> f32 {
    ((x * x + y * y) as f32).sqrt()
}

pub fn radial(
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
            let mut rng = rand::rng();

            for pos_x in 0..geometry[0] {
                let dist_x = pos_x as i32 - center.0;
                let dist_y = pos_y as i32 - center.1;
                let scaled_dist = (distance(dist_x, dist_y) - foreground_half) * one_over_max_dist;

                let pixel_pos = (pos_x * 3) as usize;
                let pixel = &mut row[pixel_pos..(pixel_pos + 3)];

                let temp_pix = lerp_color(inner_color, outer_color, scaled_dist);

                let dither = (rng.random::<f32>() - 0.5) + (rng.random::<f32>() - 0.5);

                pixel[0] = quantize_color_channel(temp_pix[0] + dither);
                pixel[1] = quantize_color_channel(temp_pix[1] + dither);
                pixel[2] = quantize_color_channel(temp_pix[2] + dither);
            }
        });
    background
}
