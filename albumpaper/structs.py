from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from misc import Color
    from PIL import Image


class PythonImageBuffer:
    def __init__(self, image: Image.Image) -> None:
        self.size = image.size
        self.buffer = image.tobytes()


@dataclass(kw_only=True)
class GenerationConfig:
    artwork: PythonImageBuffer
    background: BackgroundConfig
    foreground: ForegroundConfig
    display_geometry: tuple[int, int]
    available_geometry: tuple[int, int, int, int]


@dataclass(kw_only=True)
class ForegroundConfig:
    show_artwork: bool
    artwork_resize: int | None
    drop_shadow: bool
    spotify_code: PythonImageBuffer | None


@dataclass(kw_only=True)
class BackgroundConfig:
    background_type: str
    blur_radius: int | None = None
    color1: Color | None = None
    color2: Color | None = None
    no_colors: int | None = None
