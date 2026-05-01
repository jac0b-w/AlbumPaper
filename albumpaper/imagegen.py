import joblib
import numpy as np
import scipy
import sklearn
import xxhash
from configuration import AppPaths, ConfigManager
from misc import Color  # noqa: TC002
from PIL import Image  # noqa: TC002
from misc import timer


def srgb_to_lin(color_channel: float) -> float:
    # normalise RGB values to [0, 1]
    normalised_cc = color_channel / 255
    if normalised_cc <= 0.04045:  # noqa: PLR2004
        return normalised_cc / 12.92
    return ((normalised_cc + 0.055) / 1.055) ** 2.4


def luminance(sr: float, sg: float, sb: float) -> float:
    """
    https://stackoverflow.com/questions/596216/formula-to-determine-perceived-brightness-of-rgb-color?noredirect=1&lq=1
    Luminance L, Y is linearly addative.
    Perceived lightness L* is nonlinear. L*(black) = 0, L*(white) = 100.
    Brightness Q, perceptual attribute.
    Luma Y' is not linear luminance L.
    """
    # luminance Y
    return (
        0.2126 * srgb_to_lin(sr) + 0.7152 * srgb_to_lin(sg) + 0.0722 * srgb_to_lin(sb)
    )


def perceived_lightness(Y: float) -> float:  # noqa: N803
    if Y <= 0.008856:  # noqa: PLR2004
        return Y * 903.3

    return Y ** (1 / 3) * 116 - 16

@timer(min_time=50)
def dominant_colors(image: Image.Image) -> list[Color]:
    image_hash = xxhash.xxh32(image.tobytes("raw")).intdigest()
    return _dominant_colors_cached(image, image_hash)


mem = joblib.Memory(AppPaths.PROJECT_ROOT / "cache" / "dominant_colors", verbose=0)


@mem.cache(ignore=["image"])
def _dominant_colors_cached(image: Image.Image, _image_hash: int) -> list[Color]:
    """
    Input: PIL image
    Output: A list of 10 colors in the image from most dominant to least dominant
    Adaptation of https://stackoverflow.com/a/3244061/7274182
    """
    ar = np.asarray(image.resize((150, 150), 0))
    shape = ar.shape
    ar = ar.reshape(np.prod(shape[:2]), shape[2]).astype(
        float,
    )  # flatten to shape (width*height, 3)

    kmeans = sklearn.cluster.MiniBatchKMeans(
        n_clusters=10,
        init="k-means++",
        max_iter=20,
        random_state=1000,  # fixed seed for consistent colors
    ).fit(ar)
    codes = kmeans.cluster_centers_

    vecs, _dist = scipy.cluster.vq.vq(ar, codes)  # assign codes
    counts, _bins = np.histogram(vecs, len(codes))  # count occurrences

    mem.reduce_size(bytes_limit=f"{int(ConfigManager.settings['cache']['size']) / 2}M")

    return [tuple(row) for row in codes[np.argsort(counts)[::-1]].astype(int)]
