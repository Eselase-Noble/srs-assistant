# 02: Local Tech Stack (personal, fully offline)

| | |
|---|---|
| **Status** | Draft v0.1 |
| **Date** | 2026-11-19 |
| **Supersedes** | §5 of `01-research-and-approach.md` (that version assumed a cloud SaaS) |

## 1. Decisions captured
| Decision | Answer |
|---|---|
| Users | Personal tool, single user (me) |
| Hosting | **100% local**: no cloud STT, no cloud LLM, audio never leaves the machine |
| Languages | **English mostly, Twi sometimes**, including **code-switching** (mixing both in one sentence) |

## 2. Target machine (measured)
| Item | Value | Implication |
|---|---|---|
| CPU | Intel Core Ultra 7 155H (16 cores / 22 threads) | Good for CPU inference (int8 / GGUF) |
| GPU | Intel Arc iGPU (shared memory), **no NVIDIA/CUDA** | Most AI tools assume CUDA. Use CPU builds or Intel paths (OpenVINO / Vulkan) |
| RAM | 16 GB | One large model in memory at a time. **Run pipeline steps one after another, not in parallel** |
| Disk | ~740 GB free | Plenty for models and recordings |
| Installed | Python 3.14, Node.js, Git | Python 3.14 is too new for parts of the ML stack. Use **Python 3.12 via `uv`** |
| Missing | FFmpeg, Ollama | Need to install |

> **Update after spike (see `03-spike-findings.md`):** live mode *is* feasible. `live_record.py` captures mic + system audio and Whisper small keeps up with a live English draft (2 to 3× real time). Twi and the accurate pass still run after the session.

**Original assessment:** this machine handles **post-session processing** well. A full live co-pilot (transcription plus LLM at the same time) would compete for RAM and CPU. Live mode is limited to **recording plus optional lightweight live captions**, and the heavy analysis runs right after the session.

## 3. Recommended stack

### 3.1 Speech-to-text (the hardest part, because of Twi)
| Role | Tool | Why |
|---|---|---|
| English ASR | **faster-whisper** (Whisper `large-v3-turbo` or `small`, int8 on CPU) | Mature, accurate English, word timestamps, runs on CPU |
| Twi / English-Twi code-switching | **Kasanoma** (`projectkasa/kasanoma_whisper`): Whisper fine-tuned on bilingual English/Twi | Built for exactly our case. License is research/education, which is fine for personal use |
| Twi fallback | **GiftMark/akan-whisper-model** or **Whisper fine-tuned on WAXAL (Akan)** | Alternatives to benchmark. WAXAL tiny reports about 38% WER / 16% CER on spontaneous Akan |
| Candidate to test | **Meta Omnilingual ASR** (Apache-2.0, `pip install omnilingual-asr`) | 1,600+ languages. **Twi/Akan support not yet confirmed**: check `supported_langs` |
| Language routing | Whisper language-ID per segment | Send English segments to the English model and Twi or mixed segments to the Twi model |
| Speaker diarization | **pyannote.audio** (community-1 pipeline, CPU) | Best open-source diarization. Fine for batch on CPU. Needs a one-time Hugging Face model download, then runs offline |
| Audio handling | **FFmpeg** | Converts any recording to 16 kHz mono WAV |
| Live captions (optional) | **whisper.cpp** (Vulkan/OpenVINO for Intel Arc) or faster-whisper `small` | Light enough to run while recording |

**Honest expectation:** English will be good. Twi will be **usable but imperfect**: expect transcript edits, especially for spelling of Twi words and names. The review screen must make transcript correction fast.

### 3.2 Translation (Twi → English)
* **Meta NLLB-200 distilled 600M** (supports `twi_Latn` / `aka_Latn`, runs on CPU). Twi segments are translated to English **before** extraction, because local LLMs understand Twi poorly. The **original Twi text is always kept** as the evidence; the translation is shown alongside it.
* License is CC-BY-NC, which is fine for personal use.

### 3.3 Local LLM (requirement extraction)
| Item | Choice |
|---|---|
| Runtime | **Ollama** (simple API on `localhost:11434`; supports CPU and Intel GPU via Vulkan). Alternative: LM Studio |
| Models (16 GB RAM) | 7 to 9B models at Q4 quantization: **Qwen3 8B** (strong structured JSON), **Llama 3.1 8B**, **Gemma 3 12B Q4** if memory allows. Benchmark 2 of these on our gold transcripts |
| Embeddings | `nomic-embed-text` or `bge-m3` via Ollama (for duplicate detection) |
| Output control | Ollama **JSON-schema structured output**, validated with Pydantic |

