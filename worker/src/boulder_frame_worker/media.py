"""FFmpeg/ffprobe adapters and strict source/output media validation."""

from __future__ import annotations

import json
import math
import subprocess
from collections.abc import Buffer, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryFile
from typing import Any, BinaryIO, Protocol, cast

from .errors import ErrorCode, WorkerError, terminal
from .frame_reader import FrameReader, crop_and_resize_frame
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


@dataclass(frozen=True, slots=True)
class OutputFrameProgress:
    frame_count: int
    repeated_frame_intervals: tuple[tuple[int, int], ...]

    @property
    def repeated_frame_count(self) -> int:
        return sum(end - start + 1 for start, end in self.repeated_frame_intervals)


@dataclass(frozen=True, slots=True)
class TemporalFrameProgress:
    frame_count: int
    near_static_intervals: tuple[tuple[int, int], ...]

    @property
    def near_static_frame_count(self) -> int:
        return sum(end - start + 1 for start, end in self.near_static_intervals)


class CommandRunner(Protocol):
    def run(self, arguments: list[str], *, timeout_seconds: int | None = None) -> str: ...



class MediaProcess(Protocol):
    def write(self, data: Buffer) -> None: ...

    def finish(self) -> None: ...

    def abort(self) -> None: ...


class MediaRunner(CommandRunner, Protocol):
    def start(self, arguments: list[str]) -> MediaProcess: ...

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

    def start(self, arguments: list[str]) -> MediaProcess:
        stderr = TemporaryFile(mode="w+b")
        try:
            process = subprocess.Popen(
                arguments,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
            )
        except FileNotFoundError as error:
            stderr.close()
            raise terminal(
                ErrorCode.INTERNAL, f"Required media tool is unavailable: {arguments[0]}."
            ) from error
        except OSError as error:
            stderr.close()
            raise terminal(
                ErrorCode.INTERNAL,
                "Media process could not be started.",
                diagnostic=_command_diagnostic(str(error)),
            ) from error
        return _SubprocessMediaProcess(process, stderr)


class _SubprocessMediaProcess:
    def __init__(self, process: subprocess.Popen[bytes], stderr: BinaryIO) -> None:
        self._process = process
        self._stderr = stderr
        self._finished = False

    def write(self, data: Buffer) -> None:
        if self._finished or self._process.stdin is None:
            raise terminal(ErrorCode.INVALID_MEDIA, "Media process input is unavailable.")
        remaining = memoryview(data).cast("B")
        try:
            while remaining:
                written = self._process.stdin.write(remaining)
                if written is None or written <= 0:
                    raise BrokenPipeError("media process accepted no input")
                remaining = remaining[written:]
        except (BrokenPipeError, OSError) as error:
            diagnostic = self._finish_after_failure()
            raise terminal(
                ErrorCode.INVALID_MEDIA,
                "Media process could not accept input.",
                diagnostic=diagnostic,
            ) from error

    def finish(self) -> None:
        if self._finished:
            return
        close_error: OSError | None = None
        try:
            if self._process.stdin is not None:
                self._process.stdin.close()
        except OSError as error:
            close_error = error
        try:
            return_code = self._process.wait()
            diagnostic = self._read_diagnostic()
        finally:
            self._finished = True
            try:
                self._stderr.close()
            except OSError:
                pass
        if return_code != 0 or close_error is not None:
            close_diagnostic = (
                _command_diagnostic(str(close_error)) if close_error is not None else None
            )
            raise terminal(
                ErrorCode.INVALID_MEDIA,
                "Media process failed.",
                diagnostic=diagnostic or close_diagnostic,
            )

    def abort(self) -> None:
        if self._finished:
            return
        try:
            try:
                if self._process.stdin is not None:
                    self._process.stdin.close()
            except OSError:
                pass
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
        except OSError:
            pass
        finally:
            self._finished = True
            try:
                self._stderr.close()
            except OSError:
                pass

    def _finish_after_failure(self) -> str | None:
        try:
            if self._process.stdin is not None:
                self._process.stdin.close()
        except OSError:
            pass
        try:
            self._process.wait()
            return self._read_diagnostic()
        except OSError as error:
            return _command_diagnostic(str(error))
        finally:
            self._finished = True
            try:
                self._stderr.close()
            except OSError:
                pass

    def _read_diagnostic(self) -> str | None:
        self._stderr.seek(0)
        return _command_diagnostic(self._stderr.read().decode(errors="replace"))


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


