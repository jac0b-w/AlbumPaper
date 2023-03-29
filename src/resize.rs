use fast_image_resize as fr;
use image::RgbImage;
use std::num::NonZeroU32;

// code modified from https://github.com/Cykooz/fast_image_resize

fn resize_image_with_cropping(
    mut src_view: fr::ImageView,
    dst_width: NonZeroU32,
    dst_height: NonZeroU32,
) -> fr::Image {
    // Set cropping parameters
    src_view.set_crop_box_to_fit_dst_size(dst_width, dst_height, None);

    // Create container for data of destination image
    let mut dst_image = fr::Image::new(dst_width, dst_height, src_view.pixel_type());
    // Get mutable view of destination image data
    let mut dst_view = dst_image.view_mut();

    // Create Resizer instance and resize source image
    // into buffer of destination image
    let mut resizer = fr::Resizer::new(fr::ResizeAlg::Convolution(fr::FilterType::Lanczos3));
    resizer.resize(&src_view, &mut dst_view).unwrap();

    dst_image
}

pub fn fast_resize(img: &RgbImage, nwidth: u32, nheight: u32) -> RgbImage {
    let width = NonZeroU32::new(img.width()).unwrap();
    let height = NonZeroU32::new(img.height()).unwrap();
    let src_image =
        fr::Image::from_vec_u8(width, height, img.as_raw().to_vec(), fr::PixelType::U8x3).unwrap();
    let resized_image = resize_image_with_cropping(
        src_image.view(),
        NonZeroU32::new(nwidth).unwrap(),
        NonZeroU32::new(nheight).unwrap(),
    );
    RgbImage::from_raw(nwidth, nheight, resized_image.into_vec()).unwrap()
}
