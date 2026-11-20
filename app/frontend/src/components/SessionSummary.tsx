"use client";

import { useEffect, useState } from "react";
import type { MeetingSummary } from "../types";
import { Icon } from "./Icon";

interface Props {
  summary: MeetingSummary | null;
  canWrite: boolean;
  busy: boolean;
  onWrite: () => void;
}

function speakable(s: MeetingSummary): string {
  const parts = [s.title + ".", s.overview];
  for (const t of s.topics) parts.push(`${t.title}. ${t.summary}`);
  if (s.pain_points.length) parts.push("Pain points. " + s.pain_points.join(". "));
  if (s.decisions.length) parts.push("Decisions. " + s.decisions.join(". "));
  if (s.follow_ups.length) parts.push("To follow up. " + s.follow_ups.join(". "));
  return parts.join("\n\n");
}

/** Written summary of the session, with read aloud using the voices built into Windows (works offline). */
export function SessionSummary({ summary, canWrite, busy, onWrite }: Props) {
  const [speaking, setSpeaking] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  if (!summary) {
    return (
      <div className="card summary-card">
        <div className="card-head">Session summary</div>
        <div className="card-body">
          <p className="muted" style={{ margin: "8px 0 12px" }}>
            {busy ? "The summary is being written. It appears here when processing finishes."
              : canWrite ? "This session was processed before summaries existed. Writing one takes a minute or two."
                : "Process the session to get a written summary."}
          </p>
          {canWrite && !busy && <button className="btn" onClick={onWrite}>Write summary</button>}
        </div>
      </div>
    );
  }

  const listen = () => {
    const synth = window.speechSynthesis;
    if (!synth) return;
    if (speaking) { synth.cancel(); setSpeaking(false); return; }
    const u = new SpeechSynthesisUtterance(speakable(summary));
    u.rate = 1;
    const voice = synth.getVoices().find((v) => v.lang.startsWith("en") && /natural|online|zira|aria|jenny/i.test(v.name))
      ?? synth.getVoices().find((v) => v.lang.startsWith("en"));
    if (voice) u.voice = voice;
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    synth.cancel();
    synth.speak(u);
    setSpeaking(true);
  };

  const copy = async () => {
    await navigator.clipboard.writeText(speakable(summary));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div className="card summary-card">
      <div className="card-head">
        <span>Session summary</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <button className="btn sm" onClick={listen} title="Read the summary aloud">
            <Icon name={speaking ? "stop" : "play"} size={11} /> {speaking ? "Stop" : "Listen"}
          </button>
          <button className="btn sm" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
        </span>
      </div>
      <div className="card-body prose">
        <h2>{summary.title}</h2>
        <p className="lead">{summary.overview}</p>
        {summary.topics.length > 0 && (
          <>
            <h3>Topics</h3>
            <dl className="topics">
              {summary.topics.map((t, i) => (
                <div key={i}><dt>{t.title}</dt><dd>{t.summary}</dd></div>
              ))}
            </dl>
          </>
        )}
        <div className="summary-lists">
          {([["Pain points", summary.pain_points], ["Decisions", summary.decisions], ["Follow up next time", summary.follow_ups]] as const)
            .filter(([, items]) => items.length)
            .map(([title, items]) => (
              <section key={title}>
                <h3>{title}</h3>
                <ul>{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
              </section>
            ))}
        </div>
      </div>
    </div>
  );
}
