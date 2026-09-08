from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import isclose, isfinite
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from .config import DEFAULT_NORMALIZATION_MAX_SOURCE_BYTES
from .debug import (
    DebugBundleWriter,
    debug_bundle_header,
    serialize_crop_rect,
    serialize_frame_measurement,
    serialize_planner_trace,
    serialize_raw_frame_observation,
)
from .errors import ErrorCode, WorkerError, terminal
from .frame_reader import DecodedFrame, FrameReader, crop_and_resize_frame
from .logging import (
    configure_logging,
    local_artifact_fields,
    media_metadata_fields,
    source_video_fields,
)
from .measurement import (
    Detection,
    PersonDetector,
    RawFrameObservation,
    SelectionOutcome,
    SelectionReferenceKind,
    TargetFrameAnalyzer,
    UnavailableDetector,
)
from .media import (
    CFRNormalizer,
    FFmpegCFRNormalizer,
    FFmpegRenderer,
    FFprobeAdapter,
    MediaMetadata,
    expected_frame_count,
    output_dimensions,
)
from .planner import (
    CropPlan,
    CropPlanner,
    CropRect,
    DeterministicCropPlanner,
    FrameMeasurement,
    LookaheadCropPlanner,
    LookaheadPlannerFrameTrace,
    PlannerError,
    PlannerFrameTrace,
)
from .protocol import AspectRatio, FramingProfile, OutputSettings, TargetSelection
from .repository import OutputAsset, ReviewArtifact, output_storage_key, review_storage_key
from .review import PHASES, ReviewRenderer
from .state import JobConfiguration, JobRecord, SourceAsset
from .storage import S3Storage


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
_CROP_PATH = "crop-path.jsonl"
_ANALYSIS_REPORT = "analysis-report.json"
_RENDER_CACHE = "render-cache.json"
_STAGE_TRACE = "debug-stages.jsonl"


