# Requirements Elicitation Assistant: Research & Build Approach

| | |
|---|---|
| **Document** | 01: Research & Approach |
| **Status** | Draft v0.1 (for discussion) |
| **Date** | 2026-11-19 |
| **Next documents** | Vision & Scope → SRS → Architecture → Data model → AI pipeline spec → Test/evaluation plan |

---

## 1. The idea in one paragraph

A system that **sits in on requirement-gathering sessions** (interviews, workshops, focus groups, calls) and **listens**: it records, transcribes, works out who said what, and turns the conversation into **structured, traceable requirements**. Every requirement links back to the exact words a stakeholder said. While the session is running it can also act as a **co-pilot for the analyst**: it shows what has been covered, what is still unclear, and which follow-up questions are worth asking. After the session it produces review-ready output (requirement lists, user stories, glossary, open questions, conflicts) and, later, a full SRS document.

**Core principle:** the AI *proposes* and the analyst *decides*. Nothing becomes an approved requirement without a human accepting it, and every proposal carries its evidence.

---

## 2. Domain background (what the system must respect)

### 2.1 Elicitation techniques the system should support
| Technique | What the system does |
|---|---|
| One-to-one interviews (structured / semi-structured / open) | Main use case. Live transcript, question guide, coverage tracking |
| Workshops / JAD sessions (many speakers) | Speaker separation (diarization) matters a lot; detect when people disagree |
| Focus groups | As for workshops, plus a summary of where opinions agree or split |
| Remote calls (Zoom/Teams/Meet) | Capture call audio or import the recording |
| Observation / shadowing | Analyst dictates notes; same pipeline |
| Document analysis | Later phase: ingest existing documents (policies, old specs) as extra sources |
| Questionnaires | Later phase: import responses as text sources |

### 2.2 What gets extracted
* **Functional requirements**: what the system must do.
* **Non-functional / quality requirements**: classified with **ISO/IEC 25010** (performance, security, usability, reliability, maintainability, and so on).
* **Constraints**: regulatory, technical, budget, schedule.
* **Business rules**, **assumptions**, **dependencies**.
* **Stakeholders and roles** mentioned, **goals**, **pain points**, **current-process descriptions**.
* **Glossary terms**: domain vocabulary and acronyms.
* **Open questions / TBDs** and **conflicts** between stakeholders.

### 2.3 Standards and quality criteria
* **ISO/IEC/IEEE 29148** (requirements engineering; it replaced IEEE 830). Use it for the SRS template and for requirement-quality attributes: *necessary, unambiguous, complete, singular, feasible, verifiable, correct, conforming*.
* **User stories**: "As a ⟨role⟩, I want ⟨goal⟩, so that ⟨benefit⟩", checked against **INVEST**, with Gherkin-style acceptance criteria (Given/When/Then).
* **Prioritisation**: MoSCoW, with optional value/effort scoring.
* **Ambiguity detection**: flag vague words ("fast", "user-friendly", "etc.", "as appropriate", "should probably") and suggest how to make them measurable.

---

## 3. State of the art

### 3.1 Research (this is an active RE research area)
* **Interview → requirements alignment.** Dente, Dalpiaz and Papotti (RE 2026) formalise checking whether user stories match an interview transcript. They propose two metrics, **requirements faithfulness** and **interview coverage**. → *We should adopt both as our quality metrics.*
* **Generative Goal Modeling.** Uses textual entailment to pull goals out of transcripts. GPT-4o matched about 62% of the goals human analysts found and traced goals to the source text with about 98.7% accuracy. → *Tracing to evidence is reliable. Full recall is not, so the human review step stays.*
* **From Elicitation Interviews to Software Requirements (WER 2025).** Compares LLMs on stakeholder transcripts. They extract requirements well (especially non-functional ones) but **struggle with ambiguity and categorisation**. → *Classification needs explicit criteria and human correction.*
* **Follow-up question generation.** Studies show LLMs can suggest useful follow-up questions during interviews. → *This supports the live co-pilot feature.*
* **LLMREI / LLMs as simulated clients.** LLMs can conduct interviews or play the stakeholder for training, but they sometimes give contradictory information. → *Possible "practice mode" later; not core.*
* A master's thesis (Utrecht) builds a transcript → user-story pipeline **with traceability to the source**. This is close to our concept.

### 3.2 Existing products and the gap
| Category | Examples | What they lack for this use |
|---|---|---|
| Meeting assistants | Otter, Fireflies, Fathom, Teams/Zoom AI | Generic summaries and action items. No requirement model, no quality checks, no traceability, no SRS |
| RE / ALM tools | Jama, IBM DOORS, Visure, Polarion, Jira | Strong requirements management, but humans enter the requirements. AI add-ons work on text, not on live conversation |
| Transcription APIs | Deepgram, AssemblyAI, Speechmatics, Whisper | Raw text only |

