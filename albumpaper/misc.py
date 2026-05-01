from __future__ import annotations

import functools
import inspect
import time
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING, Any

import joblib
import requests
from configuration import AppPaths, ConfigManager
from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Callable

    from albumpaper import Track


class timer[R]:
    def __init__(self, func: Callable[..., R] = None, *, label: str = None, min_time: float = 0, max_time: float = 1e100):
        self.min_time = min_time
        self.max_time = max_time
        self._func = None
        self._label = label
        self.elapsed: float | None = None

        if func is not None:
            functools.update_wrapper(self, func)
            self._func = func

    @property
    def label(self) -> str:
        return self._label or getattr(self._func, "__name__", "block")

    def __call__(self, *args, **kwargs):
        if self._func is None:
            func = args[0]
            functools.update_wrapper(self, func)
            self._func = func
            return self

        with self:
            return self._func(*args, **kwargs)

    def __enter__(self) -> "timer":
        self._start = time.time()
        return self

    def __exit__(self, *exc_info) -> bool:
        self.elapsed = (time.time() - self._start) * 1000
        if self.min_time <= self.elapsed <= self.max_time:
            print(f"{self.label} took {self.elapsed:.1f} ms")
        return False


@timer(min_time = 100)
def download_image(url: str) -> Image.Image | None:
    try:
        response_content = _download_image_cached(url)
        return Image.open(BytesIO(response_content)).convert("RGB")
    except requests.exceptions.MissingSchema:
        return None

def clamp(num: float | int, min_: float | int, max_: float | int) -> float | int:
    return max(min_, min(max_, num))

# Factored out into a separate function to only cache compressed jpeg
mem = joblib.Memory(AppPaths.PROJECT_ROOT / "cache" / "jpeg", verbose=0)


@mem.cache
def _download_image_cached(url: str) -> bytes:
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
