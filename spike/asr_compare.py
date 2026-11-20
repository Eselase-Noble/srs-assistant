"""Compare local speech-to-text models on every clip in ./audio.

Usage:
    uv run python asr_compare.py                 # all models, all clips
    uv run python asr_compare.py --models whisper-turbo akan-turbo
    uv run python asr_compare.py --clips mixed

Writes results/asr_<clip>.json and results/asr_report.md
"""
from __future__ import annotations

import argparse
import gc
import os
import sys

from common import audio_files, load_audio, measure, save_json, RESULTS_DIR, SAMPLE_RATE

CPU_THREADS = int(os.environ.get("ASR_THREADS", 8))  # P-cores matter; all 22 logical threads is slower
# Custom vocabulary: biases Whisper toward local terms (cedis, Twi, MoMo...). Edit per project.
VOCAB_PROMPT = os.environ.get("ASR_PROMPT", "Requirements interview in Ghana. Cedis, GH₵, Twi, mobile money, MoMo, Excel, SMS.")

# name -> (backend, model id, note)
MODELS: dict[str, tuple[str, str, str]] = {
    "whisper-turbo": ("faster-whisper", "large-v3-turbo", "OpenAI Whisper baseline (English)"),
    "whisper-small": ("faster-whisper", "small", "Smaller/faster English option"),
    "akan-turbo": ("faster-whisper", "ghananlpcommunity/whisper-large-v3-turbo-twi-ctranslate",
                   "Whisper turbo fine-tuned on Akan (WAXAL)"),
    "akan-small-waxal": ("transformers", "teckedd/whisper_small-waxal_akan-asr",
                         "Whisper small fine-tuned on WAXAL Akan"),
    "akan-small-giftmark": ("transformers", "GiftMark/akan-whisper-model",
                            "Whisper small fine-tuned on Akan"),
    # Gated: request access at https://huggingface.co/Kennethdot/kasanoma and run `hf auth login`
    "kasanoma": ("transformers", "Kennethdot/kasanoma", "English-Twi code-switching (gated)"),
}


def run_faster_whisper(model_id: str, audio) -> dict:
    from faster_whisper import WhisperModel

    with measure() as load:
        model = WhisperModel(model_id, device="cpu", compute_type="int8", cpu_threads=CPU_THREADS)
    with measure() as run:
        segments, info = model.transcribe(audio, beam_size=5, vad_filter=True,
                                          initial_prompt=VOCAB_PROMPT, condition_on_previous_text=False)
        segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                 "avg_logprob": round(s.avg_logprob, 3), "compression_ratio": round(s.compression_ratio, 2),
                 "no_speech_prob": round(s.no_speech_prob, 3)} for s in segments]
    del model
    return {"language": info.language, "language_prob": round(info.language_probability, 3), "segments": segs,
            "load_s": load.seconds, "transcribe_s": run.seconds}


def run_transformers(model_id: str, audio) -> dict:
    import torch
    from transformers import pipeline

    torch.set_num_threads(CPU_THREADS)
    with measure() as load:
        asr = pipeline("automatic-speech-recognition", model=model_id, device="cpu",
                       chunk_length_s=30, stride_length_s=5)
    with measure() as run:
        # no_repeat_ngram_size stops the "ahyɛ wɔn ahyɛ wɔn ..." repetition loops seen in the first run
        out = asr({"raw": audio, "sampling_rate": SAMPLE_RATE}, return_timestamps=True,
                  generate_kwargs={"no_repeat_ngram_size": 4})
    segs = [
        {"start": c["timestamp"][0], "end": c["timestamp"][1], "text": c["text"].strip()}
        for c in out.get("chunks", [])
    ] or [{"start": 0, "end": None, "text": out["text"].strip()}]
    del asr
    return {"language": None, "language_prob": None, "segments": segs,
            "load_s": load.seconds, "transcribe_s": run.seconds}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=list(MODELS))
    ap.add_argument("--clips", nargs="*", help="substring filter on clip filenames")
    args = ap.parse_args()

    clips = audio_files()
    if args.clips:
        clips = [c for c in clips if any(f in c.name for f in args.clips)]
    if not clips:
        print("No audio found in ./audio. Add clips first (see README.md).")
        return 1

    report = ["# ASR comparison\n"]
    for clip in clips:
        audio = load_audio(clip)
        duration = len(audio) / SAMPLE_RATE
        print(f"\n=== {clip.name} ({duration:.1f}s)")
        clip_results = {"clip": clip.name, "duration_s": round(duration, 1), "models": {}}
        report.append(f"\n## {clip.name} ({duration:.1f}s)\n")
        report.append("| Model | Load (s) | Transcribe (s) | Speed (x real-time) | Peak RAM (MB) | Lang |\n"
                      "|---|---|---|---|---|---|")
        texts = []
        for name in args.models:
            backend, model_id, note = MODELS[name]
            print(f"  -> {name} ({model_id}) ...", flush=True)
            try:
                with measure() as m:
                    res = (run_faster_whisper if backend == "faster-whisper" else run_transformers)(model_id, audio)
            except Exception as e:  # keep going: one failing model must not stop the comparison
                print(f"     FAILED: {type(e).__name__}: {e}")
                clip_results["models"][name] = {"error": f"{type(e).__name__}: {e}"}
                report.append(f"| {name} | failed | n/a | n/a | n/a | n/a |")
                continue
            finally:
                gc.collect()
            speed = round(duration / res["transcribe_s"], 2) if res["transcribe_s"] else None
            res.update(model_id=model_id, note=note, seconds=m.seconds, speed_x_realtime=speed,
                       peak_rss_mb=m.peak_rss_mb)
            clip_results["models"][name] = res
            full = " ".join(s["text"] for s in res["segments"])
            texts.append((name, full))
            report.append(f"| {name} | {res['load_s']} | {res['transcribe_s']} | {speed} | {m.peak_rss_mb} "
                          f"| {res['language'] or 'n/a'} |")
            print(f"     load {res['load_s']}s, transcribe {res['transcribe_s']}s, {speed}x real-time, {m.peak_rss_mb} MB")
        report.append("")
        for name, full in texts:
            report.append(f"**{name}:** {full}\n")
        save_json(f"asr_{clip.stem}.json", clip_results)

    (RESULTS_DIR / "asr_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"\nReport: {RESULTS_DIR / 'asr_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
