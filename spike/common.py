"""Shared helpers for the spike: audio loading, timing/RAM measurement, result saving."""
from __future__ import annotations

import json
import subprocess
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import psutil

ROOT = Path(__file__).parent
AUDIO_DIR = ROOT / "audio"
RESULTS_DIR = ROOT / "results"
SAMPLE_RATE = 16_000


def load_audio(path: Path) -> np.ndarray:
    """Decode any audio/video file to 16 kHz mono float32 using FFmpeg."""
    cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path),
        "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-",
    ]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


def normalize_to_wav(path: Path) -> Path:
    """Write a 16 kHz mono WAV next to the results (needed by pyannote)."""
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{path.stem}.16k.wav"
    if not out.exists():
        subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(path),
             "-ac", "1", "-ar", str(SAMPLE_RATE), str(out)],
            check=True,
        )
    return out


def audio_files() -> list[Path]:
    exts = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".mp4", ".aac", ".opus"}
    return sorted(p for p in AUDIO_DIR.iterdir() if p.suffix.lower() in exts)


@dataclass
class Measurement:
    seconds: float = 0.0
    peak_rss_mb: float = 0.0
    extra: dict = field(default_factory=dict)


@contextmanager
def measure():
    """Measure wall time and peak resident memory of this process during the block."""
    proc = psutil.Process()
    m = Measurement()
    peak = [proc.memory_info().rss]
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            peak[0] = max(peak[0], proc.memory_info().rss)
            time.sleep(0.2)

    t = threading.Thread(target=sample, daemon=True)
    t.start()
    start = time.perf_counter()
    try:
        yield m
    finally:
        m.seconds = round(time.perf_counter() - start, 2)
        stop.set()
        t.join()
        m.peak_rss_mb = round(peak[0] / 1_048_576, 1)


def save_json(name: str, data) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / name
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
