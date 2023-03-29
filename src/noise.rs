use colorgrad::Color;
use noise::NoiseFn;
use image::RgbImage;

// taken from https://github.com/mazznoer/colorgrad-rs#colored-noise
pub fn colored(geometry: [u32; 2], color1: [u8; 3], color2: [u8; 3]) -> RgbImage {
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

    let ns = noise::OpenSimplex::new(1);
    let mut imgbuf = RgbImage::new(width, height);

    for (x, y, pixel) in imgbuf.enumerate_pixels_mut() {
        let t = ns.get([x as f64 * scale, y as f64 * scale]);
        let rgba = grad.at(remap(t, -0.5, 0.5, 0.0, 1.0)).to_rgba8();
        let rgb = [rgba[0], rgba[1], rgba[2]];
        *pixel = image::Rgb(rgb);
    }

    imgbuf
    
}
