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
from .protocol import AspectRatio


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
    def run(self, arguments: list[str]) -> str: ...


class SubprocessRunner:
    def run(self, arguments: list[str]) -> str:
        try:
            completed = subprocess.run(arguments, capture_output=True, check=True, text=True)
        except FileNotFoundError as error:
            raise terminal(
                ErrorCode.INTERNAL, f"Required media tool is unavailable: {arguments[0]}."
            ) from error
        except subprocess.CalledProcessError as error:
            raise terminal(
                ErrorCode.INVALID_MEDIA, "Video media could not be inspected."
            ) from error
        return completed.stdout


class FFprobeAdapter:
    def __init__(self, binary: str = "ffprobe", runner: CommandRunner | None = None) -> None:
        self.binary = binary
        self.runner = runner or SubprocessRunner()

    def inspect(self, path: Path) -> MediaMetadata:
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
        return metadata_from_ffprobe(payload)


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


def metadata_from_ffprobe(payload: dict[str, Any]) -> MediaMetadata:
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
    if avg_rate != real_rate:
        raise terminal(ErrorCode.VARIABLE_FRAME_RATE, "Variable-frame-rate video is not supported.")
    width, height = video.get("width"), video.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise terminal(ErrorCode.INVALID_MEDIA, "Video dimensions are invalid.")
    video_duration = _video_duration(video)
    duration_ms = round(video_duration * 1000)
    audio = _stream(payload, "audio")
    if audio is not None and audio.get("codec_name") != "aac":
        raise terminal(
            ErrorCode.UNSUPPORTED_AUDIO_CODEC, "Only AAC audio is supported when audio is present."
        )
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
    )


def output_dimensions(aspect_ratio: AspectRatio) -> tuple[int, int]:
    return (1920, 1080) if aspect_ratio is AspectRatio.LANDSCAPE else (1080, 1920)


def expected_frame_count(metadata: MediaMetadata) -> int:
    return metadata.expected_frame_count


def _frame_expression(values: Sequence[float]) -> str:
    if not values:
        raise ValueError("crop path must not be empty")
    expression = f"{values[-1]:.6f}"
    for index in range(len(values) - 2, -1, -1):
        expression = f"if(lt(n\\,{index + 1})\\,{values[index]:.6f}\\,{expression})"
    return expression


def _rotation_filter(rotation: int) -> str | None:
    return {
        0: None,
        90: "transpose=clock",
        180: "hflip,vflip",
        270: "transpose=cclock",
    }[rotation]


def crop_path_filter(
    crop_path: Sequence[CropRect], metadata: MediaMetadata, aspect_ratio: AspectRatio
) -> str:
    """Return a filter graph that applies one display-coordinate crop per input frame."""
    display_width, display_height = metadata.display_dimensions
    output_width, output_height = output_dimensions(aspect_ratio)
    expected_aspect = output_width / output_height
    for crop in crop_path:
        if (
            crop.width <= 0
            or crop.height <= 0
            or crop.x < 0
            or crop.y < 0
            or crop.right > display_width
            or crop.bottom > display_height
            or not math.isclose(crop.width / crop.height, expected_aspect, rel_tol=1e-6)
        ):
            raise terminal(ErrorCode.INVALID_OUTPUT, "Planned crop path is invalid.")

    width = _frame_expression([crop.width for crop in crop_path])
    height = _frame_expression([crop.height for crop in crop_path])
    x = _frame_expression([crop.x for crop in crop_path])
    y = _frame_expression([crop.y for crop in crop_path])
    filters = [rotation_filter] if (rotation_filter := _rotation_filter(metadata.rotation)) else []
    filters.append(
        f"crop=w='{width}':h='{height}':x='{x}':y='{y}',"
        f"scale={output_width}:{output_height}:flags=lanczos"
    )
    filters.append("setsar=1")
    return ",".join(filters)


def write_crop_path_filter(
    path: Path, crop_path: Sequence[CropRect], metadata: MediaMetadata, aspect_ratio: AspectRatio
) -> None:
    path.write_text(crop_path_filter(crop_path, metadata, aspect_ratio), encoding="ascii")


class FFmpegRenderer:
    """Renders a frame-accurate crop-path filter with source audio when present."""

    def __init__(self, binary: str = "ffmpeg", runner: CommandRunner | None = None) -> None:
        self.binary = binary
        self.runner = runner or SubprocessRunner()

    def render(self, source: Path, destination: Path, filter_script: Path, fps: Fraction) -> None:
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
                    "-map",
                    "0:a?",
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
                    "-shortest",
                    str(destination),
                ]
            )
        except WorkerError as error:
            raise terminal(
                ErrorCode.RENDER_UNAVAILABLE, "Video rendering could not be completed."
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

    def render_crop_path(
        self,
        source: Path,
        destination: Path,
        crop_path: Sequence[CropRect],
        source_metadata: MediaMetadata,
        aspect_ratio: AspectRatio,
        inspector: FFprobeAdapter,
    ) -> MediaMetadata:
        if len(crop_path) != expected_frame_count(source_metadata):
            raise terminal(
                ErrorCode.INVALID_OUTPUT, "Planned crop path does not cover the source video."
            )
        filter_script = destination.with_suffix(".ffscript")
        write_crop_path_filter(filter_script, crop_path, source_metadata, aspect_ratio)
        self.render(source, destination, filter_script, source_metadata.frame_rate)
        try:
            output_metadata = inspector.inspect(destination)
        except WorkerError as error:
            raise terminal(
                ErrorCode.INVALID_OUTPUT, "Rendered video could not be inspected."
            ) from error
        validate_output(
            output_metadata,
            aspect_ratio,
            expected_duration_ms=source_metadata.duration_ms,
            duration_tolerance_ms=math.ceil(1000 / float(source_metadata.frame_rate)),
            source_has_audio=source_metadata.has_audio,
        )
        self.decode(destination)
        return output_metadata


def validate_output(
    metadata: MediaMetadata,
    aspect_ratio: AspectRatio,
    *,
    expected_duration_ms: int | None = None,
    duration_tolerance_ms: int | None = None,
    source_has_audio: bool | None = None,
) -> None:
    expected = output_dimensions(aspect_ratio)
    if (metadata.width, metadata.height) != expected:
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
