import type { SessionSummary } from "../types";
import { day, duration } from "../format";
import { Icon } from "./Icon";

interface Props {
  sessions: SessionSummary[];
  selected: string | null;
  recordingId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}

function stateLine(s: SessionSummary) {
  if (s.state === "recording") return <><span className="dot rec" /> Recording</>;
  if (s.state === "processing") return <><span className="dot busy" /> Extracting</>;
  if (s.counts.total) {
    const reviewed = s.counts.accepted + s.counts.rejected;
    return <span className="num">{reviewed}/{s.counts.total} reviewed</span>;
  }
  return <span>Not analysed</span>;
}

export function Sidebar({ sessions, selected, recordingId, onSelect, onNew }: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark"><Icon name="doc" size={14} /></div>
        <div>
          <div className="brand-name">srs-assistant</div>
          <div className="brand-sub">Requirements workspace</div>
        </div>
      </div>
      <div className="sidebar-actions">
        <button className="btn primary block" onClick={onNew} disabled={!!recordingId}>
          <Icon name="mic" /> New session
        </button>
      </div>
      <div className="sidebar-label">Sessions</div>
      <ul className="session-list">
        {sessions.length === 0 && <li className="faint" style={{ padding: "4px 10px", fontSize: 13 }}>No sessions yet</li>}
        {sessions.map((s) => (
          <li key={s.id}>
            <button className="session-item" aria-current={s.id === selected} onClick={() => onSelect(s.id)}>
              <div className="session-title"><span>{s.name}</span></div>
              <div className="session-meta">
                <span>{day(s.started)}</span>
                <span>·</span>
                <span>{s.state === "recording" ? "live" : duration(s.duration_s)}</span>
              </div>
              <div className="session-meta" style={{ alignItems: "center" }}>{stateLine(s)}</div>
            </button>
          </li>
        ))}
      </ul>
      <div className="sidebar-foot">
        <Icon name="lock" size={14} /> Stored on this computer only
      </div>
    </aside>
  );
}
