import type { ReqType } from "./types";

export function clock(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return "0:00";
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

export function duration(seconds: number | null | undefined): string {
  if (!seconds) return "No audio";
  const m = Math.round(seconds / 60);
  if (m < 1) return `${Math.round(seconds)} sec`;
  if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}

export function day(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === today.toDateString()) return `Today, ${time}`;
  if (d.toDateString() === yesterday.toDateString()) return `Yesterday, ${time}`;
  return `${d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}, ${time}`;
}

export const SPEAKER: Record<string, string> = { MIC: "Room", SYSTEM: "Remote" };

export const TYPES: Record<ReqType, { label: string; code: string; group: string }> = {
  current_process: { label: "Current process", code: "PROC", group: "Operations" },
  pain_point: { label: "Pain point", code: "PAIN", group: "Operations" },
  stakeholder: { label: "Stakeholder", code: "ROLE", group: "Operations" },
  functional: { label: "Functional", code: "FR", group: "Requirements" },
  non_functional: { label: "Quality", code: "NFR", group: "Requirements" },
  constraint: { label: "Constraint", code: "CON", group: "Requirements" },
  business_rule: { label: "Business rule", code: "BR", group: "Requirements" },
  assumption: { label: "Assumption", code: "ASM", group: "Follow up" },
  open_question: { label: "Open question", code: "Q", group: "Follow up" },
};

export const TYPE_ORDER = Object.keys(TYPES) as ReqType[];
