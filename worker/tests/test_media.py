import shutil
import subprocess
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from io import BytesIO
from pathlib import Path

import pytest

from boulder_frame_worker.errors import ErrorCode, WorkerError
from boulder_frame_worker.frame_reader import (
    DecodedFrame,
    OpenCVFrameReader,
    crop_and_resize_frame,
)
from boulder_frame_worker.media import (
    FFmpegCFRNormalizer,
    FFmpegRenderer,
    FFprobeAdapter,
    MediaMetadata,
    _near_static_intervals,
    _SubprocessMediaProcess,
    metadata_from_ffprobe,
    validate_output,
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


def test_renderer_builds_fixed_rawvideo_input_and_maps_only_validated_aac() -> None:
    metadata = MediaMetadata(
        320,
        180,
        2000,
        Fraction(174900, 5833),
        "h264",
        "aac",
        0,
        True,
        audio_stream_index=3,
    )

    arguments = FFmpegRenderer()._render_arguments(
        Path("source.mp4"), Path("output.mp4"), metadata, AspectRatio.LANDSCAPE
    )

    assert arguments[:12] == [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-video_size",
        "1920x1080",
        "-framerate",
        "174900/5833",
        "-i",
        "pipe:0",
    ]
    assert ["-noautorotate", "-i", "source.mp4"] == arguments[12:15]
    assert ["-map", "0:v:0", "-map", "1:3"] == arguments[
        arguments.index("-map") : arguments.index("-fps_mode:v")
    ]
    assert ["-fps_mode:v", "passthrough"] == arguments[
        arguments.index("-fps_mode:v") : arguments.index("-c:v")
    ]
    assert "-r" not in arguments
    assert "-shortest" not in arguments
    assert not any("fps=" in argument for argument in arguments)


def test_output_frame_progress_reports_only_consecutive_repeats() -> None:
    class ProgressRunner:
        def run(self, arguments: list[str], *, timeout_seconds: int | None = None) -> str:
            del arguments, timeout_seconds
            return """#format: frame checksums
0,          0,          0,        1,     100, hash-a
0,          1,          1,        1,     100, hash-a
0,          2,          2,        1,     100, hash-b
0,          3,          3,        1,     100, hash-c
0,          4,          4,        1,     100, hash-c
0,          5,          5,        1,     100, hash-c
"""

    progress = FFmpegRenderer(runner=ProgressRunner()).output_frame_progress(Path("output.mp4"))

    assert progress.frame_count == 6
    assert progress.repeated_frame_intervals == ((0, 1), (3, 5))
    assert progress.repeated_frame_count == 5


def test_near_static_intervals_require_a_sustained_low_difference_run() -> None:
    intervals = _near_static_intervals(
        [2.0, 0.01, 0.02, 0.03, 0.04, 2.0, 0.01, 0.02], threshold=0.05, minimum_frames=4
    )

    assert intervals == ((1, 5),)


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
    assert raised.value.diagnostic == (
        "expected_dimensions=1920x1080 actual_dimensions=3840x2160"
    )




def test_renderer_preserves_bounded_ffmpeg_diagnostics(tmp_path: Path) -> None:
    class FailingRunner:
        def start(self, arguments: list[str]):
            del arguments
            raise WorkerError(
                ErrorCode.INVALID_MEDIA,
                "Media process failed.",
                diagnostic="FFmpeg failed while accepting raw frames.",
            )

    class UnusedReader:
        def read(self, source, metadata):
            raise AssertionError("encoder start must precede frame decoding")

    metadata = MediaMetadata(160, 90, 1000, Fraction(1), "h264", None, 0, False)
    with pytest.raises(WorkerError) as raised:
        FFmpegRenderer(runner=FailingRunner()).render_crop_path(
            tmp_path / "source.mp4",
            tmp_path / "output.mp4",
            [CropRect(0, 0, 160, 90)],
            metadata,
            AspectRatio.LANDSCAPE,
            FFprobeAdapter(),
            UnusedReader(),
        )

    assert raised.value.code is ErrorCode.RENDER_UNAVAILABLE
    assert raised.value.message == "Video rendering could not be completed."
    assert raised.value.diagnostic == "FFmpeg failed while accepting raw frames."



def test_streaming_process_reaps_encoder_when_stdin_close_fails() -> None:
    class Stdin:
        def close(self) -> None:
            raise BrokenPipeError("encoder closed input")

    class Process:
        stdin = Stdin()

        def __init__(self) -> None:
            self.wait_calls = 0

        def wait(self) -> int:
            self.wait_calls += 1
            return 1

    process = Process()
    media_process = _SubprocessMediaProcess(process, BytesIO(b"encoder rejected tail"))  # type: ignore[arg-type]

    with pytest.raises(WorkerError) as raised:
        media_process.finish()

    assert process.wait_calls == 1
    assert raised.value.diagnostic == "encoder rejected tail"


def test_renderer_rejects_nonfinite_crop_before_start(tmp_path: Path) -> None:
    class Runner:
        def start(self, arguments: list[str]):
            raise AssertionError(f"encoder must not start: {arguments}")

    metadata = MediaMetadata(160, 90, 1000, Fraction(1), "h264", None, 0, False)
    with pytest.raises(WorkerError) as raised:
        FFmpegRenderer(runner=Runner()).render_crop_path(
            tmp_path / "source.mp4",
            tmp_path / "output.mp4",
            [CropRect(float("nan"), 0, 160, 90)],
            metadata,
            AspectRatio.LANDSCAPE,
            FFprobeAdapter(),
            object(),
        )

    assert raised.value.code is ErrorCode.INVALID_OUTPUT
    assert raised.value.message == "Planned crop path is invalid."

def test_decoder_rejects_incomplete_progress_report() -> None:
    class IncompleteProgressRunner:
        def run(self, arguments: list[str], *, timeout_seconds: int | None = None) -> str:
            del arguments, timeout_seconds
            return "frame=2\nprogress=continue\n"

    with pytest.raises(WorkerError) as raised:
        FFmpegRenderer(runner=IncompleteProgressRunner()).decode(Path("output.mp4"))

    assert raised.value.code is ErrorCode.INVALID_OUTPUT
    assert raised.value.diagnostic == "FFmpeg decode progress was incomplete."


def test_rendered_output_validation_requires_exact_decoded_count() -> None:
    class OneFrameRunner:
        def run(self, arguments: list[str], *, timeout_seconds: int | None = None) -> str:
            del arguments, timeout_seconds
            return "frame=1\nprogress=end\n"

    class OutputInspector:
        def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
            del path, allow_variable_frame_rate
            return MediaMetadata(1920, 1080, 2000, Fraction(1), "h264", None, 0, False)

    source_metadata = MediaMetadata(
        320, 180, 2000, Fraction(1), "h264", None, 0, False
    )
    with pytest.raises(WorkerError) as raised:
        FFmpegRenderer(runner=OneFrameRunner()).validate_rendered_output(
            Path("output.mp4"),
            source_metadata,
            AspectRatio.LANDSCAPE,
            OutputInspector(),
        )

    assert raised.value.code is ErrorCode.INVALID_OUTPUT
    assert raised.value.message == "Rendered video frame count is invalid."
    assert raised.value.diagnostic == "expected_frame_count=2 actual_frame_count=1"


@pytest.mark.parametrize("frame_index", [None, 1], ids=["missing", "misordered"])
def test_renderer_aborts_for_incomplete_or_misaligned_source_frame(
    tmp_path: Path, frame_index: int | None
) -> None:
    class Process:
        aborted = False

        def write(self, data) -> None:
            raise AssertionError("misaligned frame must not be written")

        def finish(self) -> None:
            raise AssertionError("misaligned frame must not finish")

        def abort(self) -> None:
            self.aborted = True

    class Runner:
        def __init__(self, process: Process) -> None:
            self.process = process

        def start(self, arguments: list[str]) -> Process:
            del arguments
            return self.process

    class MisalignedReader:
        def read(self, source, metadata):
            del source, metadata
            return [] if frame_index is None else [DecodedFrame(frame_index, 0, object())]

    process = Process()
    metadata = MediaMetadata(160, 90, 1000, Fraction(1), "h264", None, 0, False)
    with pytest.raises(WorkerError) as raised:
        FFmpegRenderer(runner=Runner(process)).render_crop_path(
            tmp_path / "source.mp4",
            tmp_path / "output.mp4",
            [CropRect(0, 0, 160, 90)],
            metadata,
            AspectRatio.LANDSCAPE,
            FFprobeAdapter(),
            MisalignedReader(),
        )

    assert raised.value.code is ErrorCode.INVALID_MEDIA
    assert process.aborted
    assert not (tmp_path / "output.partial.mp4").exists()


@pytest.mark.parametrize("failure_stage", ["write", "finish"])
def test_renderer_aborts_for_encoder_stream_failure(
    tmp_path: Path, failure_stage: str
) -> None:
    np = pytest.importorskip("numpy")

    class Process:
        aborted = False

        def write(self, data) -> None:
            del data
            if failure_stage == "write":
                raise WorkerError(
                    ErrorCode.INVALID_MEDIA,
                    "Media process failed.",
                    diagnostic="raw frame stream failed",
                )

        def finish(self) -> None:
            if failure_stage == "finish":
                raise WorkerError(
                    ErrorCode.INVALID_MEDIA,
                    "Media process failed.",
                    diagnostic="encoder finalization failed",
                )

        def abort(self) -> None:
            self.aborted = True

    class Runner:
        def __init__(self, process: Process) -> None:
            self.process = process

        def start(self, arguments: list[str]) -> Process:
            del arguments
            return self.process

    class Reader:
        def read(self, source, metadata):
            del source, metadata
            return [DecodedFrame(0, 0, np.zeros((90, 160, 3), dtype=np.uint8))]

    process = Process()
    metadata = MediaMetadata(160, 90, 1000, Fraction(1), "h264", None, 0, False)
    with pytest.raises(WorkerError) as raised:
        FFmpegRenderer(runner=Runner(process)).render_crop_path(
            tmp_path / "source.mp4",
            tmp_path / "output.mp4",
            [CropRect(0, 0, 160, 90)],
            metadata,
            AspectRatio.LANDSCAPE,
            FFprobeAdapter(),
            Reader(),
        )

    assert raised.value.code is ErrorCode.RENDER_UNAVAILABLE
    assert process.aborted
    assert not (tmp_path / "output.partial.mp4").exists()


def test_decoder_preserves_bounded_ffmpeg_diagnostics() -> None:
    class FailingRunner:
        def run(self, arguments: list[str]) -> str:
            del arguments
            raise WorkerError(
                ErrorCode.INVALID_MEDIA,
                "Video media could not be inspected.",
                diagnostic="Invalid NAL unit in output stream.",
            )

    with pytest.raises(WorkerError) as raised:
        FFmpegRenderer(runner=FailingRunner()).decode(Path("output.mp4"))

    assert raised.value.code is ErrorCode.INVALID_OUTPUT
    assert raised.value.message == "Rendered video could not be decoded."
    assert raised.value.diagnostic == "Invalid NAL unit in output stream."


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
        OpenCVFrameReader(),
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
        OpenCVFrameReader(),
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
        OpenCVFrameReader(),
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


def test_renderer_uses_rotated_display_coordinates(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg and ffprobe are required for media integration tests")
    source = tmp_path / "rotated-source.mp4"
    destination = tmp_path / "rotated-output.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:size=90x160:rate=2:duration=1,"
            "drawbox=x=0:y=0:w=90:h=80:color=red:t=fill",
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
    source_metadata = replace(inspector.inspect(source), rotation=90)
    FFmpegRenderer().render_crop_path(
        source,
        destination,
        [CropRect(0, 22, 80, 45), CropRect(80, 22, 80, 45)],
        source_metadata,
        AspectRatio.LANDSCAPE,
        inspector,
        OpenCVFrameReader(),
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

    def rgb(frame: int) -> tuple[int, int, int]:
        offset = frame * frame_size + (540 * 1920 + 960) * 3
        red, green, blue = decoded[offset : offset + 3]
        return red, green, blue

    assert rgb(0)[2] > 200
    assert rgb(1)[0] > 200




def test_renderer_encodes_every_zoom_crop_at_non_integer_cfr(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg, ffprobe, and OpenCV are required for media integration tests")
    source = tmp_path / "source.mp4"
    destination = tmp_path / "output.mp4"
    frame_rate = Fraction(174900, 5833)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=320x180:rate={frame_rate}",
            "-frames:v",
            "60",
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
    assert source_metadata.expected_frame_count == 60
    assert source_metadata.frame_rate == frame_rate

    heights = (180, 162, 144, 126, 108, 90, 108, 126, 144, 162, 180, 162)
    widths = (320, 288, 256, 224, 192, 160, 192, 224, 256, 288, 320, 288)
    crops = [
        CropRect((320 - width) / 2, (180 - height) / 2, width, height)
        for _ in range(5)
        for width, height in zip(widths, heights, strict=True)
    ]
    renderer = FFmpegRenderer()
    output_metadata = renderer.render_crop_path(
        source,
        destination,
        crops,
        source_metadata,
        AspectRatio.LANDSCAPE,
        inspector,
        OpenCVFrameReader(),
    )

    assert renderer.decode(destination) == 60
    assert output_metadata.frame_rate == frame_rate
    assert (output_metadata.width, output_metadata.height) == (1920, 1080)

    output = cv2.VideoCapture(str(destination))
    assert output.isOpened()
    source_frames = OpenCVFrameReader().read(source, source_metadata)
    try:
        for index, source_frame in enumerate(source_frames):
            decoded, output_pixels = output.read()
            assert decoded
            expected = crop_and_resize_frame(
                source_frame.pixels, crops[index], (1920, 1080)
            )
            mean_absolute_error = sum(cv2.mean(cv2.absdiff(expected, output_pixels))[:3]) / 3
            assert mean_absolute_error <= 24
        decoded, _ = output.read()
        assert not decoded
    finally:
        output.release()
        close = getattr(source_frames, "close", None)
        if callable(close):
            close()


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
    assert raised.value.diagnostic == "source_has_audio=true output_has_audio=false"

    with pytest.raises(WorkerError) as raised:
        validate_output(
            metadata,
            AspectRatio.LANDSCAPE,
            expected_duration_ms=1000,
            duration_tolerance_ms=33,
        )

    assert raised.value.code is ErrorCode.INVALID_OUTPUT
    assert raised.value.diagnostic == (
        "expected_duration_ms=1000 actual_duration_ms=1200 tolerance_ms=33"
    )
