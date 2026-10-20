import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ApiError, runPythonScratch, SCRATCH_PYTHON_MUTATION_KEY } from "../../services/apiClient";
import type { ScratchPythonResult } from "../../types";
import { Icon } from "../../ui/Icon";
import { SyntaxEditor } from "../learning/SyntaxEditor";
import { CodeQuestNav } from "./CodeQuestNav";
import { ScratchOutputPanel } from "./ScratchOutputPanel";
import { useScratchPanelState } from "./useScratchPanel";
import { createScratchRunId, handleScratchEditorKeyDown } from "./editorKeys";
import { downloadText, PYTHON_SCRATCH_DRAFT_KEY, PYTHON_SCRATCH_PANEL_KEY, readScratchDraft, writeScratchDraft } from "./storage";

const STARTER_CODE = `from collections import Counter

words = "ideas are easy; testing ideas makes them useful"
print(Counter(words.split()))
`;

function statusLabel(result: ScratchPythonResult): string {
  if (result.status === "timeout") return "Stopped by the time limit";
  if (result.status === "error") return "Python reported an error";
  return "Completed";
}

function statusTone(result: ScratchPythonResult): "success" | "warning" | "error" {
  if (result.status === "timeout") return "warning";
  if (result.status === "error") return "error";
  return "success";
}

function formatDuration(ms: number): string {
  return ms < 1_000 ? `${ms} ms` : `${(ms / 1_000).toFixed(2)} s`;
}

