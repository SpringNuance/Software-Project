import cv2
import numpy as np
from typing import Optional, List
import io
import base64
from PIL import Image

from .html import remove_html_comments


def normalize(
    img: np.ndarray,
    mean: Optional[List[float]] = [0.485, 0.456, 0.406],
    std: Optional[List[float]] = [0.229, 0.224, 0.225],
) -> np.ndarray:
    """Normalize an image based on the given mean and std values.

    :param img: The input image as a numpy array
    :param mean: The mean values for each channel (default: [0.485, 0.456, 0.406])
    :param std: The standard deviation values for each channel (default: [0.229, 0.224, 0.225])
    :return: The normalized image as a numpy array
    """
    mean = np.array(mean)
    std = np.array(std)
    return (img - mean) / std


def resize(
    img: np.ndarray, width: Optional[int] = None, height: Optional[int] = None, interpolation: int = cv2.INTER_LANCZOS4
) -> np.ndarray:
    """Resize an image to the specified width and/or height using the given interpolation method.

    :param img: The input image as a numpy array
    :param width: The target width (default: None)
    :param height: The target height (default: None)
    :param interpolation: The interpolation method to be used for resizing (default: cv2.INTER_LANCZOS4)
    :return: The resized image as a numpy array
    """
    if width is None and height is None:
        return img

    if width is not None and height is not None:
        return cv2.resize(img, (width, height), interpolation=interpolation)

    dim = None
    (h, w) = img.shape[:2]

    if width is None:
        r = height / float(h)
        dim = (int(w * r), height)
    else:
        r = width / float(w)
        dim = (width, int(h * r))

    return cv2.resize(img, dim, interpolation=interpolation)


def gaussian_blur(img: np.ndarray) -> np.ndarray:
    """Apply Gaussian blur to an image.

    :param img: The input image as a numpy array
    :return: The image with Gaussian blur applied as a numpy array
    """
    h, w = img.shape[:2]
    kernel_width = (w // 7) | 1
    kernel_height = (h // 7) | 1
    return cv2.GaussianBlur(img, (kernel_width, kernel_height), 0)


def image_bytes_to_array(img: bytes) -> np.ndarray:
    """Convert image bytes to a numpy array.

    :param img: The input image as bytes
    :return: The image as a numpy array
    """
    img_np = np.frombuffer(img, np.uint8)
    return cv2.imdecode(img_np, cv2.IMREAD_COLOR)


def image_array_to_bytes(img_arr: np.ndarray, extension: str = ".png") -> bytes:
    """Convert a numpy array image to bytes.

    :param img_arr: The input image as a numpy array
    :param extension: The image file extension (default: ".png")
    :return: The image as bytes
    """
    _, img = cv2.imencode(extension, img_arr)
    return img.tobytes()


def center_crop(img: np.ndarray, width: int, height: int) -> np.ndarray:
    """Center crop an image to the specified width and height.

    :param img: The input image as a numpy array
    :param width: The target width for the cropped image
    :param height: The target height for the cropped image
    :return: The center-cropped image as a numpy array
    """
    shape = img.shape
    y, x = shape[0], shape[1]
    start_x = x // 2 - (width // 2)
    start_y = y // 2 - (height // 2)
    return img[start_y : start_y + height, start_x : start_x + width]


def svg_to_image(svg_str: str, width: int = 250, height: int = 250) -> bytes:
    import cairosvg

    svg_str = remove_html_comments(svg_str)
    svg_str = svg_str.encode()
    return cairosvg.svg2png(bytestring=svg_str, output_width=width, output_height=height)


def base64_to_image(base64_str: str) -> Image:
    return Image.open(io.BytesIO(base64.b64decode(base64_str)))
