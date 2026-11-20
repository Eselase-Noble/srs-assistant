"""Live session recorder: listens to the computer in real time, stores audio safely, and (optionally)
shows a live transcript.

Captures two sources at the same time:
  * MIC    : your microphone (you, and anyone in the room)
  * SYSTEM : whatever the computer plays (remote participants on Zoom/Teams/Meet/WhatsApp calls),
              via Windows WASAPI loopback. Keeping them separate gives free "who spoke" labels on calls.

Robustness:
  * Audio is written to disk as numbered WAV chunks every few seconds, so a crash, power cut or
    Ctrl+C loses at most one chunk. Nothing lives only in memory.
  * Transcription runs on a separate thread. If it falls behind, recording is never affected;
    chunks wait in a queue.
  * On stop, chunks are joined into full-length files for the accurate post-session pipeline.

Usage:
    uv run python live_record.py --list-devices
    uv run python live_record.py --name client-interview              # mic + system, live transcript
    uv run python live_record.py --name workshop --source mic          # in-person session only
    uv run python live_record.py --name call --no-transcribe           # just record
Stop with Ctrl+C.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import soundfile as sf

from common import FFMPEG, ROOT

SAMPLE_RATE = 16_000
BLOCK_SECONDS = 0.5
SESSIONS_DIR = ROOT / "sessions"
SILENCE_RMS = 0.003  # below this a chunk is treated as silent and not transcribed
MAX_CARRY_SECONDS = 20
# Phrases Whisper commonly invents from silence, clicks and noise (dropped only when very short)
PHANTOM_PHRASES = {"thank you", "thank you very much", "thanks for watching", "thank you for watching",
                   "welcome", "bye", "you", "thank you so much", "please subscribe"}


# --------------------------------------------------------------------------------------------- devices
def get_sources(which: str, mic_name: str | None, speaker_name: str | None):
    import soundcard as sc

    # Loopback reports a "discontinuity" whenever nothing is playing; harmless. Filter after import,
    # because soundcard registers its own warning filter on import.
    warnings.filterwarnings("ignore", message="data discontinuity")

    sources = {}
    if which in ("mic", "both"):
        sources["MIC"] = sc.get_microphone(mic_name) if mic_name else sc.default_microphone()
    if which in ("system", "both"):
        spk = sc.get_speaker(speaker_name) if speaker_name else sc.default_speaker()
        sources["SYSTEM"] = sc.get_microphone(id=str(spk.name), include_loopback=True)
    return sources


def list_devices() -> None:
    import soundcard as sc

    print("Microphones:")
    for m in sc.all_microphones():
        print(f"  - {m.name}")
    print("Speakers (their output can be captured as SYSTEM audio):")
    for s in sc.all_speakers():
        print(f"  - {s.name}")
    print(f"\nDefault mic: {sc.default_microphone().name}\nDefault speaker: {sc.default_speaker().name}")


# --------------------------------------------------------------------------------------------- capture
class SourceRecorder(threading.Thread):
    """Reads one audio device continuously and writes fixed-length WAV chunks to disk."""

    def __init__(self, label, device, out_dir: Path, chunk_seconds: int, on_chunk, stop: threading.Event):
        super().__init__(daemon=True, name=f"rec-{label}")
        self.label, self.device, self.out_dir = label, device, out_dir
        self.chunk_frames = int(chunk_seconds * SAMPLE_RATE)
        self.on_chunk, self.stop = on_chunk, stop
        self.level = 0.0
        self.error: Exception | None = None

    def run(self):
        if sys.platform == "win32":  # soundcard uses COM; every thread must initialise it
            import ctypes
            ctypes.windll.ole32.CoInitializeEx(None, 0x0)
        idx, buf, filled = 0, np.zeros(self.chunk_frames, dtype=np.float32), 0
        block = int(BLOCK_SECONDS * SAMPLE_RATE)
        try:
            with self.device.recorder(samplerate=SAMPLE_RATE, channels=1, blocksize=block) as rec:
                while not self.stop.is_set():
                    data = rec.record(numframes=block)
                    mono = data.mean(axis=1).astype(np.float32) if data.ndim > 1 else data.astype(np.float32)
                    self.level = float(np.sqrt(np.mean(mono ** 2))) if len(mono) else 0.0
                    while len(mono):
                        take = min(len(mono), self.chunk_frames - filled)
                        buf[filled:filled + take] = mono[:take]
                        filled += take
                        mono = mono[take:]
                        if filled == self.chunk_frames:
                            self._flush(idx, buf)
                            idx, filled = idx + 1, 0
        except Exception as e:  # report, never crash the other source
            self.error = e
        finally:
            self._flush(idx, buf[:filled], final=True)  # final=True even if empty: releases carried audio

    def _flush(self, idx: int, audio: np.ndarray, final: bool = False):
        path = self.out_dir / f"{self.label.lower()}_{idx:05d}.wav"
        if len(audio):
            sf.write(path, audio, SAMPLE_RATE, subtype="PCM_16")
        self.on_chunk(self.label, idx, path, audio.copy(), final)


# --------------------------------------------------------------------------------------------- live ASR
class LiveTranscriber(threading.Thread):
    """Transcribes chunks as they arrive. Draft quality; the post-session pass is the source of truth."""

    def __init__(self, model_name: str, session_dir: Path, chunk_seconds: int, threads: int, prompt: str):
        super().__init__(daemon=True, name="live-asr")
        self.q: queue.Queue = queue.Queue()
        self.model_name, self.chunk_seconds, self.threads, self.prompt = model_name, chunk_seconds, threads, prompt
        self.jsonl = session_dir / "transcript_live.jsonl"
        self.md = session_dir / "transcript_live.md"
        self.ready = threading.Event()
        self.done = threading.Event()

        self.carry: dict[str, tuple[np.ndarray, float]] = {}
        self.last_text: dict[str, str] = {}
        self.language = "en"  # Twi support is paused; forcing English avoids wrong-language guesses

    def submit(self, label, idx, audio, final=False):
        self.q.put((label, idx, audio, final))

    def run(self):
        from faster_whisper import WhisperModel

        model = WhisperModel(self.model_name, device="cpu", compute_type="int8", cpu_threads=self.threads)
        self.ready.set()
        with self.jsonl.open("a", encoding="utf-8") as jf, self.md.open("a", encoding="utf-8") as mf:
            while True:
                item = self.q.get()
                if item is None:
                    break
                label, idx, chunk, final = item
                # Carry-over: the last, possibly cut-off sentence of the previous chunk is prepended to this
                # one, so words split at chunk boundaries are transcribed whole.
                carry, carry_offset = self.carry.pop(label, (np.zeros(0, np.float32), idx * self.chunk_seconds))
                audio = np.concatenate([carry, chunk])
                offset = carry_offset
                if not len(audio) or float(np.sqrt(np.mean(audio ** 2))) < SILENCE_RMS:
                    continue
                segments, info = model.transcribe(audio, beam_size=1, vad_filter=True, initial_prompt=self.prompt,
                                                  language=self.language,
                                                  condition_on_previous_text=False)
                segments = list(segments)
                total = len(audio) / SAMPLE_RATE
                if (not final and segments and segments[-1].end > total - 1.0
                        and total - segments[-1].start < MAX_CARRY_SECONDS):
                    last = segments.pop()
                    self.carry[label] = (audio[int(last.start * SAMPLE_RATE):], offset + last.start)
                for s in segments:
                    text = s.text.strip()
                    # Hallucination guards: Whisper invents text from noise/echo. Low confidence or
                    # repetitive output is kept out of the live view (audio is still saved).
                    if (not text or s.no_speech_prob > 0.6 or s.avg_logprob < -1.0
                            or s.compression_ratio > 2.4):
                        continue
                    key = text.lower().strip(" .!?,")
                    if key in PHANTOM_PHRASES and s.end - s.start < 2.0:
                        continue  # Whisper's stock "Thank you." / "Welcome." on clicks and noise
                    if key == self.last_text.get(label):
                        continue  # repetition loop
                    self.last_text[label] = key
                    row = {"source": label, "start": round(offset + s.start, 2), "end": round(offset + s.end, 2),
                           "text": text, "language": info.language,
                           "language_prob": round(info.language_probability, 2),
                           "needs_twi_pass": False}
                    jf.write(json.dumps(row, ensure_ascii=False) + "\n")
                    jf.flush()
                    stamp = str(timedelta(seconds=int(row["start"])))
                    flag = ""
                    mf.write(f"[{stamp}] **{label}**: {text}{flag}\n\n")
                    mf.flush()
                    print(f"\r[{stamp}] {label}: {text}{flag}" + " " * 10)
                backlog = self.q.qsize()
                if backlog > 2:
                    print(f"   (live transcript is {backlog * self.chunk_seconds}s behind; recording is unaffected)")
        self.done.set()


# --------------------------------------------------------------------------------------------- finalize
def join_chunks(chunk_dir: Path, label: str, out: Path) -> bool:
    parts = sorted(chunk_dir.glob(f"{label.lower()}_*.wav"))
    if not parts:
        return False
    listfile = chunk_dir / f"{label.lower()}_list.txt"
    listfile.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(listfile), "-c", "copy", str(out)], check=True)
    listfile.unlink()
    return True


def mix(files: list[Path], out: Path) -> None:
    if len(files) == 1:
        out.write_bytes(files[0].read_bytes())
        return
    args = [FFMPEG, "-nostdin", "-loglevel", "error", "-y"]
    for f in files:
        args += ["-i", str(f)]
    args += ["-filter_complex", f"amix=inputs={len(files)}:duration=longest:normalize=0", str(out)]
    subprocess.run(args, check=True)


# --------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="Record a requirements session from the computer in real time.")
    ap.add_argument("--name", default="session", help="short session name, e.g. client-interview")
    ap.add_argument("--source", choices=["both", "mic", "system"], default="both")
    ap.add_argument("--mic", help="microphone name (substring): see --list-devices")
    ap.add_argument("--speaker", help="speaker name (substring) whose output to capture")
    ap.add_argument("--chunk-seconds", type=int, default=15)
    ap.add_argument("--no-transcribe", action="store_true", help="record only, no live transcript")
    ap.add_argument("--model", default="small", help="faster-whisper model for live drafts (small keeps up ~2-3x)")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--prompt", default="Requirements interview in Ghana. Cedis, GH₵, Twi, mobile money, MoMo.")
    ap.add_argument("--consent", help="note of who consented to recording, stored with the session")
    ap.add_argument("--duration", type=int, help="stop automatically after N seconds")
    ap.add_argument("--session-dir", type=Path, help="exact folder to record into (used by the app)")
    ap.add_argument("--vocabulary", help="topic and key words, e.g. 'hospital records, OPD, NHIS'")
    ap.add_argument("--list-devices", action="store_true")
    args = ap.parse_args()

    if args.list_devices:
        list_devices()
        return 0

    started = datetime.now()
    session_dir = args.session_dir or SESSIONS_DIR / f"{started:%Y-%m-%d_%H%M%S}_{args.name}"
    chunk_dir = session_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    stop_file = session_dir / "STOP"          # the app creates this file to stop the recording
    status_file = session_dir / "live_status.json"

    sources = get_sources(args.source, args.mic, args.speaker)
    meta = {"name": args.name, "started": started.isoformat(timespec="seconds"),
            "sources": {k: v.name for k, v in sources.items()}, "sample_rate": SAMPLE_RATE,
            "chunk_seconds": args.chunk_seconds, "consent": args.consent, "status": "recording",
            "vocabulary": args.vocabulary}
    meta_path = session_dir / "session.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    transcriber = None
    if not args.no_transcribe:
        prompt = f"Requirements interview in Ghana. {args.vocabulary}" if args.vocabulary else args.prompt
        transcriber = LiveTranscriber(args.model, session_dir, args.chunk_seconds, args.threads, prompt)
        transcriber.start()
        print(f"Loading live transcription model '{args.model}' ...")
        transcriber.ready.wait()

    stop = threading.Event()
    on_chunk = (lambda label, idx, path, audio, final: transcriber.submit(label, idx, audio, final)) if transcriber \
        else (lambda *a: None)
    recorders = [SourceRecorder(lbl, dev, chunk_dir, args.chunk_seconds, on_chunk, stop)
                 for lbl, dev in sources.items()]

    print(f"\n● RECORDING → {session_dir}")
    for lbl, dev in sources.items():
        print(f"   {lbl:<6} {dev.name}")
    print("   Remember: tell participants they are being recorded. Press Ctrl+C to stop.")
    if "MIC" in sources and "SYSTEM" in sources:
        print("   Tip: on calls, wear headphones so the mic does not pick up the other side twice.")
    print()
    for r in recorders:
        r.start()

    try:
        while any(r.is_alive() for r in recorders):
            seconds = (datetime.now() - started).total_seconds()
            if (args.duration and seconds >= args.duration) or stop_file.exists():
                break
            status_file.write_text(json.dumps({"elapsed_s": round(seconds, 1), "state": "recording",
                                               "levels": {r.label: round(r.level, 4) for r in recorders}}),
                                   encoding="utf-8")
            elapsed = timedelta(seconds=int(seconds))
            meters = "  ".join(f"{r.label} {'█' * min(10, int(r.level * 200)):<10}" for r in recorders)
            sys.stdout.write(f"\r   {elapsed}  {meters}")
            sys.stdout.flush()
            for r in recorders:
                if r.error:
                    print(f"\n!! {r.label} capture stopped: {r.error}")
                    r.error = None
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    print("\n\n■ Stopping ...")
    status_file.write_text(json.dumps({"state": "finishing"}), encoding="utf-8")
    stop.set()
    for r in recorders:
        r.join(timeout=5)

    produced = []
    for lbl in sources:
        out = session_dir / f"{lbl.lower()}.wav"
        if join_chunks(chunk_dir, lbl, out):
            produced.append(out)
    if produced:
        mix(produced, session_dir / "mixed.wav")

    if transcriber:
        print("   Finishing live transcript ...")
        transcriber.q.put(None)
        transcriber.done.wait()

    meta.update(status="recorded", ended=datetime.now().isoformat(timespec="seconds"),
                duration_s=round((datetime.now() - started).total_seconds(), 1),
                files=[p.name for p in produced] + (["mixed.wav"] if produced else []))
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    status_file.write_text(json.dumps({"state": "done"}), encoding="utf-8")
    stop_file.unlink(missing_ok=True)
    print(f"   Saved: {', '.join(meta['files'])}")
    if transcriber:
        print(f"   Live transcript: {session_dir / 'transcript_live.md'}")
    print("   Next: run the accurate pipeline on mixed.wav (asr_compare / diarize / extract).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
