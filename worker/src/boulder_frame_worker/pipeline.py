from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from .errors import ErrorCode, terminal
from .measurement import (
    PersonDetector,
    PoseEstimator,
    TargetFrameAnalyzer,
    UnavailableDetector,
    UnavailablePoseEstimator,
)
from .media import (
    FFmpegRenderer,
    FFprobeAdapter,
    MediaMetadata,
    expected_frame_count,
    validate_output,
)
from .planner import CropPlanner, CropRect, DeterministicCropPlanner, FrameMeasurement
from .protocol import AspectRatio, FramingProfile, OutputSettings, TargetSelection
from .repository import OutputAsset, output_storage_key
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
        frame_reader: FrameReader | None = None,
        detector: PersonDetector | None = None,
        pose_estimator: PoseEstimator | None = None,
        tracker: TargetTracker | None = None,
        planner_factory: PlannerFactory = DeterministicCropPlanner,
    ) -> None:
        self.storage = storage
        self.finalizer = finalizer
        self.inspector = inspector
        self.renderer = renderer
        self.frame_reader = frame_reader or UnavailableFrameReader()
        self.analyzer = TargetFrameAnalyzer(
            detector or UnavailableDetector(), pose_estimator or UnavailablePoseEstimator()
        )
        self.tracker = tracker or SingleTargetTracker()
        self.planner_factory = planner_factory

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
        source = scratch / "source"
        if not source.exists():
            self.storage.download(source_asset.storage_key, source)
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
        return self.planner_factory(
            width, height, inputs.output_settings.aspect_ratio, inputs.output_settings.profile
        ).plan(_planner_measurements(tracked))

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
