import functools
import inspect
import time
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING, Any

import joblib
import requests
from configuration import ConfigManager
from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Callable

    from albumpaper import Track


def timer[P, R](func: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.time()
        return_values = func(*args, **kwargs)
        print(f"function {func.__name__} took {((time.time() - start) * 1000):.1f} ms")
        return return_values

    return wrapper


def debug(*values: *Any) -> None:
    frame = inspect.stack()[1]
    string = " ".join([f"{value=}" for value in values])
    print(f"{frame.filename}:{frame.lineno} ".replace("\\", "/") + string)


@timer
def download_image(url: str) -> Image.Image | None:
    try:
        print(url)
        response_content = _download_image(url)
        return Image.open(BytesIO(response_content)).convert("RGB")
    except requests.exceptions.MissingSchema:
        return None


# Factored out into a separate function to only cache compressed jpeg
mem = joblib.Memory("./cache/jpeg", verbose=0)


@timer
@mem.cache
def _download_image(url: str) -> bytes:
    debug(url)
    response_content = requests.get(url, timeout=30).content
    mem.reduce_size(bytes_limit=f"{int(ConfigManager.settings['cache']['size']) / 2}M")
    return response_content


type Color = tuple[int, int, int]


@dataclass
class SetPrevious:
    pass


@dataclass
class SetDefault:
    pass


@dataclass
class Unchanged:
    pass


@dataclass
class GenerateNew:
    track: Track


type WallpaperAction = GenerateNew | SetDefault | Unchanged | SetPrevious
