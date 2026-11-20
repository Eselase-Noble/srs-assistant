"""Turn a recorded session into a clean transcript and a requirements document.

Usage (after live_record.py has finished):
    uv run python process_session.py                      # newest session, uses the live transcript (fast)
    uv run python process_session.py --retranscribe       # re-transcribe for accuracy first (slower)
    uv run python process_session.py sessions/2026-11-20_101500_meeting

Writes into the session folder:
    transcript.md      readable transcript with timestamps and speaker labels
    requirements.md    requirements grouped by type, each with quote, speaker and time
    requirements.json  the same data for the future app
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from common import load_audio
from extract import VAGUE, call_llm, chunks, grounding_score, norm

SESSIONS = Path(__file__).parent / "sessions"
SPEAKER_NAMES = {"MIC": "Room", "SYSTEM": "Remote"}
TYPE_TITLES = [
    ("current_process", "How the work is done today"),
    ("pain_point", "Pain points"),
    ("stakeholder", "People and roles involved"),
    ("functional", "Functional requirements"),
    ("non_functional", "Quality requirements (non functional)"),
    ("constraint", "Constraints"),
    ("business_rule", "Business rules"),
    ("assumption", "Assumptions"),
    ("open_question", "Open questions to follow up"),
]


def stamp(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def latest_session() -> Path:
    found = sorted(p for p in SESSIONS.iterdir() if (p / "session.json").exists())
    if not found:
        sys.exit("No sessions found. Record one with live_record.py first.")
    return found[-1]


def live_segments(session: Path) -> list[dict]:
    path = session / "transcript_live.jsonl"
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return sorted(rows, key=lambda r: r["start"])


def retranscribe(session: Path, model_name: str) -> list[dict]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=6)
    rows = []
    for source in ("MIC", "SYSTEM"):
        wav = session / f"{source.lower()}.wav"
        if not wav.exists():
            continue
        print(f"  transcribing {wav.name} with {model_name} ...", flush=True)
        segments, _ = model.transcribe(load_audio(wav), beam_size=5, vad_filter=True,
                                       condition_on_previous_text=False, language="en",
                                       initial_prompt="Requirements meeting in Ghana. Cedis, GH₵, mobile money, MoMo.")
        for s in segments:
            if s.no_speech_prob > 0.6 or s.avg_logprob < -1.0 or s.compression_ratio > 2.4 or not s.text.strip():
                continue
            rows.append({"source": source, "start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
    return sorted(rows, key=lambda r: r["start"])


def locate(quote: str, segments: list[dict]) -> dict | None:
    """Find the segment a quote came from.

    Single lines are checked first. Only when no single line contains the quote do we try pairs of
    neighbouring lines (quotes that run across a line break), and then the line holding most of the
    quote wins. Checking pairs first wrongly pinned quotes to the line before the real one.
    """
    best, best_seg = 0.0, None
    for seg in segments:
        score = grounding_score(quote, seg["text"])
        if score > best:
            best, best_seg = score, seg
    if best >= 0.9:
        return best_seg
    for a, b in zip(segments, segments[1:]):
        score = grounding_score(quote, a["text"] + " " + b["text"])
        if score > best:
            share_a = grounding_score(quote, a["text"]) if a["text"] else 0
            share_b = grounding_score(quote, b["text"]) if b["text"] else 0
            best, best_seg = score, (a if share_a >= share_b else b)
    return best_seg


def relink(session: Path) -> int:
    """Recompute time, speaker and segment for saved requirements without calling the model again."""
    segments = json.loads((session / "transcript.json").read_text(encoding="utf-8"))
    reqs = json.loads((session / "requirements.json").read_text(encoding="utf-8"))
    for r in reqs:
        seg = locate(r["quote"], segments)
        if seg:
            r.update(time=stamp(seg["start"]), start=seg["start"], segment_id=seg["id"],
                     speaker=SPEAKER_NAMES.get(seg["source"], seg["source"]))
    (session / "requirements.json").write_text(json.dumps(reqs, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(reqs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("session", nargs="?", type=Path)
    ap.add_argument("--retranscribe", action="store_true", help="re-run speech to text on the saved audio first")
    ap.add_argument("--asr-model", default="small", help="small (about 3x real time) or large-v3-turbo (about 1x)")
    ap.add_argument("--llm", default="qwen3:8b")
    ap.add_argument("--min-grounding", type=float, default=0.85)
    ap.add_argument("--relink", action="store_true", help="only fix time and speaker links of saved requirements")
    args = ap.parse_args()

    session = args.session or latest_session()
    if args.relink:
        print(f"Relinked {relink(session)} requirements in {session.name}")
        return 0
    meta = json.loads((session / "session.json").read_text(encoding="utf-8"))
    print(f"Session: {session.name}")

    segments = [] if args.retranscribe else live_segments(session)
    if not segments:
        if not args.retranscribe:
            print("  no live transcript found, transcribing the audio instead")
        segments = retranscribe(session, args.asr_model)
    if not segments:
        sys.exit("No speech found in this session.")
    for i, s in enumerate(segments):
        s["id"] = i
    (session / "transcript.json").write_text(json.dumps(segments, indent=1, ensure_ascii=False), encoding="utf-8")

    # 1. transcript.md
    lines = [f"# Transcript: {meta['name']}", "",
             f"Recorded {meta['started'].replace('T', ' ')}, length {stamp(meta.get('duration_s', 0))}.", ""]
    for s in segments:
        lines.append(f"**[{stamp(s['start'])}] {SPEAKER_NAMES.get(s['source'], s['source'])}:** {s['text']}  ")
    (session / "transcript.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  transcript.md written ({len(segments)} lines)")

    # 2. extraction
    text = "\n".join(f"{SPEAKER_NAMES.get(s['source'], s['source'])}: {s['text']}" for s in segments)
    parts = chunks(text)
    print(f"  extracting requirements with {args.llm} ({len(parts)} part(s), roughly 2 minutes each) ...")
    try:
        httpx.get("http://localhost:11434/api/tags", timeout=5).raise_for_status()
    except Exception:
        sys.exit("Ollama is not running. Start the Ollama app (or run `ollama serve`) and try again.")

    found, dropped = [], 0
    for n, part in enumerate(parts, 1):
        print(f"    part {n}/{len(parts)}", flush=True)
        for c in call_llm(args.llm, part).candidates:
            score = grounding_score(c.quote, text)
            if score < args.min_grounding:
                dropped += 1
                continue
            seg = locate(c.quote, segments)
            item = c.model_dump(mode="json") | {"grounding": score}
            item["time"] = stamp(seg["start"]) if seg else None
            item["start"] = seg["start"] if seg else None
            item["segment_id"] = seg["id"] if seg else None
            item["speaker"] = SPEAKER_NAMES.get(seg["source"], seg["source"]) if seg else c.speaker
            vague = sorted({w.group(0).lower() for w in VAGUE.finditer(c.statement + " " + c.quote)})
            item["flags"] = [f"vague wording: {', '.join(vague)}"] if vague else []
            found.append(item)

    seen, reqs = set(), []
    for r in found:
        key = norm(r["statement"])
        if key not in seen:
            seen.add(key)
            reqs.append(r)
    for i, r in enumerate(reqs, 1):
        r["id"] = f"REQ-{i:03d}"

    # 3. requirements.md
    out = [f"# Requirements: {meta['name']}", "",
           f"Drafted from the session recorded {meta['started'].replace('T', ' ')}. "
           f"Generated {datetime.now():%Y-%m-%d %H:%M}.", "",
           "Every item quotes what was actually said. These are suggestions to review, not final requirements.", ""]
    for key, title in TYPE_TITLES:
        group = [r for r in reqs if r["type"] == key]
        if not group:
            continue
        out += [f"## {title}", ""]
        for r in group:
            cat = f" ({r['quality_category']})" if r.get("quality_category") else ""
            out.append(f"**{r['id']}{cat}.** {r['statement']}  ")
            out.append(f"> \"{r['quote']}\"  ")
            out.append(f"> {r['speaker'] or 'Unknown'}, at {r['time'] or '?'}  ")
            for f in r["flags"]:
                out.append(f"> Check: {f}  ")
            out.append("")
    out += ["## Summary", "",
            f"* {len(reqs)} requirements suggested",
            f"* {dropped} suggestions dropped because their quote could not be found in the transcript",
            f"* {sum(1 for r in reqs if r['flags'])} flagged for vague wording"]
    (session / "requirements.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    (session / "requirements.json").write_text(json.dumps(reqs, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone. {len(reqs)} requirements, {dropped} dropped as ungrounded.")
    print(f"  {session / 'transcript.md'}")
    print(f"  {session / 'requirements.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
