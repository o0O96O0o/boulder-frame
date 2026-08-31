from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from .errors import ErrorCode, terminal
from .planner import CropRect

if TYPE_CHECKING:
    from .media import MediaMetadata


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    """One display-rotation-normalized decoded source frame for target analysis."""

    index: int
    timestamp_ms: int
    pixels: object


class FrameReader(Protocol):
    def read(self, source: Path, metadata: MediaMetadata) -> Iterable[DecodedFrame]: ...


class FrameReaderUnavailable(RuntimeError):
    """The configured OpenCV decoder dependency is unavailable."""


class OpenCVFrameReader:
    """Streams CFR source frames as display-normalized OpenCV BGR arrays."""

    def __init__(self) -> None:
        try:
            import cv2
        except ImportError as error:
            raise FrameReaderUnavailable(
                "opencv-python-headless==4.10.0.84 is required for frame decoding"
            ) from error
        self._cv2 = cv2

    def read(self, source: Path, metadata: MediaMetadata) -> Iterator[DecodedFrame]:
        capture = self._cv2.VideoCapture(str(source))
        if not capture.isOpened():
            capture.release()
            raise terminal(ErrorCode.INVALID_MEDIA, "Video frames could not be decoded.")
        try:
            if not capture.set(self._cv2.CAP_PROP_ORIENTATION_AUTO, 0):
                raise terminal(ErrorCode.INVALID_MEDIA, "Video rotation could not be normalized.")
            index = 0
            while True:
                decoded, pixels = capture.read()
                if not decoded:
                    break
                if getattr(pixels, "shape", ())[:2] != (metadata.height, metadata.width):
                    raise terminal(
                        ErrorCode.INVALID_MEDIA, "Video frame dimensions are inconsistent."
                    )
                yield DecodedFrame(
                    index, metadata.timestamp_for_frame(index), _rotate(pixels, metadata)
                )
                index += 1
            if index != metadata.expected_frame_count:
                raise terminal(ErrorCode.INVALID_MEDIA, "Video frame count is inconsistent.")
        finally:
            capture.release()


def crop_and_resize_frame(
    pixels: object, crop: CropRect, output_size: tuple[int, int]
) -> object:
    """Crop one display-coordinate BGR frame and return a fixed contiguous surface."""
    import cv2
    import numpy as np

    if (
        not isinstance(pixels, np.ndarray)
        or pixels.dtype != np.uint8
        or pixels.ndim != 3
        or pixels.shape[2] != 3
    ):
        raise terminal(
            ErrorCode.INVALID_MEDIA, "Video frames could not be rendered consistently."
        )

    try:
        x, y = int(crop.x), int(crop.y)
        width, height = int(crop.width), int(crop.height)
    except (OverflowError, TypeError, ValueError) as error:
        raise terminal(
            ErrorCode.INVALID_MEDIA, "Video frames could not be rendered consistently."
        ) from error
    output_width, output_height = output_size
    if (
        min(x, y) < 0
        or min(width, height, output_width, output_height) <= 0
        or x + width > pixels.shape[1]
        or y + height > pixels.shape[0]
    ):
        raise terminal(
            ErrorCode.INVALID_MEDIA, "Video frames could not be rendered consistently."
        )

    source_crop: Any = pixels[y : y + height, x : x + width]
    if source_crop.size == 0:
        raise terminal(
            ErrorCode.INVALID_MEDIA, "Video frames could not be rendered consistently."
        )
    try:
        resized = cv2.resize(
            source_crop,
            (output_width, output_height),
            interpolation=cv2.INTER_LANCZOS4,
        )
    except (cv2.error, TypeError, ValueError) as error:
        raise terminal(
            ErrorCode.INVALID_MEDIA, "Video frames could not be rendered consistently."
        ) from error
    if resized.shape != (output_height, output_width, 3) or resized.dtype != np.uint8:
        raise terminal(
            ErrorCode.INVALID_MEDIA, "Video frames could not be rendered consistently."
        )
    return np.ascontiguousarray(resized)


def _rotate(pixels: Any, metadata: MediaMetadata) -> object:
    import cv2

    return {
        0: pixels,
        90: cv2.rotate(pixels, cv2.ROTATE_90_CLOCKWISE),
        180: cv2.rotate(pixels, cv2.ROTATE_180),
        270: cv2.rotate(pixels, cv2.ROTATE_90_COUNTERCLOCKWISE),
    }[metadata.rotation]
