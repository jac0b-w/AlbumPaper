from dataclasses import dataclass
import time, requests, functools, sys
from PIL import Image

def timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        return_values = func(*args, **kwargs)
        if time.time() - start > 0.005:
            print(f"function {func.__name__} took {time.time() - start} seconds")
        return return_values

    return wrapper

# Factored out into a separate function to avoid memory leak and only cache compressed jpeg
@timer
@functools.lru_cache(10)
def download_image(url):
    response_content = requests.get(url).content
    return response_content

@dataclass
class HashableImage:
    image: Image.Image
    def __hash__(self):
        return hash(self.image.tobytes("raw"))
