import ctypes
import enum
import glob
import os
import random
import shutil
from typing import TYPE_CHECKING

import albumpaper_rs
import imagegen
import structs
from configuration import (
    AppPaths,
    ConfigManager,
)
from misc import Color, timer
from PIL import Image

if TYPE_CHECKING:
    from PySide6 import QtWidgets

    from albumpaper import LastfmTrack, SpotifyTrack

    type Track = SpotifyTrack | LastfmTrack

from misc import GenerateNew, SetDefault, SetPrevious, Unchanged, WallpaperAction


class BackgroundType(enum.StrEnum):
    SOLID_COLOR = "solidcolor"
    LINEAR_GRADIENT = "lineargradient"
    RADIAL_GRADIENT = "radialgradient"
    COLORED_NOISE = "colorednoise"
    ALBUM_ART = "albumart"
    DEFAULT_WALLPAPER = "defaultwallpaper"


class GenerateWallpaper:
    def __init__(self, app: QtWidgets.QApplication) -> None:
        self.artwork_resize = ConfigManager.settings["foreground"]["size"]

        self.blur_enabled = ConfigManager.settings["background"]["blur_enabled"]
        self.blur_strength = ConfigManager.settings["background"]["blur_strength"]

        self.foreground_enabled = ConfigManager.settings["foreground"]["enabled"]
        self.spotify_code = ConfigManager.settings["foreground"]["spotify_code"]

        dw = app.primaryScreen()
        self.display_geometry = (
            dw.size().width(),
            dw.size().height(),
            0,
            0,
        )
        self.available_geometry = (
            dw.availableGeometry().width(),
            dw.availableGeometry().height(),
            dw.availableGeometry().left(),
            dw.availableGeometry().top(),
        )

        self.drop_shadow = ConfigManager.settings["foreground"]["drop_shadow"]

    @staticmethod
    def color_difference(c1: Color, c2: Color) -> float:
        """
        Input: RGB named tuples
        Output: An aproximation of perceived color difference of two colors
        https://www.compuphase.com/cmetric.htm
        """
        r = (c1[0] + c2[0]) / 2
        delta_r = c1[0] - c2[0]
        delta_g = c1[1] - c2[1]
        delta_b = c1[2] - c2[2]
        return (
            (2 + r / 256) * delta_r**2
            + 4 * delta_g**2
            + (2 + (255 - r) / 256) * delta_b**2
        ) ** 0.5

    @staticmethod
    def color_luminosity(color: Color) -> float:
        min_rgb = min(color) / 255
        max_rgb = max(color) / 255
        return (max_rgb + min_rgb) / 2

    def color_saturation(
        self,
        color: Color,
    ) -> int:  # https://medium.com/@donatbalipapp/colours-maths-90346fb5abda
        """
        Input: RGB named tuple
        Output: Saturation of the color 0-1
        """
        min_rgb = min(color) / 255
        max_rgb = max(color) / 255
        luminosity = self.color_luminosity(color)
        if luminosity == 1:
            return 0

        denom = 1 - abs(2 * luminosity - 1)
        if denom == 0:
            return 0

        return (max_rgb - min_rgb) / (1 - abs(2 * luminosity - 1))

    def gradient_colors(
        self,
        image: Image.Image,
    ) -> tuple[Color, Color]:
        """
        Determine best colours for the gradient
        Firstly get the 7 most dominant colours and pick the most saturated
        Pair the most saturated colour with the colour that has the largest
        perceived difference.
        """
        dominant_colors = imagegen.dominant_colors(image)

        saturations = [
            {"color": color, "saturation": self.color_saturation(color)}
            for color in dominant_colors[:7]
        ]
        sorted_saturations = sorted(
            saturations,
            key=lambda x: x["saturation"],
            reverse=True,
        )
        # e.g. [{"color":(255,0,0),"saturation":0.75},{"color":(255,255,255),"saturation":0} ...]
        most_saturated = sorted_saturations[0]["color"]

        color_differences = [
            {
                "color pair": (most_saturated, saturation_dict["color"]),
                "difference": self.color_difference(
                    most_saturated,
                    saturation_dict["color"],
                ),
            }
            for saturation_dict in sorted_saturations[1:]
        ]
        sorted_color_differences = sorted(
            color_differences,
            key=lambda x: x["difference"],
            reverse=True,
        )

        return sorted_color_differences[0]["color pair"]

    def generate_background(self, track: Track) -> None:
        backgrounds = [
            (BackgroundType.SOLID_COLOR, self.solidcolor_background),
            (BackgroundType.LINEAR_GRADIENT, self.lineargradient_background),
            (BackgroundType.RADIAL_GRADIENT, self.radialgradient_background),
            (BackgroundType.COLORED_NOISE, self.colorednoise_background),
            (BackgroundType.ALBUM_ART, self.albumart_background),
            (BackgroundType.DEFAULT_WALLPAPER, self.defaultwallpaper_background),
        ]
        enabled_bg_funcs = [
            bg[1] for bg in backgrounds if ConfigManager.background[bg[0]]["enabled"]
        ]
        background_config = random.choice(enabled_bg_funcs)(track)

        image = track.artwork

        # download spotify code if required
        spotify_code = None
        if self.spotify_code and track.spotify_code_image is not None:
            spotify_code = structs.PythonImageBuffer(track.spotify_code_image)

        albumpaper_rs.generate_save_wallpaper(
            structs.GenerationConfig(
                artwork=structs.PythonImageBuffer(image),
                background=background_config,
                foreground=structs.ForegroundConfig(
                    show_artwork=self.foreground_enabled,
                    artwork_resize=self.artwork_resize,
                    drop_shadow=self.drop_shadow,
                    spotify_code=spotify_code,
                ),
                display_geometry=self.display_geometry[:2],
                available_geometry=self.available_geometry,
            ),
        )

    @timer
    def solidcolor_background(self, track: Track) -> None:
        return structs.BackgroundConfig(
            background_type=BackgroundType.SOLID_COLOR,
            color1=track.dominant_colors[0],
        )

    @timer
    def lineargradient_background(self, track: Track) -> None:
        from_color, to_color = self.gradient_colors(track.artwork)
        background_config=  structs.BackgroundConfig(
            background_type=BackgroundType.LINEAR_GRADIENT,
            color1=from_color,
            color2=to_color,
        )
        print(background_config)
        return background_config

    @timer
    def radialgradient_background(self, track: Track) -> None:
        from_color, to_color = self.gradient_colors(track.artwork)
        return structs.BackgroundConfig(
            background_type=BackgroundType.RADIAL_GRADIENT,
            color1=from_color,
            color2=to_color,
        )

    @timer
    def colorednoise_background(self, track: Track) -> None:
        blur_radius=ConfigManager.background[BackgroundType.COLORED_NOISE]["blur"]
        no_colors = ConfigManager.background[BackgroundType.COLORED_NOISE]["no_colors"]
        color1, color2 = self.gradient_colors(track.artwork)
        return structs.BackgroundConfig(
            background_type=BackgroundType.COLORED_NOISE,
            blur_radius=blur_radius,
            color1=color1,
            color2=color2,
            no_colors=no_colors,
        )

    @timer
    def albumart_background(self, _track: Track) -> None:
        blur_radius=ConfigManager.background[BackgroundType.ALBUM_ART]["blur"]
        return structs.BackgroundConfig(
            background_type=BackgroundType.ALBUM_ART,
            blur_radius=blur_radius,
        )

    @timer
    def defaultwallpaper_background(self, _track: Track) -> None:
        blur_radius=ConfigManager.background[BackgroundType.DEFAULT_WALLPAPER]["blur"]
        return structs.BackgroundConfig(
            background_type=BackgroundType.DEFAULT_WALLPAPER,
            blur_radius=blur_radius,
        )

    def generate(self, wallaper_action: WallpaperAction) -> None:
        match wallaper_action:
            case GenerateNew(track):
                print("========== Generating new image ==========")
                self.generate_background(track)
                WindowsWallpaper.set_generated_wallpaper()
            case SetPrevious():
                WindowsWallpaper.set_generated_wallpaper()
            case SetDefault():
                WindowsWallpaper.set_default_wallpaper()
            case Unchanged():
                return


