from copy import deepcopy

import pytest

from boulder_frame_worker.errors import ErrorCode, WorkerError
from boulder_frame_worker.media import metadata_from_ffprobe, validate_output
from boulder_frame_worker.protocol import AspectRatio


def probe_payload() -> dict[str, object]:
    return {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "42.0"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 3840,
                "height": 2160,
                "avg_frame_rate": "60/1",
                "r_frame_rate": "60/1",
                "tags": {"rotate": "90"},
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }


def test_valid_cfr_mp4_metadata_includes_rotation() -> None:
    metadata = metadata_from_ffprobe(probe_payload())

    assert (metadata.width, metadata.height, metadata.duration_ms) == (3840, 2160, 42000)
    assert str(metadata.frame_rate) == "60"
    assert metadata.rotation == 90
    assert metadata.display_dimensions == (2160, 3840)
    assert metadata.frame_for_time_ms(500) == 30
    assert metadata.audio_codec == "aac"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda data: data["streams"].pop(0), ErrorCode.MISSING_VIDEO_STREAM),
        (
            lambda data: data["streams"][0].update(codec_name="hevc"),
            ErrorCode.UNSUPPORTED_VIDEO_CODEC,
        ),
        (
            lambda data: data["streams"][0].update(avg_frame_rate="30000/1001"),
            ErrorCode.VARIABLE_FRAME_RATE,
        ),
        (
            lambda data: data["streams"][1].update(codec_name="mp3"),
            ErrorCode.UNSUPPORTED_AUDIO_CODEC,
        ),
        (
            lambda data: data["format"].update(format_name="matroska,webm"),
            ErrorCode.UNSUPPORTED_CONTAINER,
        ),
    ],
)
def test_invalid_media_is_classified(mutation: object, code: ErrorCode) -> None:
    data = deepcopy(probe_payload())
    mutation(data)  # type: ignore[operator]

    with pytest.raises(WorkerError) as raised:
        metadata_from_ffprobe(data)

    assert raised.value.code is code


def test_output_validation_requires_selected_dimensions() -> None:
    metadata = metadata_from_ffprobe(probe_payload())
    with pytest.raises(WorkerError) as raised:
        validate_output(metadata, AspectRatio.LANDSCAPE)

    assert raised.value.code is ErrorCode.INVALID_OUTPUT
