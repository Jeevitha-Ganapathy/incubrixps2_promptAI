# Error codes
- `INPUT_NOT_FOUND`: supplied source path does not exist.
- `INVALID_MEDIA`: FFprobe cannot read the source or no video stream exists.
- `UNSUPPORTED_MEDIA`: upload extension is not supported.
- `UPLOAD_TOO_LARGE`: upload exceeds `MAX_UPLOAD_MB`.
- `INVALID_DURATION`: synthetic demo duration is invalid.
- `JOB_NOT_FOUND`: unknown background job ID.
- `RENDER_FAILED`: FFmpeg render failed; see job error message.
- `INTERNAL_ERROR`: unexpected server error; retryable.
- `IDEMPOTENCY_CONFLICT`: reserved for incompatible same-key requests (TODO to enforce payload matching).