A small local model is weaker than a frontier cloud model, so the pipeline has to make up for it:
* Short chunks (a few minutes of transcript each) and one task per prompt (extract → classify → quality-check as separate calls).
* **Mandatory verbatim quote and a code-level grounding check** (the quote must exist in the transcript, or the candidate is dropped).
* A deterministic rules engine for vague words and 29148 quality flags; the LLM is not used for this.
* Human review of everything.
* The LLM layer stays behind an adapter, so a stronger model (local or cloud) can be swapped in later without code changes.

### 3.4 Application
| Layer | Choice | Why |
|---|---|---|
| Backend | **Python 3.12 + FastAPI**, managed with **uv** | The whole AI/audio ecosystem is Python |
| Background jobs | In-process worker queue backed by SQLite (e.g. **Huey** with its SQLite storage) | No Redis needed. Jobs survive restarts and can be retried |
| Database | **SQLite** (+ `sqlite-vec` for embeddings) | One file, zero setup, easy to back up |
| Files | Local folder `data/` (audio, exports), organised per project/session | Simple and transparent |
| Frontend | **React + TypeScript + Vite**, served locally | Rich review UI (transcript ↔ audio sync, side-by-side requirements) |
| Audio player / waveform | `wavesurfer.js` | Click a quote → jump to that moment |
| Recording | Browser MediaRecorder, saving in chunks to disk as it records | A crash never loses the session |
| Exports | Markdown → **DOCX** (`python-docx`) and **PDF**; CSV; user stories | SRS following ISO/IEC/IEEE 29148 |
| Packaging (later) | Optionally wrap as a desktop app (Tauri) | Start as `localhost` web app |

### 3.5 Languages used to build it
* **Python**: backend, audio pipeline, AI pipeline, exports.
* **TypeScript**: frontend.
* **SQL**: SQLite schema and migrations (via SQLAlchemy + Alembic).

## 4. Processing pipeline on this machine
```
Record/Import ─► FFmpeg normalize ─► Diarize (pyannote) ─► Language-ID per segment
   ─► ASR: English→faster-whisper | Twi/mixed→Kasanoma ─► Twi→English (NLLB)
   ─► Chunk ─► LLM extract (Ollama, JSON) ─► Grounding check ─► Classify + rule checks
   ─► Embeddings + dedupe ─► Review UI ─► Export SRS / stories
```
Each arrow is a separate, resumable job. Models are loaded one at a time to stay within 16 GB.
Rough timing to measure in a spike: a 1-hour interview is expected to take tens of minutes end-to-end on CPU.

## 5. Setup to install
1. `uv` → Python 3.12 virtual environment
2. FFmpeg (`winget install Gyan.FFmpeg`)
3. Ollama (`winget install Ollama.Ollama`) + pull one 8B model and one embedding model
4. Python packages: `faster-whisper`, `transformers`, `torch` (CPU), `pyannote.audio`, `fastapi`, `sqlalchemy`, `huey`, `python-docx`, `pydantic`
5. One-time model downloads (Kasanoma, NLLB, pyannote, Whisper). After that, **fully offline**

## 6. First technical spike (before full build)
Goal: prove the hard parts on real audio before writing the app.
1. Record 3 short test clips: English only, Twi only, mixed English/Twi.
2. Run Whisper vs Kasanoma vs Akan-Whisper vs Omnilingual and compare the transcripts by hand.
3. Run pyannote on a 2 to 3 speaker clip.
4. Run NLLB on the Twi output.
5. Run extraction with 2 local LLMs on the English transcript.
6. Record speed and RAM use for each step.

## 7. Sources
* Kasanoma (English/Twi code-switching Whisper): https://huggingface.co/projectkasa/kasanoma_whisper
* Akan Whisper model: https://huggingface.co/GiftMark/akan-whisper-model
* Whisper-tiny WAXAL Akan: https://friendli.ai/models/waxal-benchmarking/whisper-tiny-waxal-aka
* Google WAXAL dataset: https://research.google/blog/waxal-a-large-scale-open-resource-for-african-language-speech-technology/
* Akan ASR benchmark study: https://www.themoonlight.io/review/benchmarking-akan-asr-models-across-domain-specific-datasets-a-comparative-evaluation-of-performance-scalability-and-adaptability
* Meta Omnilingual ASR: https://ai.meta.com/research/publications/omnilingual-asr-open-source-multilingual-speech-recognition-for-1600-languages/