**Our niche:** *conversation → evidence-linked, quality-checked requirements → SRS*, with an analyst co-pilot. Nothing in the market combines these end to end.

---

## 4. Product concept

### 4.1 Two operating modes
1. **Live mode (co-pilot):** captures audio in real time and shows a rolling transcript with speaker labels. Next to it, a panel shows requirement candidates as they appear, a coverage checklist from the interview guide, ambiguity flags, and suggested follow-up questions. Live mode must stay useful even when the AI is slow or offline: recording and transcription come first.
2. **Post-session mode (analysis):** upload or import a recording, or finish a live session, and the system runs the full, slower, more accurate pipeline. The analyst then reviews, edits, merges, accepts or rejects, and exports.

### 4.2 Core workflow
```
Plan ──► Capture ──► Transcribe & diarize ──► Extract ──► Review ──► Consolidate ──► Document
 │         │               │                    │           │            │              │
 guide,    audio,          utterances with      candidates  accept/      dedupe across  SRS, user
 stake-    consent         speaker + timestamps with quotes edit/reject  sessions,      stories,
 holders                                        + type      (human)      conflicts,     backlog,
                                                                         glossary       traceability
```

### 4.3 Feature list (proposed scope)
**MVP (Phase 1)**
* Projects, stakeholders, sessions; consent capture per session
* Record in the browser *or* upload audio/video files
* Transcription with speaker diarization and timestamps; edit speaker names
* AI extraction of requirement candidates, each with **mandatory source quote(s) and timestamp** (click to replay the audio)
* Classification (FR / NFR + ISO 25010 category / constraint / business rule / assumption)
* Ambiguity and quality flags (29148 attributes)
* Review queue: accept / edit / reject / merge; full change history
* Open-questions list and glossary
* Export: Markdown/DOCX SRS (29148 structure), CSV, user stories

**Phase 2**
* Live co-pilot: streaming transcript, live candidates, interview-guide coverage, suggested follow-ups
* Cross-session consolidation: duplicate detection, **conflict detection between stakeholders**
* Prioritisation (MoSCoW) and stakeholder voting/validation links
* Jira / Azure DevOps / GitHub Issues export; ReqIF export for RE tools

**Phase 3**
* Meeting-platform bots (Zoom/Teams/Meet)
* Document and questionnaire ingestion
* Goal models / use-case diagrams, process diagrams (BPMN-lite)
* Multilingual sessions, on-premise / fully local deployment option
* Practice mode (AI-simulated stakeholder for training analysts)

---

## 5. Proposed architecture

### 5.1 Components
```
┌────────────────────────── Web client (React/Next.js, TypeScript) ───────────────────────────┐
│ Session recorder (MediaRecorder/WebAudio) · Live transcript · Review workspace · Exports    │
└───────────────┬──────────────────────────── WebSocket (live) / HTTPS (REST) ────────────────┘
                │
┌───────────────▼───────────────┐     ┌──────────────────────┐     ┌──────────────────────────┐
│ API service (Python, FastAPI) │────►│ Job queue (Redis +   │────►│ Workers                  │
│ auth, projects, sessions,     │     │ Celery/RQ/Arq)       │     │ • transcription/diarize  │
│ requirements, audit log       │     └──────────────────────┘     │ • AI extraction pipeline │
└───────┬───────────────┬───────┘                                  │ • consolidation/conflict │
        │               │                                          │ • document generation    │
┌───────▼──────┐ ┌──────▼─────────────┐                            └──────────┬───────────────┘
│ PostgreSQL   │ │ Object storage     │◄──────────── audio, exports ──────────┘
│ + pgvector   │ │ (S3/MinIO/local)   │
└──────────────┘ └────────────────────┘
        External/pluggable providers: Speech-to-text (adapter) · LLM (adapter)
```

**Why this shape**
* **Python backend:** the audio and AI tooling (WhisperX, pyannote, LLM SDKs, document generation) is strongest in Python.
* **Async workers and a job queue:** transcription and extraction are slow and can fail. Jobs have to be retryable and resumable and must not block the UI. This is the main source of robustness.
* **Provider adapters:** speech-to-text and LLM vendors change fast. Wrapping them behind interfaces lets us swap cloud for local, or one vendor for another, without rewriting the system.
* **PostgreSQL + pgvector:** relational integrity for requirements and traceability, plus embeddings for duplicate and similarity search, all in one database.

