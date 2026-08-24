import type { Evaluation } from '../api'

// Matches the backend's evaluation projection of the worker manifest.
export const evaluationResponseFixture: Evaluation = {
  available: true,
  review_id: '8d3f7cad-e11e-4b74-9cf5-4b0645a8c6e2',
  state: 'completed',
  pipeline_version: 'w0.2.0',
  model_version: 'w0.2-ssd-mobilenetv1-12-onnx-detector-only-1',
  timing: { frame_rate: 60, duration_ms: 12000, frame_count: 720 },
  phases: [
    { id: 'detection', label: 'Detection', status: 'ready', summary: { detected_frames: 691, detection_rate: 0.96 }, video_url: 'https://storage.test/review/detection.mp4?X-Amz-Signature=fixture' },
    { id: 'framing', label: 'Framing', status: 'warning', summary: { missed_frames: 18 }, warning_intervals: [{ start_ms: 4200, end_ms: 5900, label: 'Detection missed', detail: 'The crop widened toward the full frame.' }], video_url: 'https://storage.test/review/framing.mp4?X-Amz-Signature=fixture' },
    { id: 'render', label: 'Render', status: 'ready', summary: { mapping_verified: true, output_valid: true }, video_url: 'https://storage.test/review/render.mp4?X-Amz-Signature=fixture' },
  ],
  telemetry_download_url: 'https://storage.test/review/telemetry.jsonl.gz?X-Amz-Signature=fixture',
  expires_in_seconds: 900,
}
