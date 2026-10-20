# Engineering report (fill measured results before submission)

## Design
Original media is read-only. A timeline is a deterministic list of source-range segments plus content-anchored captions and audio effects. Timeline operations are pure data transformations and rendering is a separate FFmpeg step. Source-time policy is used consistently.

## Local verification
Run `python -m pytest -q` and `python -m runner.scenario_suite`. Copy actual console output here. Do not report results that were not run.

## Metrics
| Metric | Result | Method / hardware |
|---|---|---|
| 5-minute instruction median / slowest | Not measured | Record actual runs |
| 60-minute instruction median / slowest | Not measured | Record actual runs |
| Maximum A/V offset | Not measured | Inspect rendered test media at frame level |
| Maximum duration difference | Not measured | Compare ffprobe duration and timeline frame count |
| Determinism across 3 runs | Not measured | Compare `timeline_hash` for same fixed session |
| Word clipping in 20 cuts | Not measured | Human listening review |
| STT/LLM cost per edited minute | $0 for deterministic parser; STT not integrated | No paid provider called by default |

## Known limitations
See `LIMITATIONS.md`. The submission workbook must mark partial/no wherever evidence is missing.
