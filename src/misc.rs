use fast_image_resize::{ResizeOptions, Resizer};
use image::{DynamicImage, RgbaImage};
use libblur::{
    ConvolutionMode, EdgeMode, EdgeMode2D, GaussianBlurParams, ThreadingPolicy, gaussian_blur_image,
};

pub fn fast_resize(src_image: &RgbaImage, nwidth: u32, nheight: u32) -> RgbaImage {
    let mut dst_image = RgbaImage::new(nwidth, nheight);

    let mut resizer = Resizer::new();
    resizer
        .resize(
            src_image,
            &mut dst_image,
            &ResizeOptions::new()
                .resize_alg(fast_image_resize::ResizeAlg::Convolution(
                    fast_image_resize::FilterType::Lanczos3,
                ))
                .fit_into_destination(None)
                .use_alpha(true),
        )
        .unwrap();
    dst_image
}

pub fn add_blur(image: DynamicImage, blur_radius: u32) -> DynamicImage {
    let sigma = blur_radius as f64 / 2.0;

    // use the maximum kernel size possible
    let max_dimension = std::cmp::max(image.width(), image.height());
    let kernel_size = max_dimension + max_dimension % 2 + 1;

    gaussian_blur_image(
        image,
        GaussianBlurParams::new(kernel_size, sigma),
        EdgeMode2D::new(EdgeMode::Clamp),
        ConvolutionMode::Exact,
        ThreadingPolicy::Adaptive,
    )
    .unwrap()
}

pub fn round_corners(image: &mut RgbaImage, radius_fraction: f32) {
    let (width, height) = (image.dimensions().0 as f32, image.dimensions().1 as f32);
    let radius = width.max(height) * radius_fraction;

    let corner_centers = [
        (radius, radius),
        (width - radius, radius),
        (radius, height - radius),
        (width - radius, height - radius),
    ];

    for (x, y, p) in image.enumerate_pixels_mut() {
        let (x, y) = (x as f32 + 0.5, y as f32 + 0.5); // centre of pixels

        // Skip if pixel is not near a corner
        if !(x < radius && y < radius
            || x > width - radius && y < radius
            || x < radius && y > height - radius
            || x > width - radius && y > height - radius)
        {
            continue;
        }

        // Find the nearest corner center and check if we're outside its circle
        let nearest = corner_centers
            .iter()
            .min_by(|(ax, ay), (bx, by)| {
                f32::hypot(x - ax, y - ay).total_cmp(&f32::hypot(x - bx, y - by))
            })
            .unwrap();

        let dist = f32::hypot(x - nearest.0, y - nearest.1);

        let alpha = (radius + 0.5 - dist).clamp(0.0, 1.0);
        p.0[3] = (p.0[3] as f32 * alpha) as u8;
    }
}

// Easier to just replace cache/images/defefault_wallpaper ourselves for consitency with generated wallpapers
pub fn resize_default_wallpaper(
    default_wallpaper: RgbaImage,
    display_geometry: [u32; 2],
    app_paths: &crate::AppPaths,
) -> RgbaImage {
    if default_wallpaper.dimensions() != display_geometry.into() {
        let resized_wallpaper =
            fast_resize(&default_wallpaper, display_geometry[0], display_geometry[1]);
        resized_wallpaper
            .save(app_paths.default_wallpaper.clone())
            .unwrap();
        resized_wallpaper
    } else {
        default_wallpaper
    }
}

pub fn seed_from_image(image: &RgbaImage) -> u64 {
    use rustc_hash::FxHasher;
    use std::hash::Hasher;

    let mut hasher = FxHasher::with_seed(1);
    hasher.write(image.as_raw());
    hasher.finish()
}