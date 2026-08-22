import shutil
import subprocess
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from boulder_frame_worker.errors import ErrorCode, WorkerError
from boulder_frame_worker.media import (
    FFmpegRenderer,
    FFprobeAdapter,
    MediaMetadata,
    _frame_expression,
    crop_path_filter,
    metadata_from_ffprobe,
    validate_output,
    write_crop_path_filter,
)
from boulder_frame_worker.planner import CropRect
from boulder_frame_worker.protocol import AspectRatio


def probe_payload() -> dict[str, object]:
    return {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "42.0"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 3840,
                "height": 2160,
                "avg_frame_rate": "60/1",
                "r_frame_rate": "60/1",
                "duration_ts": "645120",
                "time_base": "1/15360",
                "tags": {"rotate": "90"},
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }


def test_valid_cfr_quicktime_metadata_includes_rotation() -> None:
    metadata = metadata_from_ffprobe(probe_payload())

    assert (metadata.width, metadata.height, metadata.duration_ms) == (3840, 2160, 42000)
    assert str(metadata.frame_rate) == "60"
    assert metadata.rotation == 90
    assert metadata.display_dimensions == (2160, 3840)
    assert metadata.frame_for_time_ms(500) == 30
    assert metadata.audio_codec == "aac"


def test_hevc_quicktime_metadata_is_supported() -> None:
    data = probe_payload()
    data["streams"][0]["codec_name"] = "hevc"  # type: ignore[index]

    metadata = metadata_from_ffprobe(data)

    assert metadata.video_codec == "hevc"


def test_video_timing_is_used_when_container_duration_includes_longer_audio() -> None:
    data = probe_payload()
    data["format"]["duration"] = "44.0"  # type: ignore[index]

    metadata = metadata_from_ffprobe(data)

    assert metadata.duration_ms == 42000
    assert metadata.expected_frame_count == 2520


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda data: data["streams"].pop(0), ErrorCode.MISSING_VIDEO_STREAM),
        (
            lambda data: data["streams"][0].update(avg_frame_rate="30000/1001"),
            ErrorCode.VARIABLE_FRAME_RATE,
        ),
        (
            lambda data: data["streams"][1].update(codec_name="mp3"),
            ErrorCode.UNSUPPORTED_AUDIO_CODEC,
        ),
        (
            lambda data: data["format"].update(format_name="matroska,webm"),
            ErrorCode.UNSUPPORTED_CONTAINER,
        ),
    ],
)
def test_invalid_media_is_classified(mutation: object, code: ErrorCode) -> None:
    data = deepcopy(probe_payload())
    mutation(data)  # type: ignore[operator]

    with pytest.raises(WorkerError) as raised:
        metadata_from_ffprobe(data)

    assert raised.value.code is code


def test_output_validation_requires_selected_dimensions() -> None:
    metadata = metadata_from_ffprobe(probe_payload())
    with pytest.raises(WorkerError) as raised:
        validate_output(metadata, AspectRatio.LANDSCAPE)

    assert raised.value.code is ErrorCode.INVALID_OUTPUT


def test_crop_path_filter_normalizes_clockwise_rotation_before_cropping() -> None:
    metadata = metadata_from_ffprobe(probe_payload())
    crop = CropRect(0, 0, 2160, 1215)

    filter_graph = crop_path_filter([crop], metadata, AspectRatio.LANDSCAPE)

    assert filter_graph.startswith("transpose=clock,crop=")
    assert "scale=1920:1080" in filter_graph
    assert "setsar=1" in filter_graph


def test_frame_expression_uses_logarithmic_nesting_for_long_crop_paths() -> None:
    expression = _frame_expression([float(index) for index in range(2520)])
    depth = 0
    maximum_depth = 0
    for character in expression:
        if character == "(":
            depth += 1
            maximum_depth = max(maximum_depth, depth)
        elif character == ")":
            depth -= 1

    assert expression.count("if(") == 2519
    assert depth == 0
    assert maximum_depth <= 14


def test_long_crop_path_filter_is_accepted_by_ffmpeg(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is required for media integration tests")
    metadata = MediaMetadata(
        width=160,
        height=90,
        duration_ms=42000,
        frame_rate=Fraction(60, 1),
        video_codec="h264",
        audio_codec=None,
        rotation=0,
        has_audio=False,
    )
    script = tmp_path / "crop.ffscript"
    write_crop_path_filter(
        script,
        [CropRect(0, 0, 160, 90)] * metadata.expected_frame_count,
        metadata,
        AspectRatio.LANDSCAPE,
    )

    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=60:duration=0.02",
            "-filter_script:v",
            str(script),
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("aspect_ratio", "with_audio", "audio_duration"),
    [
        pytest.param(AspectRatio.LANDSCAPE, True, 1, id="landscape-with-audio"),
        pytest.param(AspectRatio.PORTRAIT, False, None, id="portrait-without-audio"),
        pytest.param(
            AspectRatio.LANDSCAPE,
            True,
            2,
            id="video-stream-shorter-than-audio-container",
        ),
    ],
)
def test_renderer_creates_valid_decodable_mp4_from_crop_path(
    tmp_path: Path, aspect_ratio: AspectRatio, with_audio: bool, audio_duration: int | None
) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg and ffprobe are required for media integration tests")
    source = tmp_path / "source.mp4"
    destination = tmp_path / "output.mp4"
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=160x90:rate=2:duration=1",
    ]
    if with_audio:
        command.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:sample_rate=48000:duration={audio_duration}",
            ]
        )
    command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
    if with_audio:
        command.extend(["-c:a", "aac"])
    command.append(str(source))
    subprocess.run(command, check=True, capture_output=True, text=True)

    inspector = FFprobeAdapter()
    source_metadata = inspector.inspect(source)
    assert source_metadata.duration_ms == 1000
    assert source_metadata.expected_frame_count == 2
    if audio_duration and audio_duration > 1:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert float(probe.stdout) > 1
    crop = (
        CropRect(0, 0, 160, 90)
        if aspect_ratio is AspectRatio.LANDSCAPE
        else CropRect(54.6875, 0, 50.625, 90)
    )
    moving_crop = (
        CropRect(0, 0, 160, 90)
        if aspect_ratio is AspectRatio.LANDSCAPE
        else CropRect(59.375, 0, 50.625, 90)
    )

    output_metadata = FFmpegRenderer().render_crop_path(
        source,
        destination,
        [crop, moving_crop],
        source_metadata,
        aspect_ratio,
        inspector,
    )

    assert destination.exists()
    assert (output_metadata.width, output_metadata.height) == (
        (1920, 1080) if aspect_ratio is AspectRatio.LANDSCAPE else (1080, 1920)
    )
    assert output_metadata.video_codec == "h264"
    assert output_metadata.has_audio is with_audio
    assert abs(output_metadata.duration_ms - source_metadata.duration_ms) <= 500


def test_output_validation_requires_source_audio_and_duration_within_tolerance() -> None:
    metadata = MediaMetadata(
        width=1920,
        height=1080,
        duration_ms=1200,
        frame_rate=Fraction(30, 1),
        video_codec="h264",
        audio_codec=None,
        rotation=0,
        has_audio=False,
    )

    with pytest.raises(WorkerError) as raised:
        validate_output(
            metadata,
            AspectRatio.LANDSCAPE,
            expected_duration_ms=1000,
            duration_tolerance_ms=33,
            source_has_audio=True,
        )

    assert raised.value.code is ErrorCode.INVALID_OUTPUT