### 5.2 Speech-to-text options
| Option | Live streaming | Diarization | Hosting | Notes |
|---|---|---|---|---|
| Deepgram | Yes (low latency, WebSocket) | Yes | Cloud / on-prem | Strong candidate for live mode |
| AssemblyAI | Yes | Yes for batch; check streaming diarization in current docs | Cloud | Strong batch accuracy and features |
| Speechmatics | Yes | Yes | Cloud / on-prem | Good accent coverage |
| WhisperX (Whisper + pyannote) | Near-real-time at best | Yes | Self-hosted (GPU) | Free, private; best for post-session batch |
| pyannote (diarization only) | n/a | Yes, handles overlap | Self-hosted / API | Pair with any ASR |

**Recommendation:** a hybrid. Use a **streaming cloud API for live mode** and a **high-accuracy batch pass after the session**, which becomes the "source of truth" transcript. Keep a **self-hosted WhisperX path** for clients that cannot send audio to the cloud. Benchmark 2 to 3 providers on our own sample recordings (accents, noise, crosstalk) before committing. Vendor benchmarks conflict and are self-interested.

### 5.3 LLM layer
* Use a strong frontier model, e.g. the Claude family (`claude-sonnet-5-5` for high-volume extraction, `claude-opus-5-5` for consolidation, conflict analysis and SRS synthesis). Put it behind an adapter so other or local models can be used.
* Use **structured output (JSON schema / tool calling)** for every extraction step. The application never parses free text.
* Use prompt caching for the project context (glossary, existing requirements), which gets reused on every chunk.

### 5.4 Core data model (first draft)
```
Project ─┬─ Stakeholder (name, role, org, influence/interest)
         ├─ Session (type, date, guide, consent record, audio files)
         │     └─ Utterance (speaker→Stakeholder, start_ms, end_ms, text, confidence)
         ├─ Requirement (id REQ-###, title, statement, type, ISO25010 category, priority,
         │               status: candidate|accepted|rejected|merged|superseded, version)
         │     ├─ Evidence (→ Utterance(s), quote, ai_confidence)        ← traceability
         │     ├─ QualityFlag (attribute, message, severity)
         │     ├─ AcceptanceCriterion (Given/When/Then)
         │     └─ Relation (duplicates | conflicts_with | refines | depends_on)
         ├─ GlossaryTerm · OpenQuestion · Assumption
         └─ AuditEvent (who, what, when, before/after)  ← every change, human or AI
```

---

## 6. AI pipeline design (where robustness is won or lost)

1. **Preprocess:** clean the transcript and segment it into topical chunks with overlap. Speaker turns are kept intact.
2. **Extract (per chunk):** output candidate items with type, normalised statement, **verbatim quote + utterance IDs**, and confidence. Rule: *no quote, no candidate.*
3. **Verify (grounding check):** a second pass, or plain string matching, confirms each quote actually exists in the transcript and supports the statement. Candidates that fail are dropped or flagged. This targets hallucination directly.
4. **Classify and quality-check:** FR/NFR/ISO 25010 using explicit definitions and examples in the prompt, plus 29148 quality flags and a vague-word lexicon. A deterministic rules engine runs alongside the LLM.
5. **Consolidate (project level):** embedding similarity and LLM adjudication find duplicates and merges; contradictions between stakeholders are surfaced as *conflicts*, never auto-resolved.
6. **Human review:** the analyst accepts, edits or rejects. Edits are stored as **feedback data** for evaluation and prompt improvement.
7. **Generate:** SRS (29148 template), user stories + acceptance criteria, traceability matrix (requirement ↔ quote ↔ stakeholder ↔ session).

**Live-mode variant:** a smaller, faster loop over a rolling window of the last N minutes. It produces *suggestions only* (follow-ups, coverage gaps). The authoritative extraction runs after the session.

### 6.1 Evaluation (how we know it works)
* Build a **gold dataset**: 10 to 20 real or realistic interview recordings with requirements extracted by hand.
* Metrics: **precision / recall** of extracted requirements, **faithfulness** and **coverage** (Dente et al.), classification accuracy, word error rate and diarization error rate for audio, analyst acceptance rate in production.
* Automated regression evals run on every prompt or model change, so quality cannot silently drop.

---

## 7. Robustness, security and compliance

