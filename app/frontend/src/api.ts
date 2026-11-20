import type { ProcessMode, RecordingStatus, Requirement, SessionDetail, SessionSummary } from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body was not JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  sessions: () => request<SessionSummary[]>("/api/sessions"),
  session: (id: string) => request<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`),
  updateRequirement: (id: string, reqId: string, body: Partial<Pick<Requirement, "status" | "edited_statement" | "note">>) =>
    request<Requirement>(`/api/sessions/${encodeURIComponent(id)}/requirements/${reqId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  process: (id: string, mode: ProcessMode = "full") =>
    request(`/api/sessions/${encodeURIComponent(id)}/process`, {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
  transcriptUrl: (id: string) => `/api/sessions/${encodeURIComponent(id)}/transcript.md`,
  startRecording: (name: string, source: "both" | "mic", consent: string, vocabulary: string) =>
    request<{ session_id: string }>("/api/recording", {
      method: "POST",
      body: JSON.stringify({ name, source, consent, vocabulary }),
    }),
  updateSession: (id: string, body: { vocabulary?: string; name?: string }) =>
    request<SessionSummary>(`/api/sessions/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  recording: () => request<RecordingStatus>("/api/recording"),
  stopRecording: () => request("/api/recording", { method: "DELETE" }),
  audioUrl: (id: string, track: string) => `/api/sessions/${encodeURIComponent(id)}/audio/${track}`,
  exportUrl: (id: string) => `/api/sessions/${encodeURIComponent(id)}/export.md`,
};
