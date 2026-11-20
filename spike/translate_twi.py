"""Translate Twi text to English locally with Meta NLLB-200 (distilled 600M).

Usage:
    uv run python translate_twi.py "Me pɛ sɛ me hwɛ me sika wɔ app no so"
    uv run python translate_twi.py --from-asr results/asr_twi.json --model akan-turbo
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import measure, save_json

MODEL_ID = "facebook/nllb-200-distilled-600M"
SRC = "twi_Latn"  # Akan/Twi; "aka_Latn" is the alternative code
TGT = "eng_Latn"


def load():
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL_ID, src_lang=SRC)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID)
    return tok, model


def translate(texts: list[str], tok, model) -> list[str]:
    out = []
    for t in texts:
        if not t.strip():
            out.append("")
            continue
        inputs = tok(t, return_tensors="pt", truncation=True, max_length=400)
        gen = model.generate(**inputs, forced_bos_token_id=tok.convert_tokens_to_ids(TGT), max_new_tokens=400)
        out.append(tok.batch_decode(gen, skip_special_tokens=True)[0])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="*")
    ap.add_argument("--from-asr", type=Path, help="asr_<clip>.json produced by asr_compare.py")
    ap.add_argument("--model", default="akan-turbo", help="which ASR model's segments to translate")
    args = ap.parse_args()

    if args.from_asr:
        data = json.loads(args.from_asr.read_text(encoding="utf-8"))
        texts = [s["text"] for s in data["models"][args.model]["segments"]]
    else:
        texts = [" ".join(args.text)] if args.text else []
    if not texts:
        print("Nothing to translate.")
        return 1

    with measure() as m:
        tok, model = load()
        english = translate(texts, tok, model)
    rows = [{"twi": t, "english": e} for t, e in zip(texts, english)]
    for r in rows:
        print(f"TWI: {r['twi']}\nENG: {r['english']}\n")
    print(f"{m.seconds}s, peak {m.peak_rss_mb} MB")
    name = f"translate_{args.from_asr.stem}.json" if args.from_asr else "translate_cli.json"
    save_json(name, {"model": MODEL_ID, "seconds": m.seconds, "peak_rss_mb": m.peak_rss_mb, "rows": rows})
    return 0


if __name__ == "__main__":
    sys.exit(main())
