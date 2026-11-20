"""Local API for the srs-assistant review app.

Reads and writes the session folders made by spike/live_record.py and spike/process_session.py.
Run from the repo root:
    uv run --project spike python app/backend/server.py
Then open http://localhost:8765
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
SPIKE = ROOT / "spike"
SESSIONS = SPIKE / "sessions"
FRONTEND = ROOT / "app" / "frontend" / "dist"
PYTHON = sys.executable

app = FastAPI(title="srs-assistant")


# ------------------------------------------------------------------------------------------ helpers
def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def session_path(session_id: str) -> Path:
    path = (SESSIONS / session_id).resolve()
    if path.parent != SESSIONS.resolve() or not (path / "session.json").exists():
        raise HTTPException(404, "Session not found")
    return path


def transcript_for(path: Path) -> list[dict]:
    rows = read_json(path / "transcript.json")
    if rows is not None:
        return rows
    live = path / "transcript_live.jsonl"
    if not live.exists():
        return []
    rows = [json.loads(l) for l in live.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows.sort(key=lambda r: r["start"])
    for i, r in enumerate(rows):
        r["id"] = i
    return rows


def merged_requirements(path: Path) -> list[dict]:
    reqs = read_json(path / "requirements.json", [])
    review = read_json(path / "review.json", {})
    for r in reqs:
        state = review.get(r["id"], {})
        r["status"] = state.get("status", "pending")
        r["edited_statement"] = state.get("edited_statement")
        r["note"] = state.get("note")
    return reqs


def summary(path: Path) -> dict:
    meta = read_json(path / "session.json", {})
    reqs = merged_requirements(path)
    state = "recording" if meta.get("status") == "recording" else ("processed" if reqs else "recorded")
    if path.name in JOBS and JOBS[path.name]["state"] == "running":
        state = "processing"
    return {
        "id": path.name,
        "name": meta.get("name", path.name),
        "started": meta.get("started"),
        "duration_s": meta.get("duration_s"),
        "sources": list(meta.get("sources", {}).keys()),
        "consent": meta.get("consent"),
        "state": state,
        "counts": {
            "total": len(reqs),
            "accepted": sum(r["status"] == "accepted" for r in reqs),
            "rejected": sum(r["status"] == "rejected" for r in reqs),
            "pending": sum(r["status"] == "pending" for r in reqs),
        },
    }


# ------------------------------------------------------------------------------------------ sessions
@app.get("/api/sessions")
def list_sessions():
    if not SESSIONS.exists():
        return []
    dirs = [p for p in SESSIONS.iterdir() if (p / "session.json").exists()]
    return [summary(p) for p in sorted(dirs, reverse=True)]


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    path = session_path(session_id)
    audio = [n for n in ("mixed", "mic", "system") if (path / f"{n}.wav").exists()]
    return summary(path) | {
        "transcript": transcript_for(path),
        "requirements": merged_requirements(path),
        "audio": audio,
        "job": JOBS.get(session_id),
    }


@app.get("/api/sessions/{session_id}/audio/{track}")
def get_audio(session_id: str, track: Literal["mixed", "mic", "system"]):
    file = session_path(session_id) / f"{track}.wav"
    if not file.exists():
        raise HTTPException(404, "No audio")
    return FileResponse(file, media_type="audio/wav")


class ReviewUpdate(BaseModel):
    status: Literal["pending", "accepted", "rejected"] | None = None
    edited_statement: str | None = None
    note: str | None = None


@app.patch("/api/sessions/{session_id}/requirements/{req_id}")
def update_requirement(session_id: str, req_id: str, body: ReviewUpdate):
    path = session_path(session_id)
    if req_id not in {r["id"] for r in read_json(path / "requirements.json", [])}:
        raise HTTPException(404, "Requirement not found")
    review = read_json(path / "review.json", {})
    state = review.get(req_id, {})
    changes = body.model_dump(exclude_unset=True)
    state.update(changes)
    state["updated"] = datetime.now().isoformat(timespec="seconds")
    review[req_id] = state
    write_json(path / "review.json", review)
    with (path / "review_log.jsonl").open("a", encoding="utf-8") as log:  # audit trail of every change
        log.write(json.dumps({"at": state["updated"], "id": req_id, **changes}, ensure_ascii=False) + "\n")
    return next(r for r in merged_requirements(path) if r["id"] == req_id)


@app.get("/api/sessions/{session_id}/export.md", response_class=PlainTextResponse)
def export_markdown(session_id: str, include_rejected: bool = False):
    path = session_path(session_id)
    meta = read_json(path / "session.json", {})
    reqs = [r for r in merged_requirements(path) if include_rejected or r["status"] != "rejected"]
    titles = {
        "current_process": "How the work is done today", "pain_point": "Pain points",
        "stakeholder": "People and roles", "functional": "Functional requirements",
        "non_functional": "Quality requirements", "constraint": "Constraints",
        "business_rule": "Business rules", "assumption": "Assumptions", "open_question": "Open questions",
    }
    out = [f"# {meta.get('name', session_id)}", "",
           f"Session recorded {str(meta.get('started', '')).replace('T', ' ')}. Exported {datetime.now():%Y-%m-%d %H:%M}.", ""]
    for key, title in titles.items():
        group = [r for r in reqs if r["type"] == key]
        if not group:
            continue
        out += [f"## {title}", ""]
        for r in group:
            status = "" if r["status"] == "accepted" else f" ({r['status']})"
            out.append(f"**{r['id']}{status}.** {r.get('edited_statement') or r['statement']}  ")
            out.append(f"> \"{r['quote']}\" ({r.get('speaker') or 'Unknown'}, {r.get('time') or '?'})")
            if r.get("note"):
                out.append(f">\n> Note: {r['note']}")
            out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------------------------------ processing
JOBS: dict[str, dict] = {}


class ProcessRequest(BaseModel):
    retranscribe: bool = False


@app.post("/api/sessions/{session_id}/process")
def start_processing(session_id: str, body: ProcessRequest):
    path = session_path(session_id)
    if JOBS.get(session_id, {}).get("state") == "running":
        raise HTTPException(409, "Already processing")
    cmd = [PYTHON, "-u", str(SPIKE / "process_session.py"), str(path)]
    if body.retranscribe:
        cmd.append("--retranscribe")
    job = {"state": "running", "step": "Starting", "progress": 0.0, "log": [], "started": datetime.now().isoformat()}
    JOBS[session_id] = job

    def run():
        proc = subprocess.Popen(cmd, cwd=SPIKE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            job["log"] = (job["log"] + [line])[-50:]
            if m := re.search(r"part (\d+)/(\d+)", line):
                done, total = int(m[1]), int(m[2])
                job["step"] = f"Extracting requirements, part {done} of {total}"
                job["progress"] = 0.1 + 0.9 * (done - 1) / total
            elif "transcribing" in line:
                job["step"] = "Transcribing audio"
            elif "transcript.md written" in line:
                job["step"], job["progress"] = "Transcript ready", 0.1
        code = proc.wait()
        job["state"] = "done" if code == 0 else "failed"
        job["progress"] = 1.0 if code == 0 else job["progress"]
        job["step"] = "Finished" if code == 0 else (job["log"][-1] if job["log"] else "Failed")

    threading.Thread(target=run, daemon=True).start()
    return job


# ------------------------------------------------------------------------------------------ recording
RECORDING: dict = {}


class RecordRequest(BaseModel):
    name: str
    source: Literal["both", "mic", "system"] = "both"
    consent: str


@app.post("/api/recording")
def start_recording(body: RecordRequest):
    if RECORDING.get("proc") and RECORDING["proc"].poll() is None:
        raise HTTPException(409, "Already recording")
    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-") or "session"
    session_id = f"{datetime.now():%Y-%m-%d_%H%M%S}_{slug}"
    path = SESSIONS / session_id
    path.mkdir(parents=True)
    log = (path / "recorder.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [PYTHON, "-u", str(SPIKE / "live_record.py"), "--name", body.name, "--source", body.source,
         "--consent", body.consent, "--session-dir", str(path)],
        cwd=SPIKE, stdout=log, stderr=subprocess.STDOUT,
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
    )
    RECORDING.clear()
    RECORDING.update(proc=proc, session_id=session_id, path=path)
    return {"session_id": session_id}


@app.get("/api/recording")
def recording_status():
    if not RECORDING:
        return {"active": False}
    proc, path = RECORDING["proc"], RECORDING["path"]
    status = read_json(path / "live_status.json", {"state": "starting"})
    running = proc.poll() is None
    if not running and status.get("state") != "done":
        status["state"] = "failed" if proc.returncode else "done"
    live = path / "transcript_live.jsonl"
    lines = [json.loads(l) for l in live.read_text(encoding="utf-8").splitlines() if l.strip()] if live.exists() else []
    return {"active": running, "session_id": RECORDING["session_id"], **status, "transcript": lines[-200:]}


@app.delete("/api/recording")
def stop_recording():
    if not RECORDING or RECORDING["proc"].poll() is not None:
        raise HTTPException(409, "Not recording")
    (RECORDING["path"] / "STOP").touch()
    return {"stopping": True}


# ------------------------------------------------------------------------------------------ frontend
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
