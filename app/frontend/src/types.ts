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
  state: "recording" | "recorded" | "processing" | "processed";
  counts: Counts;
}

export interface Segment {
  id: number;
  source: string;
  start: number;
  end: number;
  text: string;
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

export interface SessionDetail extends SessionSummary {
  transcript: Segment[];
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