| Concern | Approach |
|---|---|
| Losing a recording | Record locally in chunks (IndexedDB) and upload them resumably. The session survives network drops and browser refreshes. Audio is never only in memory |
| Failed processing | Idempotent, retryable jobs with visible status. Any step can be re-run, e.g. re-extract with a new model |
| Wrong AI output | Mandatory evidence, grounding check, human approval gate, confidence display, full audit trail |
| Consent and law | Explicit recording consent per participant, stored with the session. Visible "recording" indicator. Comply with the applicable data-protection law (e.g. GDPR or local equivalents) |
| Sensitive data | Encryption in transit and at rest, role-based access per project, retention policies, PII redaction option, self-hosted STT/LLM option, contracts with vendors that do not train on our data |
| Accents, noise, crosstalk | Benchmark providers on our own audio, custom vocabulary (glossary fed to the STT), editable transcript, mic-quality guidance |
| Vendor lock-in or outage | Adapter interfaces for STT and LLM, with a fallback provider |
| Scale and cost | Batch the expensive passes, cache project context, track cost per session |

---

## 8. Key risks
1. **Diarization quality in group sessions.** Overlapping speech is still hard. Mitigation: easy speaker correction, and per-person mics where possible.
2. **Recall gaps.** The AI will miss things (about 60% goal recall in research). Mitigation: position the AI as an assistant, show coverage metrics, keep the analyst in the loop.
3. **Trust and privacy concerns from stakeholders.** Mitigation: transparent consent, a local/on-prem option, and a clear statement of where data goes.
4. **Scope creep.** Mitigation: phased roadmap; MVP is post-session analysis first, live co-pilot second.

---

## 9. Proposed roadmap
| Phase | Goal | Outcome |
|---|---|---|
| 0: Documentation (now) | Vision & Scope, SRS for this system, architecture, data model, AI pipeline spec, evaluation plan | Approved specs |
| 1: MVP | Upload/record → transcribe → extract → review → export | Usable on real interviews |
| 2: Live & consolidation | Streaming co-pilot, cross-session merge, conflicts, integrations | Used *during* sessions |
| 3: Expansion | Meeting bots, documents, diagrams, on-prem, multilingual | Broader product |

---

## 10. Decisions needed from you
> **Update 2026-11-19:** #1 = personal tool, #3 = fully local/offline, #4 = English + Twi (code-switching). See `02-local-tech-stack.md`, which replaces the cloud architecture in §5.

1. **Who is the user?** An internal tool for your team, or a product for many organisations (multi-tenant SaaS)?
2. **Platform:** web app first (recommended), or desktop/mobile as well?
3. **Data hosting:** is cloud STT/LLM acceptable, or must audio stay on-premise/local?
4. **Languages and accents** of your stakeholders (this affects the STT choice heavily).
5. **Session types to prioritise:** one-to-one interviews, or group workshops?
6. **MVP order:** post-session analysis first (recommended, lower risk), or live co-pilot first?
7. **Output formats that matter most:** SRS document, user stories/backlog (Jira?), or both?
8. **Tech stack preferences or constraints** of your team (languages, cloud provider, budget).

---

## 11. Sources
* Dente, Dalpiaz, Papotti: *Automated alignment between elicitation interviews and requirements* (RE 2026): https://arxiv.org/html/2510.08622
* *Generative Goal Modeling*: https://arxiv.org/html/2509.01048v1
* *From Elicitation Interviews to Software Requirements* (WER 2025): https://werpapers.dimap.ufrn.br/papers/WER2025/wer202511.pdf
* *LLMREI: Automating Requirements Elicitation Interviews with LLMs*: https://arxiv.org/abs/2507.02564
* *Using LLMs to Develop Requirements Elicitation Skills*: https://arxiv.org/abs/2503.07800
* *Requirements Elicitation Follow-Up Question Generation* (review): https://www.themoonlight.io/review/requirements-elicitation-follow-up-question-generation
* *Can LLMs Generate User Stories…*: https://arxiv.org/html/2507.15157v1
* Utrecht thesis (transcript → user stories with traceability): https://studenttheses.uu.nl/handle/20.500.12932/49759
* Visure: AI requirements elicitation: https://visuresolutions.com/ai-engineering/ai-requirements-elicitation
* pyannote: Top speaker diarization APIs 2026: https://www.pyannote.ai/blog/top-7-speaker-diarization-apis-and-models-in-2026
* Deepgram: AssemblyAI vs Deepgram: https://deepgram.com/learn/assemblyai-vs-deepgram
* Speechmatics vs AssemblyAI: https://www.speechmatics.com/product/how-we-compare/speechmatics-vs-assemblyai
* Gladia: Best speech-to-text APIs: https://gladia.io/blog/best-speech-to-text-apis
* Standards: ISO/IEC/IEEE 29148 (requirements engineering), ISO/IEC 25010 (product quality model)
