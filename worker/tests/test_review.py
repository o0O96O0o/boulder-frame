import shutil
import shutil
import subprocess
from fractions import Fraction
from importlib.util import find_spec

import pytest

from boulder_frame_worker import review
from boulder_frame_worker.frame_reader import OpenCVFrameReader
from boulder_frame_worker.media import MediaMetadata
from boulder_frame_worker.review import PHASES, ReviewLimits, ReviewRenderer, phase_annotations


def test_review_manifest_marks_all_phases_unavailable_above_duration_limit(tmp_path) -> None:
    renderer = ReviewRenderer("missing-ffmpeg", ReviewLimits(10, 320, 180, 1024, 1))
    metadata = MediaMetadata(160, 90, 11, Fraction(1, 1), "h264", None, 0, False)

    phases = renderer.render(
        tmp_path / "source.mp4",
        tmp_path / "output.mp4",
        metadata,
        [],
        tmp_path / "review",
    )

    assert phases == {
        phase: {"status": "unavailable", "detail": "duration_limit"} for phase in PHASES
    }


def test_review_renderer_writes_synchronized_no_audio_phase_media(tmp_path) -> None:
    if shutil.which("ffmpeg") is None or find_spec("cv2") is None:
        pytest.skip("FFmpeg and OpenCV are required for review-media integration tests")
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:size=160x90:rate=2:duration=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    output.write_bytes(source.read_bytes())
    metadata = MediaMetadata(160, 90, 1000, Fraction(2, 1), "h264", None, 0, False)
    trace = [
        {
            "record_type": "frame",
            "frame_index": index,
            "timestamp_ms": index * 500,
            "measurement": {"detection": {"bounds": {"x": 20, "y": 10, "width": 40, "height": 60}}},
            "tracking": {"root": {"x": 40, "y": 40}},
            "planning": {"crop": {"x": 0, "y": 0, "width": 160, "height": 90}},
        }
        for index in range(2)
    ]
    renderer = ReviewRenderer("ffmpeg", ReviewLimits(2000, 320, 180, 10_000_000, 30))
    phases = renderer.render(source, output, metadata, trace, tmp_path / "review")
    reader = OpenCVFrameReader()

    for phase in PHASES:
        path = tmp_path / "review" / f"{phase}.mp4"
        assert phases[phase]["status"] == "ready"
        phase_metadata = MediaMetadata(320, 180, 1000, Fraction(2, 1), "h264", None, 0, False)
        assert len(list(reader.read(path, phase_metadata))) == 2


def test_phase_annotations_use_authoritative_phase_trace_values() -> None:
    record = {
        "timestamp_ms": 250,
        "measurement": {
            "detection": {"confidence": 0.9},
            "pose": {"confidence": 0.8, "landmarks": [{}, {}]},
        },
        "tracking": {"state": "reacquiring", "confidence": 0.7, "reacquired": True},
        "planning": {
            "decision": {
                "containment_risk": True,
                "zoom_action": "out",
                "uncertainty_padding": 12.5,
            }
        },
        "render": {"mapping_independently_verified": False},
    }

    assert phase_annotations(record, "measurement", 3)[1] == "selection=unavailable confidence=0.9"
    assert phase_annotations(record, "pose", 3)[1] == "pose confidence=0.8 landmarks=2"
    assert (
        "state=reacquiring confidence=0.7 reacquired=True"
        in phase_annotations(record, "tracking", 3)[1]
    )
    assert "containment_risk=True zoom_action=out" in phase_annotations(record, "planning", 3)[1]
    assert phase_annotations(record, "render", 3)[1] == "mapping_verified=False output_valid=False"


def test_source_geometry_scales_and_clips_into_a_1080p_render_pane() -> None:
    transform = review._PaneTransform(3840, 2160, 0, 0, 1920, 1080)

    assert transform.point({"x": 1920, "y": 1080}) == (960, 540)
    assert transform.point({"x": -1, "y": 3000}) == (0, 1079)
    assert transform.rect({"x": 1920, "y": 1080, "width": 960, "height": 540}) == (
        (960, 540),
        (1440, 810),
    )


