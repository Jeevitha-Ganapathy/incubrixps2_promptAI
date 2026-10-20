from pathlib import Path
import os

def setting(name: str, default: str) -> str:
    return os.getenv(name, default)

OUTPUT_DIR = Path(setting("OUTPUT_DIR", "outputs"))
UPLOAD_DIR = Path(setting("UPLOAD_DIR", "uploads"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FFMPEG = setting("FFMPEG_BIN", "ffmpeg")
FFPROBE = setting("FFPROBE_BIN", "ffprobe")
MAX_UPLOAD_MB = int(setting("MAX_UPLOAD_MB", "2048"))
DEFAULT_FPS = float(setting("DEFAULT_FPS", "30"))
