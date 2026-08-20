from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import ErrorCode, terminal
from .pipeline import DecodedFrame

if TYPE_CHECKING:
    from .media import MediaMetadata


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


def _rotate(pixels: object, metadata: MediaMetadata) -> object:
    import cv2

    return {
        0: pixels,
        90: cv2.rotate(pixels, cv2.ROTATE_90_CLOCKWISE),
        180: cv2.rotate(pixels, cv2.ROTATE_180),
        270: cv2.rotate(pixels, cv2.ROTATE_90_COUNTERCLOCKWISE),
    }[metadata.rotation]
