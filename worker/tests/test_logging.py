import json
import logging
import sys
from pathlib import Path

from boulder_frame_worker.logging import JsonFormatter, log_context


def test_json_formatter_records_unhandled_exception_type_and_message() -> None:
    logger = logging.getLogger("test_json_formatter")
    try:
        raise ValueError("ROI has no pixels")
    except ValueError:
        record = logger.makeRecord(
            logger.name,
            logging.ERROR,
            __file__,
            0,
            "task response",
            (),
            exc_info=sys.exc_info(),
        )

    event = json.loads(JsonFormatter().format(record))

    assert event["error"] == {"message": "ROI has no pixels", "type": "ValueError"}


def test_json_formatter_redacts_unhandled_exception_details(tmp_path: Path) -> None:
    logger = logging.getLogger("test_json_formatter")
    scratch = tmp_path / "job"
    try:
        raise RuntimeError(
            f"decoder failed at {scratch / 'output.mp4'} "
            "https://objects.example/output?signature=secret password=secret"
        )
    except RuntimeError:
        record = logger.makeRecord(
            logger.name,
            logging.ERROR,
            __file__,
            0,
            "task response",
            (),
            exc_info=sys.exc_info(),
            extra={"scratch_path": scratch},
        )

    event = json.loads(JsonFormatter().format(record))

    assert event["error"] == {
        "message": ("decoder failed at <scratch>/output.mp4 <redacted-url> password=<redacted>"),
        "type": "RuntimeError",
    }


def test_json_formatter_records_internal_diagnostics() -> None:
    logger = logging.getLogger("test_json_formatter")
    record = logger.makeRecord(
        logger.name,
        logging.ERROR,
        __file__,
        0,
        "task response",
        (),
        None,
        extra={"diagnostic": "FFmpeg rejected the filter script."},
    )

    event = json.loads(JsonFormatter().format(record))

    assert event["diagnostic"] == "FFmpeg rejected the filter script."


def test_json_formatter_records_stage_duration() -> None:
    logger = logging.getLogger("test_json_formatter")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        0,
        "stage response",
        (),
        None,
        extra={"stage": "analyzing", "duration_ms": 123},
    )

    event = json.loads(JsonFormatter().format(record))

    assert event["stage"] == "analyzing"
    assert event["duration_ms"] == 123


def test_json_formatter_records_output_frame_progress() -> None:
    logger = logging.getLogger("test_json_formatter")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        0,
        "render output progress",
        (),
        None,
        extra={
            "output_frame_count": 627,
            "repeated_output_frame_count": 5,
            "repeated_output_frame_intervals": [{"start_frame": 84, "end_frame": 88}],
            "planned_crop_count": 473,
        },
    )

    event = json.loads(JsonFormatter().format(record))

    assert event["output_frame_count"] == 627
    assert event["repeated_output_frame_count"] == 5
    assert event["repeated_output_frame_intervals"] == [{"start_frame": 84, "end_frame": 88}]
    assert event["planned_crop_count"] == 473


def test_json_formatter_records_temporal_progress() -> None:
    logger = logging.getLogger("test_json_formatter")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        0,
        "render temporal progress",
        (),
        None,
        extra={
            "render_input_was_normalized": True,
            "render_input_frame_count": 627,
            "render_input_near_static_frame_count": 74,
            "render_input_near_static_intervals": [{"start_frame": 444, "end_frame": 518}],
            "planned_crop_near_static_frame_count": 74,
            "planned_crop_near_static_intervals": [{"start_frame": 444, "end_frame": 518}],
            "output_near_static_frame_count": 74,
            "output_near_static_intervals": [{"start_frame": 444, "end_frame": 518}],
        },
    )

    event = json.loads(JsonFormatter().format(record))

    assert event["render_input_was_normalized"] is True
    assert event["render_input_near_static_intervals"] == [{"start_frame": 444, "end_frame": 518}]
    assert event["planned_crop_near_static_frame_count"] == 74
    assert event["output_near_static_frame_count"] == 74


def test_json_formatter_inherits_stage_correlation_context() -> None:
    logger = logging.getLogger("test_json_formatter")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        0,
        "render output progress",
        (),
        None,
    )

    with log_context(trace_id="trace-42", job_id="job-7", stage="rendering"):
        event = json.loads(JsonFormatter().format(record))

    assert event["trace-id"] == "trace-42"
    assert event["job_id"] == "job-7"
    assert event["stage"] == "rendering"


def test_json_formatter_records_configuration_loading_details() -> None:
    logger = logging.getLogger("test_json_formatter")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        0,
        "configuration loaded",
        (),
        None,
        extra={
            "config_path": "/workspace/worker/conf/config.json",
            "configuration": {"model_version": "unconfigured"},
        },
    )

    event = json.loads(JsonFormatter().format(record))

    assert event["config_path"] == "/workspace/worker/conf/config.json"
    assert event["configuration"] == {"model_version": "unconfigured"}
