# IncuBrix Prompt-Based Video Editing Engine

A runnable, deterministic reference implementation for the IncuBrix Assessment 2. It uses **source-time anchors** so annotations/effects belong to original content, a reversible edit history, FFmpeg rendering, FastAPI, a session runner, and automated tests.

> Important: this is an engineering submission project, not a claim that every advanced assessment target has already been independently verified. Speech transcription and semantic intent resolution are adapters; by default the project uses a deterministic rule-based parser and supplied transcript. Read `REPORT.md` and `LIMITATIONS.md` before completing the submission workbook.

## Features
- MP4/MOV intake via upload or local path; FFprobe metadata and SHA-256 source fingerprint.
- Deterministic source-anchored timeline with cut/keep/speed/reorder/caption/mute/bleep/music, undo, redo, and restore-by-history-step.
- Three-way instruction response: `applied`, `needs_clarification`, `rejected`.
- Plain-language deterministic parser for common time-based commands. No LLM is required to run tests.
- FFmpeg renderer, SRT subtitle generation, audio mute/bleep filters, render manifest and duration/sync probe.
- FastAPI routes under `/api/v1`, idempotency keys, job status/progress, health/readiness, structured errors/logging.
- CLI session runner, OpenAPI 3.1 schema, JSON Schema timeline, OpenTimelineIO JSON export, 40+ deterministic test scenarios.
- Docker Compose with API and MinIO service. Outputs are stored in `outputs/` by default; MinIO is available for integration extension.

## Requirements
- Python 3.11+
- FFmpeg + FFprobe installed and available on PATH for real media rendering.
- Docker Desktop (optional; for container run).

## Windows PowerShell quick start
```powershell
cd incubrix_video_editing_engine
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m pytest -q
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000/docs`.

## Linux / Ubuntu quick start
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m pytest -q
uvicorn app.main:app --reload
```

## Docker
```bash
docker compose up --build
```
Run tests in another terminal with `docker compose exec api pytest -q`.

## Basic API flow
1. `POST /api/v1/sessions` with JSON `{ "source_path": "/absolute/path/video.mp4" }` (local path must be accessible to service) or multipart `POST /api/v1/sessions/upload`.
2. `POST /api/v1/sessions/{session_id}/instructions` with `{ "instruction": "cut 00:00:10 to 00:00:15" }` and `Idempotency-Key` header.
3. `GET /api/v1/sessions/{session_id}/timeline`.
4. `POST /api/v1/sessions/{session_id}/render` returns a job ID.
5. `GET /api/v1/jobs/{job_id}` until succeeded; output is under `outputs/` and linked in result.

For tests that don't need media, create a synthetic timeline using `POST /api/v1/sessions/demo` with duration seconds. See `examples/session.json` and `runner/session_runner.py`.

## Session runner
```bash
python -m runner.session_runner examples/session.json --output outputs/demo-run
```
The runner records one JSON result per step, final timeline, hash, and a report. A video render requires a real `video` path.

## Timeline semantics
- Time references are **original source time**. Responses state this policy. After cuts/reorders, an operation targeting original source seconds affects that original content wherever it currently appears.
- Each segment refers to `[source_start, source_end)` and a speed factor. Captions/effects are anchored to original source ranges, not current timeline positions.
- A caption is omitted from rendered segments if its entire anchor was cut. Partial overlap clips the caption to the surviving portion and emits a warning in timeline projection.
- Reorder uses explicit source-time ranges and moves the selected currently-visible range to the requested current segment index.
- A new edit clears redo. One successful instruction is one undo step. Restore uses a stored history snapshot.
- Determinism is defined by canonical JSON and stable IDs, not runtime UUIDs.

## API / errors
OpenAPI is served at `/openapi.json` (OpenAPI 3.1). Errors use `{ "error": {"code":"...", "message":"...", "retryable":false, "details":{}} }`. Supported codes are documented in `ERROR_CODES.md`.

## Honest evaluation
Run `python -m pytest -q` and `python -m runner.scenario_suite`. Record actual FFmpeg render measurements on your own media before claiming render accuracy, latency, cost, or word-clipping metrics. See `REPORT.md`, `AI_USE.md`, `SOURCES.md`, and `LIMITATIONS.md`.
