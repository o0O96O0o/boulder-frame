from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

from .config import DEFAULT_NORMALIZATION_MAX_SOURCE_BYTES
from .debug import (
    DebugBundleWriter,
    append_debug_record,
    debug_bundle_header,
    serialize_crop_rect,
    serialize_frame_measurement,
    serialize_raw_frame_observation,
    serialize_tracked_measurement,
)
from .errors import ErrorCode, WorkerError, terminal
from .measurement import (
    PersonDetector,
    PoseEstimator,
    RawFrameObservation,
    TargetFrameAnalyzer,
    UnavailableDetector,
    UnavailablePoseEstimator,
)
from .media import (
    CFRNormalizer,
    FFmpegCFRNormalizer,
    FFmpegRenderer,
    FFprobeAdapter,
    MediaMetadata,
    expected_frame_count,
    output_dimensions,
    validate_output,
)
from .planner import CropPlanner, CropRect, DeterministicCropPlanner, FrameMeasurement
from .protocol import AspectRatio, FramingProfile, OutputSettings, TargetSelection
from .repository import DebugAsset, OutputAsset, debug_storage_key, output_storage_key
from .state import JobConfiguration, JobRecord, SourceAsset
from .storage import S3Storage
from .tracking import SingleTargetTracker, TargetTracker, TrackedMeasurement, TrackingState


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    """One display-rotation-normalized decoded source frame for target analysis."""

    index: int
    timestamp_ms: int
    pixels: object


class FrameReader(Protocol):
    def read(self, source: Path, metadata: MediaMetadata) -> Iterable[DecodedFrame]: ...


class OutputFinalizer(Protocol):
    def finalize_output(self, record: JobRecord, output: OutputAsset) -> object: ...


class UnavailableFrameReader:
    """Safe default until a licensed, configured decode/model adapter is injected."""

    def read(self, source: Path, metadata: MediaMetadata) -> Iterable[DecodedFrame]:
        del source, metadata
        raise terminal(
            ErrorCode.MODEL_UNAVAILABLE,
            "Video analysis models are not configured for this worker.",
        )


PlannerFactory = Callable[[int, int, AspectRatio, FramingProfile], CropPlanner]
_ANALYSIS_TRACE = "debug-analysis.jsonl"
_STAGE_TRACE = "debug-stages.jsonl"


@dataclass(frozen=True, slots=True)
class _Inputs:
    source: Path
    output: Path
    metadata: MediaMetadata
    selection: TargetSelection
    output_settings: OutputSettings


