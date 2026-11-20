export type ReqStatus = "pending" | "accepted" | "rejected";

export type ReqType =
  | "current_process"
  | "pain_point"
  | "stakeholder"
  | "functional"
  | "non_functional"
  | "constraint"
  | "business_rule"
  | "assumption"
  | "open_question";

export interface Counts {
  total: number;
  accepted: number;
  rejected: number;
  pending: number;
}

export interface SessionSummary {
  id: string;
  name: string;
  started: string | null;
  duration_s: number | null;
  sources: string[];
  consent: string | null;
  vocabulary: string | null;
  state: "recording" | "recorded" | "processing" | "processed";
  counts: Counts;
}

export interface Word {
  w: string;
  s: number;
  e: number;
  p?: number; // how sure the speech model is about this word, 0 to 1
}

export interface Segment {
  id: number;
  source: string;
  start: number;
  end: number;
  text: string;
  words?: Word[];
}

export interface Paragraph {
  id: number;
  source: string;
  start: number;
  end: number;
  text: string;
  polished?: string; // clean edited version of `text`, checked against it for drift
  segment_ids: number[];
}

export interface MeetingSummary {
  title: string;
  overview: string;
  topics: { title: string; summary: string }[];
  decisions: string[];
  pain_points: string[];
  follow_ups: string[];
}

export interface Requirement {
  id: string;
  type: ReqType;
  statement: string;
  quality_category: string | null;
  quote: string;
  speaker: string | null;
  time: string | null;
  start: number | null;
  segment_id: number | null;
  confidence: number;
  grounding: number;
  flags: string[];
  status: ReqStatus;
  edited_statement: string | null;
  note: string | null;
}

export interface Job {
  state: "running" | "done" | "failed";
  step: string;
  progress: number;
  log: string[];
}

export type ProcessMode = "full" | "quick" | "summary";

export interface SessionDetail extends SessionSummary {
  transcript: Segment[];
  accurate: boolean;
  paragraphs: Paragraph[];
  dropped: (Segment & { reason: string })[];
  summary: MeetingSummary | null;
  requirements: Requirement[];
  audio: string[];
  job: Job | null;
}

export interface RecordingStatus {
  active: boolean;
  session_id?: string;
  state?: "starting" | "recording" | "finishing" | "done" | "failed";
  elapsed_s?: number;
  levels?: Record<string, number>;
  transcript?: { source: string; start: number; text: string }[];
}
