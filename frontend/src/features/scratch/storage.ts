import type { ScratchSqlWorkspace } from "../../types";

// Versioned keys keep scratch drafts independent from challenge drafts and make
// future format changes explicit.
export const PYTHON_SCRATCH_DRAFT_KEY = "central-hub:scratch-draft:v1:python";
export const SQL_SCRATCH_DRAFT_KEY = "central-hub:scratch-draft:v1:sql";

// Output panel preferences (open/closed, panel height) are remembered per page,
// like an editor remembering its panel layout.
export const PYTHON_SCRATCH_PANEL_KEY = "central-hub:scratch-panel:v1:python";
export const SQL_SCRATCH_PANEL_KEY = "central-hub:scratch-panel:v1:sql";

export interface StoredScratchPanel {
  open: boolean;
  height: number;
}

const SCRATCH_PANEL_DEFAULTS: StoredScratchPanel = { open: true, height: 320 };

export function readScratchPanel(key: string): StoredScratchPanel {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return SCRATCH_PANEL_DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<StoredScratchPanel>;
    return {
      open: typeof parsed.open === "boolean" ? parsed.open : SCRATCH_PANEL_DEFAULTS.open,
      height: typeof parsed.height === "number" && Number.isFinite(parsed.height) ? parsed.height : SCRATCH_PANEL_DEFAULTS.height,
    };
  } catch {
    return SCRATCH_PANEL_DEFAULTS;
  }
}

export function writeScratchPanel(key: string, panel: StoredScratchPanel) {
  try {
    localStorage.setItem(key, JSON.stringify(panel));
  } catch {
    // Panel preferences are a nicety; a blocked localStorage must not break the page.
  }
}

const SQL_WORKSPACE_PREFIX = "central-hub:scratch-sql-workspace:v1";

export type StoredSqlWorkspace = ScratchSqlWorkspace & { saved_at: number };

export function readScratchDraft(key: string, fallback: string): { code: string; storageAvailable: boolean } {
  try {
    return { code: localStorage.getItem(key) ?? fallback, storageAvailable: true };
  } catch {
    return { code: fallback, storageAvailable: false };
  }
}

export function writeScratchDraft(key: string, value: string): boolean {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

export function downloadText(filename: string, content: string, type = "text/plain;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function workspaceKey(learnerId: string): string {
  return `${SQL_WORKSPACE_PREFIX}:${learnerId}`;
}

function isStoredWorkspace(value: unknown): value is StoredSqlWorkspace {
  if (!value || typeof value !== "object") return false;
  const workspace = value as Partial<StoredSqlWorkspace>;
  return (
    typeof workspace.workspace_id === "string" &&
    workspace.workspace_id.length >= 20 &&
    typeof workspace.base === "string" &&
    typeof workspace.base_name === "string" &&
    typeof workspace.idle_ttl_seconds === "number" &&
    typeof workspace.saved_at === "number"
  );
}

export function readSqlWorkspace(learnerId: string): StoredSqlWorkspace | null {
  try {
    const raw = localStorage.getItem(workspaceKey(learnerId));
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isStoredWorkspace(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function writeSqlWorkspace(learnerId: string, workspace: ScratchSqlWorkspace): boolean {
  try {
    const stored: StoredSqlWorkspace = { ...workspace, saved_at: Date.now() };
    localStorage.setItem(workspaceKey(learnerId), JSON.stringify(stored));
    return true;
  } catch {
    return false;
  }
}

export function clearSqlWorkspace(learnerId: string) {
  try {
    localStorage.removeItem(workspaceKey(learnerId));
  } catch {
    // The in-memory token is still cleared by the caller.
  }
}
