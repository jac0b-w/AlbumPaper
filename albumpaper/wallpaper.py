"""
Classes in this file:
  GenerateWallpaper
   - For generating the wallpaper based on the users settings
  Wallpaper
   - For setting a new wallpaper and saving the current wallpaper
    as the default wallpaper
"""


import os, ctypes, glob, shutil, collections, numpy, scipy.cluster, sklearn.cluster, random, functools
from typing import Optional
from PIL import Image
from config import ConfigManager
from misc import timer, HashableImage
import structs

# rust functions
import albumpaper_rs

DEFAULT_WALLPAPER_PATH = "images/default_wallpaper.jpg"
GENERATED_WALLPAPER_PATH = "images/generated_wallpaper.png"


def rust_image(method):
    @functools.wraps(method) # keeps method name, docstring etc
    def _wrapper(
        self,
        artwork: Optional[Image.Image],
        *args,
        **kwargs,
    ):
        if artwork is not None:
            artwork_buf = artwork.tobytes("raw")
            buf_size: tuple = artwork.size
        else:
            artwork_buf = None
            buf_size = None

        method(
            artwork_buf,
            buf_size,
            self.foreground_size if self.foreground_enabled else None,
            self.display_geometry[:2],
            self.available_geometry,
            *args,
            **kwargs,
        )

    return _wrapper


class GenerateWallpaper:
    def __init__(self, app):
        self.foreground_size = ConfigManager.settings["foreground"]["size"]
        background_type = ConfigManager.settings["background"]["type"]

        self.gen_background = {
            "Solid": self.color_background,
            "Linear Gradient": self.linear_gradient_background,
            "Radial Gradient": self.radial_gradient_background,
            "Colored Noise": self.colored_noise_background,
            "Art": self.art_background,
            "Wallpaper": self.wallpaper_background,
            "Random": self.random_background,
        }[background_type]

        self.blur_enabled = ConfigManager.settings["background"]["blur_enabled"]
        self.blur_strength = ConfigManager.settings["background"]["blur_strength"]

        self.foreground_enabled = ConfigManager.settings["foreground"]["enabled"]

        Geometry = collections.namedtuple("Geometry", ["w", "h", "left", "top"])
        dw = app.primaryScreen()
        self.display_geometry = Geometry(dw.size().width(), dw.size().height(), 0, 0)
        self.available_geometry = Geometry(
            dw.availableGeometry().width(),
            dw.availableGeometry().height(),
            dw.availableGeometry().left(),
            dw.availableGeometry().top(),
        )

        self.dominant_colors = functools.lru_cache(10)(self.dominant_colors)

    @timer
    def dominant_colors(self, hashable_image: HashableImage):
        """
        Input: PIL image
        Output: A list of 10 colors in the image from most dominant to least dominant
        Adaptation of https://stackoverflow.com/a/3244061/7274182
        """
        ar = numpy.asarray(hashable_image.image.resize((150, 150), 0))
        shape = ar.shape
        ar = ar.reshape(numpy.product(shape[:2]), shape[2]).astype(float) # flatten to shape (width*height, 3)

        kmeans = sklearn.cluster.MiniBatchKMeans(
            n_clusters=10, init="k-means++", max_iter=20, random_state=1000
        ).fit(ar)
        codes = kmeans.cluster_centers_

        vecs, _dist = scipy.cluster.vq.vq(ar, codes)  # assign codes
        counts, _bins = numpy.histogram(vecs, len(codes))  # count occurrences

        Color = collections.namedtuple("Color", ["r", "g", "b"])
        colors = []
        for index in numpy.argsort(counts)[::-1]:
            color_tuple = tuple([int(code) for code in codes[index]])
            colors.append(Color(*color_tuple))
        return colors  # returns colors in order of dominance

    @staticmethod
    def color_difference(c1, c2):
        """
        Input: RGB named tuples
        Output: An aproximation of perceived color difference of two colors
        https://www.compuphase.com/cmetric.htm
        """
        r = (c1.r + c2.r) / 2
        delta_r = c1.r - c2.r
        delta_g = c1.g - c2.g
        delta_b = c1.b - c2.b
        return (
            (2 + r / 256) * delta_r ** 2
            + 4 * delta_g ** 2
            + (2 + (255 - r) / 256) * delta_b ** 2
        ) ** 0.5

    @staticmethod
    def color_luminosity(color):
        min_rgb = min(color) / 255
        max_rgb = max(color) / 255
        return (max_rgb + min_rgb) / 2

    def color_saturation(
        self, color
    ):  # https://medium.com/@donatbalipapp/colours-maths-90346fb5abda
        """
        Input: RGB named tuple
        Output: Saturation of the color 0-1
        """
        min_rgb = min(color) / 255
        max_rgb = max(color) / 255
        luminosity = self.color_luminosity(color)
        if luminosity == 1:
            return 0
        else:
            try:
                return (max_rgb - min_rgb) / (1 - abs(2 * luminosity - 1))
            except ZeroDivisionError:
                return 1

    def gradient_colors(
        self, image: Image.Image
    ):  # https://stackoverflow.com/questions/30608035/plot-circular-gradients-using-pil-in-python
        """
        Determine best colours for the gradient
        Firstly get the 7 most dominant colours and pick the most saturated
        Pair the most saturated colour with the colour that has the largest perceived difference
        """
        dominant_colors = self.dominant_colors(HashableImage(image))

        saturations = [
            {"color": color, "saturation": self.color_saturation(color)}
            for color in dominant_colors[:7]
        ]
        sorted_saturations = sorted(
            saturations, key=lambda x: x["saturation"], reverse=True
        )
        # e.g. [{"color":(255,0,0),"saturation":0.75},{"color":(255,255,255),"saturation":0} ...]
        most_saturated = sorted_saturations[0]["color"]

        color_differences = [
            {
                "color pair": (most_saturated, saturation_dict["color"]),
                "difference": self.color_difference(
                    most_saturated, saturation_dict["color"]
                ),
            }
            for saturation_dict in sorted_saturations[1:]
        ]
        sorted_color_differences = sorted(
            color_differences, key=lambda x: x["difference"], reverse=True
        )

        return sorted_color_differences[0]["color pair"]

        # example return data:
        # (Color(r=120, g=50, b=12), Color(r=190, g=200, b=203))

    @timer
    def linear_gradient_background(self, image: Image.Image):
        from_color, to_color = self.gradient_colors(image)
        albumpaper_rs.generate_save_wallpaper(
            structs.RequiredArguments(
                "LinearGradient",
                structs.Foreground(image, self.foreground_size),
                self.display_geometry[:2],
                self.available_geometry,
            ),
            structs.OptionalArguments(None, from_color, to_color),
        )

    @timer
    def radial_gradient_background(self, image: Image.Image):
        from_color, to_color = self.gradient_colors(image)
        albumpaper_rs.generate_save_wallpaper(
            structs.RequiredArguments(
                "RadialGradient",
                structs.Foreground(image, self.foreground_size),
                self.display_geometry[:2],
                self.available_geometry,
            ),
            structs.OptionalArguments(None, from_color, to_color),
        )

    @timer
    def color_background(self, image: Image.Image):
        color = self.dominant_colors(HashableImage(image))[0]
        albumpaper_rs.generate_save_wallpaper(
            structs.RequiredArguments(
                "SolidColor",
                structs.Foreground(image, self.foreground_size),
                self.display_geometry[:2],
                self.available_geometry,
            ),
            structs.OptionalArguments(None, color, None),
        )

    @timer
    def colored_noise_background(self, image: Image.Image):
        blur: Optional[int] = int(self.blur_strength) if self.blur_enabled else None
        color1, color2 = self.gradient_colors(image)
        albumpaper_rs.generate_save_wallpaper(
            structs.RequiredArguments(
                "ColoredNoise",
                structs.Foreground(image, self.foreground_size),
                self.display_geometry[:2],
                self.available_geometry,
            ),
            structs.OptionalArguments(blur, color1, color2),
        )

    @timer
    def art_background(self, image: Image.Image):
        blur: Optional[int] = int(self.blur_strength) if self.blur_enabled else None
        albumpaper_rs.generate_save_wallpaper(
            structs.RequiredArguments(
                "Artwork",
                structs.Foreground(image, self.foreground_size),
                self.display_geometry[:2],
                self.available_geometry,
            ),
            structs.OptionalArguments(blur, None, None),
        )

    @timer
    def wallpaper_background(self, image: Image.Image):
        blur: Optional[int] = int(self.blur_strength) if self.blur_enabled else None
        albumpaper_rs.generate_save_wallpaper(
            structs.RequiredArguments(
                "DefaultWallpaper",
                structs.Foreground(image, self.foreground_size),
                self.display_geometry[:2],
                self.available_geometry,
            ),
            structs.OptionalArguments(blur, None, None),
        )

    def random_background(self, album_art: Image) -> Image.Image:
        backgound = random.choice(
            [
                self.color_background,
                self.linear_gradient_background,
                self.radial_gradient_background,
                self.colored_noise_background,
                self.art_background,
            ]
        )
        backgound(album_art)


    def generate(self, image: Image.Image):
        if isinstance(image, Image.Image):
            print("========== Generating new image ==========")
            self.gen_background(image)

            Wallpaper.set(is_default=False)
        elif image == "default":
            Wallpaper.set(is_default=True)
        elif image == "generated":
            Wallpaper.set(is_default=False)


