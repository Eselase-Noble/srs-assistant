"""Speaker diarization (who spoke when) with pyannote community-1, fully on CPU.

One-time setup (model is gated, free):
  1. Create a Hugging Face account, accept terms at
     https://huggingface.co/pyannote/speaker-diarization-community-1
  2. `uv run hf auth login`  (paste a read token)   -- after download it runs offline
  3. `uv sync --extra diarize`

Usage:
    uv run python diarize.py audio/interview.wav
    uv run python diarize.py audio/interview.wav --asr results/asr_interview.json --model whisper-turbo
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from common import load_audio, measure, save_json, SAMPLE_RATE

PIPELINE_ID = "pyannote/speaker-diarization-community-1"


def diarize(path: Path, num_speakers: int | None = None) -> list[dict]:
    import torch
    from pyannote.audio import Pipeline

    pipeline = Pipeline.from_pretrained(PIPELINE_ID, token=os.environ.get("HF_TOKEN"))
    # Pass audio in memory: avoids pyannote's file decoder dependency issues on Windows
    wav = torch.from_numpy(load_audio(path)).unsqueeze(0)
    kwargs = {"num_speakers": num_speakers} if num_speakers else {}
    output = pipeline({"waveform": wav, "sample_rate": SAMPLE_RATE}, **kwargs)
    annotation = getattr(output, "speaker_diarization", output)
    return [
        {"start": round(turn.start, 2), "end": round(turn.end, 2), "speaker": str(spk)}
        for turn, *rest in annotation.itertracks(yield_label=True)
        for spk in [rest[-1]]
    ]


def assign_speakers(asr_segments: list[dict], turns: list[dict]) -> list[dict]:
    """Label each ASR segment with the speaker whose turns overlap it the most."""
    out = []
    for seg in asr_segments:
        s, e = seg["start"], seg["end"] if seg["end"] is not None else seg["start"]
        overlap: dict[str, float] = {}
        for t in turns:
            o = min(e, t["end"]) - max(s, t["start"])
            if o > 0:
                overlap[t["speaker"]] = overlap.get(t["speaker"], 0) + o
        out.append({**seg, "speaker": max(overlap, key=overlap.get) if overlap else "UNKNOWN"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path)
    ap.add_argument("--speakers", type=int, help="exact number of speakers, if known")
    ap.add_argument("--asr", type=Path, help="asr_<clip>.json to merge speaker labels into")
    ap.add_argument("--model", default="whisper-turbo", help="which ASR model's segments to label")
    args = ap.parse_args()

    with measure() as m:
        turns = diarize(args.audio, args.speakers)
    print(f"{len(turns)} turns, {len({t['speaker'] for t in turns})} speakers, "
          f"{m.seconds}s, peak {m.peak_rss_mb} MB")
    result = {"clip": args.audio.name, "seconds": m.seconds, "peak_rss_mb": m.peak_rss_mb, "turns": turns}

    if args.asr:
        segs = json.loads(args.asr.read_text(encoding="utf-8"))["models"][args.model]["segments"]
        result["transcript"] = assign_speakers(segs, turns)
        for seg in result["transcript"]:
            print(f"[{seg['start']:>7.2f}] {seg['speaker']}: {seg['text']}")

    save_json(f"diarize_{args.audio.stem}.json", result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
