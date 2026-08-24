from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID, uuid4

from .config import DEFAULT_NORMALIZATION_MAX_SOURCE_BYTES
from .debug import (
    DebugBundleWriter,
    append_debug_record,
    debug_bundle_header,
    serialize_crop_rect,
    serialize_frame_measurement,
    serialize_planner_trace,
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
from .planner import (
    CropPlan,
    CropPlanner,
    CropRect,
    DeterministicCropPlanner,
    FrameMeasurement,
    PlannerFrameTrace,
)
from .protocol import AspectRatio, FramingProfile, OutputSettings, TargetSelection
from .repository import OutputAsset, ReviewArtifact, output_storage_key, review_storage_key
from .review import PHASES, ReviewRenderer
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

    def finalize_review(
        self, record: JobRecord, review_id: UUID, artifacts: tuple[ReviewArtifact, ...]
    ) -> object: ...


class UnavailableFrameReader:
    """Safe default until a licensed, configured decode/model adapter is injected."""

    def read(self, source: Path, metadata: MediaMetadata) -> Iterable[DecodedFrame]:
        del source, metadata
        raise terminal(
            ErrorCode.MODEL_UNAVAILABLE,
            "Video analysis models are not configured for this worker.",
        )


PlannerFactory = Callable[[int, int, AspectRatio, FramingProfile], CropPlanner]
_ANALYSIS_TRACE = "analysis-trace.jsonl"
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
        review_renderer: ReviewRenderer | None = None,
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
        self.review_renderer = review_renderer
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
        review_directory = scratch / "review"
        review_phases: dict[str, dict[str, object]] = {}
        review_trace: list[dict[str, object]] = []
        if inputs is not None and self.review_renderer is not None:
            try:
                review_trace = _load_analysis_records(scratch / _ANALYSIS_TRACE, inputs.metadata)
                review_phases = self.review_renderer.render(
                    inputs.source,
                    inputs.output,
                    inputs.metadata,
                    review_trace,
                    review_directory,
                )
            except Exception:
                # Review media is optional; telemetry remains available for every job.
                pass
        review_id = uuid4()
        manifest = self._write_review_manifest(
            review_directory,
            review_id,
            review_trace,
            review_phases,
            configuration.pipeline_version,
            configuration.model_version,
            inputs.metadata if inputs is not None else None,
        )
        uploaded: list[str] = []
        try:
            artifacts = [
                self._upload_review_artifact(
                    "debug_telemetry",
                    bundle,
                    source_asset.project_id,
                    record.id,
                    review_id,
                    "telemetry.jsonl.gz",
                    "application/gzip",
                    uploaded,
                ),
                self._upload_review_artifact(
                    "debug_manifest",
                    manifest,
                    source_asset.project_id,
                    record.id,
                    review_id,
                    "manifest.json",
                    "application/json",
                    uploaded,
                ),
            ]
            for phase in PHASES:
                path = review_directory / f"{phase}.mp4"
                if review_phases.get(phase, {}).get("status") == "ready" and path.is_file():
                    artifacts.append(
                        self._upload_review_artifact(
                            f"debug_{phase}",
                            path,
                            source_asset.project_id,
                            record.id,
                            review_id,
                            path.name,
                            "video/mp4",
                            uploaded,
                        )
                    )
            self.finalizer.finalize_review(record, review_id, tuple(artifacts))
        except Exception:
            for storage_key in uploaded:
                try:
                    self.storage.delete(storage_key)
                except Exception:
                    pass
            raise

    def _upload_review_artifact(
        self,
        role: str,
        path: Path,
        project_id: UUID,
        job_id: UUID,
        review_id: UUID,
        name: str,
        content_type: str,
        uploaded: list[str],
    ) -> ReviewArtifact:
        storage_key = review_storage_key(project_id, job_id, review_id, name)
        # S3 upload includes a subsequent head request. Register the deterministic key first so a
        # successful put followed by a failed head is still cleaned up with this review run.
        uploaded.append(storage_key)
        stored = self.storage.upload(storage_key, path, content_type)
        if (
            stored.key != storage_key
            or stored.size_bytes != path.stat().st_size
            or stored.content_type != content_type
        ):
            raise terminal(ErrorCode.INVALID_OUTPUT, "Debug review upload could not be verified.")
        return ReviewArtifact(role, storage_key, stored.size_bytes, content_type)

    @staticmethod
    def _write_review_manifest(
        destination: Path,
        review_id: UUID,
        trace: Sequence[Mapping[str, object]],
        visual_phases: Mapping[str, Mapping[str, object]],
        pipeline_version: str = "unavailable",
        model_version: str = "unavailable",
        metadata: MediaMetadata | None = None,
    ) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        shared_summary = _review_metadata(
            pipeline_version,
            model_version,
            metadata,
            len(trace),
        )
        phases = []
        for phase in PHASES:
            visual = visual_phases.get(phase, {})
            phases.append(
                {
                    "id": phase,
                    "status": (
                        visual.get("status") if visual.get("status") == "ready" else "unavailable"
                    ),
                    **(
                        {}
                        if visual.get("status") == "ready"
                        else {"detail": _review_unavailable_detail(visual.get("detail"))}
                    ),
                    "summary": {**shared_summary, **_review_summary(trace, phase)},
                    "warning_intervals": _review_warning_intervals(trace, phase),
                }
            )
        path = destination / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "review_id": str(review_id),
                    "telemetry": {"status": "ready"},
                    "phases": phases,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="ascii",
        )
        return path

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
        trace_path = inputs.source.parent / _ANALYSIS_TRACE
        if trace_path.is_file():
            return _load_crop_path(trace_path, inputs.metadata)
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
        plan = self.planner_factory(
            width, height, inputs.output_settings.aspect_ratio, inputs.output_settings.profile
        ).plan(planner_measurements)
        self._write_analysis_trace(
            trace_path,
            observations,
            tracked,
            planner_measurements,
            plan,
            inputs.selection,
            width,
            height,
        )
        return list(plan)

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
            self._mark_render_validated(inputs.source.parent / _ANALYSIS_TRACE)
            return metadata
        rendered = self.renderer.render_crop_path(
            inputs.source,
            inputs.output,
            self._crop_path(inputs),
            inputs.metadata,
            inputs.output_settings.aspect_ratio,
            self.inspector,
        )
        self._mark_render_validated(inputs.source.parent / _ANALYSIS_TRACE)
        return rendered

    @staticmethod
    def _write_analysis_trace(
        path: Path,
        observations: Sequence[RawFrameObservation],
        tracked: Sequence[TrackedMeasurement],
        measurements: Sequence[FrameMeasurement],
        plan: CropPlan | Sequence[CropRect],
        selection: TargetSelection | None = None,
        source_width: int | None = None,
        source_height: int | None = None,
    ) -> None:
        crops = plan.crops if isinstance(plan, CropPlan) else tuple(plan)
        trace = plan.trace if isinstance(plan, CropPlan) else (None,) * len(crops)
        if not (len(observations) == len(tracked) == len(measurements) == len(crops) == len(trace)):
            raise ValueError("debug analysis records must have matching frame counts")
        path.unlink(missing_ok=True)
        for observation, tracked_measurement, measurement, crop, planner_trace in zip(
            observations, tracked, measurements, crops, trace, strict=True
        ):
            append_debug_record(
                path,
                "frame",
                {
                    "frame_index": observation.frame_index,
                    "timestamp_ms": observation.timestamp_ms,
                    "measurement": {
                        **serialize_raw_frame_observation(observation),
                        "selection": _selection_trace(
                            observation,
                            tracked_measurement,
                            selection,
                            source_width,
                            source_height,
                        ),
                    },
                    "tracking": serialize_tracked_measurement(tracked_measurement),
                    "planning": {
                        "input": serialize_frame_measurement(measurement),
                        "crop": serialize_crop_rect(crop),
                        **_planner_decision(planner_trace),
                    },
                    "render": {
                        "crop": serialize_crop_rect(crop),
                        "timestamp_ms": observation.timestamp_ms,
                        "mapping_independently_verified": False,
                        "output_validated": False,
                    },
                },
            )

    @staticmethod
    def _mark_render_validated(path: Path) -> None:
        if not path.is_file():
            return
        try:
            records = []
            with path.open(encoding="ascii") as trace:
                for line in trace:
                    record = json.loads(line)
                    if isinstance(record, dict) and isinstance(record.get("render"), dict):
                        record["render"]["output_validated"] = True
                    records.append(record)
            with path.open("w", encoding="ascii") as trace:
                for record in records:
                    trace.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        except Exception:
            # A diagnostic trace must never invalidate an already validated product output.
            return

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


