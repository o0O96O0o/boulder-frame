import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from boulder_frame_worker.frame_reader import OpenCVFrameReader, crop_and_resize_frame
from boulder_frame_worker.media import MediaMetadata
from boulder_frame_worker.planner import CropRect

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")


def _source(tmp_path: Path) -> Path:
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is required for frame-reader integration tests")
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=64x48:rate=2:duration=1.5",
            "-frames:v",
            "3",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return source


def _metadata(rotation: int = 0) -> MediaMetadata:
    return MediaMetadata(64, 48, 1500, Fraction(2, 1), "h264", None, rotation, False)


def test_reader_streams_all_cfr_frames_with_metadata_timestamps(tmp_path: Path) -> None:
    frames = list(OpenCVFrameReader().read(_source(tmp_path), _metadata()))

    assert [frame.index for frame in frames] == [0, 1, 2]
    assert [frame.timestamp_ms for frame in frames] == [0, 500, 1000]
    assert [frame.pixels.shape for frame in frames] == [(48, 64, 3)] * 3


@pytest.mark.parametrize(
    ("rotation", "code"),
    [
        (90, cv2.ROTATE_90_CLOCKWISE),
        (180, cv2.ROTATE_180),
        (270, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ],
)
def test_reader_normalizes_display_rotation(tmp_path: Path, rotation: int, code: int) -> None:
    source = _source(tmp_path)
    original = list(OpenCVFrameReader().read(source, _metadata()))[0].pixels
    rotated = list(OpenCVFrameReader().read(source, _metadata(rotation)))[0].pixels

    assert rotated.shape[:2] == _metadata(rotation).display_dimensions[::-1]
    assert (rotated == cv2.rotate(original, code)).all()


def test_crop_and_resize_uses_fractional_truncation_and_contiguous_uint8() -> None:
    pixels = np.arange(6 * 8 * 3, dtype=np.uint8).reshape((6, 8, 3))
    crop = CropRect(1.9, 2.1, 4.9, 3.9)

    resized = crop_and_resize_frame(pixels, crop, (10, 6))
    expected = cv2.resize(
        pixels[2:5, 1:5],
        (10, 6),
        interpolation=cv2.INTER_LANCZOS4,
    )

    assert resized.shape == (6, 10, 3)
    assert resized.dtype == np.uint8
    assert resized.flags.c_contiguous
    np.testing.assert_array_equal(resized, expected)
