import type { Evaluation } from '../api'

// Matches the backend's evaluation projection of the worker manifest.
export const evaluationResponseFixture: Evaluation = {
  available: true,
  review_id: '8d3f7cad-e11e-4b74-9cf5-4b0645a8c6e2',
  state: 'completed',
  pipeline_version: 'w0.1.0',
  model_version: 'w0.1-model',
  timing: { frame_rate: 60, duration_ms: 12000, frame_count: 720 },
  phases: [
    { id: 'measurement', label: 'Measurement', status: 'ready', summary: { selected_rate: 0.96 }, video_url: 'https://storage.test/review/measurement.mp4?X-Amz-Signature=fixture' },
    { id: 'pose', label: 'Pose', status: 'warning', summary: { pose_available_rate: 0.93, warning_frames: 18 }, warning_intervals: [{ start_ms: 4200, end_ms: 5900, label: 'Low confidence', detail: 'Pose landmarks were intermittently unavailable.' }], video_url: 'https://storage.test/review/pose.mp4?X-Amz-Signature=fixture' },
    { id: 'tracking', label: 'Tracking', status: 'partial', summary: { reacquisitions: 1 }, warning_intervals: [{ start_ms: 8600, label: 'Reacquired', detail: 'Tracking resumed after a brief occlusion.' }], video_url: 'https://storage.test/review/tracking.mp4?X-Amz-Signature=fixture' },
    { id: 'planning', label: 'Planning', status: 'unavailable', summary: { planned_frames: 0 }, detail: 'Planning evidence was not captured for this review run.' },
    { id: 'render', label: 'Render', status: 'ready', summary: { mapping_verified: true, output_valid: true }, video_url: 'https://storage.test/review/render.mp4?X-Amz-Signature=fixture' },
  ],
  telemetry_download_url: 'https://storage.test/review/telemetry.jsonl.gz?X-Amz-Signature=fixture',
  expires_in_seconds: 900,
}
