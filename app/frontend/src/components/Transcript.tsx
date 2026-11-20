"use client";

import { Fragment, useEffect, useMemo, useRef } from "react";
import type { Requirement, Segment } from "../types";
import { SPEAKER, clock } from "../format";

interface Props {
  segments: Segment[];
  requirements: Requirement[];
  linkedSegment: number | null;
  quote: string | null;
  currentTime: number;
  filter?: string;
  reading?: boolean;
  onSeek: (seconds: number) => void;
}

/** Wraps the part of `text` that matches the quote (case-insensitive) in <mark>. */
function highlight(text: string, quote: string | null) {
  if (!quote) return text;
  const q = quote.trim().replace(/^["“]|["”]$/g, "");
  const words = q.split(/\s+/).slice(0, 6).join(" ");
  const at = text.toLowerCase().indexOf(words.toLowerCase());
  if (at < 0) return text;
  const end = Math.min(text.length, at + q.length);
  return <>{text.slice(0, at)}<mark>{text.slice(at, end)}</mark>{text.slice(end)}</>;
}

export function Transcript({ segments, requirements, linkedSegment, quote, currentTime, filter, reading, onSeek }: Props) {
  const linkedRef = useRef<HTMLDivElement>(null);

  const refs = useMemo(() => {
    const map = new Map<number, string[]>();
    for (const r of requirements) {
      if (r.segment_id == null) continue;
      map.set(r.segment_id, [...(map.get(r.segment_id) ?? []), r.id.replace("REQ-", "")]);
    }
    return map;
  }, [requirements]);

  useEffect(() => {
    linkedRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [linkedSegment]);

  const needle = filter?.trim().toLowerCase();
  const shown = needle ? segments.filter((s) => s.text.toLowerCase().includes(needle)) : segments;

  if (!segments.length) {
    return <div className="empty"><p>No transcript for this session yet.</p></div>;
  }

  return (
    <div className={reading ? "reading" : undefined}>
      {shown.map((s, i) => {
        const linked = s.id === linkedSegment;
        const playing = currentTime >= s.start && currentTime < s.end;
        const prev = shown[i - 1];
        const gap = prev && s.start - prev.end > 20;
        return (
          <Fragment key={s.id}>
            {gap && <div className="faint" style={{ fontSize: 12, padding: "4px 20px 4px 88px" }}>{clock(s.start - prev.end)} pause</div>}
            <div ref={linked ? linkedRef : undefined}
              className={`line ${linked ? "is-linked" : ""} ${playing ? "is-playing" : ""}`}
              onClick={() => onSeek(s.start)} title="Play from here">
              <span className="line-time num">{clock(s.start)}</span>
              <span className={`line-speaker ${s.source}`}>{SPEAKER[s.source] ?? s.source}</span>
              <span className="line-text">
                {linked ? highlight(s.text, quote) : s.text}
                {refs.get(s.id) && (
                  <span className="line-refs">{refs.get(s.id)!.map((id) => <span key={id} className="ref">{id}</span>)}</span>
                )}
              </span>
            </div>
          </Fragment>
        );
      })}
    </div>
  );
}
