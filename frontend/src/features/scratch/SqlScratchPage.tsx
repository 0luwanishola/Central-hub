import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ApiError,
  createSqlScratchWorkspace,
  deleteSqlScratchWorkspace,
  isMissingWorkspace,
  LEARNING_SESSION_QUERY_KEY,
  resetSqlScratchWorkspace,
  runSqlScratch,
  SCRATCH_SQL_MUTATION_KEY,
  startLearningSession,
} from "../../services/apiClient";
import type { ScratchSqlRunResult, ScratchSqlStatement } from "../../types";
import { Icon } from "../../ui/Icon";
import { SyntaxEditor } from "../learning/SyntaxEditor";
import { CodeQuestNav } from "./CodeQuestNav";
import { ScratchOutputPanel } from "./ScratchOutputPanel";
import { useScratchPanelState } from "./useScratchPanel";
import { handleScratchEditorKeyDown } from "./editorKeys";
import {
  clearSqlWorkspace,
  downloadText,
  readScratchDraft,
  readSqlWorkspace,
  SQL_SCRATCH_DRAFT_KEY,
  SQL_SCRATCH_PANEL_KEY,
  type StoredSqlWorkspace,
  writeScratchDraft,
  writeSqlWorkspace,
} from "./storage";

const STARTER_SQL = `CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    body TEXT NOT NULL
);

INSERT INTO notes (body) VALUES ('First note');

SELECT * FROM notes;
`;

function statusLabel(result: ScratchSqlRunResult): string {
  if (result.status === "timeout") return "Stopped by the time limit";
  if (result.status === "error") return "Rolled back";
  return "Completed";
}

function statusTone(result: ScratchSqlRunResult): "success" | "warning" | "error" {
  if (result.status === "timeout") return "warning";
  if (result.status === "error") return "error";
  return "success";
}

function formatDuration(ms: number): string {
  return ms < 1_000 ? `${ms} ms` : `${(ms / 1_000).toFixed(2)} s`;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The scratch service could not complete that request.";
}