def _load_analysis_records(path: Path, metadata: MediaMetadata) -> list[dict[str, object]]:
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
                raise terminal(ErrorCode.INVALID_MEDIA, "Video analysis trace is inconsistent.")
            records.append(record)
    if len(records) != expected_frame_count(metadata):
        raise terminal(ErrorCode.INVALID_MEDIA, "Video analysis trace is incomplete.")
    return records


def _load_crop_path(path: Path, metadata: MediaMetadata) -> list[CropRect]:
    crops: list[CropRect] = []
    for record in _load_analysis_records(path, metadata):
        try:
            planning = record["planning"]
            crop = planning["crop"]  # type: ignore[index]
            if not isinstance(crop, dict):
                raise TypeError
            crops.append(
                CropRect(
                    float(crop["x"]),
                    float(crop["y"]),
                    float(crop["width"]),
                    float(crop["height"]),
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            raise terminal(
                ErrorCode.INVALID_MEDIA, "Video analysis trace is inconsistent."
            ) from error
    return crops


def _planner_decision(trace: PlannerFrameTrace | None) -> dict[str, object]:
    return {} if trace is None else {"decision": serialize_planner_trace(trace)}


def _selection_trace(
    observation: RawFrameObservation,
    tracked: TrackedMeasurement,
    selection: TargetSelection | None,
    source_width: int | None,
    source_height: int | None,
) -> dict[str, object]:
    if observation.detection is None:
        return {"selected": False, "state": "unavailable"}
    outcome = str(observation.selection_outcome or "")
    state = (
        "tap_match"
        if outcome.startswith("selected_")
        else ("reacquired" if tracked.reacquired else "continued")
    )
    result: dict[str, object] = {"selected": True, "state": state}
    if state == "tap_match" and selection is not None and source_width and source_height:
        result["marker"] = {
            "x": selection.normalized_x * source_width,
            "y": selection.normalized_y * source_height,
        }
    return result


def _review_unavailable_detail(value: object) -> str:
    if not isinstance(value, str):
        return "unavailable"
    safe = " ".join(value.split())
    return safe[:80] or "unavailable"


def _review_metadata(
    pipeline_version: str,
    model_version: str,
    metadata: MediaMetadata | None,
    frame_count: int,
) -> dict[str, object]:
    result: dict[str, object] = {
        "pipeline_version": _safe_manifest_version(pipeline_version),
        "model_version": _safe_manifest_version(model_version),
        "trace_frame_count": frame_count,
    }
    if metadata is not None:
        result.update(
            {
                "source_duration_ms": metadata.duration_ms,
                "source_frame_rate": float(metadata.frame_rate),
            }
        )
    return result


def _safe_manifest_version(value: str) -> str:
    bounded = value[:120]
    return bounded if re.fullmatch(r"[A-Za-z0-9._-]+", bounded) else "unavailable"


def _review_summary(trace: Sequence[Mapping[str, object]], phase: str) -> dict[str, object]:
    if phase == "measurement":
        detected = sum(
            _mapping(_mapping(record.get("measurement")).get("detection")).get("bounds") is not None
            for record in trace
        )
        return {"frames": len(trace), "detected_frames": detected}
    if phase == "pose":
        posed = sum(
            _mapping(_mapping(record.get("measurement")).get("pose")).get("root") is not None
            for record in trace
        )
        return {"frames": len(trace), "pose_root_frames": posed}
    if phase == "tracking":
        reacquired = sum(
            bool(_mapping(record.get("tracking")).get("reacquired")) for record in trace
        )
        lost = sum(_mapping(record.get("tracking")).get("state") == "lost" for record in trace)
        return {"frames": len(trace), "lost_frames": lost, "reacquisitions": reacquired}
    if phase == "planning":
        risks = sum(
            bool(_mapping(_mapping(record.get("planning")).get("decision")).get("containment_risk"))
            for record in trace
        )
        return {"frames": len(trace), "containment_risk_frames": risks}
    verified = sum(
        bool(_mapping(record.get("render")).get("mapping_independently_verified"))
        for record in trace
    )
    return {"frames": len(trace), "mapping_verified_frames": verified}


def _review_warning_intervals(
    trace: Sequence[Mapping[str, object]], phase: str
) -> list[dict[str, object]]:
    def warning(record: Mapping[str, object]) -> tuple[str, str] | None:
        measurement = _mapping(record.get("measurement"))
        if phase == "measurement" and _mapping(measurement.get("detection")).get("bounds") is None:
            return "Detection unavailable", "No detector bounds were recorded."
        if phase == "pose" and _mapping(measurement.get("pose")).get("root") is None:
            return "Pose unavailable", "No pose root was recorded."
        if phase == "tracking":
            tracking = _mapping(record.get("tracking"))
            if tracking.get("state") == "lost":
                return "Tracking lost", "Tracker state was lost."
            if tracking.get("reacquired") is True:
                return "Reacquired", "Tracker reacquired the selected athlete."
        if phase == "planning" and bool(
            _mapping(_mapping(record.get("planning")).get("decision")).get("containment_risk")
        ):
            return "Containment risk", "Planner recorded containment risk."
        return None

    intervals: list[dict[str, object]] = []
    active: tuple[int, str, str] | None = None
    for record in trace:
        current = warning(record)
        timestamp = record.get("timestamp_ms")
        if not isinstance(timestamp, int):
            continue
        if current is None:
            if active is not None:
                start, label, detail = active
                intervals.append(
                    {"start_ms": start, "end_ms": timestamp, "label": label, "detail": detail}
                )
                active = None
        elif active is None or active[1:] != current:
            if active is not None:
                start, label, detail = active
                intervals.append(
                    {"start_ms": start, "end_ms": timestamp, "label": label, "detail": detail}
                )
            active = (timestamp, *current)
    if active is not None:
        start, label, detail = active
        end = trace[-1].get("timestamp_ms", start) if trace else start
        intervals.append({"start_ms": start, "end_ms": end, "label": label, "detail": detail})
    return intervals[:100]


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}
