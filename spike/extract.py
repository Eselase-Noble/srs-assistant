"""Extract requirement candidates from a transcript with a local LLM (Ollama),
then run a code-level grounding check: every candidate must quote the transcript verbatim.

Usage:
    uv run python extract.py results/asr_interview.json --asr-model whisper-turbo
    uv run python extract.py transcript.txt --llm qwen3:8b
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from common import measure, save_json

OLLAMA = "http://localhost:11434/api/chat"
CHUNK_CHARS = 4000      # ~3-4 minutes of speech per LLM call
OVERLAP_CHARS = 400


class ReqType(str, Enum):
    functional = "functional"
    non_functional = "non_functional"
    constraint = "constraint"
    business_rule = "business_rule"
    assumption = "assumption"
    open_question = "open_question"
    current_process = "current_process"
    pain_point = "pain_point"
    stakeholder = "stakeholder"


class Candidate(BaseModel):
    statement: str = Field(description="One requirement, rewritten as 'The system shall ...' where possible")
    type: ReqType
    quality_category: str | None = Field(
        None, description="ISO/IEC 25010 category for non_functional (performance, security, usability, "
                          "reliability, compatibility, maintainability, portability), else null")
    quote: str = Field(description="Exact words copied verbatim from the transcript that support this")
    speaker: str | None = None
    confidence: float = Field(ge=0, le=1)


class Extraction(BaseModel):
    # summary comes first so the model reads the whole excerpt before listing items
    summary: str = Field("", description="3 to 5 plain sentences on what this part of the conversation "
                                         "covered: topics, facts given, problems raised. No bullet points.")
    candidates: list[Candidate]


SYSTEM = """You are a senior requirements analyst. You read an excerpt of a requirements-elicitation \
interview transcript and extract requirement candidates.

Rules:
- Extract only what a stakeholder actually said or clearly implied. Never invent requirements.
- Each candidate is ONE requirement (singular). Split compound statements.
- "statement" is YOUR clean rewrite, not a copy of the quote: "The system shall ..." for functional and
  non_functional items, a plain sentence for the other types. Never start it with "And", "I", "We".
- Who may see or do what (permissions, access, privacy) is non_functional with quality_category "security".
- "quote" MUST be copied character-for-character from the transcript (a short span, 5-40 words).
- Classify: functional = behaviour/feature; non_functional = quality (speed, security, usability...);
  constraint = imposed limit (technology, budget, law, deadline); business_rule = policy the business follows;
  assumption = something taken as true; open_question = something unclear that needs follow-up;
  current_process = a step in how the work is done today (who does what, with which tools, how often);
  pain_point = a problem, delay, error or frustration in the current way of working;
  stakeholder = a role, team or outside party involved in the work (statement: who they are and what they do).
- Interviews about daily operations are mostly current_process and pain_point. Capture them all: they are
  where future requirements come from.
- Ignore greetings, small talk and the interviewer's own questions unless the stakeholder confirms them.
- If nothing relevant is present, return an empty list.
- Also write "summary": a short factual summary of this excerpt in plain sentences."""

VAGUE = re.compile(
    r"\b(fast|quick(ly)?|easy|easily|user[- ]friendly|simple|intuitive|efficient|flexible|robust|"
    r"secure|modern|nice|good|better|best|etc\.?|and so on|as appropriate|as needed|if possible|"
    r"some|several|many|few|soon|regularly|normally|usually|probably|maybe|should be able)\b",
    re.IGNORECASE,
)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def grounding_score(quote: str, transcript: str) -> float:
    """1.0 = quote appears verbatim (after normalisation); otherwise best fuzzy window match."""
    q, t = norm(quote), norm(transcript)
    if not q:
        return 0.0
    if q in t:
        return 1.0
    words, qn = t.split(), len(q.split())
    best = 0.0
    for i in range(0, max(1, len(words) - qn + 1)):
        window = " ".join(words[i:i + qn])
        best = max(best, SequenceMatcher(None, q, window).ratio())
        if best > 0.97:
            break
    return round(best, 3)


def chunks(text: str) -> list[str]:
    out, i = [], 0
    while i < len(text):
        end = min(len(text), i + CHUNK_CHARS)
        if end < len(text):
            nl = text.rfind("\n", i + CHUNK_CHARS // 2, end)
            end = nl if nl > 0 else end
        out.append(text[i:end])
        if end >= len(text):
            break
        i = max(end - OVERLAP_CHARS, i + 1)
    return out


def call_llm(model: str, excerpt: str) -> Extraction:
    body = {
        "model": model,
        "stream": False,
        "think": False,
        "format": Extraction.model_json_schema(),
        "options": {"temperature": 0, "num_ctx": 8192},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Transcript excerpt:\n\n{excerpt}"},
        ],
    }
    r = httpx.post(OLLAMA, json=body, timeout=900)
    r.raise_for_status()
    return Extraction.model_validate_json(r.json()["message"]["content"])


def load_transcript(path: Path, asr_model: str) -> str:
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if "transcript" in data:  # diarized output
            segs = data["transcript"]
        else:
            segs = data["models"][asr_model]["segments"]
        return "\n".join(f"{s.get('speaker', 'SPEAKER')}: {s['text']}" for s in segs)
    return path.read_text(encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript", type=Path, help=".txt, asr_*.json or diarize_*.json")
    ap.add_argument("--asr-model", default="whisper-turbo")
    ap.add_argument("--llm", default="qwen3:8b")
    ap.add_argument("--min-grounding", type=float, default=0.85)
    args = ap.parse_args()

    text = load_transcript(args.transcript, args.asr_model)
    parts = chunks(text)
    print(f"{len(text)} chars -> {len(parts)} chunk(s), model {args.llm}")

    accepted, rejected = [], []
    with measure() as m:
        for n, part in enumerate(parts, 1):
            print(f"  chunk {n}/{len(parts)} ...", flush=True)
            for c in call_llm(args.llm, part).candidates:
                score = grounding_score(c.quote, text)
                item = c.model_dump(mode="json") | {"grounding": score}
                vague = sorted({w.group(0).lower() for w in VAGUE.finditer(c.statement + " " + c.quote)})
                if vague:
                    item["quality_flags"] = [f"vague wording: {', '.join(vague)}"]
                (accepted if score >= args.min_grounding else rejected).append(item)

    # naive exact-duplicate removal (overlapping chunks); real dedupe uses embeddings later
    seen, unique = set(), []
    for c in accepted:
        key = norm(c["statement"])
        if key not in seen:
            seen.add(key)
            unique.append(c)

    for i, c in enumerate(unique, 1):
        flags = f"  ⚠ {'; '.join(c.get('quality_flags', []))}" if c.get("quality_flags") else ""
        print(f"REQ-{i:03d} [{c['type']}] {c['statement']}\n         \"{c['quote']}\" "
              f"(grounding {c['grounding']}){flags}")
    print(f"\n{len(unique)} grounded candidates, {len(rejected)} rejected as ungrounded, "
          f"{m.seconds}s, peak {m.peak_rss_mb} MB (Ollama runs in its own process)")

    save_json(f"extract_{args.transcript.stem}_{args.llm.replace(':', '-')}.json", {
        "source": str(args.transcript), "llm": args.llm, "seconds": m.seconds,
        "candidates": unique, "rejected_ungrounded": rejected,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
