import json
from fractions import Fraction
from pathlib import Path
from uuid import uuid4

import pytest

from boulder_frame_worker.errors import ErrorCode, WorkerError, terminal
from boulder_frame_worker.measurement import Detection, Rect
from boulder_frame_worker.media import MediaMetadata, TemporalFrameProgress
from boulder_frame_worker.pipeline import (
    DecodedFrame,
    ProcessingPipeline,
    _Inputs,
    _render_mapping_samples,
)
from boulder_frame_worker.planner import CropRect
from boulder_frame_worker.protocol import (
    AspectRatio,
    FramingProfile,
    OutputSettings,
    TargetSelection,
)
from boulder_frame_worker.state import JobConfiguration, JobRecord, JobState, SourceAsset


class Storage:
    def download(self, key: str, destination: Path) -> None:
        destination.write_bytes(b"source")


class Finalizer:
    def finalize_output(self, record: JobRecord, output: object) -> None:
        return None

    def finalize_review(self, record, review_id, artifacts) -> None:
        return None


class Inspector:
    def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
        return MediaMetadata(1920, 1080, 1000, 2, "h264", None, 0, False)


class Renderer:
    def __init__(self) -> None:
        self.crops: list[CropRect] | None = None
        self.calls = 0

    def render_crop_path(
        self, source, destination, crop_path, source_metadata, aspect_ratio, inspector
    ):
        self.calls += 1
        self.crops = crop_path
        destination.write_bytes(b"output")
        return Inspector().inspect(destination)


def record(frame_time_ms: int = 0) -> JobRecord:
    source_id = uuid4()
    return JobRecord(
        id=uuid4(),
        state=JobState.UPLOADING,
        configuration=JobConfiguration(
            source_id,
            {"frame_time_ms": frame_time_ms, "normalized_x": 0.5, "normalized_y": 0.5},
            {"aspect_ratio": "16:9", "profile": "balanced"},
            "pipeline",
            "model",
            {},
        ),
        source_asset=SourceAsset(
            source_id, uuid4(), "source", "uploaded", None, None, 1, None, None, None, None
        ),
    )


def test_detector_only_pipeline_persists_aligned_crops_and_widens_later_miss(tmp_path) -> None:
    class Pixels:
        def __init__(self, index: int) -> None:
            self.index = index

    class Frames:
        def read(self, source, metadata):
            return [DecodedFrame(index, index * 500, Pixels(index)) for index in range(2)]

    class Detector:
        def detect(self, pixels: Pixels) -> list[Detection]:
            return [Detection(Rect(700, 200, 200, 400), 0.9)] if pixels.index == 0 else []

    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=Renderer(),
        frame_reader=Frames(),
        detector=Detector(),
        debug_capture=True,
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    inputs = pipeline._inputs(record(), scratch)

    crops = pipeline._crop_path(inputs)
    stored = [json.loads(line) for line in (scratch / "crop-path.jsonl").read_text().splitlines()]
    trace = [
        json.loads(line) for line in (scratch / "analysis-trace.jsonl").read_text().splitlines()
    ]

    assert len(crops) == len(stored) == len(trace) == 2
    assert crops[1].height > crops[0].height
    assert trace[1]["detection"]["selection_outcome"] == "no_detections"
    assert trace[1]["framing"]["decision"]["action"] == "widen_on_miss"
    assert "pose" not in json.dumps(trace)
    assert "tracking" not in json.dumps(trace)


def test_temporal_progress_compares_normalized_input_output_and_original_source(tmp_path) -> None:
    class TemporalRenderer(Renderer):
        def __init__(self) -> None:
            super().__init__()
            self.sources: list[Path] = []

        def temporal_frame_progress(
            self, source: Path, sample_size: tuple[int, int] = (192, 108)
        ) -> TemporalFrameProgress:
            del sample_size
            self.sources.append(source)
            return TemporalFrameProgress(30, ((4, 20),))

        def crop_path_temporal_progress(
            self,
            source: Path,
            crops: list[CropRect],
            metadata: MediaMetadata,
            aspect_ratio: AspectRatio,
        ) -> TemporalFrameProgress:
            del source, crops, metadata, aspect_ratio
            return TemporalFrameProgress(30, ((4, 20),))

    class Logger:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict[str, object]]] = []

        def info(self, message: str, *, extra: dict[str, object]) -> None:
            self.events.append((message, extra))

        def warning(self, message: str, *, extra: dict[str, object], exc_info: bool) -> None:
            raise AssertionError(message)

    renderer = TemporalRenderer()
    pipeline = ProcessingPipeline(Storage(), Finalizer(), inspector=Inspector(), renderer=renderer)
    logger = Logger()
    pipeline.logger = logger  # type: ignore[assignment]
    inputs = _Inputs(
        tmp_path / "source-cfr.mp4",
        tmp_path / "output.mp4",
        Inspector().inspect(tmp_path / "output.mp4"),
        TargetSelection(0, 0.5, 0.5),
        OutputSettings(AspectRatio.LANDSCAPE, FramingProfile.BALANCED),
    )
    (tmp_path / "crop-path.jsonl").write_text(
        """{"crop":{"height":1080,"width":1920,"x":0,"y":0},"frame_index":0,"timestamp_ms":0}
{"crop":{"height":1080,"width":1920,"x":0,"y":0},"frame_index":1,"timestamp_ms":500}
""",
        encoding="ascii",
    )

    pipeline._log_render_temporal_progress(record(), inputs)

    assert [source.name for source in renderer.sources] == [
        "source-cfr.mp4",
        "output.mp4",
        "source-original",
    ]
    assert [message for message, _ in logger.events] == [
        "render temporal progress",
        "planned crop temporal progress",
        "original source temporal progress",
    ]
    assert logger.events[0][1]["render_input_was_normalized"] is True
    assert logger.events[1][1]["planned_crop_near_static_frame_count"] == 17


