# 04 UI design

| | |
|---|---|
| **Status** | First version built |
| **Date** | 2026-11-20 |
| **Code** | `app/frontend` (React and TypeScript on Vite), `app/backend/server.py` (FastAPI) |

## What the app is for

The app is where I work after (and during) a session. It does three jobs:

1. **Record.** Start a session, see the timer, the audio levels and the live transcript, stop when done.
2. **Review.** Go through everything the model pulled out, check each item against what was actually said, and accept, edit or reject it.
3. **Hand over.** Export the reviewed list as a document I can share.

Reviewing is where I spend the most time, so most of the design effort went there.

## Design principles

* **It should feel like a work tool, not a demo.** The references were tools people use all day: issue trackers, code review screens, audio editors. Dense but calm, nothing decorative.
* **Evidence is always one click away.** Every item shows the quote it came from. Selecting it highlights that line in the transcript and puts a marker on the audio timeline. Pressing Enter plays the exact moment.
* **The model suggests, I decide.** Nothing is final until I accept it. Rejected items stay visible (struck through) so the decision is recorded, and every change is written to an audit log in the session folder.
* **Fast with the keyboard.** J and K move, A accepts, R rejects, E edits, U undoes, Space plays or pauses. Reviewing 40 items should take minutes, not an hour.
* **Honest about what the machine is doing.** Processing shows the real step and progress. The live transcript is labelled as a draft. The footer says where the data lives.

## Visual language

| Element | Choice | Why |
|---|---|---|
| Colour | Warm neutral greys with one ink blue accent (`#2b5c8a`) | One accent keeps attention on content. Warm greys read softer than pure grey on long sessions |
| Status colours | Green for accepted, brick red for rejected, amber for warnings | Used only when they mean something, never for decoration |
| Type | System UI font (Segoe UI Variable on Windows), Cascadia Mono for IDs | Looks native, renders sharply, works offline with no font downloads |
| Numbers | Tabular figures for every time and count | Columns of timestamps line up and timers do not jitter |
| Surfaces | Hairline borders, almost no shadows, 6px corners | Flat and quiet. Shadows only on things that float, like the dialog |
| Item types | Short mono codes (PROC, PAIN, FR, NFR, BR, Q) | Scannable like ticket keys, without a rainbow of coloured badges |
| Dark mode | Full token set, follows the system setting | Late evening review sessions |

Things deliberately left out: gradients, glass effects, emoji, oversized rounded cards, illustration filled empty states, and AI sparkle icons.

## Screens

### Sidebar
Product name, a single primary action (New session), and the session list. Each session shows its date, length, and either its live state (recording, extracting) or review progress such as "7/12 reviewed". The footer reminds me that everything is stored locally.

### Session: Review tab (main screen)
```
┌ header: name · date · length · room and remote · consent noted        [Re-run] [Export] ┐
│ tabs: Review (5 left) | Transcript (27) | Summary                                         │
├──────────────────────────────────────────────┬────────────────────────────────────────────┤
│ [All 9][To review 5][Accepted 3][Rejected 1]  │ SOURCE   REQ-003, said by Remote at 0:00:51 │
│ How the work is done today            2       │ 0:00:42  Remote  The system must send ...   │
│ PROC 001  The cashier reconciles ...  [✓][✕]  │ 0:00:51  Remote  ▌Orders above 5,000 ...▐   │
│           "At the end of the day the ..."     │ 0:00:58  Remote  And customers can pay ...  │
│           ▶ Remote, 0:01:05                   │                                             │
│ Pain points                           1       │                                             │
│ ...                                           │                                             │
│ J K move  A accept  R reject  E edit          │                                             │
├──────────────────────────────────────────────┴────────────────────────────────────────────┤
│ ▶  0:51 / 1:52  ━━━━━━━●──┃──┃──┃────────────  [Everyone|Room|Remote]  1x                 │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```
* Left: items grouped by type, filterable by status and type, searchable.
* Right: the transcript, scrolled to and highlighting the quote of the selected item. Clicking any line plays from there.
* Bottom: audio player with a marker for every item (green when accepted, faded when rejected, amber for the selected one), a track switch for everyone, room only or remote only, and playback speed.

### Session: Transcript tab
A comfortable reading width view of the whole conversation with search. Lines that produced an item carry its number in the margin.

### Session: Summary tab
Four numbers (items found, percent reviewed, accepted, length), then what was captured by type, speaking time split between room and remote (the stakeholder should be doing most of the talking), the pain points, and the questions to follow up next time.

### Empty and working states
* No requirements yet: a short explanation and one button, Extract requirements, plus Re-transcribe first for a cleaner transcript.
* Processing: the real step ("Extracting requirements, part 3 of 9"), a progress bar and the last log lines.

### New session dialog
Name, where the conversation is happening (online call or in person), and a consent checkbox that must be ticked before Start recording is enabled.

### Recording screen
A large timer, a level meter per source so I can see the microphone is working, a reminder that the live transcript is a draft, and the live transcript itself scrolling as lines arrive. One red button to stop.

## How the backend fits

The FastAPI server only reads and writes the session folders, so the command line tools and the app always agree:

| Endpoint | Purpose |
|---|---|
| `GET /api/sessions` | Session list with state and review counts |
| `GET /api/sessions/{id}` | Transcript, items with review state, audio tracks, processing job |
| `GET /api/sessions/{id}/audio/{track}` | Stream `mixed`, `mic` or `system` audio |
| `PATCH /api/sessions/{id}/requirements/{req}` | Accept, reject, edit, note. Saved to `review.json` and logged to `review_log.jsonl` |
| `POST /api/sessions/{id}/process` | Run `process_session.py` in the background |
| `GET /api/sessions/{id}/export.md` | Reviewed items as Markdown |
| `POST`, `GET`, `DELETE /api/recording` | Start, watch and stop a live recording |

The model's original wording is never overwritten. Edits are stored next to it, so I can always see what the machine suggested and what I changed.

## Next for the UI

* Word level timestamps so playback starts on the exact word, and the playing word is highlighted.
* Merge and split for items the model got half right.
* A project level view that collects accepted items across many sessions into one requirements document.
* DOCX export in the ISO 29148 layout.
