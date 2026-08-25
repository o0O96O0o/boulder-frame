import json
import logging
import sys

from boulder_frame_worker.logging import JsonFormatter


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
