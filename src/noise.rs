use colorgrad::Color;
use noise::NoiseFn;
use image::RgbImage;
use rayon::prelude::*;

// taken from https://github.com/mazznoer/colorgrad-rs#colored-noise
pub fn colored(geometry: [u32; 2], color1: [u8; 3], color2: [u8; 3], seed: u32) -> RgbImage {
    // Map t which is in range [a, b] to range [c, d]
    let remap = |t, a, b, c, d| (t - a) * ((d - c) / (b - a)) + c;

    let [width, height] = geometry;

    let scale = 7.5 / width.min(height) as f64;

    let grad = colorgrad::CustomGradient::new()
        .colors(&[
            Color::from_rgba8(color1[0], color1[1], color1[2], 255),
            Color::from_rgba8(color2[0], color2[1], color2[2], 255),
        ])
        .build()
        .unwrap()
        .sharp(3, 0.1);

    let ns = noise::OpenSimplex::new(seed);
    let mut imgbuf = RgbImage::new(width, height);

    imgbuf.par_chunks_exact_mut(3 * width as usize)
        .enumerate()
        .for_each(|(y, row)| {
            for x in 0..geometry[0] {
                let pixel_pos = (x * 3) as usize;
                let pixel = &mut row[pixel_pos..(pixel_pos + 3)];

                let t = ns.get([x as f64 * scale, y as f64 * scale]);
                let rgba = grad.at(remap(t, -0.5, 0.5, 0.0, 1.0)).to_rgba8();
                pixel[0] = rgba[0];
                pixel[1] = rgba[1];
                pixel[2] = rgba[2];
            }
        });

    imgbuf
    
}
