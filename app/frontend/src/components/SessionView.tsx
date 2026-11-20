import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { ReqStatus, ReqType, Requirement, SessionDetail } from "../types";
import { TYPES, TYPE_ORDER, day, duration } from "../format";
import { AudioBar, type AudioHandle } from "./AudioBar";
import { Icon } from "./Icon";
import { RequirementRow } from "./RequirementRow";
import { Summary } from "./Summary";
import { Transcript } from "./Transcript";

type Tab = "review" | "transcript" | "summary";
type StatusFilter = "all" | ReqStatus;

interface Props {
  sessionId: string;
  onChanged: () => void;
  toast: (msg: string) => void;
}

export function SessionView({ sessionId, onChanged, toast }: Props) {
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("review");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [typeFilter, setTypeFilter] = useState<ReqType | "all">("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [track, setTrack] = useState("mixed");
  const [time, setTime] = useState(0);
  const audio = useRef<AudioHandle>(null);

  const load = useCallback(async () => {
    try {
      const s = await api.session(sessionId);
      setSession(s);
      setError(null);
      return s;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }, [sessionId]);

  useEffect(() => {
    setSession(null);
    setSelected(null);
    setEditing(null);
    setTab("review");
    void load();
  }, [load]);

  // poll while a processing job is running
  useEffect(() => {
    if (session?.job?.state !== "running") return;
    const t = setInterval(async () => {
      const s = await load();
      if (s?.job?.state !== "running") {
        onChanged();
        if (s?.job?.state === "done") toast(`${s.requirements.length} items extracted`);
      }
    }, 2000);
    return () => clearInterval(t);
  }, [session?.job?.state, load, onChanged, toast]);

  const reqs = session?.requirements ?? [];
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return reqs.filter((r) =>
      (statusFilter === "all" || r.status === statusFilter) &&
      (typeFilter === "all" || r.type === typeFilter) &&
      (!q || `${r.statement} ${r.edited_statement ?? ""} ${r.quote}`.toLowerCase().includes(q)));
  }, [reqs, statusFilter, typeFilter, query]);

  const grouped = useMemo(() => TYPE_ORDER
    .map((t) => ({ type: t, items: visible.filter((r) => r.type === t) }))
    .filter((g) => g.items.length), [visible]);
  const ordered = useMemo(() => grouped.flatMap((g) => g.items), [grouped]);
  const current = reqs.find((r) => r.id === selected) ?? null;

  const patch = useCallback(async (req: Requirement, body: Partial<Requirement>) => {
    setSession((s) => s && {
      ...s,
      requirements: s.requirements.map((r) => (r.id === req.id ? { ...r, ...body } : r)),
    });
    try {
      await api.updateRequirement(sessionId, req.id, body);
      const s = await load();
      if (s) onChanged();
    } catch (e) {
      toast(`Could not save: ${(e as Error).message}`);
      void load();
    }
  }, [sessionId, load, onChanged, toast]);

  const move = useCallback((step: number) => {
    if (!ordered.length) return;
    const i = ordered.findIndex((r) => r.id === selected);
    const next = ordered[Math.min(ordered.length - 1, Math.max(0, i + step))] ?? ordered[0];
    setSelected(next.id);
  }, [ordered, selected]);

  // keyboard review: J/K or arrows to move, A accept, R reject, U undo, E edit, Space play
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || editing) return;
      if (e.key === " ") { e.preventDefault(); audio.current?.toggle(); return; }
      if (tab !== "review") return;
      const r = current;
      switch (e.key.toLowerCase()) {
        case "j": case "arrowdown": e.preventDefault(); move(1); break;
        case "k": case "arrowup": e.preventDefault(); move(-1); break;
        case "a": if (r) { void patch(r, { status: "accepted" }); move(1); } break;
        case "r": if (r) { void patch(r, { status: "rejected" }); move(1); } break;
        case "u": if (r) void patch(r, { status: "pending" }); break;
        case "e": if (r) { e.preventDefault(); setEditing(r.id); } break;
        case "enter": if (r?.start != null) audio.current?.seek(r.start); break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [tab, current, editing, move, patch]);

  const process = async (retranscribe = false) => {
    try {
      await api.process(sessionId, retranscribe);
      await load();
      onChanged();
    } catch (e) {
      toast((e as Error).message);
    }
  };

  if (error) return <div className="empty"><h2>Could not open this session</h2><p>{error}</p></div>;
  if (!session) return <div className="empty"><p className="faint">Loading…</p></div>;

  const job = session.job;
  const running = job?.state === "running";
  const tracks = session.audio;
  const activeTrack = tracks.includes(track) ? track : tracks[0];
  const c = session.counts;

  return (
    <>
      <header className="page-head">
        <div className="page-head-row">
          <div style={{ minWidth: 0 }}>
            <h1 className="page-title">{session.name}</h1>
            <div className="page-meta">
              <span><Icon name="clock" size={14} /> {day(session.started)}</span>
              <span className="num">{duration(session.duration_s)}</span>
              <span><Icon name="users" size={14} /> {session.sources.length > 1 ? "Room and remote" : "In person"}</span>
              {session.consent && <span title={session.consent}><Icon name="check" size={14} /> Consent noted</span>}
            </div>
          </div>
          <div className="page-actions">
            {reqs.length > 0 && !running && (
              <button className="btn" onClick={() => process(false)} title="Run extraction again on the transcript">
                Re-run extraction
              </button>
            )}
            <a className="btn" href={api.exportUrl(sessionId)} download={`${session.id}.md`}>
              <Icon name="download" /> Export
            </a>
          </div>
        </div>
        <div className="tabs" role="tablist">
          <button className="tab" role="tab" aria-selected={tab === "review"} onClick={() => setTab("review")}>
            Review <span className="count num">{c.pending ? `${c.pending} left` : c.total}</span>
          </button>
          <button className="tab" role="tab" aria-selected={tab === "transcript"} onClick={() => setTab("transcript")}>
            Transcript <span className="count num">{session.transcript.length}</span>
          </button>
          <button className="tab" role="tab" aria-selected={tab === "summary"} onClick={() => setTab("summary")}>
            Summary
          </button>
        </div>
      </header>

      <div className="content">
        {tab === "review" && (reqs.length === 0 || running ? (
          <div className="empty">
            <div className="empty-icon"><Icon name="doc" size={28} /></div>
            {running ? (
              <>
                <h2>Working through the conversation</h2>
                <p>{job!.step}. This runs on your computer and takes about two minutes for every four minutes of talk.</p>
                <div className="progress"><div style={{ width: `${Math.max(4, job!.progress * 100)}%` }} /></div>
                <div className="log">{job!.log.slice(-3).map((l, i) => <div key={i}>{l}</div>)}</div>
              </>
            ) : (
              <>
                <h2>No requirements yet</h2>
                <p>
                  {session.transcript.length
                    ? `The live transcript has ${session.transcript.length} lines. Extract the current processes, pain points and requirements from it, then review them here.`
                    : "There is no transcript yet. Transcribe the audio first, then extract."}
                </p>
                {job?.state === "failed" && <p className="error">Last attempt failed: {job.step}</p>}
                <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
                  <button className="btn primary" onClick={() => process(!session.transcript.length)}>
                    {session.transcript.length ? "Extract requirements" : "Transcribe and extract"}
                  </button>
                  {session.transcript.length > 0 && (
                    <button className="btn" onClick={() => process(true)} title="Slower, more accurate transcript first">
                      Re-transcribe first
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="split">
            <section className="pane" aria-label="Requirements">
              <div className="pane-head">
                <div className="segmented" role="group" aria-label="Filter by status">
                  {([["all", "All", c.total], ["pending", "To review", c.pending], ["accepted", "Accepted", c.accepted], ["rejected", "Rejected", c.rejected]] as const).map(([k, label, n]) => (
                    <button key={k} aria-pressed={statusFilter === k} onClick={() => setStatusFilter(k)}>
                      {label} <span className="faint num">{n}</span>
                    </button>
                  ))}
                </div>
                <select className="select" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as ReqType | "all")} aria-label="Filter by type">
                  <option value="all">All types</option>
                  {TYPE_ORDER.filter((t) => reqs.some((r) => r.type === t)).map((t) => <option key={t} value={t}>{TYPES[t].label}</option>)}
                </select>
                <label className="search">
                  <Icon name="search" size={14} />
                  <input className="input" placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search requirements" />
                </label>
              </div>
              <div className="pane-body" role="listbox" aria-label="Extracted items">
                {grouped.map((g) => (
                  <div key={g.type}>
                    <div className="group-head">{TYPES[g.type].label} <span className="faint num">{g.items.length}</span></div>
                    {g.items.map((r) => (
                      <RequirementRow key={r.id} req={r} selected={r.id === selected} editing={r.id === editing}
                        onSelect={() => setSelected(r.id)}
                        onPlay={() => { setSelected(r.id); if (r.start != null) audio.current?.seek(r.start); }}
                        onStatus={(status) => patch(r, { status })}
                        onEdit={(open) => setEditing(open ? r.id : null)}
                        onSave={(statement, note) => {
                          setEditing(null);
                          void patch(r, {
                            edited_statement: statement.trim() && statement.trim() !== r.statement ? statement.trim() : null,
                            note: note.trim() || null,
                          });
                        }} />
                    ))}
                  </div>
                ))}
                {!grouped.length && <div className="empty"><p>Nothing matches these filters.</p></div>}
              </div>
              <div className="pane-head" style={{ borderTop: "1px solid var(--line)", borderBottom: 0, minHeight: 36, fontSize: 12, color: "var(--text-3)", gap: 14 }}>
                <span><kbd>J</kbd> <kbd>K</kbd> move</span>
                <span><kbd>A</kbd> accept</span>
                <span><kbd>R</kbd> reject</span>
                <span><kbd>E</kbd> edit</span>
                <span><kbd>U</kbd> undo</span>
                <span><kbd>Enter</kbd> play</span>
              </div>
            </section>

            <section className="pane" aria-label="Transcript">
              <div className="pane-head">
                <span className="pane-title">Source</span>
                {current && <span className="muted" style={{ fontSize: 13 }}>{current.id}, said by {current.speaker ?? "unknown"} at {current.time}</span>}
              </div>
              <div className="pane-body">
                <Transcript segments={session.transcript} requirements={reqs}
                  linkedSegment={current?.segment_id ?? null} quote={current?.quote ?? null}
                  currentTime={time} onSeek={(t) => audio.current?.seek(t)} />
              </div>
            </section>
          </div>
        ))}

        {tab === "transcript" && (
          <div className="pane" style={{ flex: 1 }}>
            <div className="pane-head">
              <span className="pane-title">Full transcript</span>
              <label className="search">
                <Icon name="search" size={14} />
                <input className="input" placeholder="Search transcript" value={query} onChange={(e) => setQuery(e.target.value)} />
              </label>
            </div>
            <div className="pane-body">
              <Transcript reading segments={session.transcript} requirements={reqs} linkedSegment={null} quote={null}
                currentTime={time} filter={query} onSeek={(t) => audio.current?.seek(t)} />
            </div>
          </div>
        )}

        {tab === "summary" && <Summary session={session} />}

        <AudioBar ref={audio} src={activeTrack ? api.audioUrl(sessionId, activeTrack) : null}
          tracks={tracks} track={activeTrack ?? "mixed"} onTrack={setTrack}
          markers={reqs} selectedId={selected} onTime={setTime} />
      </div>
    </>
  );
}
