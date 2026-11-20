# srs-assistant

I do a lot of requirement gathering. Interviews, workshops, long calls where a client explains how their business works. The hard part is never the talking. It is going back afterwards, digging through notes and half remembered sentences, and turning all of that into a clean list of requirements without losing what people actually said.

So I am building a tool that sits in on those sessions and listens. It records, writes out what was said, and pulls out the requirements for me to review. Every requirement points back to the exact words someone used, so I can always check where it came from.

It runs completely on my own laptop. No audio goes to any cloud service.

## Why Twi matters here

Most of the people I talk to speak English, but they switch into Twi when they want to explain something properly. Off the shelf speech tools handle English well and Twi badly, and they fall apart when someone mixes the two in one sentence. A big part of this project is finding a setup that copes with that.

## Where it is right now

This is early. What exists today is a working test bench in the `spike` folder:

* **Live recording.** It captures my microphone and whatever the computer is playing at the same time, so it works for people in the room and for Zoom, Teams or WhatsApp calls. Audio is saved to disk every few seconds, so a crash does not lose the session.
* **Live transcript.** An English draft appears on screen while the session is going. Anything that does not look like English gets flagged for a slower Twi pass afterwards.
* **Model comparison.** A script that runs several speech models (Whisper plus a few Twi models trained on Ghanaian data) on the same clip, so I can see which one handles my recordings best.
* **Twi to English.** Translation with Meta's NLLB model, keeping the original Twi as the evidence.
* **Requirement extraction.** A local language model (Qwen3 8B through Ollama) reads the transcript and suggests requirements. Each one has to quote the transcript word for word, and the code checks the quote is really there before I ever see it.

The actual app with a proper review screen comes next.

## Trying it

You need Windows, Python handled through [uv](https://docs.astral.sh/uv/), FFmpeg and [Ollama](https://ollama.com).

```powershell
cd spike
uv sync
ollama pull qwen3:8b

# record a session (Ctrl+C to stop)
uv run python live_record.py --name first-interview

# compare speech models on clips you put in spike/audio
uv run python asr_compare.py

# suggest requirements from a transcript
uv run python extract.py results/asr_<clip>.json
```

The first run downloads the models, a few gigabytes in total. After that everything works offline. More detail is in [spike/README.md](spike/README.md).

## The thinking behind it

I wrote the research and decisions down as I went:

* [01 Research and approach](docs/01-research-and-approach.md): what already exists, what the research says, and the overall plan.
* [02 Local tech stack](docs/02-local-tech-stack.md): which tools, and why, given my laptop has no NVIDIA card and 16 GB of RAM.
* [03 Spike findings](docs/03-spike-findings.md): what happened when I actually ran everything.

## A note on privacy

Recordings, transcripts and results are ignored by git on purpose. They contain real people's voices and business details, and they stay on my machine. If you use this, please tell people they are being recorded and get their OK first.

## What is next

* Test with real English, Twi and mixed recordings and pick the best Twi model.
* Add speaker separation for in person group sessions.
* Build the review app: transcript next to audio, click a requirement to hear where it came from, accept or edit or reject.
* Export a proper requirements document (SRS) and user stories.
