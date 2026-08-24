# Manifest and Reliability Review

Final review found the following issues despite passing local suites.

1. The worker omits root `pipeline_version`, `model_version`, and `timing` from its manifest. The backend requires them, so every worker-created review is returned as unavailable.
2. A subprocess can escape review-deadline cleanup if the deadline expires after child start but before joining. Always terminate and close a live child in the cleanup path.
3. The pipeline writes a full diagnostic trace even when debug capture is disabled and without debug capture bounds. Scratch failure can therefore fail a product job. Keep a minimal required render trace distinct from optional bounded diagnostic evidence, and make optional writes safe.
4. Backend and frontend accept warning intervals beyond `timing.duration_ms`. Reject those invalid ranges in both validation layers.

Documentation also needs to consistently describe root manifest metadata and the final trace contract.

No corrections from this review have been applied.
