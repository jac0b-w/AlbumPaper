use kmeans_colors::{get_kmeans, Sort};
use ordered_float::OrderedFloat;
use palette::{FromColor, IntoColor, Lab, Pixel, Srgb};
use rayon::prelude::*;
use std::time;

type RgbColor = [u8; 3];

pub fn dominant_colors(pixels: Vec<u8>) -> Vec<RgbColor> {
    // Convert RGB [u8] buffer to Lab for k-means.
    let lab: Vec<Lab> = Srgb::from_raw_slice(&pixels)
        .iter()
        .map(|x| x.into_format().into_color())
        .collect();

    let now = time::Instant::now();

    let result = (0..10)
        .into_par_iter()
        .map(|i| get_kmeans(10, 20, 0.0001, false, &lab, 1000 + i as u64))
        .max_by_key(|result| OrderedFloat(result.score))
        .unwrap();

    dbg!(now.elapsed());

    // Process centroid data.
    let mut res = Lab::sort_indexed_colors(&result.centroids, &result.indices);

    // Sort indexed colors by percentage.
    res.sort_unstable_by(|a, b| {
        (b.percentage)
            .partial_cmp(&a.percentage)
            .expect("Failed to compare values while sorting.")
    });

    let fin = res.into_par_iter()
        .map(|cluster| {
            let (r, g, b) = Srgb::from_color(cluster.centroid)
                .into_format()
                .into_components();
            [r, g, b]
        })
        .collect();
    
    fin
}

pub fn gradient_colors(pixels: Vec<u8>) -> [RgbColor; 2] {
    let mut dominant_colors = dominant_colors(pixels);

    dominant_colors.truncate(7);
    dominant_colors.sort_by_key(|color| OrderedFloat(saturation(*color)));
    dominant_colors.reverse();

    let most_saturated = dominant_colors[0];

    let other = dominant_colors
        .into_iter()
        .skip(1)
        .max_by_key(|color| OrderedFloat(color_difference(most_saturated, *color)))
        .unwrap();

    [most_saturated, other]
}

// https://donatbalipapp.medium.com/colours-maths-90346fb5abda
fn saturation(color: RgbColor) -> f32 {
    let min_rgb = color.into_iter().min().unwrap() as f32 / 255.0;
    let max_rgb = color.into_iter().max().unwrap() as f32 / 255.0;

    let lumonosity = (min_rgb + max_rgb) * 0.5;

    if lumonosity == 1.0 {
        0.0
    } else {
        (max_rgb - min_rgb) / (1.0 - (2.0 * lumonosity - 1.0).abs())
    }
}

// https://www.compuphase.com/cmetric.htm
fn color_difference(a: RgbColor, b: RgbColor) -> f32 {
    let a: Vec<f32> = a.into_iter().map(|channel| channel as f32).collect();
    let b: Vec<f32> = b.into_iter().map(|channel| channel as f32).collect();

    let mean_r = (a[0] + b[0]) * 0.5;
    let r = a[0] - b[0];
    let g = a[1] - b[1];
    let b = a[2] - b[2];

    (2.0 + mean_r / 256.0) * r * r + 4.0 * g * g + (2.0 + (255.0 - mean_r) / 256.0) * b * b
}