def test_render_progress_is_skipped_without_debug_capture(tmp_path) -> None:
    class FailingRenderer(Renderer):
        def output_frame_progress(self, output: Path) -> object:
            del output
            raise AssertionError("debug diagnostics must be disabled")

    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=FailingRenderer(),
        debug_capture=False,
    )
    inputs = _Inputs(
        tmp_path / "source-original",
        tmp_path / "output.mp4",
        Inspector().inspect(tmp_path / "output.mp4"),
        TargetSelection(0, 0.5, 0.5),
        OutputSettings(AspectRatio.LANDSCAPE, FramingProfile.BALANCED),
    )

    pipeline._log_render_progress(record(), inputs)


def test_render_reuses_crop_path_without_running_detector(tmp_path) -> None:
    class FailingFrames:
        def read(self, source, metadata):
            raise AssertionError("persisted crop path must be reused")

    renderer = Renderer()
    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=renderer,
        frame_reader=FailingFrames(),
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    (scratch / "crop-path.jsonl").write_text(
        """{\"crop\":{\"height\":1080,\"width\":1920,\"x\":0,\"y\":0},\"frame_index\":0,\"timestamp_ms\":0}
{\"crop\":{\"height\":1080,\"width\":1920,\"x\":0,\"y\":0},\"frame_index\":1,\"timestamp_ms\":500}
""",
        encoding="ascii",
    )

    pipeline.rendering(record(), scratch)
    assert renderer.crops == [CropRect(0, 0, 1920, 1080), CropRect(0, 0, 1920, 1080)]


def test_render_discards_output_when_crop_path_changes(tmp_path) -> None:
    class FailingFrames:
        def read(self, source, metadata):
            raise AssertionError("persisted crop path must be reused")

    renderer = Renderer()
    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=renderer,
        frame_reader=FailingFrames(),
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    crop_path = scratch / "crop-path.jsonl"
    crop_path.write_text(
        """{\"crop\":{\"height\":1080,\"width\":1920,\"x\":0,\"y\":0},\"frame_index\":0,\"timestamp_ms\":0}
{\"crop\":{\"height\":1080,\"width\":1920,\"x\":0,\"y\":0},\"frame_index\":1,\"timestamp_ms\":500}
""",
        encoding="ascii",
    )

    pipeline.rendering(record(), scratch)
    pipeline.rendering(record(), scratch)
    assert renderer.calls == 1

    crop_path.write_text(
        """{\"crop\":{\"height\":1080,\"width\":1920,\"x\":0,\"y\":0},\"frame_index\":0,\"timestamp_ms\":0}
{\"crop\":{\"height\":1080,\"width\":1920,\"x\":1,\"y\":0},\"frame_index\":1,\"timestamp_ms\":500}
""",
        encoding="ascii",
    )

    pipeline.rendering(record(), scratch)

    assert renderer.calls == 2
    assert renderer.crops == [CropRect(0, 0, 1920, 1080), CropRect(1, 0, 1920, 1080)]


def test_render_mapping_samples_include_the_first_crop_change() -> None:
    crops = [
        CropRect(0, 0, 1920, 1080),
        CropRect(0, 0, 1920, 1080),
        CropRect(20, 0, 1900, 1068.75),
        CropRect(30, 0, 1890, 1063.125),
    ]

    assert _render_mapping_samples(crops) == (0, 2, 3)