class ProcessingPipeline:
    """Concrete, restart-safe four-stage orchestration for one immutable job snapshot."""

    def __init__(
        self,
        storage: S3Storage,
        finalizer: OutputFinalizer,
        *,
        inspector: FFprobeAdapter,
        renderer: FFmpegRenderer,
        normalizer: CFRNormalizer | None = None,
        frame_reader: FrameReader | None = None,
        detector: PersonDetector | None = None,
        pose_estimator: PoseEstimator | None = None,
        tracker: TargetTracker | None = None,
        planner_factory: PlannerFactory = DeterministicCropPlanner,
        debug_capture: bool = False,
        debug_max_frames: int = 10_000,
        debug_max_bytes: int = 50 * 1024 * 1024,
        normalization_max_source_bytes: int = DEFAULT_NORMALIZATION_MAX_SOURCE_BYTES,
    ) -> None:
        self.storage = storage
        self.finalizer = finalizer
        self.inspector = inspector
        self.renderer = renderer
        self.normalizer = normalizer or FFmpegCFRNormalizer()
        self.frame_reader = frame_reader or UnavailableFrameReader()
        self.analyzer = TargetFrameAnalyzer(
            detector or UnavailableDetector(), pose_estimator or UnavailablePoseEstimator()
        )
        self.tracker = tracker or SingleTargetTracker()
        self.planner_factory = planner_factory
        self.debug_capture = debug_capture
        self.debug_max_frames = debug_max_frames
        self.debug_max_bytes = debug_max_bytes
        self.normalization_max_source_bytes = normalization_max_source_bytes

    def validating(self, record: JobRecord, scratch: Path) -> None:
        self._inputs(record, scratch)

    def analyzing(self, record: JobRecord, scratch: Path) -> None:
        inputs = self._inputs(record, scratch)
        self._crop_path(inputs)

    def rendering(self, record: JobRecord, scratch: Path) -> None:
        inputs = self._inputs(record, scratch)
        self._render(inputs)

    def uploading(self, record: JobRecord, scratch: Path) -> None:
        inputs = self._inputs(record, scratch)
        output_metadata = self._render(inputs)
        storage_key = output_storage_key(self._source(record).project_id, record.id)
        stored = self.storage.upload(storage_key, inputs.output, "video/mp4")
        if (
            stored.key != storage_key
            or stored.size_bytes != inputs.output.stat().st_size
            or stored.content_type != "video/mp4"
        ):
            raise terminal(ErrorCode.INVALID_OUTPUT, "Rendered video upload could not be verified.")
        self.finalizer.finalize_output(
            record,
            OutputAsset(
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
                width=output_metadata.width,
                height=output_metadata.height,
                frame_rate=float(output_metadata.frame_rate),
                duration_ms=output_metadata.duration_ms,
            ),
        )

    def publish_debug(self, record: JobRecord, scratch: Path) -> None:
        """Publish optional sanitized telemetry after all stage timing records are complete."""
        if not self.debug_capture:
            return
        source_asset = self._source(record)
        configuration = self._configuration(record)
        try:
            inputs = self._inputs(record, scratch)
        except Exception:
            # Validation failures still need their sanitized stage trace for diagnosis.
            inputs = None
        bundle = scratch / "debug.jsonl.gz"
        source_metadata: dict[str, object] = {"source_id": str(source_asset.id)}
        if inputs is not None:
            source_metadata.update(
                {
                    "sha256": _sha256(inputs.source),
                    "display_width": inputs.metadata.display_dimensions[0],
                    "display_height": inputs.metadata.display_dimensions[1],
                    "frame_rate": float(inputs.metadata.frame_rate),
                    "variable_frame_rate": False,
                }
            )
        planner_config = dict(configuration.planner)
        planner_config.setdefault("planner_version", "deterministic-v1")
        if inputs is not None:
            planner_config.setdefault("profile", inputs.output_settings.profile.value)
            planner_config.setdefault("aspect_ratio", inputs.output_settings.aspect_ratio.value)
        with DebugBundleWriter(
            bundle,
            debug_bundle_header(
                job_id=record.id,
                source_metadata=source_metadata,
                pipeline_version=configuration.pipeline_version,
                model_version=configuration.model_version,
                planner_config=planner_config,
                model_manifest={"model_version": configuration.model_version},
                source_checksum=(
                    source_metadata["sha256"] if "sha256" in source_metadata else None
                ),
            ),
            max_frames=self.debug_max_frames,
            max_bytes=self.debug_max_bytes,
        ) as writer:
            self._copy_trace(writer, scratch / _STAGE_TRACE)
            self._copy_trace(writer, scratch / _ANALYSIS_TRACE)
            if inputs is not None:
                output_width, output_height = output_dimensions(inputs.output_settings.aspect_ratio)
                writer.write(
                    "render_summary",
                    {
                        "output": {
                            "width": output_width,
                            "height": output_height,
                        }
                    },
                )
        storage_key = debug_storage_key(source_asset.project_id, record.id, uuid4())
        try:
            stored = self.storage.upload(storage_key, bundle, "application/gzip")
            if (
                stored.key != storage_key
                or stored.size_bytes != bundle.stat().st_size
                or stored.content_type != "application/gzip"
            ):
                raise terminal(
                    ErrorCode.INVALID_OUTPUT, "Debug telemetry upload could not be verified."
                )
            finalizer = getattr(self.finalizer, "finalize_debug", None)
            if not callable(finalizer):
                raise terminal(ErrorCode.INTERNAL, "Debug telemetry finalization is unavailable.")
            finalizer(record, storage_key, DebugAsset(stored.size_bytes, stored.content_type))
        except Exception:
            try:
                self.storage.delete(storage_key)
            except Exception:
                pass
            raise

    def _inputs(self, record: JobRecord, scratch: Path) -> _Inputs:
        source_asset = self._source(record)
        configuration = self._configuration(record)
        if source_asset.upload_state != "uploaded":
            raise terminal(ErrorCode.INVALID_MEDIA, "The source video upload is not available.")
        if configuration.source_asset_id != source_asset.id:
            raise terminal(
                ErrorCode.INVALID_MEDIA, "The job source video does not match its configuration."
            )
        selection = _selection(configuration)
        output_settings = _output_settings(configuration)
        source = scratch / "source-original"
        if not source.exists():
            self.storage.download(source_asset.storage_key, source)
        try:
            metadata = self.inspector.inspect(source)
        except WorkerError as error:
            if error.code is not ErrorCode.VARIABLE_FRAME_RATE:
                raise
            source_metadata = self.inspector.inspect(source, allow_variable_frame_rate=True)
            if source_asset.size_bytes > self.normalization_max_source_bytes:
                raise terminal(
                    ErrorCode.INVALID_MEDIA,
                    "This variable-frame-rate video is too large to normalize.",
                ) from error
            normalized_source = scratch / "source-cfr.mp4"
            if not normalized_source.exists():
                self.normalizer.normalize(
                    source,
                    normalized_source,
                    source_metadata.frame_rate,
                    source_metadata.audio_stream_index,
                )
            source = normalized_source
            metadata = self.inspector.inspect(source)
        metadata.frame_for_time_ms(selection.frame_time_ms)
        return _Inputs(source, scratch / "output.mp4", metadata, selection, output_settings)

    def _crop_path(self, inputs: _Inputs) -> list[CropRect]:
        expected = expected_frame_count(inputs.metadata)
        width, height = inputs.metadata.display_dimensions
        selected_index = inputs.metadata.frame_for_time_ms(inputs.selection.frame_time_ms)
        normalized_x, normalized_y = inputs.selection.normalized_x, inputs.selection.normalized_y
        observations = []
        frames = iter(self.frame_reader.read(inputs.source, inputs.metadata))
        try:
            for index, frame in enumerate(frames):
                if (
                    index >= expected
                    or frame.index != index
                    or frame.timestamp_ms != inputs.metadata.timestamp_for_frame(index)
                ):
                    raise terminal(
                        ErrorCode.INVALID_MEDIA, "Video frames could not be analyzed consistently."
                    )
                if frame.index == selected_index:
                    observation = self.analyzer.observe_selected(
                        frame.pixels,
                        frame_index=frame.index,
                        timestamp_ms=frame.timestamp_ms,
                        normalized_x=normalized_x,
                        normalized_y=normalized_y,
                        source_width=width,
                        source_height=height,
                    )
                else:
                    observation = self.analyzer.observe(
                        frame.pixels,
                        frame_index=frame.index,
                        timestamp_ms=frame.timestamp_ms,
                        normalized_x=normalized_x,
                        normalized_y=normalized_y,
                        source_width=width,
                        source_height=height,
                    )
                if observation.root is not None:
                    root = observation.root
                    normalized_x, normalized_y = root.x / width, root.y / height
                observations.append(observation)
                del frame
        finally:
            close = getattr(frames, "close", None)
            if callable(close):
                close()
        if len(observations) != expected:
            raise terminal(
                ErrorCode.INVALID_MEDIA, "Video frames could not be analyzed consistently."
            )
        tracked = self.tracker.track(observations)
        planner_measurements = _planner_measurements(tracked)
        crops = self.planner_factory(
            width, height, inputs.output_settings.aspect_ratio, inputs.output_settings.profile
        ).plan(planner_measurements)
        if self.debug_capture:
            try:
                self._write_analysis_trace(
                    inputs.source.parent / _ANALYSIS_TRACE,
                    observations,
                    tracked,
                    planner_measurements,
                    crops,
                )
            except OSError:
                # Debug capture is optional and must not fail media processing.
                pass
        return crops

    def _render(self, inputs: _Inputs) -> MediaMetadata:
        if inputs.output.exists():
            metadata = self.inspector.inspect(inputs.output)
            validate_output(
                metadata,
                inputs.output_settings.aspect_ratio,
                expected_duration_ms=inputs.metadata.duration_ms,
                duration_tolerance_ms=round(1000 / float(inputs.metadata.frame_rate)),
                source_has_audio=inputs.metadata.has_audio,
            )
            return metadata
        return self.renderer.render_crop_path(
            inputs.source,
            inputs.output,
            self._crop_path(inputs),
            inputs.metadata,
            inputs.output_settings.aspect_ratio,
            self.inspector,
        )

    @staticmethod
    def _write_analysis_trace(
        path: Path,
        observations: Sequence[RawFrameObservation],
        tracked: Sequence[TrackedMeasurement],
        measurements: Sequence[FrameMeasurement],
        crops: Sequence[CropRect],
    ) -> None:
        if not (len(observations) == len(tracked) == len(measurements) == len(crops)):
            raise ValueError("debug analysis records must have matching frame counts")
        path.unlink(missing_ok=True)
        for observation, tracked_measurement, measurement, crop in zip(
            observations, tracked, measurements, crops, strict=True
        ):
            append_debug_record(
                path,
                "frame",
                {
                    "frame_index": observation.frame_index,
                    "timestamp_ms": observation.timestamp_ms,
                    "measurement": {
                        **serialize_raw_frame_observation(observation),
                        "selection": None
                        if observation.detection is None
                        else {"selected": True},
                    },
                    "tracking": serialize_tracked_measurement(tracked_measurement),
                    "planning": {
                        "input": serialize_frame_measurement(measurement),
                        "crop": serialize_crop_rect(crop),
                    },
                    "render": {
                        "crop": serialize_crop_rect(crop),
                        "timestamp_ms": observation.timestamp_ms,
                        "mapping_independently_verified": False,
                    },
                },
            )

    @staticmethod
    def _copy_trace(writer: DebugBundleWriter, path: Path) -> None:
        if not path.is_file():
            return
        with path.open(encoding="ascii") as trace:
            for line in trace:
                if not line.strip():
                    continue
                record = json.loads(line)
                record_type = record.pop("record_type", None)
                record.pop("schema_version", None)
                if isinstance(record_type, str):
                    writer.write(record_type, record)

    @staticmethod
    def _source(record: JobRecord) -> SourceAsset:
        if record.source_asset is None:
            raise terminal(ErrorCode.INVALID_MEDIA, "The job source video is unavailable.")
        return record.source_asset

    @staticmethod
    def _configuration(record: JobRecord) -> JobConfiguration:
        if record.configuration is None:
            raise terminal(ErrorCode.INVALID_TASK, "The job configuration is unavailable.")
        return record.configuration


