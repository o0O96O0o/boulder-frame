"""FFmpeg/ffprobe adapters and strict source/output media validation."""

from __future__ import annotations

import json
import math
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Protocol

from .errors import ErrorCode, WorkerError, terminal
from .planner import CropRect


@dataclass(frozen=True, slots=True)
class MediaMetadata:
    width: int
    height: int
    duration_ms: int
    frame_rate: Fraction
    video_codec: str
    audio_codec: str | None
    rotation: int
    has_audio: bool
    video_duration: Fraction | None = None
    audio_stream_index: int | None = None

    @property
    def display_dimensions(self) -> tuple[int, int]:
        """Decoded coordinate dimensions after applying display rotation."""
        if self.rotation in {90, 270}:
            return self.height, self.width
        return self.width, self.height

    def frame_for_time_ms(self, frame_time_ms: int) -> int:
        if not 0 <= frame_time_ms < self.duration_ms:
            raise terminal(
                ErrorCode.INVALID_TARGET_SELECTION, "Target frame time is outside the video."
            )
        return int(Fraction(frame_time_ms, 1000) * self.frame_rate)

    @property
    def expected_frame_count(self) -> int:
        duration = self.video_duration or Fraction(self.duration_ms, 1000)
        return round(duration * self.frame_rate)

    def timestamp_for_frame(self, index: int) -> int:
        if index < 0:
            raise ValueError("frame index must not be negative")
        return round(Fraction(index * 1000, 1) / self.frame_rate)


class CommandRunner(Protocol):
    def run(self, arguments: list[str], *, timeout_seconds: int | None = None) -> str: ...


class CFRNormalizer(Protocol):
    def normalize(
        self,
        source: Path,
        destination: Path,
        frame_rate: Fraction,
        audio_stream_index: int | None,
    ) -> None: ...


def _command_diagnostic(stderr: str | None) -> str | None:
    if not stderr:
        return None
    # FFmpeg can echo an entire generated filter expression in an error. Keep the
    # useful final diagnostics without allowing one failed job to flood logs.
    lines = [line.replace("\x00", "")[-512:] for line in stderr.splitlines() if line.strip()]
    return "\n".join(lines[-16:])[-4096:] or None


