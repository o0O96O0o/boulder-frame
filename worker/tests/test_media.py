import shutil
import subprocess
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from boulder_frame_worker.errors import ErrorCode, WorkerError
from boulder_frame_worker.media import (
    FFmpegCFRNormalizer,
    FFmpegRenderer,
    FFprobeAdapter,
    MediaMetadata,
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
    assert metadata.audio_stream_index == 1


def test_hevc_quicktime_metadata_is_supported() -> None:
    data = probe_payload()
    data["streams"][0]["codec_name"] = "hevc"  # type: ignore[index]

    metadata = metadata_from_ffprobe(data)

    assert metadata.video_codec == "hevc"


def test_permissive_inspection_retains_supported_vfr_metadata() -> None:
    data = probe_payload()
    data["streams"][0].update(avg_frame_rate="30000/1001")  # type: ignore[index]

    metadata = metadata_from_ffprobe(data, allow_variable_frame_rate=True)

    assert metadata.frame_rate == Fraction(30000, 1001)


def test_aac_stream_is_selected_without_mapping_codec_none_tracks() -> None:
    data = probe_payload()
    data["streams"] = [
        data["streams"][0],  # type: ignore[index]
        {"index": 1, "codec_type": "audio", "codec_name": "none"},
        {"index": 2, "codec_type": "data", "codec_name": "mebx"},
        {"index": 3, "codec_type": "audio", "codec_name": "aac"},
    ]

    metadata = metadata_from_ffprobe(data)

    assert metadata.has_audio
    assert metadata.audio_stream_index == 3


def test_renderer_maps_only_the_validated_aac_stream() -> None:
    class CapturingRunner:
        def __init__(self) -> None:
            self.arguments: list[str] = []

        def run(self, arguments: list[str], *, timeout_seconds: int | None = None) -> str:
            del timeout_seconds
            self.arguments = arguments
            return ""

    runner = CapturingRunner()
    FFmpegRenderer(runner=runner).render(
        Path("source.mp4"),
        Path("output.mp4"),
        Path("crop.ffscript"),
        Fraction(30, 1),
        audio_stream_index=3,
    )

    assert ["-map", "0:v:0", "-map", "0:3"] == runner.arguments[
        runner.arguments.index("-map") : runner.arguments.index("-r")
    ]
    assert "-shortest" not in runner.arguments


def test_normalizer_creates_rotation_normalized_cfr_h264_aac_derivative() -> None:
    class CapturingRunner:
        def __init__(self) -> None:
            self.arguments: list[str] = []
            self.timeout_seconds: int | None = None

        def run(self, arguments: list[str], *, timeout_seconds: int | None = None) -> str:
            self.arguments = arguments
            self.timeout_seconds = timeout_seconds
            return ""

    runner = CapturingRunner()
    FFmpegCFRNormalizer(runner=runner, timeout_seconds=123).normalize(
        Path("source.mov"), Path("source-cfr.mp4"), Fraction(30000, 1001), 3
    )

    assert "-noautorotate" not in runner.arguments
    assert ["-vf", "fps=fps=30000/1001", "-fps_mode:v", "cfr"] == runner.arguments[
        runner.arguments.index("-vf") : runner.arguments.index("-map")
    ]
    assert ["-map", "0:v:0", "-map", "0:3"] == runner.arguments[
        runner.arguments.index("-map") : runner.arguments.index("-c:v")
    ]
    assert ["-map_metadata", "-1", "-metadata:s:v:0", "rotate=0"] == runner.arguments[
        runner.arguments.index("-map_metadata") : runner.arguments.index("-movflags")
    ]
    assert "-shortest" not in runner.arguments
    assert runner.timeout_seconds == 123


@pytest.mark.parametrize("code", [ErrorCode.INTERNAL, ErrorCode.STORAGE_UNAVAILABLE])
def test_normalizer_preserves_non_media_error_classification(code: ErrorCode) -> None:
    class FailingRunner:
        def run(self, arguments: list[str], *, timeout_seconds: int | None = None) -> str:
            del arguments, timeout_seconds
            raise WorkerError(code, "media tool is unavailable", diagnostic="missing ffmpeg")

    with pytest.raises(WorkerError) as raised:
        FFmpegCFRNormalizer(runner=FailingRunner()).normalize(
            Path("source.mov"), Path("source-cfr.mp4"), Fraction(30, 1), None
        )

    assert raised.value.code is code
    assert raised.value.message == "media tool is unavailable"
    assert raised.value.diagnostic == "missing ffmpeg"


def test_normalizer_reports_user_safe_media_error() -> None:
    class FailingRunner:
        def run(self, arguments: list[str], *, timeout_seconds: int | None = None) -> str:
            del arguments, timeout_seconds
            raise WorkerError(
                ErrorCode.INVALID_MEDIA,
                "Video media could not be inspected.",
                diagnostic="FFmpeg normalization failed.",
            )

    with pytest.raises(WorkerError) as raised:
        FFmpegCFRNormalizer(runner=FailingRunner()).normalize(
            Path("source.mov"), Path("source-cfr.mp4"), Fraction(30, 1), None
        )

    assert raised.value.code is ErrorCode.INVALID_MEDIA
    assert raised.value.message == "Video timing could not be normalized."
    assert raised.value.diagnostic == "FFmpeg normalization failed."


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


def test_output_validation_requires_requested_1080p_dimensions() -> None:
    metadata = metadata_from_ffprobe(probe_payload())
    with pytest.raises(WorkerError) as raised:
        validate_output(metadata, AspectRatio.LANDSCAPE)

    assert raised.value.code is ErrorCode.INVALID_OUTPUT


def test_crop_path_filter_normalizes_clockwise_rotation_before_cropping() -> None:
    metadata = metadata_from_ffprobe(probe_payload())
    crop = CropRect(0, 0, 2160, 1215)

    filter_graph = crop_path_filter([crop], metadata, AspectRatio.LANDSCAPE)

    assert filter_graph.startswith("transpose=clock,crop@path=")
    assert "w=2160.000000:h=1215.000000" in filter_graph
    assert "scale=1920:1080:flags=lanczos" in filter_graph
    assert "setsar=1" in filter_graph


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


def test_renderer_preserves_bounded_ffmpeg_diagnostics() -> None:
    class FailingRunner:
        def run(self, arguments: list[str]) -> str:
            del arguments
            raise WorkerError(
                ErrorCode.INVALID_MEDIA,
                "Video media could not be inspected.",
                diagnostic="FFmpeg failed while configuring crop.",
            )

    with pytest.raises(WorkerError) as raised:
        FFmpegRenderer(runner=FailingRunner()).render(
            Path("source.mp4"), Path("output.mp4"), Path("crop.ffscript"), Fraction(30, 1)
        )

    assert raised.value.code is ErrorCode.RENDER_UNAVAILABLE
    assert raised.value.message == "Video rendering could not be completed."
    assert raised.value.diagnostic == "FFmpeg failed while configuring crop."


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
def test_renderer_creates_valid_decodable_mp4_with_crop_path(
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


@pytest.mark.parametrize("audio_duration", [1, 3], ids=["shorter-audio", "longer-audio"])
def test_normalizer_preserves_vfr_video_duration_with_optional_aac(
    tmp_path: Path, audio_duration: int
) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg and ffprobe are required for media integration tests")
    source = tmp_path / "source-vfr.mp4"
    destination = tmp_path / "source-cfr.mp4"
    output = tmp_path / "output.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=30:duration=2",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:duration={audio_duration}",
            "-vf",
            "select=not(mod(n\\,2))",
            "-fps_mode:v",
            "vfr",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    inspector = FFprobeAdapter()
    with pytest.raises(WorkerError) as raised:
        inspector.inspect(source)
    assert raised.value.code is ErrorCode.VARIABLE_FRAME_RATE

    source_metadata = inspector.inspect(source, allow_variable_frame_rate=True)
    FFmpegCFRNormalizer().normalize(
        source, destination, source_metadata.frame_rate, source_metadata.audio_stream_index
    )
    derivative = inspector.inspect(destination)

    assert derivative.frame_rate == source_metadata.frame_rate
    assert derivative.has_audio
    assert derivative.rotation == 0
    assert derivative.duration_ms >= source_metadata.duration_ms - 100
    derivative.frame_for_time_ms(source_metadata.duration_ms - 200)
    if audio_duration > 1:
        derivative_duration = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(destination),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert float(derivative_duration.stdout) > source_metadata.duration_ms / 1000

    rendered = FFmpegRenderer().render_crop_path(
        destination,
        output,
        [CropRect(0, 0, derivative.width, derivative.height)] * derivative.expected_frame_count,
        derivative,
        AspectRatio.LANDSCAPE,
        inspector,
    )

    assert rendered.duration_ms >= source_metadata.duration_ms - 100
    rendered.frame_for_time_ms(source_metadata.duration_ms - 200)
    if audio_duration > 1:
        rendered_duration = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert float(rendered_duration.stdout) > source_metadata.duration_ms / 1000


def test_renderer_applies_the_planned_crop_to_each_source_frame(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg and ffprobe are required for media integration tests")
    source = tmp_path / "source.mp4"
    destination = tmp_path / "output.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:size=160x90:rate=2:duration=1,drawbox=x=0:y=0:w=80:h=90:color=red:t=fill",
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
    inspector = FFprobeAdapter()
    source_metadata = inspector.inspect(source)
    FFmpegRenderer().render_crop_path(
        source,
        destination,
        [CropRect(0, 10, 80, 45), CropRect(80, 10, 80, 45)],
        source_metadata,
        AspectRatio.LANDSCAPE,
        inspector,
    )
    decoded = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(destination),
            "-frames:v",
            "2",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    frame_size = 1920 * 1080 * 3

    def rgb(frame: int, x: int, y: int) -> tuple[int, int, int]:
        offset = frame * frame_size + (y * 1920 + x) * 3
        red, green, blue = decoded[offset : offset + 3]
        return red, green, blue

    assert rgb(0, 960, 540)[0] > 200
    assert rgb(1, 960, 540)[2] > 200


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