export function PythonScratchPage() {
  const initialDraft = readScratchDraft(PYTHON_SCRATCH_DRAFT_KEY, STARTER_CODE);
  const [code, setCode] = useState(initialDraft.code);
  const [storageAvailable, setStorageAvailable] = useState(initialDraft.storageAvailable);
  const [draftDirty, setDraftDirty] = useState(!initialDraft.storageAvailable);
  const [result, setResult] = useState<ScratchPythonResult | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [requestErrorStatus, setRequestErrorStatus] = useState(0);
  const [copyStatus, setCopyStatus] = useState("");
  const outputPanel = useScratchPanelState(PYTHON_SCRATCH_PANEL_KEY);
  const outputRef = useRef<HTMLElement | null>(null);

  const runMutation = useMutation({
    mutationKey: SCRATCH_PYTHON_MUTATION_KEY,
    mutationFn: ({ code: source, runId }: { code: string; runId: string }) =>
      runPythonScratch({ code: source, run_id: runId }),
    onMutate: () => {
      setResult(null);
      setRequestError(null);
      setRequestErrorStatus(0);
    },
    onSuccess: (answer) => setResult(answer),
    onError: (error: Error) => {
      setRequestError(error.message);
      setRequestErrorStatus(error instanceof ApiError ? error.status : 0);
    },
  });

  useEffect(() => {
    if (!draftDirty) return;
    function warnBeforeLeaving(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", warnBeforeLeaving);
    return () => window.removeEventListener("beforeunload", warnBeforeLeaving);
  }, [draftDirty]);

  function updateCode(value: string) {
    setCode(value);
    const saved = writeScratchDraft(PYTHON_SCRATCH_DRAFT_KEY, value);
    setStorageAvailable(saved);
    setDraftDirty(!saved);
  }

  function run() {
    if (runMutation.isPending) return;
    outputPanel.expand();
    // Bring the panel into view if it sits below the fold; no jump when visible.
    window.requestAnimationFrame(() => outputRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }));
    runMutation.mutate({ code, runId: createScratchRunId() });
  }

  function resetEditor() {
    if (code === STARTER_CODE) return;
    if (!window.confirm("Replace the current Python draft with the starter example?")) return;
    updateCode(STARTER_CODE);
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code);
      setCopyStatus("Code copied");
    } catch {
      setCopyStatus("Clipboard access is unavailable in this browser");
    }
    window.setTimeout(() => setCopyStatus(""), 2_500);
  }

  function downloadFile(name: string, content: string) {
    downloadText(name || "artifact.txt", content);
  }

  const limits = result?.limits;
  const rejected = requestErrorStatus === 422;

  return (
    <section className="page-wrap scratch-page">
      <CodeQuestNav />
      <span className="sr-only" id="quest-editor-help">Each Python Scratch run is bounded, starts in a fresh process, and is never graded.</span>
      <span className="sr-only" id="quest-editor-shortcuts">Press Ctrl and Enter to run. Press Ctrl and the backquote key to show or hide the output panel.</span>

      <header className="scratch-header">
        <div>
          <span className="eyebrow">Code Quest · Scratch</span>
          <h1>Python Scratch</h1>
          <p>Run your own Python ideas without selecting a challenge. Nothing here is graded or added to XP.</p>
        </div>
        <div className="scratch-mode-badge">
          <Icon name="refresh" />
          <span><strong>Fresh process every run</strong><small>Variables, imports, and files reset each time.</small></span>
        </div>
      </header>

      <div className="scratch-notice-strip">
        <p><Icon name="alert" /><span><strong>Bounded runs:</strong> each run has a server-owned time limit plus output and file caps. The exact limits appear after a run.</span></p>
        <p><Icon name="lock" /><span><strong>Local and trusted use:</strong> source runs in the Python subprocess sandbox, not a shell. Do not treat it as a public code service.</span></p>
      </div>

      <div className="scratch-layout">
        <section className="scratch-panel" aria-label="Python scratch editor">
          <div className="query-tab-bar">
            <div className="query-tab active" aria-current="page">
              <span className="tab-icon"><Icon name="code" /></span>
              <span className="tab-label">scratch.py</span>
              {draftDirty && <span className="tab-dirty" aria-label="Draft could not be saved">●</span>}
            </div>
          </div>

          <div className="query-toolbar" role="toolbar" aria-label="Python scratch actions">
            <div className="toolbar-group">
              <button
                type="button"
                className="button button-primary toolbar-button"
                onClick={run}
                disabled={runMutation.isPending}
                title="Run Python (Ctrl+Enter)"
              >
                <Icon name="play" /> {runMutation.isPending ? "Running..." : "Run Python"}
              </button>
            </div>
            <div className="toolbar-group">
              <button type="button" className="text-button toolbar-button" onClick={resetEditor} disabled={runMutation.isPending || code === STARTER_CODE}>
                <Icon name="refresh" /> Reset editor
              </button>
              <button type="button" className="text-button toolbar-button" onClick={() => { setResult(null); setRequestError(null); setRequestErrorStatus(0); }} disabled={runMutation.isPending || (!result && !requestError)}>
                Clear output
              </button>
              <button type="button" className="text-button toolbar-button" onClick={() => downloadText("python-scratch.py", code)}>
                <Icon name="download" /> Download
              </button>
              <button type="button" className="text-button toolbar-button" onClick={copyCode}>
                <Icon name="notes" /> Copy
              </button>
            </div>
          </div>

          <div className="code-workspace scratch-code-workspace">
            <SyntaxEditor
              id="python-scratch-editor"
              language="python"
              value={code}
              onChange={updateCode}
              onKeyDown={(event) => handleScratchEditorKeyDown(event, { value: code, language: "python", onChange: updateCode, onRun: run })}
              readOnly={runMutation.isPending}
            />
          </div>

          <div className="scratch-editor-footnote">
            <span>{storageAvailable ? "Draft saved in this browser" : "This browser cannot save the draft. Download it before leaving."}</span>
            <span className="separator" aria-hidden="true">·</span>
            <span><kbd>Ctrl</kbd> + <kbd>Enter</kbd> to run</span>
            <span className="separator" aria-hidden="true">·</span>
            <span><kbd>Ctrl</kbd> + <kbd>`</kbd> shows or hides the output panel</span>
            {copyStatus && <span className="copy-status" aria-live="polite">{copyStatus}</span>}
          </div>
        </section>

        <ScratchOutputPanel
          eyebrow="Output"
          title="Run result"
          ariaLabel="Python scratch output"
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
              <span>Only UTF-8 text files created during the run are returned.</span>
            </>
          }
        >
            {runMutation.isPending && (
              <div className="scratch-empty-state">
                <span className="scratch-spinner" aria-hidden="true" />
                <strong>Running in a fresh Python process...</strong>
                <p>The editor is locked until this run finishes.</p>
              </div>
            )}

            {!runMutation.isPending && requestError && (
              <div className="scratch-error-card" role="alert">
                <strong>{rejected ? "That run was rejected" : "That run could not start"}</strong>
                <p>{requestError}</p>
                <p className="scratch-error-action">{rejected ? "Edit the script and try again." : "Check the service is running, then try again."}</p>
              </div>
            )}

            {!runMutation.isPending && !requestError && !result && (
              <div className="scratch-empty-state">
                <Icon name="play" className="scratch-empty-icon" />
                <strong>Ready when you are</strong>
                <p>Run the complete editor buffer. Each run starts with no variables or files from the previous run.</p>
              </div>
            )}

            {!runMutation.isPending && result && (
              <>
                {result.error && (
                  <div className="scratch-error-card" role="alert">
                    <strong>{result.timed_out ? "Time limit reached" : "Python reported an error"}</strong>
                    <p>{result.error}</p>
                    {result.error_line && <p className="scratch-error-action">Line {result.error_line}</p>}
                  </div>
                )}

                {result.truncated && (
                  <div className="scratch-inline-notice">
                    <Icon name="alert" />
                    <span>Some output or generated files were truncated to keep this run bounded.</span>
                  </div>
                )}

                <div className="scratch-output-block">
                  <span className="scratch-output-label">Standard output</span>
                  {result.stdout ? <pre className="scratch-pre">{result.stdout}</pre> : <p className="scratch-muted">No standard output.</p>}
                </div>

                {result.stderr && (
                  <div className="scratch-output-block">
                    <span className="scratch-output-label">Standard error</span>
                    <pre className="scratch-pre scratch-pre-stderr">{result.stderr}</pre>
                  </div>
                )}

                {result.files.length > 0 && (
                  <div className="scratch-output-block">
                    <span className="scratch-output-label">Generated text files</span>
                    <p className="scratch-muted">Files exist only for this response. Download anything you want to keep.</p>
                    <div className="scratch-file-list">
                      {result.files.map((file) => (
                        <article className="scratch-file" key={file.name}>
                          <div className="scratch-file-heading">
                            <span><Icon name="files" /> <strong>{file.name}</strong></span>
                            <button type="button" className="text-button" onClick={() => downloadFile(file.name, file.content)}>
                              Download
                            </button>
                          </div>
                          <pre className="scratch-pre">{file.content || "(empty file)"}</pre>
                          <small>
                            {file.size_bytes !== undefined ? `${file.size_bytes.toLocaleString()} bytes` : `${file.content.length.toLocaleString()} characters`}
                            {file.truncated ? " · truncated to the file limit" : ""}
                          </small>
                        </article>
                      ))}
                    </div>
                  </div>
                )}

                {result.skipped_files.length > 0 && (
                  <div className="scratch-output-block">
                    <span className="scratch-output-label">Files not returned</span>
                    <ul className="scratch-skipped-list">
                      {result.skipped_files.map((file) => (
                        <li key={`${file.name}:${file.reason}`}><strong>{file.name}</strong> — {file.reason}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="scratch-result-meta">
                  <span>{formatDuration(result.duration_ms)}</span>
                  <span>{result.files.length} file{result.files.length === 1 ? "" : "s"} returned</span>
                  {limits && <span>{limits.timeout_seconds}s time limit · {limits.max_stdout_characters.toLocaleString()} character output cap</span>}
                </div>
              </>
            )}
        </ScratchOutputPanel>
      </div>
    </section>
  );
}