class SubprocessRunner:
    def run(self, arguments: list[str], *, timeout_seconds: int | None = None) -> str:
        try:
            completed = subprocess.run(
                arguments,
                capture_output=True,
                check=True,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as error:
            raise terminal(
                ErrorCode.INTERNAL, f"Required media tool is unavailable: {arguments[0]}."
            ) from error
        except subprocess.TimeoutExpired as error:
            raise terminal(
                ErrorCode.INTERNAL,
                "Media processing exceeded its time limit.",
                diagnostic=_command_diagnostic(
                    error.stderr.decode() if isinstance(error.stderr, bytes) else error.stderr
                ),
            ) from error
        except subprocess.CalledProcessError as error:
            raise terminal(
                ErrorCode.INVALID_MEDIA,
                "Video media could not be inspected.",
                diagnostic=_command_diagnostic(error.stderr),
            ) from error
        return completed.stdout


class FFprobeAdapter:
    def __init__(self, binary: str = "ffprobe", runner: CommandRunner | None = None) -> None:
        self.binary = binary
        self.runner = runner or SubprocessRunner()

    def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
        output = self.runner.run(
            [
                self.binary,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ]
        )
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as error:
            raise terminal(
                ErrorCode.INVALID_MEDIA, "Video media could not be inspected."
            ) from error
        if not isinstance(payload, dict):
            raise terminal(ErrorCode.INVALID_MEDIA, "Video media could not be inspected.")
        return metadata_from_ffprobe(payload, allow_variable_frame_rate=allow_variable_frame_rate)


def _stream(payload: dict[str, Any], codec_type: str) -> dict[str, Any] | None:
    streams = payload.get("streams")
    if not isinstance(streams, list):
        return None
    return next(
        (
            item
            for item in streams
            if isinstance(item, dict) and item.get("codec_type") == codec_type
        ),
        None,
    )


def _audio_stream(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, int | None]:
    streams = payload.get("streams")
    if not isinstance(streams, list):
        return None, None
    for index, item in enumerate(streams):
        if isinstance(item, dict) and item.get("codec_type") == "audio":
            if item.get("codec_name") == "aac":
                stream_index = item.get("index", index)
                if isinstance(stream_index, int) and stream_index >= 0:
                    return item, stream_index
                raise terminal(ErrorCode.INVALID_MEDIA, "Video audio stream metadata is invalid.")
            if item.get("codec_name") != "none":
                raise terminal(
                    ErrorCode.UNSUPPORTED_AUDIO_CODEC,
                    "Only AAC audio is supported when audio is present.",
                )
    return None, None


def _fraction(value: object) -> Fraction:
    if not isinstance(value, str) or value in {"0/0", "N/A"}:
        raise terminal(ErrorCode.INVALID_MEDIA, "Video frame rate is invalid.")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise terminal(ErrorCode.INVALID_MEDIA, "Video frame rate is invalid.") from error
    if result <= 0:
        raise terminal(ErrorCode.INVALID_MEDIA, "Video frame rate is invalid.")
    return result


def _rotation(video: dict[str, Any]) -> int:
    tags = video.get("tags")
    raw = tags.get("rotate") if isinstance(tags, dict) else None
    if raw is None:
        for side_data in video.get("side_data_list", []):
            if isinstance(side_data, dict) and "rotation" in side_data:
                raw = side_data["rotation"]
                break
    if raw is None:
        return 0
    try:
        rotation = int(raw) % 360
    except (TypeError, ValueError) as error:
        raise terminal(ErrorCode.INVALID_MEDIA, "Video rotation metadata is invalid.") from error
    if rotation not in {0, 90, 180, 270}:
        raise terminal(ErrorCode.INVALID_MEDIA, "Video rotation metadata is invalid.")
    return rotation


def _video_duration(video: dict[str, Any]) -> Fraction:
    duration_ts = video.get("duration_ts")
    time_base = video.get("time_base")
    if duration_ts not in {None, "N/A"} and time_base not in {None, "N/A"}:
        try:
            duration = Fraction(str(duration_ts)) * Fraction(str(time_base))
        except (ValueError, ZeroDivisionError) as error:
            raise terminal(ErrorCode.INVALID_MEDIA, "Video duration is invalid.") from error
    else:
        try:
            duration = Fraction(str(video.get("duration")))
        except (ValueError, ZeroDivisionError) as error:
            raise terminal(ErrorCode.INVALID_MEDIA, "Video duration is invalid.") from error
    if duration <= 0:
        raise terminal(ErrorCode.INVALID_MEDIA, "Video duration is invalid.")
    return duration


def metadata_from_ffprobe(
    payload: dict[str, Any], *, allow_variable_frame_rate: bool = False
) -> MediaMetadata:
    format_info = payload.get("format")
    format_name = format_info.get("format_name") if isinstance(format_info, dict) else None
    if not isinstance(format_name, str) or not {"mp4", "mov"}.intersection(format_name.split(",")):
        raise terminal(
            ErrorCode.UNSUPPORTED_CONTAINER,
            "Only MP4 and QuickTime video files are supported.",
        )
    video = _stream(payload, "video")
    if video is None:
        raise terminal(ErrorCode.MISSING_VIDEO_STREAM, "The source file has no video stream.")
    if video.get("codec_name") not in {"h264", "hevc"}:
        raise terminal(ErrorCode.UNSUPPORTED_VIDEO_CODEC, "Only H.264 or HEVC video is supported.")
    avg_rate = _fraction(video.get("avg_frame_rate"))
    real_rate = _fraction(video.get("r_frame_rate"))
    if avg_rate != real_rate and not allow_variable_frame_rate:
        raise terminal(ErrorCode.VARIABLE_FRAME_RATE, "Variable-frame-rate video is not supported.")
    width, height = video.get("width"), video.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise terminal(ErrorCode.INVALID_MEDIA, "Video dimensions are invalid.")
    video_duration = _video_duration(video)
    duration_ms = round(video_duration * 1000)
    audio, audio_stream_index = _audio_stream(payload)
    return MediaMetadata(
        width=width,
        height=height,
        duration_ms=duration_ms,
        frame_rate=avg_rate,
        video_codec=str(video.get("codec_name")),
        audio_codec="aac" if audio is not None else None,
        rotation=_rotation(video),
        has_audio=audio is not None,
        video_duration=video_duration,
        audio_stream_index=audio_stream_index,
    )


class FFmpegCFRNormalizer:
    """Creates a display-rotation-normalized H.264/AAC CFR derivative for analysis."""

    def __init__(
        self,
        binary: str = "ffmpeg",
        runner: CommandRunner | None = None,
        timeout_seconds: int = 30 * 60,
    ) -> None:
        self.binary = binary
        self.runner = runner or SubprocessRunner()
        self.timeout_seconds = timeout_seconds

    def normalize(
        self,
        source: Path,
        destination: Path,
        frame_rate: Fraction,
        audio_stream_index: int | None,
    ) -> None:
        audio_mapping = (
            ["-map", f"0:{audio_stream_index}"] if audio_stream_index is not None else []
        )
        try:
            self.runner.run(
                [
                    self.binary,
                    "-y",
                    "-i",
                    str(source),
                    "-vf",
                    f"fps=fps={frame_rate}",
                    "-fps_mode:v",
                    "cfr",
                    "-map",
                    "0:v:0",
                    *audio_mapping,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-map_metadata",
                    "-1",
                    "-metadata:s:v:0",
                    "rotate=0",
                    "-movflags",
                    "+faststart",
                    str(destination),
                ],
                timeout_seconds=self.timeout_seconds,
            )
        except WorkerError as error:
            if error.code is not ErrorCode.INVALID_MEDIA:
                raise
            raise terminal(
                ErrorCode.INVALID_MEDIA,
                "Video timing could not be normalized.",
                diagnostic=error.diagnostic,
            ) from error


def expected_frame_count(metadata: MediaMetadata) -> int:
    return metadata.expected_frame_count


def _rotation_filter(rotation: int) -> str | None:
    return {
        0: None,
        90: "transpose=clock",
        180: "hflip,vflip",
        270: "transpose=cclock",
    }[rotation]


def _crop_annotation_commands(crop_path: Sequence[CropRect], metadata: MediaMetadata) -> str:
    commands = []
    for index, crop in enumerate(crop_path[1:], start=1):
        time = float(Fraction(index, 1) / metadata.frame_rate)
        commands.append(
            f"{time:.6f} drawbox@crop x {crop.x:.6f},"
            f"drawbox@crop y {crop.y:.6f},"
            f"drawbox@crop w {crop.width:.6f},"
            f"drawbox@crop h {crop.height:.6f}"
        )
    return ";".join(commands)


def crop_annotation_filter(crop_path: Sequence[CropRect], metadata: MediaMetadata) -> str:
    """Return a filter graph that draws each display-coordinate crop on its source frame."""
    display_width, display_height = metadata.display_dimensions
    for crop in crop_path:
        if (
            crop.width <= 0
            or crop.height <= 0
            or crop.x < 0
            or crop.y < 0
            or crop.right > display_width
            or crop.bottom > display_height
        ):
            raise terminal(ErrorCode.INVALID_OUTPUT, "Planned crop path is invalid.")

    initial = crop_path[0]
    filters = [rotation_filter] if (rotation_filter := _rotation_filter(metadata.rotation)) else []
    if commands := _crop_annotation_commands(crop_path, metadata):
        filters.append(f"sendcmd=commands='{commands}'")
    filters.append(
        f"drawbox@crop=x={initial.x:.6f}:y={initial.y:.6f}:"
        f"w={initial.width:.6f}:h={initial.height:.6f}:color=lime@0.9:thickness=8"
    )
    filters.append("setsar=1")
    return ",".join(filters)


def write_crop_annotation_filter(
    path: Path, crop_path: Sequence[CropRect], metadata: MediaMetadata
) -> None:
    path.write_text(crop_annotation_filter(crop_path, metadata), encoding="ascii")


class FFmpegRenderer:
    """Renders frame-accurate crop annotations with source audio when present."""

    def __init__(self, binary: str = "ffmpeg", runner: CommandRunner | None = None) -> None:
        self.binary = binary
        self.runner = runner or SubprocessRunner()

    def render(
        self,
        source: Path,
        destination: Path,
        filter_script: Path,
        fps: Fraction,
        audio_stream_index: int | None = None,
    ) -> None:
        audio_mapping = (
            ["-map", f"0:{audio_stream_index}"] if audio_stream_index is not None else []
        )
        try:
            self.runner.run(
                [
                    self.binary,
                    "-y",
                    "-noautorotate",
                    "-i",
                    str(source),
                    "-filter_script:v",
                    str(filter_script),
                    "-map",
                    "0:v:0",
                    *audio_mapping,
                    "-r",
                    str(fps),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-map_metadata",
                    "-1",
                    "-metadata:s:v:0",
                    "rotate=0",
                    "-movflags",
                    "+faststart",
                    str(destination),
                ]
            )
        except WorkerError as error:
            raise terminal(
                ErrorCode.RENDER_UNAVAILABLE,
                "Video rendering could not be completed.",
                diagnostic=error.diagnostic,
            ) from error

    def decode(self, output: Path) -> None:
        try:
            self.runner.run(
                [
                    self.binary,
                    "-v",
                    "error",
                    "-i",
                    str(output),
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a?",
                    "-f",
                    "null",
                    "-",
                ]
            )
        except WorkerError as error:
            raise terminal(
                ErrorCode.INVALID_OUTPUT, "Rendered video could not be decoded."
            ) from error

    def render_crop_annotations(
        self,
        source: Path,
        destination: Path,
        crop_path: Sequence[CropRect],
        source_metadata: MediaMetadata,
        inspector: FFprobeAdapter,
    ) -> MediaMetadata:
        if len(crop_path) != expected_frame_count(source_metadata):
            raise terminal(
                ErrorCode.INVALID_OUTPUT, "Planned crop path does not cover the source video."
            )
        filter_script = destination.with_suffix(".ffscript")
        write_crop_annotation_filter(filter_script, crop_path, source_metadata)
        self.render(
            source,
            destination,
            filter_script,
            source_metadata.frame_rate,
            source_metadata.audio_stream_index,
        )
        try:
            output_metadata = inspector.inspect(destination)
        except WorkerError as error:
            raise terminal(
                ErrorCode.INVALID_OUTPUT, "Rendered video could not be inspected."
            ) from error
        validate_output(
            output_metadata,
            source_metadata.display_dimensions,
            expected_duration_ms=source_metadata.duration_ms,
            duration_tolerance_ms=math.ceil(1000 / float(source_metadata.frame_rate)),
            source_has_audio=source_metadata.has_audio,
        )
        self.decode(destination)
        return output_metadata


def validate_output(
    metadata: MediaMetadata,
    expected_dimensions: tuple[int, int],
    *,
    expected_duration_ms: int | None = None,
    duration_tolerance_ms: int | None = None,
    source_has_audio: bool | None = None,
) -> None:
    if (metadata.width, metadata.height) != expected_dimensions:
        raise terminal(ErrorCode.INVALID_OUTPUT, "Rendered video dimensions are invalid.")
    if metadata.video_codec != "h264":
        raise terminal(ErrorCode.INVALID_OUTPUT, "Rendered video codec is invalid.")
    if metadata.has_audio and metadata.audio_codec != "aac":
        raise terminal(ErrorCode.INVALID_OUTPUT, "Rendered audio codec is invalid.")
    if source_has_audio and not metadata.has_audio:
        raise terminal(ErrorCode.INVALID_OUTPUT, "Rendered video audio is missing.")
    if expected_duration_ms is not None:
        if duration_tolerance_ms is None or duration_tolerance_ms < 0:
            raise ValueError("duration tolerance must be non-negative")
        if abs(metadata.duration_ms - expected_duration_ms) > duration_tolerance_ms:
            raise terminal(ErrorCode.INVALID_OUTPUT, "Rendered video duration is invalid.")