def _selection(configuration: JobConfiguration) -> TargetSelection:
    try:
        return TargetSelection(
            frame_time_ms=int(configuration.target_selection["frame_time_ms"]),
            normalized_x=float(configuration.target_selection["normalized_x"]),
            normalized_y=float(configuration.target_selection["normalized_y"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise terminal(
            ErrorCode.INVALID_TARGET_SELECTION, "Target selection is invalid."
        ) from error


def _output_settings(configuration: JobConfiguration) -> OutputSettings:
    try:
        return OutputSettings(
            aspect_ratio=AspectRatio(str(configuration.output["aspect_ratio"])),
            profile=FramingProfile(str(configuration.output["profile"])),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise terminal(
            ErrorCode.INVALID_OUTPUT, "Requested output settings are invalid."
        ) from error


def _planner_measurements(tracked: Sequence[TrackedMeasurement]) -> list[FrameMeasurement]:
    result: list[FrameMeasurement] = []
    prior_root = None
    prior_timestamp = None
    for measurement in tracked:
        velocity = _velocity(prior_root, prior_timestamp, measurement)
        result.append(
            FrameMeasurement(
                root=measurement.root,
                bounds=measurement.pose_bounds,
                detector_bounds=measurement.detector_bounds,
                confidence=measurement.confidence,
                covariance=measurement.covariance,
                velocity=velocity,
                lost=measurement.state is TrackingState.LOST,
            )
        )
        if measurement.root is not None:
            prior_root, prior_timestamp = measurement.root, measurement.timestamp_ms
    return result


def _velocity(prior_root: object, prior_timestamp: int | None, measurement: TrackedMeasurement):
    from .measurement import Point

    if prior_root is None or prior_timestamp is None or measurement.root is None:
        return Point(0, 0)
    elapsed = (measurement.timestamp_ms - prior_timestamp) / 1000
    if elapsed <= 0:
        return Point(0, 0)
    root = cast(Point, prior_root)
    return Point((measurement.root.x - root.x) / elapsed, (measurement.root.y - root.y) / elapsed)


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()
