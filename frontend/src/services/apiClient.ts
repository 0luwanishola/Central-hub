import type { Fixture, LearningAnswer, LearningCodeResult, LearningSession, LearningSolution, LearningReviewSet, LearningTrackId, PdfDownload, PdfSignPreview, ScratchPythonResult, ScratchSqlRunResult, ScratchSqlWorkspace, Tool } from "../types";

// Use relative URLs in development (proxied by Vite), absolute in production
const isDev = import.meta.env.DEV;
const API_BASE_URL = isDev ? "" : (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export function apiUrl(path: string): string {
  if (isDev) return path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
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
    throw new ApiError(detail, response.status);
  }
  return payload as T;
}

export function isMissingWorkspace(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 404 || error.status === 410);
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

export const LEARNING_REVIEW_QUERY_KEY = ["learning-review"] as const;

export function getLearningReview(learner_id: string): Promise<LearningReviewSet> {
  return requestJson<LearningReviewSet>("/api/learning/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ learner_id }),
  });
}

export const SCRATCH_PYTHON_MUTATION_KEY = ["scratch-python-run"] as const;
export const SCRATCH_SQL_MUTATION_KEY = ["scratch-sql-run"] as const;

export function runPythonScratch(input: { code: string; run_id: string }): Promise<ScratchPythonResult> {
  return requestJson<ScratchPythonResult>("/api/learning/scratch/python/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function createSqlScratchWorkspace(input: { learner_id: string; base: string }): Promise<ScratchSqlWorkspace> {
  return requestJson<ScratchSqlWorkspace>("/api/learning/scratch/sql/workspaces", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function runSqlScratch(input: { learner_id: string; workspace_id: string; sql: string }): Promise<ScratchSqlRunResult> {
  return requestJson<ScratchSqlRunResult>("/api/learning/scratch/sql/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function resetSqlScratchWorkspace(input: { learner_id: string; workspace_id: string }): Promise<ScratchSqlWorkspace> {
  return requestJson<ScratchSqlWorkspace>("/api/learning/scratch/sql/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function deleteSqlScratchWorkspace(input: { learner_id: string; workspace_id: string }): Promise<{ workspace_id: string; deleted: boolean }> {
  const params = new URLSearchParams({ learner_id: input.learner_id });
  return requestJson<{ workspace_id: string; deleted: boolean }>(
    `/api/learning/scratch/sql/workspaces/${encodeURIComponent(input.workspace_id)}?${params.toString()}`,
    { method: "DELETE" },
  );
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

