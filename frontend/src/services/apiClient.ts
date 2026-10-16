import type { Fixture, LearningAnswer, LearningCodeResult, LearningSession, LearningSolution, LearningTrackId, NewsResponse, PdfDownload, PdfSignPreview, Tool } from "../types";

// Use relative URLs in development (proxied by Vite), absolute in production
const isDev = import.meta.env.DEV;
const API_BASE_URL = isDev ? "" : (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export function apiUrl(path: string): string {
  if (isDev) return path.startsWith("/") ? path : `/${path}`;
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

export function previewLearningCode(input: { learner_id: string; track: LearningTrackId; level: number; code: string }): Promise<LearningCodeResult> {
  return requestJson<LearningCodeResult>("/api/learning/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function recordLearningEvent(learner_id: string, challenge_id: string, event: "hint_open"): Promise<void> {
  return requestJson<void>("/api/learning/event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ learner_id, challenge_id, event }),
  });
}

export function getLearningSolution(input: { learner_id: string; track: LearningTrackId; challenge_id: string }): Promise<LearningSolution> {
  return requestJson<LearningSolution>("/api/learning/solution", {
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

export async function runPdfTool(toolId: string, form: FormData): Promise<PdfDownload> {
  return requestJson(`/api/pdf/${encodeURIComponent(toolId)}`, {
    method: "POST",
    body: form,
  });
}

export function previewPdfSign(file: File, page = 1): Promise<PdfSignPreview> {
  const form = new FormData();
  form.append("files", file);
  form.append("page", String(page));
  return requestJson<PdfSignPreview>("/api/pdf/pdf-sign/preview", { method: "POST", body: form });
}

export function getPdfSignPage(token: string, page: number): Promise<PdfSignPreview> {
  const params = new URLSearchParams({ page: String(page) });
  return requestJson<PdfSignPreview>(`/api/pdf/pdf-sign/page/${encodeURIComponent(token)}?${params.toString()}`);
}

export function applyPdfSignature(input: { token: string; page: number; across: number; down: number; width: number; signature: string }): Promise<PdfDownload> {
  const form = new FormData();
  form.append("draft", input.token);
  form.append("page", String(input.page));
  form.append("across", String(input.across));
  form.append("down", String(input.down));
  form.append("width", String(input.width));
  form.append("signature", input.signature);
  return requestJson<PdfDownload>("/api/pdf/pdf-sign/apply", { method: "POST", body: form });
}

export function getLatestNews(limit = 5): Promise<NewsResponse> {
  const params = new URLSearchParams({ limit: String(Math.max(1, Math.min(limit, 10))) });
  return requestJson<NewsResponse>(`/api/news/latest?${params.toString()}`);
}
