import type { Fixture, LearningAnswer, LearningCodeResult, LearningSession, LearningTrackId, Tool } from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload?.detail === "string" ? payload.detail : typeof payload?.error === "string" ? payload.error : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return payload as T;
}

export function getTools(): Promise<Tool[]> {
  return requestJson<Tool[]>("/api/tools");
}

const LEARNER_KEY = "central-hub:learning-profile:v1";
export const LEARNING_SESSION_QUERY_KEY = ["learning-session"] as const;

export async function startLearningSession(): Promise<LearningSession> {
  let learnerId: string | null = null;
  try {
    learnerId = localStorage.getItem(LEARNER_KEY);
  } catch {
    // A fresh anonymous profile is created when this browser blocks storage.
  }

  const session = await requestJson<LearningSession>("/api/learning/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ learner_id: learnerId }),
  });
  try {
    localStorage.setItem(LEARNER_KEY, session.learner_id);
  } catch {
    // The current session still works; it just cannot be resumed after reload.
  }
  return session;
}

export function submitLearningAnswer(input: { learner_id: string; track: LearningTrackId; level: number; choice: number }): Promise<LearningAnswer> {
  return requestJson<LearningAnswer>("/api/learning/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function submitLearningCode(input: { learner_id: string; track: LearningTrackId; level: number; code: string }): Promise<LearningCodeResult> {
  return requestJson<LearningCodeResult>("/api/learning/code", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function getLive(day: string, scope: string): Promise<{ provider: string; day: string; scope: string; matches: Fixture[]; error?: string }> {
  const params = new URLSearchParams({ day, scope });
  return requestJson<{ provider: string; day: string; scope: string; matches: Fixture[]; error?: string }>(`/api/live?${params.toString()}`);
}

export function getMatch(fixtureId: string): Promise<Fixture & { provider?: string; error?: string }> {
  return requestJson<Fixture & { provider?: string; error?: string }>(`/api/match/${encodeURIComponent(fixtureId)}`);
}

export async function runPdfTool(toolId: string, form: FormData): Promise<{ download_url: string; filename: string; expires_in_seconds: number }> {
  return requestJson(`/api/pdf/${encodeURIComponent(toolId)}`, {
    method: "POST",
    body: form,
  });
}