class Wallpaper:
    @staticmethod
    def set(is_default: bool):
        file_name = DEFAULT_WALLPAPER_PATH if is_default else GENERATED_WALLPAPER_PATH
        abs_path = os.path.abspath(file_name)
        ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 0)
        print("WALLPAPER SET: " + ("Default" if is_default else "Generated"))

    @staticmethod
    def set_default():
        """
        1. First look in %APPDATA%\Microsoft\Windows\Themes\CachedFiles
        and use most recent image (this will have the resolution of the desktop)
        2. If that fails look for %APPDATA%\Microsoft\Windows\Themes\TranscodedWallpaper
        (this will have the resolution of the original image)
        3. If that fails find the original path of the wallpaper and save that image instead
        # https://stackoverflow.com/questions/44867820/
        4. Finally if all fail just save use a blank image as the dafault wallpaper
        """
        cached_folder = os.path.expandvars(
            r"%APPDATA%\Microsoft\Windows\Themes\CachedFiles\*"
        )
        list_of_files = glob.glob(cached_folder)
        if list_of_files:
            current_wallpaper = max(list_of_files, key=os.path.getctime)
        else:
            current_wallpaper = os.path.expandvars(
                r"%APPDATA%\Microsoft\Windows\Themes\TranscodedWallpaper"
            )
        try:
            shutil.copy(current_wallpaper, DEFAULT_WALLPAPER_PATH)
        except FileNotFoundError:
            ubuf = ctypes.create_unicode_buffer(200)
            ctypes.windll.user32.SystemParametersInfoW(0x0073, 200, ubuf, 0)
            try:
                shutil.copy(ubuf.value, DEFAULT_WALLPAPER_PATH)
            except FileNotFoundError:
                image = Image.new("RGB", (1, 1))
                image.save(DEFAULT_WALLPAPER_PATH, "JPEG", quality=100)
