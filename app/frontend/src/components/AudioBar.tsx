"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { Requirement } from "../types";
import { clock } from "../format";
import { Icon } from "./Icon";

export interface AudioHandle {
  seek: (seconds: number, play?: boolean) => void;
  toggle: () => void;
}

interface Props {
  src: string | null;
  tracks: string[];
  track: string;
  onTrack: (t: string) => void;
  markers: Requirement[];
  selectedId: string | null;
  onTime: (t: number) => void;
  onPlaying?: (playing: boolean) => void;
}

const TRACK_LABEL: Record<string, string> = { mixed: "Everyone", mic: "Room", system: "Remote" };
const SPEEDS = [1, 1.25, 1.5, 2];

export const AudioBar = forwardRef<AudioHandle, Props>(function AudioBar(
  { src, tracks, track, onTrack, markers, selectedId, onTime, onPlaying }, ref) {
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [length, setLength] = useState(0);
  const [speed, setSpeed] = useState(1);

  useImperativeHandle(ref, () => ({
    seek(seconds, play = true) {
      const a = audio.current;
      if (!a) return;
      a.currentTime = Math.max(0, seconds - 0.4);
      if (play) void a.play();
    },
    toggle() {
      const a = audio.current;
      if (!a) return;
      if (a.paused) void a.play(); else a.pause();
    },
  }));

  useEffect(() => {
    if (audio.current) audio.current.playbackRate = speed;
  }, [speed, src]);

  const scrub = (e: React.MouseEvent<HTMLDivElement>) => {
    const a = audio.current;
    if (!a || !length) return;
    const box = e.currentTarget.getBoundingClientRect();
    a.currentTime = ((e.clientX - box.left) / box.width) * length;
  };

  const pct = length ? (time / length) * 100 : 0;

  if (!src) {
    return <div className="player"><span className="faint">No audio saved for this session.</span></div>;
  }

  return (
    <div className="player">
      <audio
        ref={audio}
        src={src}
        preload="metadata"
        onPlay={() => { setPlaying(true); onPlaying?.(true); }}
        onPause={() => { setPlaying(false); onPlaying?.(false); }}
        onLoadedMetadata={(e) => setLength(e.currentTarget.duration)}
        onTimeUpdate={(e) => { setTime(e.currentTarget.currentTime); onTime(e.currentTarget.currentTime); }}
      />
      <button className="play" onClick={() => (playing ? audio.current?.pause() : audio.current?.play())}
        aria-label={playing ? "Pause" : "Play"} title="Play or pause (Space)">
        <Icon name={playing ? "pause" : "play"} size={14} />
      </button>
      <span className="time num">{clock(time)} / {clock(length)}</span>
      <div className="scrub" onClick={scrub} role="slider" aria-label="Position" aria-valuemin={0}
        aria-valuemax={Math.round(length)} aria-valuenow={Math.round(time)}>
        <div className="scrub-track" />
        <div className="scrub-fill" style={{ width: `${pct}%` }} />
        {length > 0 && markers.filter((m) => m.start != null).map((m) => (
          <span key={m.id} title={`${m.id} at ${clock(m.start)}`}
            className={`tick ${m.status} ${m.id === selectedId ? "selected" : ""}`}
            style={{ left: `${((m.start as number) / length) * 100}%` }} />
        ))}
        <div className="scrub-knob" style={{ left: `${pct}%` }} />
      </div>
      {tracks.length > 1 && (
        <div className="segmented" aria-label="Audio track">
          {tracks.map((t) => (
            <button key={t} aria-pressed={t === track} onClick={() => onTrack(t)}>{TRACK_LABEL[t] ?? t}</button>
          ))}
        </div>
      )}
      <button className="btn sm ghost num" onClick={() => setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length])}
        title="Playback speed">{speed}x</button>
    </div>
  );
});
