# 03: Technical Spike Findings

| | |
|---|---|
| **Status** | Round 1 complete (synthetic audio). Round 2 needs real English/Twi recordings |
| **Date** | 2026-11-19 |
| **Code** | `spike/` (see `spike/README.md`) |

## 1. What was tested
Test audio: `spike/audio/sample_english_tts.wav`. It is a 78-second, 2-voice synthetic English interview made with Windows text-to-speech. It contains 9 known requirements, including a business rule, a non-functional requirement, an access rule and an open question about Twi.
Machine: Core Ultra 7 155H, 16 GB RAM, CPU only.

## 2. Results

### 2.1 Speech-to-text (models already downloaded; transcription time only)
| Model | Speed | RAM | English quality | Notes |
|---|---|---|---|---|
| Whisper large-v3-turbo (faster-whisper int8) | **1.1× real time** (1 h audio ≈ 55 min) | 1.8 GB | Excellent | Best accuracy for the post-session pass |
| Whisper small (int8) | **2.3 to 3× real time** (1 h ≈ 20 to 25 min) | 0.7 GB | Excellent on clean audio | **Fast enough for live mode** |
| Akan turbo (ghananlp, WAXAL) | 0.56× real time (1 h ≈ 1 h 50 min) | 1.9 GB | Turns English into Twi-like gibberish | Twi-only. Must not receive English |
| Akan small (WAXAL / GiftMark) | 0.5× real time | 2.1 GB | Starts in English, then falls into repetition loops | Twi-only |
| Kasanoma (English/Twi) | n/a | n/a | n/a | Not tested: gated, access must be requested |

* 6 CPU threads perform the same as 12, so the default is now 6.
* Thread count made no difference; model size is what drives speed.

**Conclusions**
1. **Language routing is mandatory.** The Twi models destroy English audio, and English Whisper cannot write Twi (it mislabels Twi as Portuguese, Yoruba and so on). The pipeline runs English Whisper first, and only segments it detects as *non-English* go to the Twi model.
2. Whisper occasionally **hallucinates text from silence or noise**: an invented trailing sentence, and "Thank you." / "Welcome." on mic clicks. Fixed with `condition_on_previous_text=False`, VAD, confidence/compression filters and a stock-phrase filter.
3. Local words get misheard ("cedis" → "SATIS"/"Sadis", "Twi" → "CHWI"). A vocabulary prompt helps in some runs (the live run got "Cedis" and "Twi" right) but not reliably. The app needs a **project glossary with automatic correction** and easy manual edits.

### 2.2 Requirement extraction (Ollama, qwen3:8b, CPU)
* **9 of 9** scripted requirements found. **9 of 9 quotes passed the grounding check** (exact match against the transcript). Took 113 s for 1,176 characters.
* Vague-word flags fired correctly ("should be able", "fast").
* Weaknesses: statements were copied verbatim and not rewritten as "The system shall…". "Only managers should see profit figures" was labelled *functional* when it should be *security (non-functional)*. ASR errors ("SATIS") flowed straight into the requirements. → Next step: a separate rewrite/classify pass, and glossary correction before extraction.
* Projected: 1-hour interview ≈ 13 chunks ≈ 25 minutes.

### 2.3 Twi → English translation (NLLB-200 600M)
| Twi (test sentence) | NLLB output |
|---|---|
| Me pɛ sɛ me tumi hwɛ me sika wɔ fon no so. | I want to be able to monitor my money on the phone. |
| Sɛ intanɛt nni hɔ a, ɛsɛ sɛ application no kɔ so yɛ adwuma. | When the Internet is not available, the application must continue to operate. |
| Akontaabufoɔ no hia nkrataa a ɛkyerɛ sika a yɛanya ɔsram biara. | Accountants need a letter stating the monthly income. |
Good quality on clean written Twi ("nkrataa" → "letter" should be "report"). The real test is on *transcribed* Twi, which will be noisier. Peak RAM was 2.9 GB.

### 2.4 Live listening (`live_record.py`)
* Captures **microphone + system audio (WASAPI loopback)** at the same time, so Zoom/Teams/Meet/WhatsApp calls work as well as in-person sessions. Separate sources give a free speaker label (MIC = room, SYSTEM = remote side).
* Audio is saved as 15-second WAV chunks while recording (crash-safe). On stop the chunks are joined into `mic.wav`, `system.wav` and `mixed.wav`, and `session.json` stores the metadata and consent note.
* Live transcript with Whisper small: every sentence in the sample was transcribed correctly. A carry-over buffer fixed words that were being split at chunk boundaries. Lag was about 15 to 60 s behind live and never affected recording.
* Non-English speech is flagged `needs_twi_pass` for the accurate pass after the session. The Twi models run at 0.5× real time, which is too slow to keep up live.
* **Echo:** with loudspeakers, the mic hears the remote side again, and Whisper produces junk from it. → **Use headphones on calls.** Later: echo-aware filtering.

## 3. Decisions confirmed by the spike
| Area | Decision |
|---|---|
| Live mode | **Feasible**: record + live English draft transcript with Whisper small. Twi and the accurate pass run after the session |
| Post-session ASR | Whisper large-v3-turbo for everything → non-English segments re-done with the best Twi model → NLLB translation |
| Extraction | qwen3:8b is good enough for an assistant role, with grounding check + separate classify/rewrite pass + human review |
| Hallucination control | Required at every ASR step (filters above) |
| Glossary | Required: feeds the ASR prompt and an automatic correction step |

## 4. Open items / round 2 (needs you)
1. **Real recordings**: English, Twi and mixed clips with what was actually said written out (`spike/audio/`). This is the only way to choose the Twi model.
2. **Hugging Face account**: accept pyannote's terms (speaker separation for in-room group sessions) and request Kasanoma access.
3. Benchmark Kasanoma and Omnilingual ASR on the real Twi clips.
4. Test the extraction rewrite/classify pass and a second LLM (Llama 3.1 8B or Gemma 3 12B) for comparison.

## 5. Known technical notes
* `av` 19 breaks faster-whisper's built-in file decoding (`metadata_errors` error). Our code always passes decoded numpy audio, so it is unaffected.
* The Hugging Face cache warns about symlinks on Windows. This is harmless; set `HF_HUB_DISABLE_SYMLINKS_WARNING=1`.
* Downloaded models are in about `%USERPROFILE%\.cache\huggingface` (~8 GB) plus Ollama's model folder (~5.5 GB).
