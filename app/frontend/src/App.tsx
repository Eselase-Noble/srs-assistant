import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { RecordingStatus, SessionSummary } from "./types";
import { Icon } from "./components/Icon";
import { RecordDialog } from "./components/RecordDialog";
import { RecordingView } from "./components/RecordingView";
import { SessionView } from "./components/SessionView";
import { Sidebar } from "./components/Sidebar";

function readHash(): string | null {
  const m = location.hash.match(/^#\/s\/(.+)$/);
  return m ? decodeURIComponent(m[1]) : null;
}

export default function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(readHash());
  const [dialog, setDialog] = useState(false);
  const [rec, setRec] = useState<RecordingStatus>({ active: false });
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  const toast = useCallback((msg: string) => {
    setToastMsg(msg);
    window.setTimeout(() => setToastMsg(null), 3200);
  }, []);

  const refresh = useCallback(async () => {
    try {
      setSessions(await api.sessions());
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  const select = (id: string) => {
    setSelected(id);
    location.hash = `#/s/${encodeURIComponent(id)}`;
  };

  useEffect(() => {
    void refresh();
    void api.recording().then(setRec).catch(() => undefined);
    const t = setInterval(refresh, 6000);
    const onHash = () => setSelected(readHash());
    window.addEventListener("hashchange", onHash);
    return () => { clearInterval(t); window.removeEventListener("hashchange", onHash); };
  }, [refresh]);

  useEffect(() => {
    if (!selected && sessions.length) select(sessions[0].id);
  }, [sessions, selected]);

  // poll the recorder once a second while it runs
  useEffect(() => {
    if (!rec.active && rec.state !== "finishing") return;
    const t = setInterval(async () => {
      const s = await api.recording();
      setRec(s);
      if (!s.active) {
        await refresh();
        if (s.session_id) select(s.session_id);
        toast("Recording saved");
      }
    }, 1000);
    return () => clearInterval(t);
  }, [rec.active, rec.state, refresh, toast]);

  const start = async (name: string, source: "both" | "mic", consent: string) => {
    const { session_id } = await api.startRecording(name, source, consent);
    setDialog(false);
    setRec({ active: true, session_id, state: "starting" });
    select(session_id);
    void refresh();
  };

  const recording = rec.active && rec.session_id === selected;
  const recName = sessions.find((s) => s.id === rec.session_id)?.name ?? "New session";

  return (
    <div className="shell">
      <Sidebar sessions={sessions} selected={selected} recordingId={rec.active ? rec.session_id ?? null : null}
        onSelect={select} onNew={() => setDialog(true)} />
      <main className="main">
        {offline ? (
          <div className="empty">
            <h2>Cannot reach the local server</h2>
            <p>Start it with <span className="mono">uv run --project spike python app/backend/server.py</span> and this page will reconnect.</p>
          </div>
        ) : recording ? (
          <RecordingView status={rec} name={recName} onStop={() => { void api.stopRecording(); setRec({ ...rec, state: "finishing" }); }} />
        ) : selected ? (
          <SessionView key={selected} sessionId={selected} onChanged={refresh} toast={toast} />
        ) : (
          <div className="empty">
            <div className="empty-icon"><Icon name="mic" size={28} /></div>
            <h2>Start your first session</h2>
            <p>Record an interview or a call. The transcript and the requirements stay on this computer.</p>
            <button className="btn primary" onClick={() => setDialog(true)}>New session</button>
          </div>
        )}
      </main>
      {dialog && <RecordDialog onClose={() => setDialog(false)} onStart={start} />}
      {toastMsg && <div className="toast" role="status">{toastMsg}</div>}
    </div>
  );
}
