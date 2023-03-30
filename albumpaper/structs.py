from dataclasses import dataclass
from PIL import Image


class Foreground:
    def __init__(self, artwork: Image.Image, artwork_resize: int, visable: bool):
        self.artwork_size = artwork.size
        self.artwork_buffer = artwork.tobytes("raw")
        self.artwork_resize = artwork_resize
        self.visable = visable


@dataclass
class RequiredArguments:
    background_type: str
    foreground: Foreground
    display_geometry: tuple[int, int]
    available_geometry: tuple[int, int, int, int]


@dataclass
class OptionalArguments:
    blur_radius: int
    color1: tuple[int, int, int]
    color2: tuple[int, int, int]
