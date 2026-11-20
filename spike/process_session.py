"""Turn a recorded session into an accurate transcript, readable paragraphs, a summary and requirements.

Usage:
    uv run python process_session.py                         # newest session, full accurate pass
    uv run python process_session.py SESSION_DIR --quick     # reuse the live transcript (fast, rougher)
    uv run python process_session.py SESSION_DIR --relink    # only repair quote links
    uv run python process_session.py SESSION_DIR --summary-only

Writes into the session folder:
    transcript.json / transcript.md   timed transcript (one line per spoken segment, with word timings)
    paragraphs.json                   clean paragraphs grouped by speaker, for reading
    summary.json / summary.md         overview, topics, decisions, pain points, follow ups
    requirements.json / requirements.md

Progress lines start with "STEP <0..1> <message>" so the app can show them.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import numpy as np
from pydantic import BaseModel, Field

from common import FFMPEG, load_audio
from extract import OLLAMA, VAGUE, call_llm, chunks, grounding_score, norm, post_llm

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
VOCAB = ("Requirements meeting in Ghana about daily business operations. Cedis, GH₵, mobile money, MoMo, "
         "Excel, WhatsApp, invoice, stock, inventory, receipt, branch, manager, accountant.")
HOTWORDS = ""  # the session's key words, boosted during decoding (set from session.json)


def step(progress: float, message: str) -> None:
    print(f"STEP {progress:.3f} {message}", flush=True)


def stamp(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def latest_session() -> Path:
    found = sorted(p for p in SESSIONS.iterdir() if (p / "session.json").exists())
    if not found:
        sys.exit("No sessions found. Record one with live_record.py first.")
    return found[-1]


# ============================================================================== 1. transcription
def accurate_transcript(session: Path) -> list[dict] | None:
    """The saved accurate transcript (it has word timings), if a previous run produced one."""
    path = session / "transcript.json"
    if not path.exists():
        return None
    rows = json.loads(path.read_text(encoding="utf-8"))
    return rows if rows and "words" in rows[0] else None


def live_segments(session: Path) -> list[dict]:
    path = session / "transcript_live.jsonl"
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return sorted(rows, key=lambda r: r["start"])


# Noise clean up applied before transcription (FFmpeg, all local):
#   highpass/lowpass  cut generator and fan hum below 90 Hz and hiss above 7.5 kHz (speech lives in between)
#   afftdn            spectral noise reduction that learns the steady background noise (mild, so speech
#                     is not damaged: Whisper copes better with a little noise than with over-filtered audio)
#   dynaudnorm        evens out loud and quiet speakers so soft voices are still picked up
DENOISE = "highpass=f=90,lowpass=f=7500,afftdn=nf=-25:tn=1,dynaudnorm=f=200:g=15:p=0.9"
PHANTOMS = {"thank you", "thank you very much", "thanks for watching", "thank you for watching", "welcome",
            "bye", "you", "thank you so much", "please subscribe", "okay", "ok", "hmm", "mm"}


def load_clean(path: Path, denoise: bool) -> np.ndarray:
    import subprocess

    cmd = [FFMPEG, "-nostdin", "-loglevel", "error", "-i", str(path)]
    if denoise:
        cmd += ["-af", DENOISE]
    cmd += ["-f", "f32le", "-ac", "1", "-ar", "16000", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32).copy()


def rms(audio: np.ndarray, start: float, end: float) -> float:
    part = audio[int(start * 16000):int(end * 16000)]
    return float(np.sqrt(np.mean(part ** 2))) if len(part) else 0.0


def redecode(model, audio: np.ndarray, row: dict, context: str) -> dict | None:
    """Decode one unclear line again in isolation. Returns the new text and words if clearly better."""
    pad = 0.3
    start = max(0.0, row["start"] - pad)
    piece = audio[int(start * 16000):int((row["end"] + pad) * 16000)]
    if len(piece) < 8000:
        return None
    segs, _ = model.transcribe(
        piece, language="en", beam_size=10, best_of=5, temperature=0.0, word_timestamps=True,
        vad_filter=False, condition_on_previous_text=False, without_timestamps=False,
        initial_prompt=(VOCAB + " " + context).strip()[-800:], hotwords=HOTWORDS or None,
    )
    segs = list(segs)
    words = [{"w": w.word, "s": round(start + w.start, 2), "e": round(start + w.end, 2), "p": round(w.probability, 2)}
             for s in segs for w in (s.words or [])]
    text = " ".join(s.text.strip() for s in segs).strip()
    if not words or not text:
        return None
    conf = float(np.mean([w["p"] for w in words]))
    if conf < row["confidence"] + 0.05:
        return None
    return {"text": text, "words": words, "confidence": round(conf, 2), "redecoded": True}


def transcribe(session: Path, model_name: str, threads: int, share: float, denoise: bool = True) -> list[dict]:
    """Accurate pass over the full recording: noise clean up, strict speech detection, large model,
    beam search, context carried across the file, word timestamps with confidence, and filters that
    drop background talk and text invented from noise. Dropped lines go to transcript_dropped.json."""
    from faster_whisper import WhisperModel

    step(0.01, f"Loading the {model_name} speech model")
    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=threads)
    tracks = []
    for source in ("MIC", "SYSTEM"):
        wav = session / f"{source.lower()}.wav"
        if not wav.exists():
            continue
        raw = load_audio(wav)
        if not len(raw) or float(np.sqrt(np.mean(raw ** 2))) < 0.002:
            continue  # silent track (for example no call audio in an in person meeting)
        step(0.01, f"Cleaning up background noise in the {SPEAKER_NAMES.get(source, source).lower()} audio")
        tracks.append((source, raw, load_clean(wav, denoise)))
    total = sum(len(a) for _, a, _ in tracks) / 16000 or 1
    done_before = 0.0
    rows: list[dict] = []
    dropped: list[dict] = []
    for source, raw, audio in tracks:
        name = SPEAKER_NAMES.get(source, source).lower()
        segments, _ = model.transcribe(
            audio, language="en", beam_size=5, best_of=5, word_timestamps=True,
            vad_filter=True,
            vad_parameters={"threshold": 0.55, "min_speech_duration_ms": 300,
                            "min_silence_duration_ms": 500, "speech_pad_ms": 300},
            condition_on_previous_text=True, initial_prompt=VOCAB, hotwords=HOTWORDS or None,
            compression_ratio_threshold=2.2, log_prob_threshold=-1.0, no_speech_threshold=0.6,
            hallucination_silence_threshold=2.0,
        )
        kept: list[dict] = []
        last_report = -1
        for s in segments:
            text = s.text.strip()
            words = [{"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2), "p": round(w.probability, 2)}
                     for w in (s.words or [])]
            mean_p = float(np.mean([w["p"] for w in words])) if words else 0.0
            row = {"source": source, "start": round(s.start, 2), "end": round(s.end, 2), "text": text,
                   "words": words, "level": round(rms(raw, s.start, s.end), 4), "confidence": round(mean_p, 2)}
            reason = None
            if not text:
                reason = "empty"
            elif s.no_speech_prob > 0.6 or s.avg_logprob < -1.0 or s.compression_ratio > 2.4:
                reason = "low confidence or repetitive"
            elif words and mean_p < 0.4:
                reason = "mostly unclear words"
            elif text.lower().strip(" .!?,") in PHANTOMS and s.end - s.start < 2.0:
                reason = "stock phrase from noise"
            (dropped if reason else kept).append(row | ({"reason": reason} if reason else {}))
            minute = int(s.end // 60)
            if minute != last_report:
                last_report = minute
                frac = (done_before + s.end) / total
                step(share * frac, f"Transcribing {name} audio, {stamp(s.end)} of {stamp(len(raw) / 16000)}")
        # Second pass: lines the model was unsure of are decoded again on their own, with a wider beam
        # and the preceding sentence as context. The better reading wins; unclear lines can be rescued.
        retry = [r for r in kept if r["confidence"] < 0.65 and r["end"] - r["start"] >= 1.0]
        retry += [r for r in dropped if r.get("reason") == "mostly unclear words" and r["source"] == source
                  and r["end"] - r["start"] >= 1.0]
        for i, r in enumerate(retry[:400]):
            if i % 10 == 0:
                step(share * (done_before + len(raw) / 16000) / total,
                     f"Checking unclear passages again, {i + 1} of {min(len(retry), 400)}")
            context = " ".join(k["text"] for k in kept if k["end"] <= r["start"])[-200:]
            better = redecode(model, audio, r, context)
            if better is None:
                continue
            if r in dropped and better["confidence"] >= 0.5:
                dropped.remove(r)
                r.pop("reason", None)
                kept.append(r)
            r.update(better)
        kept.sort(key=lambda r: r["start"])
        # Background talk: much quieter than the main conversation in this track
        if kept:
            typical = float(np.median([r["level"] for r in kept]))
            for r in list(kept):
                # 0.2 is about 14 dB quieter. Clear speech (confidence 0.85+) is always kept, so a soft spoken
                # stakeholder sitting further from the microphone is not lost.
                if r["level"] < 0.2 * typical and r["confidence"] < 0.85:
                    kept.remove(r)
                    dropped.append(r | {"reason": "background speech (much quieter than the conversation)"})
        rows += kept
        done_before += len(raw) / 16000
    rows.sort(key=lambda r: r["start"])
    dropped.sort(key=lambda r: r["start"])
    (session / "transcript_dropped.json").write_text(json.dumps(dropped, indent=1, ensure_ascii=False),
                                                     encoding="utf-8")
    print(f"  kept {len(rows)} lines, filtered out {len(dropped)} as noise or background", flush=True)
    return rows


# ============================================================================== 2. paragraphs
# a filler sound together with the commas around it: "challenges, uh, that" -> "challenges that"
FILLERS = re.compile(r"(?:,\s*)?(?<![\w'-])(?:mm-hmm|uh-huh|um+|uh+|erm+|er|ah+|hmm+|mm+|mhm)(?![\w'-])[,.]?\s*",
                     re.IGNORECASE)
# the same 1 to 4 word phrase said two or more times in a row: "we we we", "so that, so that"
REPEATS = re.compile(r"\b((?:\w+[\s,]+){0,3}\w+)(?:[\s,]+\1\b)+", re.IGNORECASE)
FALSE_START = re.compile(r"\b(\w+)-\s+(?=\w)")          # "the- the system" -> "the system"
LEADING_JUNK = re.compile(r"^(?:(?:so|and|but|okay|ok|yeah|right|well|now)[,.]?\s+){2,}", re.IGNORECASE)
ACKS = {"okay", "ok", "yes", "yeah", "yep", "right", "alright", "all right", "mm-hmm", "uh-huh", "sure",
        "i see", "oh", "ah", "hmm", "mm", "no", "fine", "good", "great", "thank you", "thanks", "exactly",
        "true", "correct", "ok ok", "okay okay"}


def clean(text: str) -> str:
    """Clean read: drop filler sounds, stutters, false starts and repeated phrases, tidy punctuation.
    The words that carry meaning are never changed here."""
    text = FILLERS.sub(" ", text)
    text = FALSE_START.sub("", text)
    for _ in range(2):
        text = REPEATS.sub(r"\1", text)
    text = LEADING_JUNK.sub(lambda m: m.group(0).split()[0].rstrip(",.") + " ", text)
    text = re.sub(r"\s+([,.?!])", r"\1", text)
    text = re.sub(r"([,.?!])\1+", r"\1", text)
    text = re.sub(r",\s*([.?!])", r"\1", text)
    ending = text.rstrip()[-1:] if text.rstrip()[-1:] in ".?!" else ""
    text = re.sub(r"\s{2,}", " ", text).strip(" ,-")
    if not re.search(r"\w", text):
        return ""
    if ending and text[-1] not in ".?!":
        text += ending
    return text[:1].upper() + text[1:]


def is_ack(text: str) -> bool:
    return text.lower().strip(" .,!?") in ACKS


def build_paragraphs(segments: list[dict], max_words: int = 140, gap: float = 2.5) -> list[dict]:
    """Group lines into readable paragraphs. Lone acknowledgements ("okay", "mm-hmm") are left out of
    the reading view unless they answer a question; they stay in the timed transcript."""
    paras: list[dict] = []
    for i, s in enumerate(segments):
        text = clean(s["text"])
        if not text:
            continue
        prev = segments[i - 1]["text"].rstrip() if i else ""
        if is_ack(text) and not prev.endswith("?"):
            continue
        cur = paras[-1] if paras else None
        words = len(cur["text"].split()) if cur else 0
        same = cur and cur["source"] == s["source"] and s["start"] - cur["end"] < gap
        sentence_done = cur and cur["text"].rstrip().endswith((".", "?", "!"))
        if same and not (words > max_words and sentence_done):
            cur["text"] += " " + text
            cur["end"] = s["end"]
            cur["segment_ids"].append(s["id"])
        else:
            paras.append({"id": len(paras), "source": s["source"], "start": s["start"], "end": s["end"],
                          "text": text, "segment_ids": [s["id"]]})
    return paras


# ============================================================================== 2b. polished transcript
class PolishedParagraph(BaseModel):
    id: int
    text: str


class PolishedBatch(BaseModel):
    paragraphs: list[PolishedParagraph]


POLISH_SYSTEM = """You are an experienced transcript editor preparing an interview transcript for a report.
You receive paragraphs produced by speech recognition. For each paragraph, return a clean version:
- fix punctuation, capitalisation and sentence boundaries
- remove filler words, false starts, stutters and repeated phrases
- correct words that were clearly misheard, using the context and the key words given
  (for example "the photo must be opened" in a records office means "the folder must be opened")
