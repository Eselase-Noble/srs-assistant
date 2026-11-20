"use client";

import { useEffect, useRef } from "react";
import type { RecordingStatus } from "../types";
import { SPEAKER, clock } from "../format";
import { Icon } from "./Icon";

interface Props {
  status: RecordingStatus;
  name: string;
  onStop: () => void;
}

export function RecordingView({ status, name, onStop }: Props) {
  const end = useRef<HTMLDivElement>(null);
  const lines = status.transcript ?? [];

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [lines.length]);

  const state = status.state ?? "starting";
  const levels = status.levels ?? {};

  return (
    <>
      <header className="page-head" style={{ paddingBottom: 16 }}>
        <div className="page-head-row">
          <div>
            <h1 className="page-title">{name}</h1>
            <div className="page-meta"><span>Live session</span></div>
          </div>
          <div className="page-actions">
            <button className="btn danger" onClick={onStop} disabled={state !== "recording"}>
              <Icon name="stop" size={12} /> {state === "finishing" ? "Saving…" : "Stop recording"}
            </button>
          </div>
        </div>
      </header>
      <div className="rec-wrap">
        <aside className="rec-side">
          <div>
            <div className="rec-state">
              <span className={`dot ${state === "recording" ? "rec" : "busy"}`} />
              {state === "recording" ? "Recording" : state === "finishing" ? "Saving audio" : "Starting"}
            </div>
            <div className="rec-timer" style={{ marginTop: 10 }}>{clock(status.elapsed_s ?? 0)}</div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {Object.entries(levels).map(([src, v]) => (
              <div className="meter" key={src}>
                <span>{SPEAKER[src] ?? src}</span>
                <div className="meter-bar"><div style={{ width: `${Math.min(100, v * 600)}%` }} /></div>
              </div>
            ))}
            {!Object.keys(levels).length && <span className="faint" style={{ fontSize: 13 }}>Loading the speech model…</span>}
          </div>
          <div className="hint">
            The live transcript is a quick draft and runs 15 to 30 seconds behind. When you stop, everything is saved and
            you can extract requirements from the session.
          </div>
        </aside>
        <section className="pane">
          <div className="pane-head"><span className="pane-title">Live transcript</span>
            <span className="faint num" style={{ fontSize: 12 }}>{lines.length} lines</span></div>
          <div className="pane-body">
            {lines.length === 0 && <div className="empty"><p>Waiting for the first words…</p></div>}
            {lines.map((l, i) => (
              <div className="line" key={i} style={{ cursor: "default" }}>
                <span className="line-time num">{clock(l.start)}</span>
                <span className={`line-speaker ${l.source}`}>{SPEAKER[l.source] ?? l.source}</span>
                <span className="line-text">{l.text}</span>
              </div>
            ))}
            <div ref={end} />
          </div>
        </section>
      </div>
    </>
  );
}