function StatementResult({ statement }: { statement: ScratchSqlStatement }) {
  const hasRows = statement.columns.length > 0;
  return (
    <article className="scratch-statement">
      <header className="scratch-statement-header">
        <span className="scratch-statement-index">Statement {statement.index + 1}</span>
        <strong>{statement.kind}</strong>
        {statement.affected_rows > 0 && <span>{statement.affected_rows.toLocaleString()} row{statement.affected_rows === 1 ? "" : "s"} affected</span>}
        {statement.truncated && <span className="scratch-mini-badge">truncated</span>}
      </header>

      {hasRows ? (
        <div className="sql-result-table-wrap">
          <div className="sql-result-scroll">
            <table className="sql-result-table">
              <thead>
                <tr>{statement.columns.map((column, columnIndex) => <th key={`${column}:${columnIndex}`}>{column}</th>)}</tr>
              </thead>
              <tbody>
                {statement.rows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex}>{cell === null ? <em>NULL</em> : String(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {statement.rows.length === 0 && <p className="sql-empty-result">(no rows returned)</p>}
        </div>
      ) : (
        <p className="scratch-muted">
          {statement.affected_rows > 0
            ? `${statement.affected_rows.toLocaleString()} row${statement.affected_rows === 1 ? "" : "s"} changed.`
            : "Completed with no rows to display."}
        </p>
      )}
    </article>
  );
}

export function SqlScratchPage() {
  const { data: session, isLoading, error: sessionError } = useQuery({
    queryKey: LEARNING_SESSION_QUERY_KEY,
    queryFn: startLearningSession,
    staleTime: 30_000,
  });
  const learnerId = session?.learner_id;

  const initialDraft = readScratchDraft(SQL_SCRATCH_DRAFT_KEY, STARTER_SQL);
  const [sql, setSql] = useState(initialDraft.code);
  const [storageAvailable, setStorageAvailable] = useState(initialDraft.storageAvailable);
  const [draftDirty, setDraftDirty] = useState(!initialDraft.storageAvailable);
  const [copyStatus, setCopyStatus] = useState("");
  const [base, setBase] = useState("blank");

  const [workspace, setWorkspace] = useState<StoredSqlWorkspace | null>(null);
  const [workspacePending, setWorkspacePending] = useState(false);
  const [workspaceNotice, setWorkspaceNotice] = useState<string | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [workspaceStorageAvailable, setWorkspaceStorageAvailable] = useState(true);
  const initializedFor = useRef<string | null>(null);

  const [result, setResult] = useState<ScratchSqlRunResult | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [requestErrorStatus, setRequestErrorStatus] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const outputPanel = useScratchPanelState(SQL_SCRATCH_PANEL_KEY);
  const outputRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!learnerId || initializedFor.current === learnerId) return;
    initializedFor.current = learnerId;
    const stored = readSqlWorkspace(learnerId);
    setWorkspace(stored);
    if (stored) {
      setBase(stored.base);
      setWorkspaceStorageAvailable(true);
    }
  }, [learnerId]);

  useEffect(() => {
    if (!draftDirty) return;
    function warnBeforeLeaving(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", warnBeforeLeaving);
    return () => window.removeEventListener("beforeunload", warnBeforeLeaving);
  }, [draftDirty]);

  useEffect(() => {
    if (!workspace) return;
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, [workspace?.workspace_id]);

  const runMutation = useMutation({
    mutationKey: SCRATCH_SQL_MUTATION_KEY,
    mutationFn: (source: string) => {
      if (!learnerId || !workspace) return Promise.reject(new Error("Create a SQL workspace before running a script."));
      return runSqlScratch({ learner_id: learnerId, workspace_id: workspace.workspace_id, sql: source });
    },
    onMutate: () => {
      setResult(null);
      setRequestError(null);
      setRequestErrorStatus(0);
      setWorkspaceError(null);
    },
    onSuccess: (answer) => {
      setResult(answer);
      setWorkspaceNotice(null);
      setNow(Date.now());
      const updated: StoredSqlWorkspace = { ...answer.workspace, saved_at: Date.now() };
      setWorkspace(updated);
      if (learnerId) setWorkspaceStorageAvailable(writeSqlWorkspace(learnerId, answer.workspace));
    },
    onError: (error: Error) => {
      if (isMissingWorkspace(error)) {
        if (learnerId) clearSqlWorkspace(learnerId);
        setWorkspace(null);
        setResult(null);
        setWorkspaceNotice("That SQL workspace is no longer available. Your editor text is safe — create a new workspace to continue.");
      } else {
        setRequestError(error.message);
        setRequestErrorStatus(error instanceof ApiError ? error.status : 0);
      }
    },
  });

  function updateSql(value: string) {
    setSql(value);
    const saved = writeScratchDraft(SQL_SCRATCH_DRAFT_KEY, value);
    setStorageAvailable(saved);
    setDraftDirty(!saved);
  }

  function run() {
    if (runMutation.isPending) return;
    if (!workspace) {
      setWorkspaceError("Create a SQL workspace before running a script.");
      return;
    }
    outputPanel.expand();
    // Bring the panel into view if it sits below the fold; no jump when visible.
    window.requestAnimationFrame(() => outputRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }));
    runMutation.mutate(sql);
  }

  function resetEditor() {
    if (sql === STARTER_SQL) return;
    if (!window.confirm("Replace the current SQL draft with the starter script?")) return;
    updateSql(STARTER_SQL);
  }

  async function createOrReplaceWorkspace() {
    if (!learnerId || workspacePending || runMutation.isPending) return;
    const replacing = workspace;
    if (replacing && !window.confirm(`Replace "${replacing.base_name}" with a new SQL workspace? All tables and rows in the current workspace will be deleted. Your editor text will stay.`)) return;

    setWorkspacePending(true);
    setWorkspaceError(null);
    setWorkspaceNotice(null);
    try {
      const created = await createSqlScratchWorkspace({ learner_id: learnerId, base });
      const saved = writeSqlWorkspace(learnerId, created);
      setWorkspaceStorageAvailable(saved);
      setWorkspace({ ...created, saved_at: Date.now() });
      setBase(created.base);
      setResult(null);
      setRequestError(null);
      setNow(Date.now());

      if (replacing) {
        // The replacement is committed before the old token is destroyed, so a
        // failed create cannot discard the learner's current database.
        try {
          await deleteSqlScratchWorkspace({ learner_id: learnerId, workspace_id: replacing.workspace_id });
        } catch (error) {
          if (!isMissingWorkspace(error)) {
            setWorkspaceNotice("The new workspace is ready, but the previous workspace could not be deleted. It will expire on its own.");
          }
        }
      }
    } catch (error) {
      setWorkspaceError(errorMessage(error));
    } finally {
      setWorkspacePending(false);
    }
  }

  async function resetWorkspace() {
    if (!learnerId || !workspace || workspacePending || runMutation.isPending) return;
    if (!window.confirm(`Reset this workspace to "${workspace.base_name}"? Every table and row created here will be lost. Your editor text will stay.`)) return;

    setWorkspacePending(true);
    setWorkspaceError(null);
    setWorkspaceNotice(null);
    try {
      const metadata = await resetSqlScratchWorkspace({ learner_id: learnerId, workspace_id: workspace.workspace_id });
      setWorkspace({ ...metadata, saved_at: Date.now() });
      setWorkspaceStorageAvailable(writeSqlWorkspace(learnerId, metadata));
      setResult(null);
      setRequestError(null);
      setNow(Date.now());
    } catch (error) {
      if (isMissingWorkspace(error)) {
        clearSqlWorkspace(learnerId);
        setWorkspace(null);
        setWorkspaceNotice("That SQL workspace is no longer available. Your editor text is safe — create a new workspace to continue.");
      } else {
        setWorkspaceError(errorMessage(error));
      }
    } finally {
      setWorkspacePending(false);
    }
  }

  async function deleteWorkspace() {
    if (!learnerId || !workspace || workspacePending || runMutation.isPending) return;
    if (!window.confirm(`Delete "${workspace.base_name}"? All tables and rows in this SQL workspace will be destroyed. Your editor text will stay.`)) return;

    setWorkspacePending(true);
    setWorkspaceError(null);
    setWorkspaceNotice(null);
    try {
      try {
        await deleteSqlScratchWorkspace({ learner_id: learnerId, workspace_id: workspace.workspace_id });
      } catch (error) {
        if (!isMissingWorkspace(error)) throw error;
      }
      clearSqlWorkspace(learnerId);
      setWorkspace(null);
      setResult(null);
      setRequestError(null);
      setWorkspaceNotice("Workspace deleted. Your editor text is still here if you want to create another.");
    } catch (error) {
      setWorkspaceError(errorMessage(error));
    } finally {
      setWorkspacePending(false);
    }
  }

  async function copySql() {
    try {
      await navigator.clipboard.writeText(sql);
      setCopyStatus("SQL copied");
    } catch {
      setCopyStatus("Clipboard access is unavailable in this browser");
    }
    window.setTimeout(() => setCopyStatus(""), 2_500);
  }

  const idleMinutes = workspace ? Math.ceil(workspace.idle_ttl_seconds / 60) : 0;
  const remainingSeconds = workspace
    ? Math.max(0, workspace.expires_in_seconds - Math.floor((now - workspace.saved_at) / 1_000))
    : 0;
  const datasets = session?.datasets ?? [];
  const activeBaseName = workspace?.base_name ?? datasets.find((dataset) => dataset.id === base)?.name ?? "Blank SQLite database";
  const rejected = requestErrorStatus === 422;

  if (isLoading) {
    return (
      <section className="page-wrap scratch-page">
        <CodeQuestNav module="sql" />
        <div className="loading-line">Loading Code Quest...</div>
      </section>
    );
  }

  if (sessionError || !session) {
    return (
      <section className="page-wrap scratch-page">
        <CodeQuestNav module="sql" />
        <div className="empty-state">
          <span className="eyebrow">SQL Scratch unavailable</span>
          <h1>This workspace is unavailable right now.</h1>
          <p>Please try again shortly.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="page-wrap scratch-page">
      <CodeQuestNav module="sql" />
      <span className="sr-only" id="quest-editor-help">SQL Scratch scripts are bounded and never graded. Each run is one workspace-managed transaction.</span>
      <span className="sr-only" id="quest-editor-shortcuts">Press Ctrl and Enter to run. Press Ctrl and the backquote key to show or hide the output panel.</span>

      <header className="scratch-header">
        <div>
          <span className="eyebrow">Code Quest · Scratch</span>
          <h1>SQL Scratch</h1>
          <p>A persistent, temporary SQLite workspace for your own queries and schema experiments. Nothing here is graded or added to XP.</p>
        </div>
        <div className="scratch-mode-badge">
          <Icon name="database" />
          <span><strong>SQLite workspace</strong><small>State survives runs, then expires after idle time.</small></span>
        </div>
      </header>

      <div className="scratch-notice-strip">
        <p><Icon name="lock" /><span><strong>Atomic scripts:</strong> every statement runs in one workspace-managed transaction. If one fails, the whole run rolls back.</span></p>
        <p><Icon name="alert" /><span><strong>Bounded runs:</strong> each run has a server-owned time cap plus limits on statements, rows per statement, cell text, and response size. Filter or LIMIT larger results.</span></p>
        <p><Icon name="time" /><span><strong>Temporary data:</strong> database state is disposable, not backed up, and expires after {workspace ? `${idleMinutes} minutes` : "about an hour"} idle. Keep the SQL you want to reuse in the editor draft.</span></p>
      </div>

      <section className="scratch-workspace-bar" aria-label="SQL workspace status and actions">
        <div className="scratch-workspace-summary">
          <span className={`status-dot ${workspace ? "connected" : "legacy"}`} aria-hidden="true" />
          <div>
            <strong>{workspace ? workspace.base_name : "No active workspace"}</strong>
            <small>
              {workspace
                ? remainingSeconds > 0
                  ? `Base copy · about ${Math.ceil(remainingSeconds / 60)} min idle remaining · refreshed by successful runs`
                  : "Idle time elapsed. Run once to check, or create a fresh workspace."
                : "Choose a base and create a workspace before running SQL."}
            </small>
          </div>
        </div>

        <div className="scratch-workspace-controls">
          <label className="scratch-base-picker">
            <span>{workspace ? "Base for a new workspace" : "Workspace base"}</span>
            <select className="form-select" value={base} onChange={(event) => setBase(event.target.value)} disabled={workspacePending || runMutation.isPending}>
              <option value="blank">Blank SQLite database</option>
              {datasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>{dataset.name}</option>
              ))}
            </select>
          </label>
          <button type="button" className="button button-primary toolbar-button" onClick={createOrReplaceWorkspace} disabled={workspacePending || runMutation.isPending}>
            <Icon name={workspace ? "refresh" : "plus"} /> {workspacePending ? "Working..." : workspace ? "New workspace" : "Create workspace"}
          </button>
          {workspace && (
            <>
              <button type="button" className="button button-secondary toolbar-button" onClick={resetWorkspace} disabled={workspacePending || runMutation.isPending}>
                <Icon name="refresh" /> Reset data
              </button>
              <button type="button" className="text-button toolbar-button scratch-danger-text" onClick={deleteWorkspace} disabled={workspacePending || runMutation.isPending}>
                Delete
              </button>
            </>
          )}
        </div>
      </section>

      {!workspaceStorageAvailable && (
        <div className="scratch-inline-notice" role="alert">
          <Icon name="alert" />
          <span>This browser cannot remember the workspace token. Keep this tab open, or create a new workspace after reload.</span>
        </div>
      )}

      {workspaceError && (
        <div className="scratch-error-card scratch-page-alert" role="alert">
          <strong>Workspace action failed</strong>
          <p>{workspaceError}</p>
        </div>
      )}

      {workspaceNotice && (
        <div className="scratch-inline-notice" role="status">
          <Icon name="alert-circle" />
          <span>{workspaceNotice}</span>
        </div>
      )}

      <div className="scratch-layout">
        <section className="scratch-panel" aria-label="SQL scratch editor">
          <div className="query-tab-bar">
            <div className="query-tab active" aria-current="page">
              <span className="tab-icon"><Icon name="database" /></span>
              <span className="tab-label">scratch.sql</span>
              {draftDirty && <span className="tab-dirty" aria-label="Draft could not be saved">●</span>}
            </div>
          </div>

          <div className="query-toolbar" role="toolbar" aria-label="SQL scratch actions">
            <div className="toolbar-group">
              <button
                type="button"
                className="button button-primary toolbar-button"
                onClick={run}
                disabled={runMutation.isPending || workspacePending || !workspace}
                title="Run SQL (Ctrl+Enter)"
              >
                <Icon name="play" /> {runMutation.isPending ? "Running..." : "Run SQL"}
              </button>
            </div>
            <div className="toolbar-group">
              <button type="button" className="text-button toolbar-button" onClick={resetEditor} disabled={runMutation.isPending || sql === STARTER_SQL}>
                <Icon name="refresh" /> Reset editor
              </button>
              <button type="button" className="text-button toolbar-button" onClick={() => { setResult(null); setRequestError(null); setRequestErrorStatus(0); }} disabled={runMutation.isPending || (!result && !requestError)}>
                Clear output
              </button>
              <button type="button" className="text-button toolbar-button" onClick={() => downloadText("sql-scratch.sql", sql)}>
                <Icon name="download" /> Download
              </button>
              <button type="button" className="text-button toolbar-button" onClick={copySql}>
                <Icon name="notes" /> Copy
              </button>
            </div>
          </div>

          <div className="code-workspace scratch-code-workspace">
            <SyntaxEditor
              id="sql-scratch-editor"
              language="sql"
              value={sql}
              onChange={updateSql}
              onKeyDown={(event) => handleScratchEditorKeyDown(event, { value: sql, language: "sql", onChange: updateSql, onRun: run })}
              readOnly={runMutation.isPending}
            />
          </div>

          <div className="scratch-editor-footnote">
            <span>{storageAvailable ? "Draft saved in this browser" : "This browser cannot save the draft. Download it before leaving."}</span>
            <span className="separator" aria-hidden="true">·</span>
            <span><kbd>Ctrl</kbd> + <kbd>Enter</kbd> to run</span>
            <span className="separator" aria-hidden="true">·</span>
            <span><kbd>Ctrl</kbd> + <kbd>`</kbd> shows or hides the output panel</span>
            <span className="separator" aria-hidden="true">·</span>
            <span>{activeBaseName}</span>
            {copyStatus && <span className="copy-status" aria-live="polite">{copyStatus}</span>}
          </div>
        </section>

        <ScratchOutputPanel
          eyebrow="Results"
          title="Script output"
          ariaLabel="SQL scratch output"
          status={result ? { label: statusLabel(result), tone: statusTone(result) } : null}
          open={outputPanel.open}
          height={outputPanel.height}
          dragging={outputPanel.dragging}
          onToggle={outputPanel.toggle}
          onResize={outputPanel.setHeight}
          onDragChange={outputPanel.setDragging}
          panelRef={outputRef}
          footer={
            <>
              <span><Icon name="check" /> No XP, hints, badges, or challenge progress change here.</span>
              <span>SQLite dialect only. BEGIN, COMMIT, ROLLBACK, SAVEPOINT, ATTACH, and PRAGMA are workspace-managed or unavailable.</span>
            </>
          }
        >
            {runMutation.isPending && (
              <div className="scratch-empty-state">
                <span className="scratch-spinner" aria-hidden="true" />
                <strong>Running the script atomically...</strong>
                <p>The workspace is locked for this run. Reset and delete wait until it finishes.</p>
              </div>
            )}

            {!runMutation.isPending && !workspace && !result && (
              <div className="scratch-empty-state">
                <Icon name="database" className="scratch-empty-icon" />
                <strong>Create a workspace first</strong>
                <p>Pick a blank database or a registered dataset copy above. Your SQL draft is already saved independently.</p>
              </div>
            )}

            {!runMutation.isPending && workspace && !result && !requestError && (
              <div className="scratch-empty-state">
                <Icon name="play" className="scratch-empty-icon" />
                <strong>Ready to run</strong>
                <p>Statements execute in order. Reads return bounded rows; writes report affected rows.</p>
              </div>
            )}

            {!runMutation.isPending && requestError && (
              <div className="scratch-error-card" role="alert">
                <strong>{rejected ? "That script was rejected" : "That run could not start"}</strong>
                <p>{requestError}</p>
                <p className="scratch-error-action">{rejected ? "Edit the script and run again. No workspace changes were made." : "Check the service and try again."}</p>
              </div>
            )}

            {!runMutation.isPending && result && (
              <>
                {result.error && (
                  <div className="scratch-error-card" role="alert">
                    <strong>{result.status === "timeout" ? "Time limit reached" : "Script rolled back"}</strong>
                    <p>{result.error}</p>
                    {result.error_statement !== null && <p className="scratch-error-action">Statement {result.error_statement + 1} failed.</p>}
                    <p className="scratch-error-action">Atomic run: no changes from this script were saved.</p>
                  </div>
                )}

                {result.truncated && (
                  <div className="scratch-inline-notice">
                    <Icon name="alert" />
                    <span>Some rows or cells were truncated to keep the response bounded. Add filters or a LIMIT for a smaller result.</span>
                  </div>
                )}

                {result.statements.length === 0 && !result.error && (
                  <p className="scratch-muted">The script completed without a statement result.</p>
                )}

                <div className="scratch-statement-list">
                  {result.statements.map((statement) => (
                    <StatementResult key={statement.index} statement={statement} />
                  ))}
                </div>

                <div className="scratch-result-meta">
                  <span>{formatDuration(result.duration_ms)}</span>
                  <span>{result.summary.statements.toLocaleString()} statement{result.summary.statements === 1 ? "" : "s"}</span>
                  <span>{result.summary.rows.toLocaleString()} row{result.summary.rows === 1 ? "" : "s"} returned</span>
                  <span>{result.summary.affected_rows.toLocaleString()} row{result.summary.affected_rows === 1 ? "" : "s"} affected</span>
                  {workspace && <span>{workspace.limits.time_cap_ms / 1000}s time cap · {workspace.limits.max_statements} statement limit</span>}
                </div>
              </>
            )}
        </ScratchOutputPanel>
      </div>
    </section>
  );
}
