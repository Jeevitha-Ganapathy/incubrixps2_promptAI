from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from .config import FFMPEG, FFPROBE, OUTPUT_DIR
from .models import Timeline


def run(cmd):
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if p.returncode:
        raise RuntimeError(p.stderr[-3000:])
    return p.stdout


def probe(path):
    data = json.loads(run([
        FFPROBE, "-v", "error",
        "-show_format", "-show_streams",
        "-of", "json", str(path)
    ]))

    video = next(
        (s for s in data.get("streams", [])
         if s.get("codec_type") == "video"),
        None
    )
    audio = next(
        (s for s in data.get("streams", [])
         if s.get("codec_type") == "audio"),
        None
    )

    if not video:
        raise ValueError("Input contains no video stream")

    fpss = video.get("avg_frame_rate", "30/1").split("/")
    fps = float(fpss[0]) / float(fpss[1] or 1)

    duration = data.get("format", {}).get(
        "duration", video.get("duration", 0)
    )

    return {
        "duration_s": float(duration),
        "fps": fps,
        "width": int(video["width"]),
        "height": int(video["height"]),
        "has_audio": audio is not None,
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None
    }


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def project_annotations(tl: Timeline):
    out = []
    cursor = 0.0

    for seg in tl.segments:
        for cap in tl.captions:
            a = max(seg.source_start, cap.anchor_start)
            b = min(seg.source_end, cap.anchor_end)

            if b > a:
                start = cursor + (a - seg.source_start) / seg.speed
                end = cursor + (b - seg.source_start) / seg.speed
                out.append({
                    "id": cap.id,
                    "text": cap.text,
                    "start": start,
                    "end": end,
                    "color": cap.color,
                    "size": cap.size
                })

        cursor += seg.duration

    return out


def _atempo(speed):
    # FFmpeg atempo accepts speeds from 0.5 to 2 per filter.
    vals = []
    x = speed

    while x > 2:
        vals.append(2.0)
        x /= 2

    while x < 0.5:
        vals.append(0.5)
        x /= 0.5

    vals.append(x)
    return ",".join(f"atempo={v:.8f}" for v in vals)


def render_timeline(tl: Timeline, output_path=None):
    if not tl.source_path or not Path(tl.source_path).exists():
        raise ValueError("A real source_path is required to render")

    output_path = Path(
        output_path or (OUTPUT_DIR / f"render_{tl.source_id}.mp4")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not tl.segments:
        raise ValueError("Cannot render an empty timeline")

    source_meta = probe(tl.source_path)
    has_audio = source_meta["has_audio"]

    filters = []
    labels = []

    for i, s in enumerate(tl.segments):
        filters.append(
            f"[0:v]trim=start={s.source_start:.6f}:"
            f"end={s.source_end:.6f},"
            f"setpts=(PTS-STARTPTS)/{s.speed:.8f}[v{i}]"
        )

        if has_audio:
            filters.append(
                f"[0:a]atrim=start={s.source_start:.6f}:"
                f"end={s.source_end:.6f},"
                f"asetpts=PTS-STARTPTS,"
                f"{_atempo(s.speed)}[a{i}]"
            )
            labels.append(f"[v{i}][a{i}]")
        else:
            labels.append(f"[v{i}]")

    if has_audio:
        filters.append(
            "".join(labels)
            + f"concat=n={len(tl.segments)}:v=1:a=1[vcat][acat]"
        )
    else:
        filters.append(
            "".join(labels)
            + f"concat=n={len(tl.segments)}:v=1:a=0[vcat]"
        )

    # Overlay captions on the output timeline.
    vlabel = "vcat"

    for j, c in enumerate(project_annotations(tl)):
        txt = (
            c["text"]
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(":", "\\:")
            .replace("%", "\\%")
        )

        nxt = f"vcap{j}"
        filters.append(
            f"[{vlabel}]drawtext=text='{txt}':"
            f"fontcolor={c['color']}:fontsize={c['size']}:"
            f"x=(w-text_w)/2:y=h-text_h-40:"
            f"enable='between(t,{c['start']:.6f},{c['end']:.6f})'"
            f"[{nxt}]"
        )
        vlabel = nxt

    # Apply audio effects only when the source contains audio.
    if has_audio:
        cursor = 0.0
        audio_filters = []

        for seg in tl.segments:
            for eff in tl.effects:
                a = max(seg.source_start, eff.anchor_start)
                b = min(seg.source_end, eff.anchor_end)

                if b > a:
                    audio_filters.append((
                        cursor + (a - seg.source_start) / seg.speed,
                        cursor + (b - seg.source_start) / seg.speed,
                        eff.kind
                    ))

            cursor += seg.duration

        alabel = "acat"

        for j, (a, b, kind) in enumerate(audio_filters):
            nxt = f"afx{j}"

            if kind == "mute":
                filters.append(
                    f"[{alabel}]volume=0:"
                    f"enable='between(t,{a:.6f},{b:.6f})'[{nxt}]"
                )
            else:
                sil = f"asil{j}"
                delay = max(0, round(a * 1000))

                filters.append(
                    f"[{alabel}]volume=0:"
                    f"enable='between(t,{a:.6f},{b:.6f})'[{sil}]"
                )
                filters.append(
                    f"sine=frequency=1000:sample_rate=48000:"
                    f"duration={max(.01, b-a):.6f},"
                    f"adelay={delay}|{delay}[tone{j}]"
                )
                filters.append(
                    f"[{sil}][tone{j}]amix=inputs=2:"
                    f"duration=first:dropout_transition=0[{nxt}]"
                )

            alabel = nxt

    graph = ";".join(filters)

    cmd = [
        FFMPEG, "-y",
        "-i", tl.source_path,
        "-filter_complex", graph,
        "-map", f"[{vlabel}]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-movflags", "+faststart"
    ]

    if has_audio:
        cmd.extend(["-map", f"[{alabel}]", "-c:a", "aac"])
    else:
        cmd.append("-an")

    cmd.append(str(output_path))

    run(cmd)
    info = probe(output_path)

    manifest = {
        "source_hash": tl.source_hash,
        "timeline_hash": tl.timeline_hash,
        "output": str(output_path),
        "timeline_duration_s": tl.duration,
        "render_duration_s": info["duration_s"],
        "fps": info["fps"],
        "av_sync_frame_measurement":
            "Not independently measured; use ffprobe/audio waveform check",
        "warnings": (
            ["Source has no audio; output is video-only."]
            if not has_audio else []
        ),
        "models": [],
        "settings": {
            "fps": tl.fps,
            "segments": len(tl.segments)
        },
        "seed": 0,
        "cost_estimate_usd": 0,
        "rights": "Caller must confirm rights to source and music."
    }

    mp = output_path.with_suffix(".manifest.json")
    mp.write_text(json.dumps(manifest, indent=2))

    return {
        "path": str(output_path),
        "probe": info,
        "manifest": str(mp),
        "manifest_data": manifest
    }