class WindowsWallpaper:
    @staticmethod
    def _set(*, is_default: bool) -> None:
        file_name = (
            AppPaths.DEFAULT_WALLPAPER if is_default else AppPaths.GENERATED_WALLPAPER
        )
        abs_path = os.path.abspath(file_name)  # noqa: PTH100
        ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 0)
        print("WALLPAPER SET: " + ("Default" if is_default else "Generated"))

    @staticmethod
    def set_default_wallpaper() -> None:
        WindowsWallpaper._set(is_default=True)

    @staticmethod
    def set_generated_wallpaper() -> None:
        WindowsWallpaper._set(is_default=False)

    @staticmethod
    def cache_current() -> None:
        r"""
        1. First look in %APPDATA%\Microsoft\Windows\Themes\CachedFiles
        and use most recent image (this will have the resolution of the desktop)
        2. If that fails look for %APPDATA%\Microsoft\Windows\Themes\TranscodedWallpaper
        (this will have the resolution of the original image)
        3. If that fails find the original path of the wallpaper and save that
        image instead https://stackoverflow.com/questions/44867820/
        4. Finally if all fail just save use a blank image as the dafault wallpaper
        """
        cached_folder = os.path.expandvars(
            r"%APPDATA%\Microsoft\Windows\Themes\CachedFiles\*",
        )
        list_of_files = glob.glob(cached_folder)  # noqa: PTH207
        if list_of_files:
            current_wallpaper = max(list_of_files, key=os.path.getctime)
        else:
            current_wallpaper = os.path.expandvars(
                r"%APPDATA%\Microsoft\Windows\Themes\TranscodedWallpaper",
            )
        try:
            shutil.copy(current_wallpaper, AppPaths.DEFAULT_WALLPAPER)
        except FileNotFoundError:
            ubuf = ctypes.create_unicode_buffer(200)
            ctypes.windll.user32.SystemParametersInfoW(0x0073, 200, ubuf, 0)
            try:
                shutil.copy(ubuf.value, AppPaths.DEFAULT_WALLPAPER)
            except FileNotFoundError:
                image = Image.new("RGB", (1, 1))
                image.save(AppPaths.DEFAULT_WALLPAPER, "JPEG", quality=100)
