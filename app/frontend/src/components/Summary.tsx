import type { SessionDetail } from "../types";
import { TYPES, TYPE_ORDER, duration } from "../format";

export function Summary({ session }: { session: SessionDetail }) {
  const reqs = session.requirements;
  const c = session.counts;
  const reviewed = c.accepted + c.rejected;
  const max = Math.max(1, ...TYPE_ORDER.map((t) => reqs.filter((r) => r.type === t).length));

  const talk: Record<string, number> = {};
  for (const s of session.transcript) talk[s.source] = (talk[s.source] ?? 0) + (s.end - s.start);
  const talkTotal = Object.values(talk).reduce((a, b) => a + b, 0) || 1;

  const pains = reqs.filter((r) => r.type === "pain_point" && r.status !== "rejected");
  const questions = reqs.filter((r) => r.type === "open_question" && r.status !== "rejected");

  return (
    <div className="summary">
      <div className="stats">
        <div className="stat">
          <div className="stat-label">Items found</div>
          <div className="stat-value">{c.total}</div>
          <div className="stat-sub">from {session.transcript.length} transcript lines</div>
        </div>
        <div className="stat">
          <div className="stat-label">Reviewed</div>
          <div className="stat-value">{c.total ? Math.round((reviewed / c.total) * 100) : 0}%</div>
          <div className="stat-sub num">{reviewed} of {c.total}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Accepted</div>
          <div className="stat-value" style={{ color: "var(--ok)" }}>{c.accepted}</div>
          <div className="stat-sub">{c.rejected} rejected</div>
        </div>
        <div className="stat">
          <div className="stat-label">Session length</div>
          <div className="stat-value">{duration(session.duration_s)}</div>
          <div className="stat-sub">{session.sources.length > 1 ? "Room and remote audio" : "Room audio"}</div>
        </div>
      </div>

      <div className="cols">
        <div className="card">
          <div className="card-head">What was captured</div>
          <div className="card-body">
            {TYPE_ORDER.map((t) => {
              const n = reqs.filter((r) => r.type === t).length;
              if (!n) return null;
              return (
                <div className="bar-row" key={t}>
                  <span>{TYPES[t].label}</span>
                  <div className="bar"><div style={{ width: `${(n / max) * 100}%` }} /></div>
                  <span className="num muted" style={{ textAlign: "right" }}>{n}</span>
                </div>
              );
            })}
            {!reqs.length && <p className="faint">Nothing extracted yet.</p>}
          </div>
        </div>

        <div className="card">
          <div className="card-head">Speaking time</div>
          <div className="card-body">
            {Object.entries(talk).map(([src, secs]) => (
              <div className="bar-row" key={src}>
                <span>{src === "MIC" ? "Room" : "Remote"}</span>
                <div className="bar"><div style={{ width: `${(secs / talkTotal) * 100}%`, background: src === "MIC" ? "var(--accent)" : "var(--ok)" }} /></div>
                <span className="num muted" style={{ textAlign: "right" }}>{Math.round((secs / talkTotal) * 100)}%</span>
              </div>
            ))}
            <p className="faint" style={{ fontSize: 12, margin: "8px 0 0" }}>
              In an elicitation interview the stakeholder should do most of the talking.
            </p>
          </div>
        </div>

        <div className="card">
          <div className="card-head">Pain points <span className="count">{pains.length}</span></div>
          <div className="card-body">
            <ul className="plain-list">
              {pains.map((r) => <li key={r.id}>{r.edited_statement ?? r.statement}</li>)}
              {!pains.length && <li className="faint">None recorded.</li>}
            </ul>
          </div>
        </div>

        <div className="card">
          <div className="card-head">Follow up next time <span className="count">{questions.length}</span></div>
          <div className="card-body">
            <ul className="plain-list">
              {questions.map((r) => <li key={r.id}>{r.edited_statement ?? r.statement}</li>)}
              {!questions.length && <li className="faint">No open questions.</li>}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