@dataclass(frozen=True, slots=True)
class _Inputs:
    source: Path
    output: Path
    metadata: MediaMetadata
    selection: TargetSelection
    output_settings: OutputSettings
    detection_sample_fps: int | float
    original_metadata: MediaMetadata | None = None


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
        planner_factory: PlannerFactory = LookaheadCropPlanner,
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
        self.analyzer = TargetFrameAnalyzer(detector or UnavailableDetector())
        self.planner_factory = planner_factory
        self.debug_capture = debug_capture
        self.logger = configure_logging()
        self.debug_max_frames = debug_max_frames
        self.debug_max_bytes = debug_max_bytes
        self.review_renderer = review_renderer
        self.normalization_max_source_bytes = normalization_max_source_bytes

    def validating(self, record: JobRecord, scratch: Path) -> Mapping[str, object]:
        inputs = self._inputs(record, scratch)
        source_asset = self._source(record)
        original_source = scratch / "source-original"
        outputs = [
            local_artifact_fields(
                original_source,
                "source_original",
                media=inputs.original_metadata or inputs.metadata,
            )
        ]
        if inputs.source != original_source:
            outputs.append(
                local_artifact_fields(inputs.source, "source_normalized", media=inputs.metadata)
            )
        return {
            "inputs": [_source_object_fields(source_asset)],
            "outputs": outputs,
        }

    def analyzing(self, record: JobRecord, scratch: Path) -> Mapping[str, object]:
        inputs = self._inputs(record, scratch)
        crops = self._crop_path(inputs)
        outputs = [
            local_artifact_fields(scratch / _CROP_PATH, "crop_path", record_count=len(crops))
        ]
        analysis_trace = scratch / _ANALYSIS_TRACE
        report = _load_analysis_report(scratch)
        if analysis_trace.is_file():
            outputs.append(
                local_artifact_fields(analysis_trace, "analysis_trace", record_count=len(crops))
            )
        return {
            "report": report,
            "inputs": [_processing_source_fields(inputs)],
            "outputs": outputs,
        }

    def rendering(self, record: JobRecord, scratch: Path) -> Mapping[str, object]:
        inputs = self._inputs(record, scratch)
        output_metadata = self._render(inputs)
        self._log_render_progress(record, inputs)
        return {
            "report": {
                **_load_analysis_report(scratch),
                "frames_processed": expected_frame_count(inputs.metadata),
            },
            "inputs": [
                _processing_source_fields(inputs),
                local_artifact_fields(scratch / _CROP_PATH, "crop_path"),
            ],
            "outputs": [
                local_artifact_fields(inputs.output, "rendered_output", media=output_metadata)
            ],
        }

    def uploading(self, record: JobRecord, scratch: Path) -> Mapping[str, object]:
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
        return {
            "report": {
                **_load_analysis_report(scratch),
                "frames_processed": expected_frame_count(inputs.metadata),
            },
            "inputs": [
                local_artifact_fields(inputs.output, "rendered_output", media=output_metadata)
            ],
            "outputs": [
                {
                    "kind": "video",
                    "role": "output",
                    "location": "object_storage",
                    "storage_key": stored.key,
                    "size_bytes": stored.size_bytes,
                    "content_type": stored.content_type,
                    "media": media_metadata_fields(output_metadata),
                }
            ],
        }

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
        try:
            _planner_configuration(configuration)
        except WorkerError:
            planner_config: dict[str, object] = {"planner_version": "unavailable"}
        else:
            planner_config = dict(configuration.planner)
            planner_config["planner_version"] = planner_config["controller"]
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
        shared_summary = _review_metadata(len(trace))
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
                    "pipeline_version": _manifest_version(pipeline_version),
                    "model_version": _manifest_version(model_version),
                    "timing": _manifest_timing(metadata),
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
        detection_sample_fps = _planner_configuration(configuration)
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
            original_metadata = metadata
        except WorkerError as error:
            if error.code is not ErrorCode.VARIABLE_FRAME_RATE:
                raise
            original_metadata = self.inspector.inspect(source, allow_variable_frame_rate=True)
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
                    original_metadata.frame_rate,
                    original_metadata.audio_stream_index,
                )
            source = normalized_source
            metadata = self.inspector.inspect(source)
        metadata.frame_for_time_ms(selection.frame_time_ms)
        return _Inputs(
            source,
            scratch / "output.mp4",
            metadata,
            selection,
            output_settings,
            detection_sample_fps,
            original_metadata,
        )

    def _crop_path(self, inputs: _Inputs) -> list[CropRect]:
        crop_path = inputs.source.parent / _CROP_PATH
        if crop_path.is_file():
            return _load_crop_path(crop_path, inputs.metadata)
        expected = expected_frame_count(inputs.metadata)
        width, height = inputs.metadata.display_dimensions
        selected_index = inputs.metadata.frame_for_time_ms(inputs.selection.frame_time_ms)
        tap_normalized_x = inputs.selection.normalized_x
        tap_normalized_y = inputs.selection.normalized_y
        detections: list[tuple[Detection, ...] | None] = []
        # Cross regular sampling ticks on the exact CFR clock, never rounded milliseconds.
        # The selected frame is an extra sample and does not shift the regular grid.
        sample_step = Fraction(str(inputs.detection_sample_fps)) / inputs.metadata.frame_rate
        numerator, denominator = sample_step.numerator, sample_step.denominator
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
                sampled = (
                    numerator == 0
                    or numerator >= denominator
                    or index == 0
                    or index == selected_index
                    or index * numerator // denominator > (index - 1) * numerator // denominator
                )
                detections.append(
                    tuple(self.analyzer.detector.detect(frame.pixels)) if sampled else None
                )
                del frame
        finally:
            close = getattr(frames, "close", None)
            if callable(close):
                close()
        if len(detections) != expected:
            raise terminal(
                ErrorCode.INVALID_MEDIA, "Video frames could not be analyzed consistently."
            )
        observations = [
            RawFrameObservation(
                index,
                inputs.metadata.timestamp_for_frame(index),
                None,
                SelectionOutcome.DETECTION_SKIPPED,
            )
            for index in range(expected)
        ]
        selected_detections = detections[selected_index]
        assert selected_detections is not None
        observations[selected_index] = self.analyzer.select_selected(
            selected_detections,
            frame_index=selected_index,
            timestamp_ms=inputs.metadata.timestamp_for_frame(selected_index),
            normalized_x=tap_normalized_x,
            normalized_y=tap_normalized_y,
            source_width=width,
            source_height=height,
            capture_association_evidence=self.debug_capture,
        )
        self._associate_from_selected(observations, detections, selected_index, 1, inputs.metadata)
        self._associate_from_selected(observations, detections, selected_index, -1, inputs.metadata)
        planner_measurements = _planner_measurements(observations)
        try:
            plan = self.planner_factory(
                width, height, inputs.output_settings.aspect_ratio, inputs.output_settings.profile
            ).plan(planner_measurements)
        except PlannerError as error:
            self.logger.error("crop_planning_failed", extra={"planner_error": str(error)})
            raise terminal(
                ErrorCode.INTERNAL,
                "Video framing could not be planned.",
                diagnostic=str(error),
            ) from error
        report_path = inputs.source.parent / _ANALYSIS_REPORT
        temporary_report = report_path.with_suffix(".tmp")
        temporary_report.write_text(
            json.dumps(_analysis_report(observations, planner_measurements, plan, inputs.metadata)),
            encoding="ascii",
        )
        temporary_report.replace(report_path)
        self._write_crop_path(
            crop_path,
            observations,
            plan,
        )
        if self.debug_capture:
            try:
                self._write_analysis_trace(
                    inputs.source.parent / _ANALYSIS_TRACE,
                    observations,
                    planner_measurements,
                    plan,
                    self.debug_max_frames,
                    self.debug_max_bytes,
                )
            except (OSError, ValueError):
                # Semantic evidence is optional; the crop path remains sufficient to render output.
                (inputs.source.parent / _ANALYSIS_TRACE).unlink(missing_ok=True)
        return list(plan)

    def _associate_from_selected(
        self,
        observations: list[RawFrameObservation],
        detections: Sequence[Sequence[Detection] | None],
        selected_index: int,
        direction: int,
        metadata: MediaMetadata,
    ) -> None:
        selected = observations[selected_index]
        assert selected is not None and selected.detector_bounds is not None
        reference_bounds = selected.detector_bounds
        stop = len(detections) if direction > 0 else -1
        for index in range(selected_index + direction, stop, direction):
            sampled_detections = detections[index]
            if sampled_detections is None:
                continue
            observation = self.analyzer.associate(
                sampled_detections,
                frame_index=index,
                timestamp_ms=metadata.timestamp_for_frame(index),
                reference=reference_bounds.center,
                reference_kind=SelectionReferenceKind.PRIOR_DETECTOR_BOX_CENTER,
                reference_bounds=reference_bounds,
                capture_association_evidence=self.debug_capture,
            )
            observations[index] = observation
            if observation.detector_bounds is not None:
                reference_bounds = observation.detector_bounds

    @staticmethod
    def _write_crop_path(
        path: Path,
        observations: Sequence[RawFrameObservation],
        plan: CropPlan | Sequence[CropRect],
    ) -> None:
        crops = plan.crops if isinstance(plan, CropPlan) else tuple(plan)
        if len(observations) != len(crops):
            raise ValueError("crop path records must have matching frame counts")
        temporary = path.with_suffix(".tmp")
        temporary.unlink(missing_ok=True)
        try:
            with temporary.open("w", encoding="ascii") as destination:
                for observation, crop in zip(observations, crops, strict=True):
                    destination.write(
                        json.dumps(
                            {
                                "frame_index": observation.frame_index,
                                "timestamp_ms": observation.timestamp_ms,
                                "crop": serialize_crop_rect(crop),
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
            temporary.replace(path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _write_analysis_trace(
        path: Path,
        observations: Sequence[RawFrameObservation],
        measurements: Sequence[FrameMeasurement],
        plan: CropPlan | Sequence[CropRect],
        max_frames: int = 10_000,
        max_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        crops = plan.crops if isinstance(plan, CropPlan) else tuple(plan)
        trace = plan.trace if isinstance(plan, CropPlan) else (None,) * len(crops)
        if not (len(observations) == len(measurements) == len(crops) == len(trace)):
            raise ValueError("debug analysis records must have matching frame counts")
        if len(observations) > max_frames:
            raise ValueError("debug analysis records exceed max_frames")
        temporary = path.with_suffix(".tmp")
        temporary.unlink(missing_ok=True)
        try:
            with temporary.open("w", encoding="ascii") as destination:
                for observation, measurement, crop, planner_trace in zip(
                    observations, measurements, crops, trace, strict=True
                ):
                    record = {
                        "record_type": "frame",
                        "schema_version": 1,
                        "frame_index": observation.frame_index,
                        "timestamp_ms": observation.timestamp_ms,
                        "detection": {
                            **serialize_raw_frame_observation(observation),
                        },
                        "framing": {
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
                    }
                    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
                    if destination.tell() + len(encoded.encode("ascii")) > max_bytes:
                        raise ValueError("debug analysis records exceed max_bytes")
                    destination.write(encoded)
            temporary.replace(path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _render(self, inputs: _Inputs) -> MediaMetadata:
        crops = self._crop_path(inputs)
        cache_path = inputs.source.parent / _RENDER_CACHE
        cache = {
            "aspect_ratio": inputs.output_settings.aspect_ratio.value,
            "crop_path_sha256": _sha256(inputs.source.parent / _CROP_PATH),
            "renderer_version": "fixed-output-v1",
        }
        if inputs.output.exists() and self._render_cache_matches(cache_path, cache):
            metadata = self.renderer.validate_rendered_output(
                inputs.output,
                inputs.metadata,
                inputs.output_settings.aspect_ratio,
                self.inspector,
            )
            self._mark_render_validated(
                inputs.source.parent / _ANALYSIS_TRACE, self.debug_max_bytes
            )
            return metadata
        cache_path.unlink(missing_ok=True)
        rendered = self.renderer.render_crop_path(
            inputs.source,
            inputs.output,
            crops,
            inputs.metadata,
            inputs.output_settings.aspect_ratio,
            self.inspector,
            self.frame_reader,
        )
        self._write_render_cache(cache_path, cache)
        self._mark_render_validated(inputs.source.parent / _ANALYSIS_TRACE, self.debug_max_bytes)
        return rendered

    def _log_render_progress(self, record: JobRecord, inputs: _Inputs) -> None:
        if not self.debug_capture:
            return
        try:
            progress = self.renderer.output_frame_progress(inputs.output)
        except (ValueError, WorkerError):
            self.logger.warning(
                "render output progress unavailable",
                extra={"job_id": str(record.id), "stage": "rendering"},
                exc_info=True,
            )
            return
        crops = self._crop_path(inputs)
        intervals = [
            {"start_frame": start, "end_frame": end}
            for start, end in progress.repeated_frame_intervals[:10]
        ]
        self.logger.info(
            "render output progress",
            extra={
                "job_id": str(record.id),
                "stage": "rendering",
                "output_frame_count": progress.frame_count,
                "repeated_output_frame_count": progress.repeated_frame_count,
                "repeated_output_frame_intervals": intervals,
                "planned_crop_count": len(set(crops)),
            },
        )
        self._log_render_temporal_progress(record, inputs)
        self._log_render_mapping(record, inputs, crops)

    def _log_render_temporal_progress(self, record: JobRecord, inputs: _Inputs) -> None:
        original = inputs.source.parent / "source-original"
        normalized = inputs.source != original
        output_sample_size = (
            (192, 108)
            if inputs.output_settings.aspect_ratio is AspectRatio.LANDSCAPE
            else (108, 192)
        )
        try:
            render_input = self.renderer.temporal_frame_progress(inputs.source)
            output = self.renderer.temporal_frame_progress(inputs.output, output_sample_size)
        except Exception:
            self.logger.warning(
                "render temporal progress unavailable",
                extra={"job_id": str(record.id), "stage": "rendering"},
                exc_info=True,
            )
            return
        self.logger.info(
            "render temporal progress",
            extra={
                "job_id": str(record.id),
                "stage": "rendering",
                "render_input_was_normalized": normalized,
                "render_input_frame_count": render_input.frame_count,
                "render_input_near_static_frame_count": render_input.near_static_frame_count,
                "render_input_near_static_intervals": _interval_records(
                    render_input.near_static_intervals
                ),
                "output_near_static_frame_count": output.near_static_frame_count,
                "output_near_static_intervals": _interval_records(output.near_static_intervals),
            },
        )
        try:
            planned_crop = self.renderer.crop_path_temporal_progress(
                inputs.source,
                self._crop_path(inputs),
                inputs.metadata,
                inputs.output_settings.aspect_ratio,
                self.frame_reader,
            )
        except Exception:
            self.logger.warning(
                "planned crop temporal progress unavailable",
                extra={"job_id": str(record.id), "stage": "rendering"},
                exc_info=True,
            )
        else:
            self.logger.info(
                "planned crop temporal progress",
                extra={
                    "job_id": str(record.id),
                    "stage": "rendering",
                    "planned_crop_near_static_frame_count": planned_crop.near_static_frame_count,
                    "planned_crop_near_static_intervals": _interval_records(
                        planned_crop.near_static_intervals
                    ),
                },
            )
        if not normalized:
            return
        try:
            original_progress = self.renderer.temporal_frame_progress(original)
        except Exception:
            self.logger.warning(
                "original source temporal progress unavailable",
                extra={"job_id": str(record.id), "stage": "rendering"},
                exc_info=True,
            )
            return
        self.logger.info(
            "original source temporal progress",
            extra={
                "job_id": str(record.id),
                "stage": "rendering",
                "original_source_frame_count": original_progress.frame_count,
                "original_source_near_static_frame_count": (
                    original_progress.near_static_frame_count
                ),
                "original_source_near_static_intervals": _interval_records(
                    original_progress.near_static_intervals
                ),
            },
        )

    def _log_render_mapping(
        self, record: JobRecord, inputs: _Inputs, crops: Sequence[CropRect]
    ) -> None:
        try:
            samples = _render_mapping_samples(crops)
            errors = _render_mapping_errors(inputs, crops, samples, self.frame_reader)
        except Exception:
            self.logger.warning(
                "render crop mapping unavailable",
                extra={"job_id": str(record.id), "stage": "rendering"},
                exc_info=True,
            )
            return
        matching = sum(error <= 24.0 for _, error in errors)
        self.logger.info(
            "render crop mapping",
            extra={
                "job_id": str(record.id),
                "stage": "rendering",
                "render_mapping_checked_frames": len(errors),
                "render_mapping_matching_frames": matching,
                "render_mapping_max_mean_absolute_error": max(error for _, error in errors),
                "render_mapping_samples": [
                    {"frame_index": index, "mean_absolute_error": round(error, 3)}
                    for index, error in errors
                ],
            },
        )

    @staticmethod
    def _render_cache_matches(path: Path, expected: Mapping[str, str]) -> bool:
        try:
            with path.open(encoding="ascii") as source:
                cache: object = json.load(source)
                return cache == dict(expected)
        except (OSError, json.JSONDecodeError):
            return False

    @staticmethod
    def _write_render_cache(path: Path, cache: Mapping[str, str]) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.unlink(missing_ok=True)
        try:
            with temporary.open("w", encoding="ascii") as destination:
                json.dump(cache, destination, sort_keys=True, separators=(",", ":"))
                destination.write("\n")
            temporary.replace(path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _mark_render_validated(path: Path, max_bytes: int) -> None:
        if not path.is_file():
            return
        temporary = path.with_suffix(".tmp")
        temporary.unlink(missing_ok=True)
        try:
            with path.open(encoding="ascii") as trace:
                with temporary.open("w", encoding="ascii") as destination:
                    for line in trace:
                        record = json.loads(line)
                        if isinstance(record, dict) and isinstance(record.get("render"), dict):
                            record["render"]["output_validated"] = True
                        encoded = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
                        if destination.tell() + len(encoded.encode("ascii")) > max_bytes:
                            raise ValueError("debug analysis records exceed max_bytes")
                        destination.write(encoded)
            temporary.replace(path)
        except Exception:
            # A diagnostic trace must never invalidate an already validated product output.
            temporary.unlink(missing_ok=True)

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


def _source_object_fields(source: SourceAsset) -> dict[str, object]:
    return {
        "kind": "video",
        "role": "source",
        "location": "object_storage",
        **source_video_fields(source),
    }


def _processing_source_fields(inputs: _Inputs) -> dict[str, object]:
    role = "source_normalized" if inputs.source.name == "source-cfr.mp4" else "source_original"
    return local_artifact_fields(inputs.source, role, media=inputs.metadata)


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


def _planner_configuration(configuration: JobConfiguration) -> int | float:
    settings = configuration.planner
    expected: dict[str, str | float] = {
        "controller": "lookahead-v1",
        "seed_controller": "deterministic-v3",
        "optimizer": "scipy-highs-ds",
        "lookahead_scope": "full_shot",
        "containment_policy": "sampled_detections",
        "solver_feasibility_tolerance": LookaheadCropPlanner.solver_feasibility_tolerance,
        "scale_enter_fraction": DeterministicCropPlanner.scale_enter_fraction,
        "scale_exit_fraction": DeterministicCropPlanner.scale_exit_fraction,
        "center_enter_fraction": DeterministicCropPlanner.center_enter_fraction,
        "center_exit_fraction": DeterministicCropPlanner.center_exit_fraction,
        "zoom_max_speed": DeterministicCropPlanner.zoom_max_speed,
        "zoom_max_acceleration": DeterministicCropPlanner.zoom_max_acceleration,
        "pan_max_speed": LookaheadCropPlanner.pan_max_speed,
        "pan_max_acceleration": LookaheadCropPlanner.pan_max_acceleration,
    }
    invalid = set(settings) != {*expected, "detection_sample_fps"}
    for key, required in expected.items():
        value = settings.get(key)
        if isinstance(required, str):
            invalid |= not isinstance(value, str) or value != required
        else:
            invalid |= (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value != required
                or not isfinite(value)
            )
    sample_fps = settings.get("detection_sample_fps")
    if (
        invalid
        or isinstance(sample_fps, bool)
        or not isinstance(sample_fps, (int, float))
        or not 0 <= sample_fps <= 1000
        or not isfinite(sample_fps)
    ):
        raise terminal(ErrorCode.INTERNAL, "The job planner configuration is invalid.")
    return sample_fps


def _planner_measurements(observations: Sequence[RawFrameObservation]) -> list[FrameMeasurement]:
    measurements: list[FrameMeasurement] = []
    held: Detection | None = None
    for observation in observations:
        if observation.selection_outcome is not SelectionOutcome.DETECTION_SKIPPED:
            # A sampled miss clears the held box until a later successful sample.
            held = observation.detection
        measurements.append(
            FrameMeasurement(
                None if held is None else held.bounds,
                observation.timestamp_ms,
                0 if held is None else held.confidence,
                detection_sampled=(
                    observation.selection_outcome is not SelectionOutcome.DETECTION_SKIPPED
                ),
            )
        )
    return measurements


def _render_mapping_samples(crops: Sequence[CropRect]) -> tuple[int, ...]:
    if not crops:
        raise ValueError("crop path must not be empty")
    first_change = next(
        (index for index, crop in enumerate(crops[1:], start=1) if crop != crops[index - 1]),
        0,
    )
    return tuple(dict.fromkeys((0, first_change, len(crops) // 2, len(crops) - 1)))


def _interval_records(intervals: Sequence[tuple[int, int]]) -> list[dict[str, int]]:
    return [{"start_frame": start, "end_frame": end} for start, end in intervals[:10]]


def _render_mapping_errors(
    inputs: _Inputs,
    crops: Sequence[CropRect],
    samples: Sequence[int],
    frame_reader: FrameReader,
) -> list[tuple[int, float]]:
    import cv2

    sample_set = set(samples)
    output_width, output_height = output_dimensions(inputs.output_settings.aspect_ratio)
    output = cv2.VideoCapture(str(inputs.output))
    if not output.isOpened():
        output.release()
        raise ValueError("rendered output could not be decoded")
    source_frames = frame_reader.read(inputs.source, inputs.metadata)
    errors: list[tuple[int, float]] = []
    try:
        for index, source in enumerate(source_frames):
            decoded, output_pixels = output.read()
            if not decoded:
                raise ValueError("rendered output frame alignment failed")
            if source.index != index or source.timestamp_ms != inputs.metadata.timestamp_for_frame(
                index
            ):
                raise ValueError("source video frame alignment failed")
            if index not in sample_set:
                continue
            expected: Any = crop_and_resize_frame(
                source.pixels, crops[index], (output_width, output_height)
            )
            difference = cv2.absdiff(expected, output_pixels)
            errors.append((index, sum(cv2.mean(difference)[:3]) / 3))
        if len(errors) != len(samples):
            raise ValueError("source video frame alignment failed")
    finally:
        output.release()
        close = getattr(source_frames, "close", None)
        if callable(close):
            close()
    return errors


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


def _load_analysis_report(scratch: Path) -> dict[str, object]:
    path = scratch / _ANALYSIS_REPORT
    if not path.is_file():
        return {}
    report: dict[str, object] = json.loads(path.read_text(encoding="ascii"))
    return report


def _analysis_report(
    observations: Sequence[RawFrameObservation],
    measurements: Sequence[FrameMeasurement],
    plan: CropPlan | Sequence[CropRect],
    metadata: MediaMetadata,
) -> dict[str, object]:
    outcomes = dict.fromkeys((outcome.value for outcome in SelectionOutcome), 0)
    detected = unavailable = gap_count = longest_gap_ms = 0
    gap_start: int | None = None
    for observation, measurement in zip(observations, measurements, strict=True):
        outcomes[observation.selection_outcome.value] += 1
        detected += observation.detection is not None
        if measurement.detector_bounds is None:
            unavailable += 1
            if gap_start is None:
                gap_start = observation.timestamp_ms
                gap_count += 1
        elif gap_start is not None:
            longest_gap_ms = max(longest_gap_ms, observation.timestamp_ms - gap_start)
            gap_start = None
    if gap_start is not None:
        longest_gap_ms = max(
            longest_gap_ms, metadata.timestamp_for_frame(len(observations)) - gap_start
        )
    skipped = outcomes[SelectionOutcome.DETECTION_SKIPPED.value]
    sampled = len(observations) - skipped
    max_pan_step = max_zoom_step = 0.0
    max_pan_timestamp: int | None = None
    previous: CropRect | None = None
    previous_timestamp = 0
    previous_velocity = (0.0, 0.0)
    previous_dt = 0.0
    max_speed = max_acceleration = 0.0
    source_width, source_height = metadata.display_dimensions
    for observation, crop in zip(observations, plan, strict=True):
        if previous is not None:
            pan_step = (
                (crop.center.x - previous.center.x) ** 2 + (crop.center.y - previous.center.y) ** 2
            ) ** 0.5
            if pan_step > max_pan_step:
                max_pan_step = pan_step
                max_pan_timestamp = observation.timestamp_ms
            max_zoom_step = max(max_zoom_step, abs(crop.height / previous.height - 1))
            dt = (observation.timestamp_ms - previous_timestamp) / 1000
            velocity = (
                (crop.center.x - previous.center.x) / source_width / dt,
                (crop.center.y - previous.center.y) / source_height / dt,
            )
            max_speed = max(max_speed, abs(velocity[0]), abs(velocity[1]))
            max_acceleration = max(
                max_acceleration,
                2 * abs(velocity[0] - previous_velocity[0]) / (dt + previous_dt),
                2 * abs(velocity[1] - previous_velocity[1]) / (dt + previous_dt),
            )
            previous_velocity, previous_dt = velocity, dt
        previous = crop
        previous_timestamp = observation.timestamp_ms
    if previous_dt:
        max_acceleration = max(
            max_acceleration,
            2 * abs(previous_velocity[0]) / previous_dt,
            2 * abs(previous_velocity[1]) / previous_dt,
        )
    speed_excess = max(0.0, max_speed - LookaheadCropPlanner.pan_max_speed)
    acceleration_excess = max(0.0, max_acceleration - LookaheadCropPlanner.pan_max_acceleration)
    tolerance = LookaheadCropPlanner.solver_feasibility_tolerance
    if speed_excess <= tolerance or isclose(speed_excess, tolerance, rel_tol=0, abs_tol=1e-12):
        speed_excess = 0.0
    if acceleration_excess <= tolerance or isclose(
        acceleration_excess, tolerance, rel_tol=0, abs_tol=1e-12
    ):
        acceleration_excess = 0.0
    framing: dict[str, object] = {
        "planner_controller": "lookahead-v1",
        "optimizer": "scipy-highs-ds",
        "lookahead_scope": "full_shot",
        "containment_policy": "sampled_detections",
        "sampled_detection_constraint_frames": 0,
        "sampled_detection_uncontained_frames": 0,
        "held_target_outside_crop_frames": 0,
        "max_pan_axis_speed_source_fraction_per_second": max_speed,
        "max_pan_axis_acceleration_source_fraction_per_second2": max_acceleration,
        "pan_speed_limit_exceeded_frames": 0,
        "pan_acceleration_limit_exceeded_frames": 0,
        "pan_speed_limit_excess_source_fraction_per_second": speed_excess,
        "pan_acceleration_limit_excess_source_fraction_per_second2": acceleration_excess,
        "unavailable_target_frames": unavailable,
        "detection_gap_count": gap_count,
        "longest_detection_gap_ms": longest_gap_ms,
        "max_center_step_source_px": max_pan_step,
        "max_center_step_timestamp_ms": max_pan_timestamp,
        "max_height_step_fraction": max_zoom_step,
    }
    if isinstance(plan, CropPlan):
        actions: dict[str, int] = {}
        constrained = uncontained = held_outside = speed_exceeded = acceleration_exceeded = 0
        for trace in plan.trace:
            actions[trace.action] = actions.get(trace.action, 0) + 1
            if isinstance(trace, LookaheadPlannerFrameTrace):
                constrained += trace.sampled_detection_constraint
                uncontained += trace.sampled_detection_contained is False
                held_outside += trace.held_target_contained is False
                speed_exceeded += trace.pan_speed_limit_exceeded
                acceleration_exceeded += trace.pan_acceleration_limit_exceeded
        framing.update(
            sampled_detection_constraint_frames=constrained,
            sampled_detection_uncontained_frames=uncontained,
            held_target_outside_crop_frames=held_outside,
            pan_speed_limit_exceeded_frames=speed_exceeded,
            pan_acceleration_limit_exceeded_frames=acceleration_exceeded,
            action_counts=actions,
            containment_override_frames=sum(trace.containment_override for trace in plan.trace),
            source_aspect_limited_frames=sum(trace.source_aspect_limited for trace in plan.trace),
        )
    return {
        "detection": {
            "frames": len(observations),
            "sampled_frames": sampled,
            "skipped_frames": skipped,
            "detected_frames": detected,
            "missed_frames": sampled - detected,
            "outcome_counts": outcomes,
        },
        "framing": framing,
    }


def _load_crop_path(path: Path, metadata: MediaMetadata) -> list[CropRect]:
    crops: list[CropRect] = []
    with path.open(encoding="ascii") as source:
        records = (json.loads(line) for line in source)
        for index, record in enumerate(records):
            if (
                not isinstance(record, dict)
                or record.get("frame_index") != index
                or record.get("timestamp_ms") != metadata.timestamp_for_frame(index)
            ):
                raise terminal(ErrorCode.INVALID_MEDIA, "Crop path is inconsistent.")
            try:
                crop = record["crop"]
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
                raise terminal(ErrorCode.INVALID_MEDIA, "Crop path is inconsistent.") from error
    if len(crops) != expected_frame_count(metadata):
        raise terminal(ErrorCode.INVALID_MEDIA, "Crop path is incomplete.")
    return crops


def _planner_decision(
    trace: PlannerFrameTrace | LookaheadPlannerFrameTrace | None,
) -> dict[str, object]:
    return {} if trace is None else {"decision": serialize_planner_trace(trace)}


def _review_unavailable_detail(value: object) -> str:
    if not isinstance(value, str):
        return "unavailable"
    safe = " ".join(value.split())
    return safe[:80] or "unavailable"


def _review_metadata(frame_count: int) -> dict[str, object]:
    return {"trace_frame_count": frame_count}


def _manifest_version(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value):
        raise ValueError("manifest version is invalid")
    return value


def _manifest_timing(metadata: MediaMetadata | None) -> dict[str, object]:
    if metadata is None:
        raise ValueError("manifest timing is unavailable")
    frame_count = expected_frame_count(metadata)
    if not (0 < float(metadata.frame_rate) <= 1000):
        raise ValueError("manifest frame rate is invalid")
    if not (0 < metadata.duration_ms <= 7 * 24 * 60 * 60 * 1000):
        raise ValueError("manifest duration is invalid")
    if not (0 < frame_count <= 10_000_000):
        raise ValueError("manifest frame count is invalid")
    return {
        "frame_rate": float(metadata.frame_rate),
        "duration_ms": metadata.duration_ms,
        "frame_count": frame_count,
    }


def _review_summary(trace: Sequence[Mapping[str, object]], phase: str) -> dict[str, object]:
    if phase == "detection":
        detected = sum(
            _mapping(_mapping(record.get("detection")).get("detection")).get("bounds") is not None
            for record in trace
        )
        skipped = sum(
            _mapping(record.get("detection")).get("selection_outcome")
            == SelectionOutcome.DETECTION_SKIPPED.value
            for record in trace
        )
        return {
            "frames": len(trace),
            "sampled_frames": len(trace) - skipped,
            "skipped_frames": skipped,
            "detected_frames": detected,
            "missed_frames": len(trace) - skipped - detected,
        }
    if phase == "framing":
        risks = sum(
            bool(
                _mapping(_mapping(record.get("framing")).get("decision")).get(
                    "containment_override"
                )
            )
            for record in trace
        )
        misses = sum(
            bool(_mapping(_mapping(record.get("framing")).get("decision")).get("detection_missed"))
            for record in trace
        )
        limited = sum(
            bool(
                _mapping(_mapping(record.get("framing")).get("decision")).get(
                    "source_aspect_limited"
                )
            )
            for record in trace
        )
        counts = {
            "sampled_detection_constraint_frames": 0,
            "sampled_detection_uncontained_frames": 0,
            "held_target_outside_crop_frames": 0,
            "pan_speed_limit_exceeded_frames": 0,
            "pan_acceleration_limit_exceeded_frames": 0,
        }
        for record in trace:
            decision = _mapping(_mapping(record.get("framing")).get("decision"))
            counts["sampled_detection_constraint_frames"] += (
                decision.get("sampled_detection_constraint") is True
            )
            counts["sampled_detection_uncontained_frames"] += (
                decision.get("sampled_detection_contained") is False
            )
            counts["held_target_outside_crop_frames"] += (
                decision.get("held_target_contained") is False
            )
            counts["pan_speed_limit_exceeded_frames"] += (
                decision.get("pan_speed_limit_exceeded") is True
            )
            counts["pan_acceleration_limit_exceeded_frames"] += (
                decision.get("pan_acceleration_limit_exceeded") is True
            )
        return {
            **counts,
            "frames": len(trace),
            "containment_override_frames": risks,
            "unavailable_detection_frames": misses,
            "source_aspect_limited_frames": limited,
        }
    verified = sum(
        bool(_mapping(record.get("render")).get("mapping_independently_verified"))
        for record in trace
    )
    return {"frames": len(trace), "mapping_verified_frames": verified}


def _review_warning_intervals(
    trace: Sequence[Mapping[str, object]], phase: str
) -> list[dict[str, object]]:
    def warnings(record: Mapping[str, object]) -> dict[str, str]:
        detection = _mapping(record.get("detection"))
        if phase == "detection":
            if (
                detection.get("selection_outcome") != SelectionOutcome.DETECTION_SKIPPED.value
                and _mapping(detection.get("detection")).get("bounds") is None
            ):
                return {"Detection unavailable": "No detector bounds were recorded."}
            return {}
        if phase != "framing":
            return {}
        decision = _mapping(_mapping(record.get("framing")).get("decision"))
        current: dict[str, str] = {}
        if decision.get("detection_missed"):
            current["Held detection unavailable"] = (
                "Crop widened until a successful detection sample."
            )
        if decision.get("source_aspect_limited"):
            current["Source/aspect limited"] = (
                "The largest valid crop cannot contain this detector box."
            )
        if decision.get("pan_speed_limit_exceeded"):
            current["Pan speed limit exceeded"] = (
                "Sampled detection containment requires motion above the pan speed limit."
            )
        if decision.get("pan_acceleration_limit_exceeded"):
            current["Pan acceleration limit exceeded"] = (
                "Sampled detection containment requires motion above the pan acceleration limit."
            )
        if decision.get("held_target_contained") is False:
            current["Held target outside crop"] = (
                "A stale held target is guidance, not a fresh sampled containment constraint."
            )
        return current

    intervals: list[dict[str, object]] = []
    active: dict[str, tuple[int, str]] = {}
    end = 0
    for record in trace:
        timestamp = record.get("timestamp_ms")
        if not isinstance(timestamp, int):
            continue
        end = timestamp
        current = warnings(record)
        for label in tuple(active):
            if label not in current:
                start, detail = active.pop(label)
                intervals.append(
                    {"start_ms": start, "end_ms": timestamp, "label": label, "detail": detail}
                )
        for label, detail in current.items():
            active.setdefault(label, (timestamp, detail))
    for label, (start, detail) in active.items():
        intervals.append({"start_ms": start, "end_ms": end, "label": label, "detail": detail})
    intervals.sort(key=lambda interval: (int(str(interval["start_ms"])), str(interval["label"])))
    return intervals[:100]


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}