def output_dimensions(aspect_ratio: AspectRatio) -> tuple[int, int]:
    return (1920, 1080) if aspect_ratio is AspectRatio.LANDSCAPE else (1080, 1920)


def _validate_crop_path(
    crop_path: Sequence[CropRect], metadata: MediaMetadata, aspect_ratio: AspectRatio
) -> None:
    if len(crop_path) != expected_frame_count(metadata):
        raise terminal(
            ErrorCode.INVALID_OUTPUT, "Planned crop path does not cover the source video."
        )
    display_width, display_height = metadata.display_dimensions
    output_width, output_height = output_dimensions(aspect_ratio)
    expected_aspect = output_width / output_height
    for crop in crop_path:
        if (
            not all(
                math.isfinite(value)
                for value in (crop.x, crop.y, crop.width, crop.height)
            )
            or
            crop.width <= 0
            or crop.height <= 0
            or crop.x < 0
            or crop.y < 0
            or crop.right > display_width
            or crop.bottom > display_height
            or not math.isclose(crop.width / crop.height, expected_aspect, rel_tol=1e-6)
        ):
            raise terminal(ErrorCode.INVALID_OUTPUT, "Planned crop path is invalid.")


class FFmpegRenderer:
    """Crops every decoded frame and streams one fixed output frame to FFmpeg."""

    def __init__(self, binary: str = "ffmpeg", runner: MediaRunner | None = None) -> None:
        self.binary = binary
        self.runner = runner or SubprocessRunner()

    def render_crop_path(
        self,
        source: Path,
        destination: Path,
        crop_path: Sequence[CropRect],
        source_metadata: MediaMetadata,
        aspect_ratio: AspectRatio,
        inspector: FFprobeAdapter,
        frame_reader: FrameReader,
    ) -> MediaMetadata:
        _validate_crop_path(crop_path, source_metadata, aspect_ratio)
        partial = destination.with_name(destination.stem + ".partial" + destination.suffix)
        try:
            partial.unlink(missing_ok=True)
        except OSError as error:
            raise terminal(
                ErrorCode.RENDER_UNAVAILABLE,
                "Video rendering could not be completed.",
                diagnostic=_command_diagnostic(str(error)),
            ) from error

        process: MediaProcess | None = None
        frames: Any = None
        try:
            try:
                process = self.runner.start(
                    self._render_arguments(
                        source, partial, source_metadata, aspect_ratio
                    )
                )
            except WorkerError as error:
                raise self._render_failure(error) from error
            except Exception as error:
                raise terminal(
                    ErrorCode.RENDER_UNAVAILABLE,
                    "Video rendering could not be completed.",
                    diagnostic=_command_diagnostic(str(error)),
                ) from error

            try:
                frames = iter(frame_reader.read(source, source_metadata))
            except WorkerError:
                raise
            except Exception as error:
                raise terminal(
                    ErrorCode.INVALID_MEDIA,
                    "Video frames could not be rendered consistently.",
                    diagnostic=_command_diagnostic(str(error)),
                ) from error

            for index, crop in enumerate(crop_path):
                try:
                    frame = next(frames)
                except StopIteration as error:
                    raise terminal(
                        ErrorCode.INVALID_MEDIA,
                        "Video frames could not be rendered consistently.",
                    ) from error
                except WorkerError:
                    raise
                except Exception as error:
                    raise terminal(
                        ErrorCode.INVALID_MEDIA,
                        "Video frames could not be rendered consistently.",
                        diagnostic=_command_diagnostic(str(error)),
                    ) from error
                if (
                    frame.index != index
                    or frame.timestamp_ms != source_metadata.timestamp_for_frame(index)
                ):
                    raise terminal(
                        ErrorCode.INVALID_MEDIA,
                        "Video frames could not be rendered consistently.",
                    )
                resized = cast(
                    Buffer,
                    crop_and_resize_frame(
                        frame.pixels, crop, output_dimensions(aspect_ratio)
                    ),
                )
                try:
                    payload = memoryview(resized).cast("B")
                except (TypeError, ValueError) as error:
                    raise terminal(
                        ErrorCode.INVALID_MEDIA,
                        "Video frames could not be rendered consistently.",
                    ) from error
                try:
                    process.write(payload)
                except WorkerError as error:
                    raise self._render_failure(error) from error
                except Exception as error:
                    raise terminal(
                        ErrorCode.RENDER_UNAVAILABLE,
                        "Video rendering could not be completed.",
                        diagnostic=_command_diagnostic(str(error)),
                    ) from error

            try:
                next(frames)
            except StopIteration:
                pass
            except WorkerError:
                raise
            except Exception as error:
                raise terminal(
                    ErrorCode.INVALID_MEDIA,
                    "Video frames could not be rendered consistently.",
                    diagnostic=_command_diagnostic(str(error)),
                ) from error
            else:
                raise terminal(
                    ErrorCode.INVALID_MEDIA,
                    "Video frames could not be rendered consistently.",
                )

            try:
                process.finish()
            except WorkerError as error:
                raise self._render_failure(error) from error
            except Exception as error:
                raise terminal(
                    ErrorCode.RENDER_UNAVAILABLE,
                    "Video rendering could not be completed.",
                    diagnostic=_command_diagnostic(str(error)),
                ) from error

            output_metadata = self.validate_rendered_output(
                partial, source_metadata, aspect_ratio, inspector
            )
            try:
                partial.replace(destination)
            except OSError as error:
                raise terminal(
                    ErrorCode.RENDER_UNAVAILABLE,
                    "Video rendering could not be completed.",
                    diagnostic=_command_diagnostic(str(error)),
                ) from error
            return output_metadata
        except Exception:
            if process is not None:
                process.abort()
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        finally:
            close = getattr(frames, "close", None)
            if callable(close):
                close()

    def _render_arguments(
        self,
        source: Path,
        destination: Path,
        metadata: MediaMetadata,
        aspect_ratio: AspectRatio,
    ) -> list[str]:
        output_width, output_height = output_dimensions(aspect_ratio)
        audio_input = (
            ["-noautorotate", "-i", str(source)]
            if metadata.audio_stream_index is not None
            else []
        )
        audio_mapping = (
            ["-map", f"1:{metadata.audio_stream_index}"]
            if metadata.audio_stream_index is not None
            else []
        )
        return [
            self.binary,
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-video_size",
            f"{output_width}x{output_height}",
            "-framerate",
            str(metadata.frame_rate),
            "-i",
            "pipe:0",
            *audio_input,
            "-map",
            "0:v:0",
            *audio_mapping,
            "-fps_mode:v",
            "passthrough",
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

    @staticmethod
    def _render_failure(error: WorkerError) -> WorkerError:
        return terminal(
            ErrorCode.RENDER_UNAVAILABLE,
            "Video rendering could not be completed.",
            diagnostic=error.diagnostic or f"{error.code.value}: {error.message}",
        )

    def decode(self, output: Path) -> int:
        try:
            report = self.runner.run(
                [
                    self.binary,
                    "-v",
                    "error",
                    "-progress",
                    "pipe:1",
                    "-nostats",
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
                ErrorCode.INVALID_OUTPUT,
                "Rendered video could not be decoded.",
                diagnostic=error.diagnostic or f"{error.code.value}: {error.message}",
            ) from error
        frame_count: int | None = None
        ended = False
        for line in report.splitlines():
            key, separator, value = line.partition("=")
            if not separator:
                continue
            if key == "frame":
                try:
                    frame_count = int(value)
                except ValueError:
                    frame_count = None
            elif key == "progress" and value == "end":
                ended = True
        if not ended or frame_count is None or frame_count < 0:
            raise terminal(
                ErrorCode.INVALID_OUTPUT,
                "Rendered video could not be decoded.",
                diagnostic="FFmpeg decode progress was incomplete.",
            )
        return frame_count

    def validate_rendered_output(
        self,
        output: Path,
        source_metadata: MediaMetadata,
        aspect_ratio: AspectRatio,
        inspector: FFprobeAdapter,
    ) -> MediaMetadata:
        try:
            output_metadata = inspector.inspect(output)
        except WorkerError as error:
            raise terminal(
                ErrorCode.INVALID_OUTPUT,
                "Rendered video could not be inspected.",
                diagnostic=error.diagnostic or f"{error.code.value}: {error.message}",
            ) from error
        validate_output(
            output_metadata,
            aspect_ratio,
            expected_duration_ms=source_metadata.duration_ms,
            duration_tolerance_ms=math.ceil(1000 / float(source_metadata.frame_rate)),
            source_has_audio=source_metadata.has_audio,
        )
        actual_frame_count = self.decode(output)
        if actual_frame_count != source_metadata.expected_frame_count:
            raise terminal(
                ErrorCode.INVALID_OUTPUT,
                "Rendered video frame count is invalid.",
                diagnostic=(
                    f"expected_frame_count={source_metadata.expected_frame_count} "
                    f"actual_frame_count={actual_frame_count}"
                ),
            )
        return output_metadata

    def output_frame_progress(self, output: Path) -> OutputFrameProgress:
        """Return repeated decoded-output frame intervals without retaining frame content."""
        try:
            report = self.runner.run(
                [
                    self.binary,
                    "-v",
                    "error",
                    "-i",
                    str(output),
                    "-map",
                    "0:v:0",
                    "-f",
                    "framemd5",
                    "-",
                ]
            )
        except WorkerError as error:
            raise terminal(
                ErrorCode.INVALID_OUTPUT, "Rendered video frames could not be inspected."
            ) from error
        return _output_frame_progress(report)

    def temporal_frame_progress(
        self, source: Path, sample_size: tuple[int, int] = (192, 108)
    ) -> TemporalFrameProgress:
        """Return sustained, near-static decoded-frame intervals for debug diagnosis."""
        import cv2

        if sample_size[0] <= 0 or sample_size[1] <= 0:
            raise ValueError("temporal progress sample dimensions are invalid")
        capture = cv2.VideoCapture(str(source))
        if not capture.isOpened():
            capture.release()
            raise ValueError("video frames could not be decoded")
        previous = None
        differences: list[float] = []
        frame_count = 0
        try:
            while True:
                decoded, pixels = capture.read()
                if not decoded:
                    break
                current = cv2.resize(
                    cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY),
                    sample_size,
                    interpolation=cv2.INTER_AREA,
                )
                if previous is not None:
                    differences.append(float(cv2.absdiff(current, previous).mean()))
                previous = current
                frame_count += 1
        finally:
            capture.release()
        if not frame_count:
            raise ValueError("video has no decoded frames")
        return TemporalFrameProgress(
            frame_count, _near_static_intervals(differences, threshold=0.05, minimum_frames=15)
        )

    def crop_path_temporal_progress(
        self,
        source: Path,
        crop_path: Sequence[CropRect],
        metadata: MediaMetadata,
        aspect_ratio: AspectRatio,
        frame_reader: FrameReader,
    ) -> TemporalFrameProgress:
        """Return near-static intervals after applying the planned crop path to decoded input."""
        import cv2

        if len(crop_path) != expected_frame_count(metadata):
            raise ValueError("crop path does not cover the source video")
        sample_size = (192, 108) if aspect_ratio is AspectRatio.LANDSCAPE else (108, 192)
        previous = None
        differences: list[float] = []
        frame_count = 0
        frames = iter(frame_reader.read(source, metadata))
        try:
            for frame_count, (crop, frame) in enumerate(
                zip(crop_path, frames, strict=True), start=1
            ):
                index = frame_count - 1
                if (
                    frame.index != index
                    or frame.timestamp_ms != metadata.timestamp_for_frame(index)
                ):
                    raise ValueError("video frame alignment failed")
                cropped: Any = crop_and_resize_frame(frame.pixels, crop, sample_size)
                current = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
                if previous is not None:
                    differences.append(float(cv2.absdiff(current, previous).mean()))
                previous = current
        finally:
            close = getattr(frames, "close", None)
            if callable(close):
                close()
        if frame_count != len(crop_path):
            raise ValueError("video frame count is inconsistent")
        return TemporalFrameProgress(
            frame_count, _near_static_intervals(differences, threshold=0.05, minimum_frames=15)
        )


def _output_frame_progress(report: str) -> OutputFrameProgress:
    frame_hashes: list[str] = []
    for line in report.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split(",")
        if len(fields) != 6:
            raise ValueError("FFmpeg frame checksum report is invalid")
        frame_hashes.append(fields[-1].strip())
    intervals: list[tuple[int, int]] = []
    repeat_start: int | None = None
    for index in range(1, len(frame_hashes)):
        if frame_hashes[index] == frame_hashes[index - 1]:
            if repeat_start is None:
                repeat_start = index - 1
        elif repeat_start is not None:
            intervals.append((repeat_start, index - 1))
            repeat_start = None
    if repeat_start is not None:
        intervals.append((repeat_start, len(frame_hashes) - 1))
    return OutputFrameProgress(len(frame_hashes), tuple(intervals))


def _near_static_intervals(
    differences: Sequence[float], *, threshold: float, minimum_frames: int
) -> tuple[tuple[int, int], ...]:
    if threshold < 0 or minimum_frames < 2:
        raise ValueError("temporal progress thresholds are invalid")
    intervals: list[tuple[int, int]] = []
    start: int | None = None
    for index, difference in enumerate(differences, start=1):
        if difference <= threshold:
            if start is None:
                start = index - 1
        elif start is not None:
            if index - start >= minimum_frames:
                intervals.append((start, index - 1))
            start = None
    if start is not None and len(differences) + 1 - start >= minimum_frames:
        intervals.append((start, len(differences)))
    return tuple(intervals)




def validate_output(
    metadata: MediaMetadata,
    aspect_ratio: AspectRatio,
    *,
    expected_duration_ms: int | None = None,
    duration_tolerance_ms: int | None = None,
    source_has_audio: bool | None = None,
) -> None:
    expected_dimensions = output_dimensions(aspect_ratio)
    if (metadata.width, metadata.height) != expected_dimensions:
        raise terminal(
            ErrorCode.INVALID_OUTPUT,
            "Rendered video dimensions are invalid.",
            diagnostic=(
                f"expected_dimensions={expected_dimensions[0]}x{expected_dimensions[1]} "
                f"actual_dimensions={metadata.width}x{metadata.height}"
            ),
        )
    if metadata.video_codec != "h264":
        raise terminal(
            ErrorCode.INVALID_OUTPUT,
            "Rendered video codec is invalid.",
            diagnostic=f"expected_video_codec=h264 actual_video_codec={metadata.video_codec}",
        )
    if metadata.has_audio and metadata.audio_codec != "aac":
        raise terminal(
            ErrorCode.INVALID_OUTPUT,
            "Rendered audio codec is invalid.",
            diagnostic=f"expected_audio_codec=aac actual_audio_codec={metadata.audio_codec}",
        )
    if source_has_audio and not metadata.has_audio:
        raise terminal(
            ErrorCode.INVALID_OUTPUT,
            "Rendered video audio is missing.",
            diagnostic="source_has_audio=true output_has_audio=false",
        )
    if expected_duration_ms is not None:
        if duration_tolerance_ms is None or duration_tolerance_ms < 0:
            raise ValueError("duration tolerance must be non-negative")
        if abs(metadata.duration_ms - expected_duration_ms) > duration_tolerance_ms:
            raise terminal(
                ErrorCode.INVALID_OUTPUT,
                "Rendered video duration is invalid.",
                diagnostic=(
                    f"expected_duration_ms={expected_duration_ms} "
                    f"actual_duration_ms={metadata.duration_ms} "
                    f"tolerance_ms={duration_tolerance_ms}"
                ),
            )
