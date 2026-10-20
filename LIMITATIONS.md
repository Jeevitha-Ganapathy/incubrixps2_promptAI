# Known limitations — read before making claims
1. The default instruction parser is rule-based and only handles explicit supported phrasing; semantic transcript search and production ASR are adapter work, not magically inferred.
2. Rendering requires FFmpeg. Audio-less inputs may fail in current renderer because the filter graph assumes an audio stream; API should return a clear render error.
3. Caption overlay uses FFmpeg drawtext and requires a compatible font/build. Font/color values should be validated before untrusted inputs are accepted.
4. Music is represented in timeline schema but mixing/ducking is not implemented in renderer yet.
5. Bleep filter support depends on FFmpeg filter graph support; validate output with test media.
6. The API's job store and idempotency cache are in-memory; not durable across restart or multiple workers. MinIO is started by Compose but result upload to MinIO is not yet wired.
7. Callback URL/HMAC callback delivery, rate limits, auth, and URL-fetch intake are not implemented.
8. Reorder is limited to complete visible segments aligned to source ranges. It is not a full nonlinear editor.
9. Word-level transcript, diarization, VFR normalization, silence snapping, filler detection, and robust overlapping-speaker correction require an STT/VAD/diarization adapter and validation.
10. OpenTimelineIO export is a simplified JSON structure and must be validated with the OTIO library before claiming interoperability.
11. Frame-level A/V sync accuracy, latency on 60-minute videos, word clipping, and cost have not been measured.
12. Test suite includes deterministic unit/hard-case coverage but does not establish all assessment claims. Expand with actual media end-to-end scenarios before submission.
