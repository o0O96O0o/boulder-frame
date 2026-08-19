"""FFmpeg/ffprobe adapters and strict source/output media validation."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Protocol

from .errors import ErrorCode, terminal
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
        return int(raw) % 360
    except (TypeError, ValueError) as error:
        raise terminal(ErrorCode.INVALID_MEDIA, "Video rotation metadata is invalid.") from error


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
    duration_value = format_info.get("duration")
    try:
        duration_ms = round(float(duration_value) * 1000)
    except (TypeError, ValueError) as error:
        raise terminal(ErrorCode.INVALID_MEDIA, "Video duration is invalid.") from error
    if duration_ms <= 0:
        raise terminal(ErrorCode.INVALID_MEDIA, "Video duration is invalid.")
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
    )


class FFmpegRenderer:
    """A narrow adapter for frame-accurate crop commands supplied by a future encoder layer."""

    def __init__(self, binary: str = "ffmpeg", runner: CommandRunner | None = None) -> None:
        self.binary = binary
        self.runner = runner or SubprocessRunner()

    def render(self, source: Path, destination: Path, filter_script: Path, fps: Fraction) -> None:
        self.runner.run(
            [
                self.binary,
                "-y",
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
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(destination),
            ]
        )


def validate_output(metadata: MediaMetadata, aspect_ratio: AspectRatio) -> None:
    expected = (1920, 1080) if aspect_ratio is AspectRatio.LANDSCAPE else (1080, 1920)
    if (metadata.width, metadata.height) != expected:
        raise terminal(ErrorCode.INVALID_OUTPUT, "Rendered video dimensions are invalid.")
    if metadata.video_codec != "h264":
        raise terminal(ErrorCode.INVALID_OUTPUT, "Rendered video codec is invalid.")
    if metadata.has_audio and metadata.audio_codec != "aac":
        raise terminal(ErrorCode.INVALID_OUTPUT, "Rendered audio codec is invalid.")
