const PATHS: Record<string, string> = {
  play: "M5 3.5v9l7.5-4.5z",
  pause: "M5 3.5h2v9H5zM9 3.5h2v9H9z",
  check: "M3.5 8.5l3 3 6-7",
  x: "M4.5 4.5l7 7M11.5 4.5l-7 7",
  edit: "M10.5 3l2.5 2.5L6 12.5H3.5V10z",
  undo: "M5 6.5H10a3 3 0 010 6H7M5 6.5L7.5 4M5 6.5L7.5 9",
  search: "M7 12A5 5 0 107 2a5 5 0 000 10zM10.5 10.5L14 14",
  download: "M8 2.5v8M4.5 7L8 10.5 11.5 7M3 13.5h10",
  mic: "M8 2a2 2 0 012 2v4a2 2 0 01-4 0V4a2 2 0 012-2zM4.5 7.5a3.5 3.5 0 007 0M8 11v3",
  wave: "M2 8h1.5M5 5v6M8 3v10M11 5.5v5M14 8h-1",
  sparkle: "M8 2.5v3M8 10.5v3M2.5 8h3M10.5 8h3",
  warn: "M8 2.5l6 11H2zM8 6.5v3M8 11.5v.5",
  lock: "M4.5 7.5h7v6h-7zM6 7.5V5.5a2 2 0 014 0v2",
  quote: "M3 9.5h3v3H3zM3 9.5c0-3 1-4.5 3-5M9.5 9.5h3v3h-3zM9.5 9.5c0-3 1-4.5 3-5",
  plus: "M8 3v10M3 8h10",
  stop: "M4.5 4.5h7v7h-7z",
  doc: "M4 2h5.5L12 4.5V14H4zM9.5 2v2.5H12M6 8h4M6 10.5h4",
  clock: "M8 14A6 6 0 108 2a6 6 0 000 12zM8 5v3.5l2 1.5",
  users: "M6 7.5a2.25 2.25 0 100-4.5 2.25 2.25 0 000 4.5zM2 13c0-2.2 1.8-3.5 4-3.5s4 1.3 4 3.5M11 7a1.8 1.8 0 100-3.6M12 9.5c1.3.4 2 1.5 2 3",
};

export function Icon({ name, size = 16 }: { name: keyof typeof PATHS | string; size?: number }) {
  const filled = name === "play" || name === "pause" || name === "stop";
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true"
      fill={filled ? "currentColor" : "none"} stroke={filled ? "none" : "currentColor"}
      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d={PATHS[name] ?? ""} />
    </svg>
  );
}
