"""
Classes in this file:
  GenerateWallpaper
   - For generating the wallpaper based on the users settings
  Wallpaper
   - For setting a new wallpaper and saving the current wallpaper
    as the default wallpaper
"""


import os, ctypes, glob, shutil, collections, time, numpy, scipy.cluster, sklearn.cluster
from PIL import Image, ImageFilter
from config import config  # object

# rust functions
from albumpaper_imagegen import linear_gradient, radial_gradient


DEFAULT_WALLPAPER_PATH = "images/default_wallpaper.jpg"
GENERATED_WALLPAPER_PATH = "images/generated_wallpaper.jpg"


def timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        return_values = func(*args, **kwargs)
        if time.time() - start > 0.005:
            print(f"function {func.__name__} took {time.time() - start} seconds")
        return return_values

    return wrapper


class GenerateWallpaper:
    def __init__(self, app):
        self.foreground_size = config.settings.getint("foreground_size")
        background_type = config.settings.get("background_type")
        self.gen_background = {
            "Solid": self.color_background,
            "Linear Gradient": self.linear_gradient_background,
            "Radial Gradient": self.radial_gradient_background,
            "Art": self.art_background,
            "Wallpaper": self.wallpaper_background,
        }[background_type]

        self.blur_enabled = config.settings.getboolean("blur_enabled")
        self.blur_strength = config.settings.getfloat("blur_strength")

        self.foreground_enabled = config.settings.getboolean("foreground_enabled")

        Geometry = collections.namedtuple("Geometry", ["w", "h", "left", "top"])
        dw = app.primaryScreen()
        self.display_geometry = Geometry(dw.size().width(), dw.size().height(), 0, 0)
        self.avaliable_geometry = Geometry(
            dw.availableGeometry().width(),
            dw.availableGeometry().height(),
            dw.availableGeometry().left(),
            dw.availableGeometry().top(),
        )

    @timer
    def dominant_colors(self, image: Image.Image):
        """
        Input: PIL image
        Output: A list of 10 colors in the image from most dominant to least dominant
        Adaptation of https://stackoverflow.com/a/3244061/7274182
        """

        image = image.resize((150, 150))  # optional, to reduce time
        ar = numpy.asarray(image)
        shape = ar.shape
        ar = ar.reshape(numpy.product(shape[:2]), shape[2]).astype(float)

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
        Output: An aproximation of percieved color difference of two colors
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
        if luminosity == 0:
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
        Pair the most saturated colour with the colour that has the largest percieved difference
        """
        dominant_colors = self.dominant_colors(image)

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
    def linear_gradient_background(
        self, image: Image.Image
    ) -> Image.Image:  # https://gist.github.com/weihanglo/1e754ec47fdd683a42fdf6a272904535
        gradient_pair = self.gradient_colors(image)
        geometry: tuple = self.display_geometry[:2]

        raw = linear_gradient(
            geometry=geometry,
            from_color=list(gradient_pair[0]),
            to_color=list(gradient_pair[1]),
        )
        background = Image.frombuffer("RGB", geometry, raw)

        return background

    @timer
    def radial_gradient_background(self, image: Image.Image) -> Image.Image:
        gradient_pair = self.gradient_colors(image)
        geometry: tuple = self.display_geometry[:2]

        if not self.foreground_enabled:
            self.foreground_size = 0

        raw = radial_gradient(
            geometry=geometry,
            inner_color=list(gradient_pair[0]),
            outer_color=list(gradient_pair[1]),
            foreground_size=self.foreground_size,
        )
        background = Image.frombuffer("RGB", geometry, raw)

        return background

    @timer
    def color_background(self, image: Image.Image) -> Image.Image:
        color = self.dominant_colors(image)[0]
        return Image.new("RGB", self.display_geometry[:2], color)

    @timer
    def art_background(self, image: Image.Image) -> Image.Image:
        max_dim = max(self.display_geometry[:2])
        art_resized = image.resize([max_dim] * 2, 3)
        return art_resized

    @timer
    def wallpaper_background(self, *_):
        return Image.open(DEFAULT_WALLPAPER_PATH)

    def gen_foreground(self, image: Image.Image):
        if self.foreground_enabled:
            return image.resize([self.foreground_size] * 2, 3)
        else:
            return None

    def save_image(self, path, image: Image.Image):
        try:
            image.save(path, "JPEG", quality=100)
        except OSError:
            time.sleep(0.1)
            self.save_image(path, image)

    def paste_images(self, background: Image, foreground: Image.Image):
        base = Image.new("RGB", self.display_geometry[:2])

        # background paste
        x = (
            int((self.display_geometry.w - background.size[0]) / 2)
            + self.display_geometry.left
        )
        y = (
            int((self.display_geometry.h - background.size[1]) / 2)
            + self.display_geometry.top
        )
        base.paste(background, (x, y))

        # foreground paste
        if foreground is not None:
            x = (
                int((self.avaliable_geometry.w - foreground.size[0]) / 2)
                + self.avaliable_geometry.left
            )
            y = (
                int((self.avaliable_geometry.h - foreground.size[1]) / 2)
                + self.avaliable_geometry.top
            )
            base.paste(foreground, (x, y))

        self.save_image(GENERATED_WALLPAPER_PATH, base)

    @timer
    def __call__(self, image: Image.Image):
        if isinstance(image, Image.Image):
            background = self.gen_background(image)
            if self.blur_enabled:
                background = background.filter(
                    ImageFilter.GaussianBlur(self.blur_strength)
                )

            self.paste_images(
                background,
                self.gen_foreground(image),
            )

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
        print("NEW WALLPAPER SET")

    @staticmethod
    def set_default():
        """
        1. First look in %APPDATA%\Microsoft\Windows\Themes\CachedFiles
        and use most recent image
        2. If that fails look for %APPDATA%\Microsoft\Windows\Themes\TranscodedWallpaper
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
