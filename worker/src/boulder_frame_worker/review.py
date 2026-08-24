"""Best-effort, scratch-local visual evidence for an analyzed job."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .media import MediaMetadata

PHASES = ("measurement", "pose", "tracking", "planning", "render")
_SKELETON = (
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
    (11, 23),
    (12, 24),
    (23, 24),
    (23, 25),
    (25, 27),
    (27, 29),
    (29, 31),
    (24, 26),
    (26, 28),
    (28, 30),
    (30, 32),
)


@dataclass(frozen=True, slots=True)
class ReviewLimits:
    max_duration_ms: int
    width: int
    height: int
    max_bytes: int
    timeout_seconds: int


class ReviewRenderer:
    """Renders bounded no-audio phase videos without affecting product rendering."""

    def __init__(self, ffmpeg_bin: str, limits: ReviewLimits) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.limits = limits

    def render(
        self,
        source: Path,
        output: Path,
        metadata: MediaMetadata,
        trace: Sequence[Mapping[str, object]],
        destination: Path,
    ) -> dict[str, dict[str, object]]:
        destination.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.limits.timeout_seconds
        phases: dict[str, dict[str, object]] = {}
        if metadata.duration_ms > self.limits.max_duration_ms:
            phases = {
                phase: {"status": "unavailable", "detail": "duration_limit"} for phase in PHASES
            }
        else:
            for phase in PHASES:
                try:
                    path = destination / f"{phase}.mp4"
                    self._render_phase(source, output, metadata, trace, path, phase, deadline)
                    if self._aggregate_size(destination) > self.limits.max_bytes:
                        path.unlink(missing_ok=True)
                        raise ValueError("aggregate_size_limit")
                    phases[phase] = {
                        "status": "ready",
                        "path": path.name,
                        "frame_count": len(trace),
                    }
                except Exception as error:
                    (destination / f"{phase}.mp4").unlink(missing_ok=True)
                    phases[phase] = {"status": "unavailable", "detail": _reason(error)}
        return phases

    def _render_phase(
        self,
        source: Path,
        output: Path,
        metadata: MediaMetadata,
        trace: Sequence[Mapping[str, object]],
        destination: Path,
        phase: str,
        deadline: float,
    ) -> None:
        status = destination.with_suffix(".status")
        raw = destination.with_suffix(".avi")
        status.unlink(missing_ok=True)
        process = _review_process(
            self.ffmpeg_bin,
            self.limits,
            source,
            output,
            metadata,
            trace,
            destination,
            phase,
            _remaining_seconds(deadline),
            status,
        )
        try:
            process.join(_remaining_seconds(deadline))
            if process.is_alive():
                raise _ReviewTimeout()
            _require_remaining(deadline)
            if process.exitcode != 0:
                raise ValueError("unavailable")
            try:
                outcome = status.read_text(encoding="ascii")
            except OSError as error:
                raise ValueError("unavailable") from error
            if outcome != "ready":
                raise ValueError(outcome)
        finally:
            status.unlink(missing_ok=True)
            raw.unlink(missing_ok=True)
            # _remaining_seconds can expire immediately after start, before join. Always reap a
            # live child here so its OpenCV/FFmpeg descendants cannot outlive the review deadline.
            if process.is_alive():
                _terminate_process(process)
            close = getattr(process, "close", None)
            if callable(close) and not process.is_alive():
                close()

    @staticmethod
    def _render_phase_in_process(
        ffmpeg_bin: str,
        limits: ReviewLimits,
        source: Path,
        output: Path,
        metadata: MediaMetadata,
        trace: Sequence[Mapping[str, object]],
        destination: Path,
        phase: str,
        timeout_seconds: float,
    ) -> None:
        import cv2
        import numpy as np

        from .frame_reader import OpenCVFrameReader

        source_frames = iter(OpenCVFrameReader().read(source, metadata))
        output_capture = cv2.VideoCapture(str(output)) if phase == "render" else None
        if output_capture is not None and not output_capture.isOpened():
            output_capture.release()
            raise ValueError("decode_unavailable")
        deadline = time.monotonic() + timeout_seconds
        raw = destination.with_suffix(".avi")
        writer = cv2.VideoWriter(
            str(raw),
            cv2.VideoWriter_fourcc(*"MJPG"),
            float(metadata.frame_rate),
            (limits.width, limits.height),
        )
        try:
            if not writer.isOpened():
                raise ValueError("encode_unavailable")
            for index, record in enumerate(trace):
                _require_remaining(deadline)
                try:
                    decoded = next(source_frames)
                except StopIteration as error:
                    raise ValueError("source_frame_alignment") from error
                if decoded.index != index or decoded.timestamp_ms != record.get("timestamp_ms"):
                    raise ValueError("source_frame_alignment")
                _require_remaining(deadline)
                pixels = decoded.pixels
                output_pixels = None
                if output_capture is not None:
                    decoded_output, output_pixels = output_capture.read()
                    if not decoded_output:
                        raise ValueError("output_frame_alignment")
                    _require_remaining(deadline)
                frame = ReviewRenderer._annotate(
                    cv2,
                    np,
                    pixels,
                    record,
                    phase,
                    index,
                    output_pixels,
                    trace[: index + 1],
                    (limits.width, limits.height),
                )
                _require_remaining(deadline)
                writer.write(_fit_and_pad(cv2, frame, limits.width, limits.height))
                _require_remaining(deadline)
            try:
                next(source_frames)
            except StopIteration:
                pass
            else:
                raise ValueError("source_frame_alignment")
        finally:
            writer.release()
            close = getattr(source_frames, "close", None)
            if callable(close):
                close()
            if output_capture is not None:
                output_capture.release()
        try:
            subprocess.run(
                [
                    ffmpeg_bin,
                    "-y",
                    "-i",
                    str(raw),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(destination),
                ],
                check=True,
                capture_output=True,
                timeout=_remaining_seconds(deadline),
            )
        finally:
            raw.unlink(missing_ok=True)

    @staticmethod
    def _annotate(
        cv2, np, pixels, record, phase, index, output_pixels, prior_records=(), render_size=None
    ):
        if phase == "render" and output_pixels is not None:
            width, height = render_size or (
                pixels.shape[1] * 2,
                max(pixels.shape[0], output_pixels.shape[0]),
            )
            pane_width = width // 2
            frame = np.zeros((height, width, 3), dtype=pixels.dtype)
            transform = _fit_transform(pixels.shape[1], pixels.shape[0], 0, 0, pane_width, height)
            output_transform = _fit_transform(
                output_pixels.shape[1],
                output_pixels.shape[0],
                pane_width,
                0,
                width - pane_width,
                height,
            )
            _place_image(cv2, frame, pixels, transform)
            _place_image(cv2, frame, output_pixels, output_transform)
        else:
            frame = pixels.copy()
            transform = _PaneTransform(
                pixels.shape[1], pixels.shape[0], 0, 0, pixels.shape[1], pixels.shape[0]
            )
        measurement = _mapping(record.get("measurement"))
        tracking = _mapping(record.get("tracking"))
        planning = _mapping(record.get("planning"))
        if phase == "measurement":
            detection = _mapping(measurement.get("detection"))
            _draw_rect(cv2, frame, detection.get("bounds"), (0, 220, 255), transform)
            _draw_point(
                cv2,
                frame,
                _mapping(measurement.get("selection")).get("marker"),
                (0, 0, 255),
                transform,
                8,
            )
        elif phase == "pose":
            pose = _mapping(measurement.get("pose"))
            _draw_rect(cv2, frame, pose.get("bounds"), (255, 0, 255), transform)
            _draw_skeleton(cv2, frame, pose.get("landmarks"), (255, 0, 255), transform)
            _draw_point(cv2, frame, pose.get("root"), (255, 0, 255), transform, 5)
        elif phase == "tracking":
            detection = _mapping(measurement.get("detection"))
            _draw_rect(cv2, frame, detection.get("bounds"), (0, 220, 255), transform)
            _draw_rect(cv2, frame, tracking.get("pose_bounds"), (0, 255, 0), transform)
            _draw_trail(cv2, frame, prior_records, transform)
            _draw_point(cv2, frame, tracking.get("root"), (0, 255, 0), transform, 5)
            _draw_covariance(
                cv2, frame, tracking.get("root"), tracking.get("covariance"), transform
            )
            if tracking.get("reacquired") is True:
                _draw_reacquisition(cv2, frame, tracking.get("root"), transform)
        elif phase == "planning":
            inputs = _mapping(planning.get("input"))
            _draw_rect(
                cv2,
                frame,
                inputs.get("bounds") or inputs.get("detector_bounds"),
                (0, 220, 255),
                transform,
            )
            decision = _mapping(planning.get("decision"))
            _draw_rect(cv2, frame, decision.get("envelope"), (255, 0, 255), transform)
            _draw_lead(cv2, frame, inputs.get("root"), decision.get("lead_room"), transform)
            _draw_rect(cv2, frame, planning.get("crop"), (255, 255, 0), transform)
        else:
            _draw_rect(
                cv2, frame, _mapping(record.get("render")).get("crop"), (255, 255, 0), transform
            )
        for line_index, text in enumerate(phase_annotations(record, phase, index)):
            cv2.putText(
                frame,
                text,
                (12, 28 + line_index * 26),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )
        return frame

    @staticmethod
    def _aggregate_size(destination: Path) -> int:
        return sum(path.stat().st_size for path in destination.glob("*.mp4"))


class _ReviewTimeout(Exception):
    pass


def _review_process(
    ffmpeg_bin: str,
    limits: ReviewLimits,
    source: Path,
    output: Path,
    metadata: MediaMetadata,
    trace: Sequence[Mapping[str, object]],
    destination: Path,
    phase: str,
    timeout_seconds: float,
    status: Path,
):
    from multiprocessing import get_context

    process = get_context("spawn").Process(
        target=_render_phase_process,
        args=(
            ffmpeg_bin,
            limits,
            source,
            output,
            metadata,
            trace,
            destination,
            phase,
            timeout_seconds,
            status,
        ),
    )
    process.start()
    return process


def _render_phase_process(
    ffmpeg_bin: str,
    limits: ReviewLimits,
    source: Path,
    output: Path,
    metadata: MediaMetadata,
    trace: Sequence[Mapping[str, object]],
    destination: Path,
    phase: str,
    timeout_seconds: float,
    status: Path,
) -> None:
    if os.name == "posix":
        os.setsid()
    try:
        ReviewRenderer._render_phase_in_process(
            ffmpeg_bin,
            limits,
            source,
            output,
            metadata,
            trace,
            destination,
            phase,
            timeout_seconds,
        )
    except Exception as error:
        status.write_text(_reason(error), encoding="ascii")
    else:
        status.write_text("ready", encoding="ascii")


def _terminate_process(process) -> None:
    if os.name == "posix" and process.pid is not None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    process.terminate()
    process.join(1)
    if process.is_alive():
        if os.name == "posix" and process.pid is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.kill()
        process.join()


def load_trace(path: Path, metadata: MediaMetadata) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open(encoding="ascii") as source:
        for index, line in enumerate(source):
            record = json.loads(line)
            if (
                not isinstance(record, dict)
                or record.get("record_type") != "frame"
                or record.get("frame_index") != index
                or record.get("timestamp_ms") != metadata.timestamp_for_frame(index)
            ):
                raise ValueError("analysis trace is not frame aligned")
            records.append(record)
    if len(records) != metadata.expected_frame_count:
        raise ValueError("analysis trace does not cover the source")
    return records


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class _PaneTransform:
    source_width: int
    source_height: int
    x: int
    y: int
    width: int
    height: int

    def point(self, raw: object) -> tuple[int, int] | None:
        point = _source_point(raw)
        if point is None:
            return None
        return (
            _clip(
                round(self.x + point[0] * self.width / self.source_width),
                self.x,
                self.x + self.width - 1,
            ),
            _clip(
                round(self.y + point[1] * self.height / self.source_height),
                self.y,
                self.y + self.height - 1,
            ),
        )

    def rect(self, raw: object) -> tuple[tuple[int, int], tuple[int, int]] | None:
        if not isinstance(raw, Mapping):
            return None
        try:
            left, top = float(raw["x"]), float(raw["y"])
            right, bottom = left + float(raw["width"]), top + float(raw["height"])
        except (KeyError, TypeError, ValueError):
            return None
        if right <= left or bottom <= top:
            return None
        first = self.point({"x": left, "y": top})
        last = self.point({"x": right, "y": bottom})
        return None if first is None or last is None else (first, last)


def _fit_transform(
    source_width: int,
    source_height: int,
    x: int,
    y: int,
    width: int,
    height: int,
) -> _PaneTransform:
    scale = min(width / source_width, height / source_height)
    fitted_width = round(source_width * scale)
    fitted_height = round(source_height * scale)
    return _PaneTransform(
        source_width,
        source_height,
        x + (width - fitted_width) // 2,
        y + (height - fitted_height) // 2,
        fitted_width,
        fitted_height,
    )


def _place_image(cv2, destination, pixels, transform: _PaneTransform) -> None:
    resized = cv2.resize(pixels, (transform.width, transform.height))
    destination[
        transform.y : transform.y + transform.height,
        transform.x : transform.x + transform.width,
    ] = resized


def _fit_and_pad(cv2, pixels, width: int, height: int):
    frame = pixels * 0
    transform = _fit_transform(pixels.shape[1], pixels.shape[0], 0, 0, width, height)
    _place_image(cv2, frame, pixels, transform)
    return frame


def _draw_rect(cv2, image, raw, color, transform: _PaneTransform) -> None:
    rect = transform.rect(raw)
    if rect is not None:
        cv2.rectangle(image, *rect, color, 2)


def _draw_point(cv2, image, raw, color, transform: _PaneTransform, radius: int) -> None:
    point = transform.point(raw)
    if point is not None:
        cv2.circle(image, point, radius, color, -1)


def _draw_skeleton(cv2, image, raw, color, transform: _PaneTransform) -> None:
    if not isinstance(raw, Sequence):
        return
    points = [transform.point(point) for point in raw]
    for first, second in _SKELETON:
        if first < len(points) and second < len(points) and points[first] and points[second]:
            cv2.line(image, points[first], points[second], color, 2)
    for point in points:
        if point is not None:
            cv2.circle(image, point, 3, color, -1)


def _draw_trail(cv2, image, records, transform: _PaneTransform) -> None:
    points = [
        transform.point(_mapping(_mapping(item.get("tracking")).get("root")))
        for item in records[-60:]
        if isinstance(item, Mapping)
    ]
    for first, second in zip(points, points[1:], strict=False):
        if first is not None and second is not None:
            cv2.line(image, first, second, (0, 180, 0), 2)


def _draw_covariance(cv2, image, root, covariance, transform: _PaneTransform) -> None:
    point = transform.point(root)
    try:
        radius = float(covariance) ** 0.5 * transform.width / transform.source_width
    except (TypeError, ValueError):
        return
    if point is not None and radius > 0:
        cv2.circle(image, point, max(1, round(radius)), (0, 180, 0), 1)


def _draw_reacquisition(cv2, image, root, transform: _PaneTransform) -> None:
    point = transform.point(root)
    if point is not None:
        cv2.drawMarker(image, point, (0, 0, 255), cv2.MARKER_CROSS, 16, 2)


def _draw_lead(cv2, image, root, lead, transform: _PaneTransform) -> None:
    root_point = _source_point(root)
    lead_point = _source_point(lead)
    if root_point is None or lead_point is None:
        return
    start = transform.point({"x": root_point[0], "y": root_point[1]})
    end = transform.point({"x": root_point[0] + lead_point[0], "y": root_point[1] + lead_point[1]})
    if start is not None and end is not None:
        cv2.arrowedLine(image, start, end, (255, 128, 0), 2, tipLength=0.25)


def _source_point(raw: object) -> tuple[float, float] | None:
    if not isinstance(raw, Mapping):
        return None
    try:
        return float(raw["x"]), float(raw["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _clip(value: int, lower: int, upper: int) -> int:
    return min(max(value, lower), upper)


def _reason(error: Exception) -> str:
    if isinstance(error, (subprocess.TimeoutExpired, _ReviewTimeout)):
        return "timeout"
    if isinstance(error, subprocess.CalledProcessError):
        return "encode_failed"
    reason = str(error)
    return (
        reason
        if reason
        in {
            "aggregate_size_limit",
            "decode_unavailable",
            "encode_unavailable",
            "output_frame_alignment",
            "source_frame_alignment",
        }
        else "unavailable"
    )


def phase_annotations(record: Mapping[str, object], phase: str, index: int) -> tuple[str, ...]:
    """Expose only values recorded in the aligned trace for visual inspection."""
    timestamp = record.get("timestamp_ms", 0)
    measurement = _mapping(record.get("measurement"))
    tracking = _mapping(record.get("tracking"))
    planning = _mapping(record.get("planning"))
    lines = [f"{phase} frame={index} t={timestamp}ms"]
    if phase == "measurement":
        detection = _mapping(measurement.get("detection"))
        selection = _mapping(measurement.get("selection"))
        lines.append(
            f"selection={selection.get('state', 'unavailable')} confidence="
            f"{detection.get('confidence', 'unavailable')}"
        )
    elif phase == "pose":
        pose = _mapping(measurement.get("pose"))
        landmarks = pose.get("landmarks")
        lines.append(
            f"pose confidence={pose.get('confidence', 'unavailable')} landmarks="
            f"{len(landmarks) if isinstance(landmarks, Sequence) else 0}"
        )
    elif phase == "tracking":
        lines.append(
            f"state={tracking.get('state', 'unavailable')} confidence="
            f"{tracking.get('confidence', 'unavailable')} reacquired="
            f"{tracking.get('reacquired', False)}"
        )
    elif phase == "planning":
        decision = _mapping(planning.get("decision"))
        lines.append(
            f"containment_risk={decision.get('containment_risk', False)} zoom_action="
            f"{decision.get('zoom_action', 'unavailable')}"
        )
        lines.append(f"uncertainty_padding={decision.get('uncertainty_padding', 'unavailable')}")
    else:
        render = _mapping(record.get("render"))
        lines.append(
            f"mapping_verified={render.get('mapping_independently_verified', False)} output_valid="
            f"{render.get('output_validated', False)}"
        )
    return tuple(lines)


def _remaining_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise subprocess.TimeoutExpired("review", 0)
    return remaining


def _require_remaining(deadline: float) -> None:
    _remaining_seconds(deadline)
