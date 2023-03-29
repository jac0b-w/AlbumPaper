use rayon::prelude::*;
use image::RgbImage;

type Color = [u8; 3];
/**
Returns an `RgbImage` of dimentions `geometry` with a linear gradient between
`from_color` and `to_color`

# Arguments

* `geometry` - A tuple of the width and height of generated image
* `from_color` - A list of rgb values for the left color of linear gradient
* `to_color` - A list of rgb values for the right color of linear gradient

*/
pub fn linear(geometry: [u32; 2], from_color: Color, to_color: Color) -> RgbImage {
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

/*
Returns an `RgbImage` of dimentions `geometry` with a linear gradient between
`inner_color` and `outer_color`

# Arguments

* `geometry` - A tuple of the width and height of generated image
* `inner_color` - A list of rgb values for the centre color of radial gradient
* `outer_color` - A list of rgb values for the outer color of radial gradient

*/

#[inline]
fn lerp(pct: f32, a: f32, b: f32) -> f32 {
    pct.mul_add(b - a, a)
}

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