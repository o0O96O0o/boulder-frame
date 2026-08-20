"""Tracking contracts reserved for the selected-athlete implementation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .errors import ErrorCode, terminal
from .measurement import Point, RawFrameObservation, Rect


class TrackingState(StrEnum):
    TRACKED = "tracked"
    REACQUIRING = "reacquiring"
    LOST = "lost"


@dataclass(frozen=True, slots=True)
class TrackedMeasurement:
    frame_index: int
    root: Point | None
    pose_bounds: Rect | None
    detector_bounds: Rect | None
    confidence: float
    covariance: float | None
    state: TrackingState
    timestamp_ms: int = 0


class TargetTracker(Protocol):
    def track(self, observations: Sequence[RawFrameObservation]) -> list[TrackedMeasurement]: ...


class UnavailableTargetTracker:
    """Avoids presenting planned Kalman behavior as an implemented CV feature."""

    def track(self, observations: Sequence[RawFrameObservation]) -> list[TrackedMeasurement]:
        raise terminal(
            ErrorCode.MODEL_UNAVAILABLE, "Target tracking is not configured for this worker."
        )


@dataclass(frozen=True, slots=True)
class TrackerConfig:
    """Conservative thresholds for a single target in source-pixel coordinates."""

    max_gap_frames: int = 3
    reacquire_confirmations: int = 2
    max_position_error: float = 300.0
    outlier_distance: float = 450.0
    minimum_confidence: float = 0.2
    position_gain: float = 0.65
    velocity_gain: float = 0.35
    process_noise: float = 25.0


class SingleTargetTracker:
    """A one-target alpha-beta filter with guarded loss and reacquisition transitions."""

    def __init__(self, config: TrackerConfig | None = None) -> None:
        self.config = config or TrackerConfig()
        if self.config.max_gap_frames < 0 or self.config.reacquire_confirmations < 1:
            raise ValueError("tracker gap and confirmation settings are invalid")

    def track(self, observations: Sequence[RawFrameObservation]) -> list[TrackedMeasurement]:
        previous_timestamp: int | None = None
        root: Point | None = None
        velocity = Point(0, 0)
        bounds: Rect | None = None
        covariance: float | None = None
        missing_frames = 0
        reacquire_count = 0
        pending_root: Point | None = None
        has_tracked = False
        result: list[TrackedMeasurement] = []

        for observation in observations:
            if previous_timestamp is not None and observation.timestamp_ms <= previous_timestamp:
                raise ValueError("observation timestamps must be strictly increasing")
            dt = (
                1.0
                if previous_timestamp is None
                else (observation.timestamp_ms - previous_timestamp) / 1000
            )
            previous_timestamp = observation.timestamp_ms
            predicted = (
                None if root is None else Point(root.x + velocity.x * dt, root.y + velocity.y * dt)
            )
            candidate = observation.root
            confidence = observation.confidence

            is_valid = candidate is not None and confidence >= self.config.minimum_confidence
            if is_valid and predicted is not None:
                distance = _distance(candidate, predicted)
                limit = (
                    self.config.outlier_distance
                    if missing_frames == 0
                    else self.config.max_position_error
                )
                is_valid = distance <= limit

            if is_valid and candidate is not None:
                if root is None and not has_tracked:
                    root = candidate
                    velocity = Point(0, 0)
                    covariance = self.config.process_noise
                elif root is None:
                    if (
                        pending_root is None
                        or _distance(candidate, pending_root) > self.config.max_position_error
                    ):
                        pending_root = candidate
                        reacquire_count = 1
                    else:
                        reacquire_count += 1
                    if root is None and reacquire_count < self.config.reacquire_confirmations:
                        result.append(
                            self._measurement(
                                observation, None, None, None, TrackingState.REACQUIRING
                            )
                        )
                        continue
                    if root is not None and reacquire_count < self.config.reacquire_confirmations:
                        result.append(
                            self._measurement(
                                observation,
                                predicted,
                                bounds,
                                covariance,
                                TrackingState.REACQUIRING,
                            )
                        )
                        continue
                    root = candidate
                    velocity = Point(0, 0)
                    covariance = self.config.process_noise
                else:
                    assert predicted is not None
                    residual = Point(candidate.x - predicted.x, candidate.y - predicted.y)
                    root = Point(
                        predicted.x + residual.x * self.config.position_gain,
                        predicted.y + residual.y * self.config.position_gain,
                    )
                    velocity = Point(
                        velocity.x + residual.x * self.config.velocity_gain / dt,
                        velocity.y + residual.y * self.config.velocity_gain / dt,
                    )
                    covariance = max(
                        1.0, (covariance or self.config.process_noise) * (1 - confidence)
                    )
                bounds = observation.pose_bounds or observation.detector_bounds
                missing_frames = 0
                pending_root = None
                reacquire_count = 0
                has_tracked = True
                result.append(
                    self._measurement(observation, root, bounds, covariance, TrackingState.TRACKED)
                )
                continue

            missing_frames += 1
            reacquire_count = 0
            pending_root = None
            if root is not None and missing_frames <= self.config.max_gap_frames:
                root = predicted
                covariance = (covariance or self.config.process_noise) + self.config.process_noise
                result.append(
                    self._measurement(
                        observation, root, bounds, covariance, TrackingState.REACQUIRING
                    )
                )
            else:
                root = None
                bounds = None
                covariance = None
                result.append(self._measurement(observation, None, None, None, TrackingState.LOST))
        return result

    @staticmethod
    def _measurement(
        observation: RawFrameObservation,
        root: Point | None,
        bounds: Rect | None,
        covariance: float | None,
        state: TrackingState,
    ) -> TrackedMeasurement:
        return TrackedMeasurement(
            frame_index=observation.frame_index,
            root=root,
            pose_bounds=observation.pose_bounds if state is TrackingState.TRACKED else None,
            detector_bounds=(
                observation.detector_bounds if state is TrackingState.TRACKED else bounds
            ),
            confidence=observation.confidence if state is TrackingState.TRACKED else 0,
            covariance=covariance,
            state=state,
            timestamp_ms=observation.timestamp_ms,
        )


def _distance(left: Point, right: Point) -> float:
    return ((left.x - right.x) ** 2 + (left.y - right.y) ** 2) ** 0.5