def test_selected_frame_miss_remains_terminal(tmp_path) -> None:
    class Frames:
        def read(self, source, metadata):
            return [DecodedFrame(0, 0, object()), DecodedFrame(1, 500, object())]

    class Detector:
        def detect(self, pixels) -> list[Detection]:
            return []

    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=Inspector(),
        renderer=Renderer(),
        frame_reader=Frames(),
        detector=Detector(),
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    with pytest.raises(WorkerError) as raised:
        pipeline._crop_path(pipeline._inputs(record(), scratch))
    assert raised.value.code is ErrorCode.NO_SELECTED_ATHLETE


def test_selected_frame_association_propagates_both_directions_without_identity_switch(
    tmp_path,
) -> None:
    class Pixels:
        def __init__(self, index: int) -> None:
            self.index = index

    class Frames:
        def read(self, source, metadata):
            return [DecodedFrame(index, index * 500, Pixels(index)) for index in range(3)]

    class ThreeFrameInspector(Inspector):
        def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
            return MediaMetadata(1920, 1080, 1500, 2, "h264", None, 0, False)

    target = [Rect(680, 200, 100, 400), Rect(700, 200, 100, 400), Rect(720, 200, 100, 400)]
    competitor = Rect(1300, 200, 100, 400)

    class Detector:
        def detect(self, pixels: Pixels) -> list[Detection]:
            if pixels.index == 0:
                return [Detection(target[0], 0.9), Detection(competitor, 0.9)]
            if pixels.index == 1:
                return [Detection(competitor, 0.9), Detection(target[1], 0.9)]
            return [Detection(competitor, 0.9), Detection(target[2], 0.9)]

    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=ThreeFrameInspector(),
        renderer=Renderer(),
        frame_reader=Frames(),
        detector=Detector(),
        debug_capture=True,
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    inputs = pipeline._inputs(record(frame_time_ms=500), scratch)
    pipeline._crop_path(inputs)
    trace = [
        json.loads(line) for line in (scratch / "analysis-trace.jsonl").read_text().splitlines()
    ]

    assert [entry["detection"]["detection"]["bounds"]["x"] for entry in trace] == [680, 700, 720]


def test_competing_person_after_loss_is_rejected_until_target_is_reacquired(tmp_path) -> None:
    class Pixels:
        def __init__(self, index: int) -> None:
            self.index = index

    class Frames:
        def read(self, source, metadata):
            return [DecodedFrame(index, index * 500, Pixels(index)) for index in range(3)]

    class ThreeFrameInspector(Inspector):
        def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
            return MediaMetadata(1920, 1080, 1500, 2, "h264", None, 0, False)

    target = Rect(700, 200, 100, 400)

    class Detector:
        def detect(self, pixels: Pixels) -> list[Detection]:
            return {
                0: [Detection(Rect(1500, 200, 100, 400), 0.9)],
                1: [Detection(target, 0.9)],
                2: [Detection(Rect(740, 200, 100, 400), 0.9)],
            }[pixels.index]

    pipeline = ProcessingPipeline(
        Storage(),
        Finalizer(),
        inspector=ThreeFrameInspector(),
        renderer=Renderer(),
        frame_reader=Frames(),
        detector=Detector(),
        debug_capture=True,
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    pipeline._crop_path(pipeline._inputs(record(frame_time_ms=500), scratch))
    trace = [
        json.loads(line) for line in (scratch / "analysis-trace.jsonl").read_text().splitlines()
    ]

    assert trace[0]["detection"]["detection"] is None
    assert trace[0]["detection"]["selection_outcome"] == "no_accepted_candidate"
    assert trace[2]["detection"]["detection"]["bounds"]["x"] == 740


def test_vfr_normalization_stays_job_local_and_reusable(tmp_path) -> None:
    class VFRInspector:
        def inspect(self, path: Path, *, allow_variable_frame_rate: bool = False) -> MediaMetadata:
            if path.name == "source-original" and not allow_variable_frame_rate:
                raise terminal(
                    ErrorCode.VARIABLE_FRAME_RATE, "Variable-frame-rate video is not supported."
                )
            return MediaMetadata(1920, 1080, 1000, Fraction(30, 1), "h264", None, 0, False)

    class Normalizer:
        def __init__(self) -> None:
            self.calls = 0

        def normalize(self, source, destination, frame_rate, audio_stream_index) -> None:
            self.calls += 1
            destination.write_bytes(b"cfr")

    normalizer = Normalizer()
    pipeline = ProcessingPipeline(
        Storage(), Finalizer(), inspector=VFRInspector(), renderer=Renderer(), normalizer=normalizer
    )
    scratch = tmp_path / "job"
    scratch.mkdir()
    assert pipeline._inputs(record(), scratch).source.name == "source-cfr.mp4"
    assert pipeline._inputs(record(), scratch).source.name == "source-cfr.mp4"
    assert normalizer.calls == 1
