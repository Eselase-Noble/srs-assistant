"use client";

import { memo, useEffect, useMemo, useRef } from "react";
import type { Paragraph, Segment } from "../types";
import { SPEAKER, clock } from "../format";

interface Props {
  paragraphs: Paragraph[];
  segments: Segment[];
  currentTime: number;
  playing: boolean;
  follow: boolean;
  filter?: string;
  polished?: boolean;
  onSeek: (seconds: number) => void;
}

interface BlockProps {
  polished: boolean;
  para: Paragraph;
  segs: Segment[];
  activeTime: number | null; // only the paragraph being played gets a time, so the others never re-render
  follow: boolean;
  query: string;
  onSeek: (seconds: number) => void;
}

function mark(text: string, query: string) {
  if (!query) return text;
  const at = text.toLowerCase().indexOf(query);
  if (at < 0) return text;
  return <>{text.slice(0, at)}<mark>{text.slice(at, at + query.length)}</mark>{text.slice(at + query.length)}</>;
}

const Block = memo(function Block({ para, segs, activeTime, follow, query, polished, onSeek }: BlockProps) {
  const ref = useRef<HTMLElement>(null);
  const active = activeTime != null;

  useEffect(() => {
    if (active && follow) ref.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [active, follow]);

  const hasWords = segs.some((s) => s.words?.length);

  return (
    <article ref={ref} className={`para ${active ? "is-active" : ""}`}>
      <button className="para-meta" onClick={() => onSeek(para.start)} title="Play from here">
        <span className={`para-speaker ${para.source}`}>{SPEAKER[para.source] ?? para.source}</span>
        <span className="num">{clock(para.start)}</span>
      </button>
      <p className="para-text">
        {polished ? (
          <span onClick={() => onSeek(para.start)} title="Play this paragraph">
            {mark(para.polished ?? para.text, query)}
          </span>
        ) : hasWords && !query
          ? segs.map((s) => (s.words ?? []).map((w, i) => {
              const on = activeTime != null && activeTime >= w.s && activeTime < w.e + 0.15;
              const unclear = w.p != null && w.p < 0.5;
              return (
                <span key={`${s.id}-${i}`} className={`w${on ? " is-on" : ""}${unclear ? " is-unclear" : ""}`}
                  title={unclear ? "Unclear word, click to listen" : undefined} onClick={() => onSeek(w.s)}>{w.w}</span>
              );
            }))
          : <span onClick={() => onSeek(para.start)}>{mark(para.text, query)}</span>}
      </p>
    </article>
  );
});

export function Paragraphs({ paragraphs, segments, currentTime, playing, follow, filter, polished = false, onSeek }: Props) {
  const byId = useMemo(() => new Map(segments.map((s) => [s.id, s])), [segments]);
  const query = filter?.trim().toLowerCase() ?? "";
  const textOf = (p: Paragraph) => (polished ? p.polished ?? p.text : p.text);
  const shown = query ? paragraphs.filter((p) => textOf(p).toLowerCase().includes(query)) : paragraphs;

  if (!paragraphs.length) return <div className="empty"><p>No transcript for this session yet.</p></div>;

  return (
    <div className="reading paras">
      {shown.map((p) => {
        const inside = currentTime >= p.start && currentTime <= p.end + 0.5 && (playing || currentTime > 0);
        return (
          <Block key={p.id} para={p} segs={p.segment_ids.map((id) => byId.get(id)).filter(Boolean) as Segment[]}
            activeTime={inside ? currentTime : null} follow={follow && playing} query={query}
            polished={polished} onSeek={onSeek} />
        );
      })}
      {query && !shown.length && <div className="empty"><p>No paragraph mentions “{filter}”.</p></div>}
    </div>
  );
}