- keep the speaker's own words, meaning, facts, numbers, names and order. Do not summarise, shorten
  ideas, add explanations, or add anything that was not said
- if a passage is unintelligible, keep it as it is
Return every paragraph with its id, in the same order."""


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def polish_is_safe(original: str, polished: str) -> bool:
    """Reject rewrites that drift from what was said: too different, too short or long, or new numbers."""
    from difflib import SequenceMatcher

    a, b = _words(original), _words(polished)
    if not b or not a:
        return False
    if not 0.55 <= len(b) / len(a) <= 1.15:
        return False
    if set(re.findall(r"\d+", polished)) - set(re.findall(r"\d+", original)):
        # allow numbers written out as digits ("seventy two" -> 72) only if the words were there
        spelled = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "twelve",
                   "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
                   "thousand", "million"}
        if not spelled & set(a):
            return False
    return SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.6


def polish(paragraphs: list[dict], llm: str, vocab: str, share_from: float, share_to: float) -> int:
    """Adds a 'polished' text to each paragraph. Returns how many rewrites were accepted."""
    batches, cur, size = [], [], 0
    for p in paragraphs:
        if size + len(p["text"]) > 2400 and cur:
            batches.append(cur)
            cur, size = [], 0
        cur.append(p)
        size += len(p["text"])
    if cur:
        batches.append(cur)
    accepted = 0
    for n, batch in enumerate(batches, 1):
        step(share_from + (share_to - share_from) * (n - 1) / len(batches),
             f"Polishing the transcript, part {n} of {len(batches)}")
        listing = "\n\n".join(f"[{p['id']}] {SPEAKER_NAMES.get(p['source'], p['source'])}: {p['text']}" for p in batch)
        body = {
            "model": llm, "stream": False, "think": False, "format": PolishedBatch.model_json_schema(),
            "options": {"temperature": 0.1, "num_ctx": 8192},
            "messages": [
                {"role": "system", "content": POLISH_SYSTEM},
                {"role": "user", "content": f"Key words for this session: {vocab}\n\nParagraphs:\n\n{listing}"},
            ],
        }
        try:
            result = PolishedBatch.model_validate_json(post_llm(body))
        except Exception as e:  # a failed batch keeps the cleaned text, it never blocks the pipeline
            print(f"  polish batch {n} failed: {e}", flush=True)
            continue
        by_id = {p.id: p.text.strip() for p in result.paragraphs}
        for p in batch:
            new = by_id.get(p["id"], "")
            new = re.sub(r"^(Room|Remote):\s*", "", new)
            if new and polish_is_safe(p["text"], new):
                p["polished"] = new
                accepted += 1
    return accepted


# ============================================================================== 3. summary
class Topic(BaseModel):
    title: str = Field(description="3 to 6 words")
    summary: str = Field(description="2 to 4 sentences")


class MeetingSummary(BaseModel):
    title: str = Field(description="A short descriptive title for the session, at most 8 words")
    overview: str = Field(description="One paragraph of 4 to 7 sentences: who was interviewed about what, "
                                      "the main things learned, and the biggest problems raised")
    topics: list[Topic] = Field(description="The main topics in the order they came up, 3 to 8 items")
    decisions: list[str] = Field(description="Anything agreed or decided. Empty if nothing was decided")
    pain_points: list[str] = Field(description="The most important problems in the current way of working")
    follow_ups: list[str] = Field(description="Questions to ask or things to check in the next session")


SUMMARY_SYSTEM = """You are a senior business analyst writing up a requirements elicitation interview.
You receive notes on each part of the conversation, in order, plus the pain points and open questions
already extracted. Write a clear, factual summary for a colleague who was not there.
Rules: use only what is in the notes; never invent names, numbers or decisions; plain professional English;
no marketing language; write sentences, not fragments."""


def summarise(meta: dict, part_notes: list[str], reqs: list[dict], llm: str) -> MeetingSummary:
    pains = [r["statement"] for r in reqs if r["type"] == "pain_point"]
    questions = [r["statement"] for r in reqs if r["type"] == "open_question"]
    notes = "\n\n".join(f"Part {i + 1}: {n}" for i, n in enumerate(part_notes) if n.strip())
    user = (f"Session: {meta.get('name')}, recorded {meta.get('started', '')[:10]}, "
            f"length {stamp(meta.get('duration_s', 0))}.\n\nNotes by part:\n{notes}\n\n"
            f"Pain points found:\n" + "\n".join(f"- {p}" for p in pains[:40]) +
            "\n\nOpen questions found:\n" + "\n".join(f"- {q}" for q in questions[:30]))
    body = {
        "model": llm, "stream": False, "think": False, "format": MeetingSummary.model_json_schema(),
        "options": {"temperature": 0.2, "num_ctx": 16384},
        "messages": [{"role": "system", "content": SUMMARY_SYSTEM}, {"role": "user", "content": user}],
    }
    return MeetingSummary.model_validate_json(post_llm(body))


def summary_markdown(meta: dict, s: MeetingSummary) -> str:
    out = [f"# {s.title}", "", f"Session {meta.get('name')}, recorded {meta.get('started', '').replace('T', ' ')}, "
           f"length {stamp(meta.get('duration_s', 0))}.", "", "## Overview", "", s.overview, "", "## Topics", ""]
    for t in s.topics:
        out += [f"**{t.title}.** {t.summary}", ""]
    for title, items in (("Decisions", s.decisions), ("Pain points", s.pain_points), ("Follow up", s.follow_ups)):
        if items:
            out += [f"## {title}", ""] + [f"* {i}" for i in items] + [""]
    return "\n".join(out)


# ============================================================================== 4. linking
def locate(quote: str, segments: list[dict]) -> dict | None:
    """Find the segment a quote came from. Single lines first, then neighbouring pairs."""
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
    segments = json.loads((session / "transcript.json").read_text(encoding="utf-8"))
    reqs = json.loads((session / "requirements.json").read_text(encoding="utf-8"))
    for r in reqs:
        seg = locate(r["quote"], segments)
        if seg:
            r.update(time=stamp(seg["start"]), start=seg["start"], segment_id=seg["id"],
                     speaker=SPEAKER_NAMES.get(seg["source"], seg["source"]))
    (session / "requirements.json").write_text(json.dumps(reqs, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(reqs)


# ============================================================================== main
def write_transcripts(session: Path, meta: dict, segments: list[dict], paragraphs: list[dict]) -> None:
    (session / "transcript.json").write_text(json.dumps(segments, ensure_ascii=False), encoding="utf-8")
    (session / "paragraphs.json").write_text(json.dumps(paragraphs, indent=1, ensure_ascii=False), encoding="utf-8")
    lines = [f"# Transcript: {meta['name']}", "",
             f"Recorded {meta['started'].replace('T', ' ')}, length {stamp(meta.get('duration_s', 0))}.", ""]
    for p in paragraphs:
        lines += [f"**{SPEAKER_NAMES.get(p['source'], p['source'])}, {stamp(p['start'])}**", "",
                  p.get("polished") or p["text"], ""]
    (session / "transcript.md").write_text("\n".join(lines), encoding="utf-8")


def requirements_markdown(meta: dict, reqs: list[dict], dropped: int) -> str:
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
            out += [f"**{r['id']}{cat}.** {r['statement']}  ", f"> \"{r['quote']}\"  ",
                    f"> {r['speaker'] or 'Unknown'}, at {r['time'] or '?'}  "]
            out += [f"> Check: {f}  " for f in r["flags"]] + [""]
    out += ["## Summary", "", f"* {len(reqs)} items suggested",
            f"* {dropped} suggestions dropped because their quote could not be found in the transcript",
            f"* {sum(1 for r in reqs if r['flags'])} flagged for vague wording"]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("session", nargs="?", type=Path)
    ap.add_argument("--quick", action="store_true", help="reuse the live transcript instead of re-transcribing")
    ap.add_argument("--retranscribe", action="store_true", help="(default) kept for compatibility")
    ap.add_argument("--asr-model", default="large-v3-turbo")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--no-denoise", action="store_true", help="skip the background noise clean up")
    ap.add_argument("--llm", default="qwen3:8b")
    ap.add_argument("--min-grounding", type=float, default=0.85)
    ap.add_argument("--relink", action="store_true", help="only fix time and speaker links of saved requirements")
    ap.add_argument("--summary-only", action="store_true", help="only rebuild the summary from saved parts")
    ap.add_argument("--polish-only", action="store_true", help="only rebuild and polish the readable transcript")
    ap.add_argument("--no-polish", action="store_true", help="skip the polished transcript step")
    ap.add_argument("--fresh", action="store_true", help="transcribe again even if an accurate transcript exists")
    args = ap.parse_args()

    session = args.session or latest_session()
    meta = json.loads((session / "session.json").read_text(encoding="utf-8"))
    print(f"Session: {session.name}", flush=True)
    global VOCAB, HOTWORDS
    if meta.get("vocabulary"):
        # the topic and key words for this session guide spelling of names and domain terms
        VOCAB = f"Requirements interview in Ghana. {meta['vocabulary'].strip()}"
        HOTWORDS = meta["vocabulary"].strip()
    if args.relink:
        print(f"Relinked {relink(session)} requirements in {session.name}")
        return 0

    try:
        httpx.get("http://localhost:11434/api/tags", timeout=5).raise_for_status()
    except Exception:
        sys.exit("Ollama is not running. Start the Ollama app (or run `ollama serve`) and try again.")

    if args.polish_only:
        segments = json.loads((session / "transcript.json").read_text(encoding="utf-8"))
        paragraphs = build_paragraphs(segments)
        n = polish(paragraphs, args.llm, HOTWORDS or VOCAB, 0.02, 0.98)
        write_transcripts(session, meta, segments, paragraphs)
        step(1.0, f"Polished {n} of {len(paragraphs)} paragraphs")
        return 0

    if args.summary_only:
        notes = json.loads((session / "part_summaries.json").read_text(encoding="utf-8"))
        reqs = json.loads((session / "requirements.json").read_text(encoding="utf-8"))
        step(0.9, "Writing the summary")
        s = summarise(meta, notes, reqs, args.llm)
        (session / "summary.json").write_text(s.model_dump_json(indent=2), encoding="utf-8")
        (session / "summary.md").write_text(summary_markdown(meta, s), encoding="utf-8")
        step(1.0, "Summary ready")
        return 0

    # 1. transcript
    if args.quick:
        segments = live_segments(session)
        tx_share = 0.0
    elif not args.fresh and accurate_transcript(session):
        # an earlier run already made the accurate transcript (for example it stopped later on): reuse it
        segments = accurate_transcript(session)
        tx_share = 0.0
        step(0.01, f"Reusing the accurate transcript from the last run ({len(segments)} lines)")
    else:
        tx_share = 0.45
        segments = transcribe(session, args.asr_model, args.threads, tx_share, denoise=not args.no_denoise)
    if not segments:
        sys.exit("No speech found in this session.")
    for i, s in enumerate(segments):
        s["id"] = i
    paragraphs = build_paragraphs(segments)
    write_transcripts(session, meta, segments, paragraphs)
    step(tx_share + 0.02, f"Transcript ready: {len(segments)} lines, {len(paragraphs)} paragraphs")

    # 2. extraction, with a short summary of each part
    text = "\n".join(f"{SPEAKER_NAMES.get(s['source'], s['source'])}: {s['text']}" for s in segments)
    parts = chunks(text)
    found, dropped, notes = [], 0, []
    span = 0.8 - (tx_share + 0.02)
    for n, part in enumerate(parts, 1):
        step(tx_share + 0.02 + span * (n - 1) / len(parts), f"Reading the conversation, part {n} of {len(parts)}")
        result = call_llm(args.llm, part)
        notes.append(result.summary)
        for c in result.candidates:
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
    (session / "part_summaries.json").write_text(json.dumps(notes, indent=1, ensure_ascii=False), encoding="utf-8")
    (session / "requirements.json").write_text(json.dumps(reqs, indent=2, ensure_ascii=False), encoding="utf-8")
    (session / "requirements.md").write_text(requirements_markdown(meta, reqs, dropped), encoding="utf-8")

    # 3. summary of the whole session
    step(0.8, "Writing the summary")
    s = summarise(meta, notes, reqs, args.llm)
    (session / "summary.json").write_text(s.model_dump_json(indent=2), encoding="utf-8")
    (session / "summary.md").write_text(summary_markdown(meta, s), encoding="utf-8")

    # 4. polished reading version of the transcript (last, so items and summary are ready sooner)
    if not args.no_polish:
        n = polish(paragraphs, args.llm, HOTWORDS or VOCAB, 0.83, 0.99)
        write_transcripts(session, meta, segments, paragraphs)
        print(f"  polished {n} of {len(paragraphs)} paragraphs", flush=True)

    step(1.0, f"Done: {len(reqs)} items, {dropped} dropped as ungrounded")
    print(f"  {session / 'transcript.md'}\n  {session / 'summary.md'}\n  {session / 'requirements.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
