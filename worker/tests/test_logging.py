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