def test_phase_annotations_draw_trace_evidence_in_source_coordinate_panes() -> None:
    if find_spec("cv2") is None:
        pytest.skip("OpenCV is required for overlay tests")
    import cv2
    import numpy as np

    pixels = np.zeros((200, 400, 3), dtype=np.uint8)
    output = np.zeros((100, 200, 3), dtype=np.uint8)
    landmarks = [{"x": 100 + index, "y": 80 + index} for index in range(33)]
    record = {
        "timestamp_ms": 0,
        "measurement": {
            "detection": {
                "bounds": {"x": 100, "y": 50, "width": 80, "height": 120},
                "confidence": 0.9,
            },
            "selection": {"selected": True, "state": "tap_match", "marker": {"x": 120, "y": 70}},
            "pose": {
                "bounds": {"x": 110, "y": 60, "width": 60, "height": 100},
                "landmarks": landmarks,
                "root": {"x": 140, "y": 130},
                "confidence": 0.8,
            },
        },
        "tracking": {
            "pose_bounds": {"x": 110, "y": 60, "width": 60, "height": 100},
            "root": {"x": 140, "y": 130},
            "covariance": 64,
            "state": "tracked",
            "confidence": 0.8,
            "reacquired": True,
        },
        "planning": {
            "input": {
                "bounds": None,
                "detector_bounds": {"x": 100, "y": 50, "width": 80, "height": 120},
                "root": {"x": 140, "y": 130},
            },
            "crop": {"x": 40, "y": 20, "width": 240, "height": 135},
            "decision": {
                "envelope": {"x": 90, "y": 40, "width": 120, "height": 140},
                "lead_room": {"x": 30, "y": 0},
                "zoom_action": "zoom_out",
            },
        },
        "render": {
            "crop": {"x": 200, "y": 100, "width": 160, "height": 90},
            "mapping_independently_verified": True,
            "output_validated": True,
        },
    }
    prior = [{"tracking": {"root": {"x": 120, "y": 120}}}, record]

    measurement = ReviewRenderer._annotate(cv2, np, pixels, record, "measurement", 0, None, prior)
    pose = ReviewRenderer._annotate(cv2, np, pixels, record, "pose", 0, None, prior)
    tracking = ReviewRenderer._annotate(cv2, np, pixels, record, "tracking", 0, None, prior)
    planning = ReviewRenderer._annotate(cv2, np, pixels, record, "planning", 0, None, prior)
    rendering = ReviewRenderer._annotate(cv2, np, pixels, record, "render", 0, output, prior)

    assert tuple(measurement[50, 100]) == (0, 220, 255)  # selected detector box
    assert tuple(measurement[70, 120]) == (0, 0, 255)  # selection marker
    assert tuple(pose[60, 110]) == (255, 0, 255)  # pose bounds/skeleton
    assert tuple(tracking[130, 140]) == (0, 0, 255)  # reacquisition marker
    assert tuple(planning[40, 90]) == (255, 0, 255)  # composed envelope
    assert tuple(rendering[100, 200]) == (255, 255, 0)  # source crop stays in the left pane
    assert tuple(rendering[50, 500]) == (0, 0, 0)  # no source geometry leaks into output pane


@pytest.mark.parametrize(
    ("output_shape", "output_pixel", "output_point", "matte_point"),
    [
        ((90, 160, 3), (0, 255, 0), (240, 90), (240, 10)),
        ((160, 90, 3), (0, 255, 0), (240, 90), (170, 90)),
    ],
)
def test_render_comparison_letterboxes_each_pane_and_maps_source_crop(
    output_shape, output_pixel, output_point, matte_point
) -> None:
    if find_spec("cv2") is None:
        pytest.skip("OpenCV is required for overlay tests")
    import cv2
    import numpy as np

    source = np.full((200, 400, 3), (255, 0, 0), dtype=np.uint8)
    output = np.full(output_shape, output_pixel, dtype=np.uint8)
    record = {
        "timestamp_ms": 0,
        "render": {
            "crop": {"x": 100, "y": 50, "width": 100, "height": 100},
            "mapping_independently_verified": False,
        },
    }

    frame = ReviewRenderer._annotate(
        cv2, np, source, record, "render", 0, output, (), (320, 180)
    )

    assert frame.shape == (180, 320, 3)
    assert tuple(frame[70, 40]) == (255, 255, 0)  # source crop maps into its letterboxed pane
    assert tuple(frame[90, 20]) == (255, 0, 0)  # source pane retains its 2:1 pixels
    assert tuple(frame[output_point[1], output_point[0]]) == output_pixel
    assert tuple(frame[matte_point[1], matte_point[0]]) == (0, 0, 0)


def test_review_deadline_is_total_and_expires_without_waiting_for_another_ffmpeg_call(
    monkeypatch,
) -> None:
    monkeypatch.setattr(review.time, "monotonic", lambda: 10.0)

    with pytest.raises(subprocess.TimeoutExpired):
        review._remaining_seconds(10.0)


def test_review_decode_timeout_terminates_blocked_process_without_waiting(monkeypatch, tmp_path) -> None:
    class BlockedProcess:
        pid = None

        def join(self, timeout) -> None:
            assert timeout == 1

        def is_alive(self) -> bool:
            return True

    terminated = []
    monkeypatch.setattr(review, "_review_process", lambda *args: BlockedProcess())
    monkeypatch.setattr(review, "_terminate_process", lambda process: terminated.append(process))
    monkeypatch.setattr(review, "_remaining_seconds", lambda deadline: 1)
    renderer = ReviewRenderer("ffmpeg", ReviewLimits(1000, 320, 180, 1_000_000, 1))
    metadata = MediaMetadata(160, 90, 1000, Fraction(1, 1), "h264", None, 0, False)

    with pytest.raises(review._ReviewTimeout):
        renderer._render_phase(
            tmp_path / "source.mp4",
            tmp_path / "output.mp4",
            metadata,
            [],
            tmp_path / "render.mp4",
            "render",
            99,
        )

    assert len(terminated) == 1


def test_review_unavailable_reason_never_exposes_arbitrary_exception_text() -> None:
    assert (
        review._reason(ValueError("https://storage.example/private/debug/token")) == "unavailable"
    )
