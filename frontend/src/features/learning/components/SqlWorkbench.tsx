import { useState, type KeyboardEvent } from "react";
import type { LearningSession, LearningTrackId, LearningChallenge, LearningSchema, LearningCodeResult } from "../../../types";
import { SyntaxEditor } from "../SyntaxEditor";
import { ChallengeBrief } from "./ChallengeBrief";
import { SchemaNavigator } from "./SchemaNavigator";
import { ChallengeExplorer } from "./ChallengeExplorer";
import { LearningOutputPanel } from "./LearningOutputPanel";
import { Icon } from "../../../ui/Icon";

interface SqlWorkbenchProps {
  session: LearningSession;
  trackId: LearningTrackId;
  challenge: LearningChallenge;
  code: string;
  onCodeChange: (value: string) => void;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  readOnly: boolean;
  previewResult: LearningCodeResult | null;
  result: LearningCodeResult | null;
  isCleared: boolean;
  isFinished: boolean;
  hintsRevealed: number;
  onRevealHint: () => void;
  onPreview: () => void;
  onCheck: () => void;
  onReset: () => void;
  onUndoReset: () => void;
  resetSnapshot: string | null;
  draftStorageAvailable: boolean;
  draftDirty: boolean;
  onDownloadDraft: () => void;
  onCopyCode: () => void;
  copyStatus: string;
  onNext: () => void;
  solution: { explanation: string; code: string; language: "python" | "sql" } | null;
  onLoadSolution: () => void;
  portfolioNote: string;
  setPortfolioNote: (value: string) => void;
  portfolioValidation: string;
  setPortfolioValidation: (value: string) => void;
  onDownloadCapstoneReport: () => void;
  challengeSearch: string;
  setChallengeSearch: (value: string) => void;
  selectLevel: (level: number) => void;
  selectTrack: (trackId: LearningTrackId) => void;
  selectCurriculum: (curriculumId: "legacy" | "northwind_data") => void;
  curriculumId: "legacy" | "northwind_data";
  curriculumTracks: { id: LearningTrackId; name: string; challenges: LearningChallenge[]; summary: string }[];
  completed: number[];
  schema: LearningSchema;
  codeMutationPending: boolean;
  previewMutationPending: boolean;
  isMySQLTrack: boolean;
  isPythonTrack: boolean;
}

export function SqlWorkbench(props: SqlWorkbenchProps) {
  const {
    session,
    trackId,
    challenge,
    code,
    onCodeChange,
    onKeyDown,
    readOnly,
    previewResult,
    result,
    isCleared,
    isFinished,
    hintsRevealed,
    onRevealHint,
    onPreview,
    onCheck,
    onReset,
    onUndoReset,
    resetSnapshot,
    draftStorageAvailable,
    draftDirty,
    onDownloadDraft,
    onCopyCode,
    copyStatus,
    onNext,
    solution,
    onLoadSolution,
    portfolioNote,
    setPortfolioNote,
    portfolioValidation,
    setPortfolioValidation,
    onDownloadCapstoneReport,
    challengeSearch,
    setChallengeSearch,
    selectLevel,
    selectTrack,
    selectCurriculum,
    curriculumId,
    curriculumTracks,
    completed,
    schema,
    codeMutationPending,
    previewMutationPending,
    isMySQLTrack,
    isPythonTrack,
  } = props;

  const track = session.tracks.find((t) => t.id === trackId)!;
  const coding = challenge.coding;
  const hints = coding.hints ?? [];
  const [navigatorCollapsed, setNavigatorCollapsed] = useState(false);

  // Determine sandbox label based on track
  const sandboxLabel = isMySQLTrack
    ? "MySQL 8.0 sandbox: read-only queries against curated Northwind views"
    : isPythonTrack && trackId === "northwind_python"
      ? "Restricted Python sandbox: bounded Northwind row dictionaries"
      : isPythonTrack
        ? "Python sandbox: supported language subset with bounded execution"
        : "SQL sandbox: read-only queries on the lesson sample tables";
  const connectionLabel = isMySQLTrack
    ? "MySQL 8.0 · SELECT-only learning views"
    : trackId === "northwind_python"
      ? "Northwind read-only table API"
      : isPythonTrack
        ? "Restricted Python runner"
        : "SQLite legacy sandbox";

  return (
    <div className="sql-workbench">
      {/* Top bar - Code Quest heading and progress */}
      <header className="workbench-topbar">
        <div className="workbench-brand">
          <span className="eyebrow">Learn by building</span>
          <h1>Code Quest</h1>
        </div>
        <div className="workbench-scorebar">
          <div><span className="quest-score-icon"><Icon name="trophy" /></span><span><strong>{session.xp} XP</strong><small>Total points</small></span></div>
          <div><span className="quest-score-icon"><Icon name="check" /></span><span><strong>{Object.values(session.progress).reduce((total, levels) => total + levels.length, 0)} / {session.tracks.reduce((total, t) => total + t.challenges.length, 0)}</strong><small>Challenges cleared</small></span></div>
        </div>
      </header>

      {/* Curriculum and track switchers */}
      <div className="workbench-switchers">
        <div className="curriculum-switcher" role="group" aria-label="Choose a learning curriculum">
          {session.curricula.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={curriculumId === item.id}
              className={`curriculum-tab ${curriculumId === item.id ? "curriculum-tab-active" : ""}`}
              onClick={() => selectCurriculum(item.id)}
              disabled={codeMutationPending || previewMutationPending}
            >
              <strong>{item.name}</strong>
              <small>{item.summary}</small>
            </button>
          ))}
        </div>

        <div className="track-switcher" role="group" aria-label="Choose a track in this curriculum">
          {curriculumTracks.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={trackId === item.id}
              className={`track-tab ${trackId === item.id ? "track-tab-active" : ""}`}
              onClick={() => selectTrack(item.id)}
              disabled={codeMutationPending || previewMutationPending}
            >
              <Icon name={item.id.includes("python") ? "code" : "data"} />
              <strong>{item.name}</strong>
              <small>{(session.progress[item.id] ?? []).length} / {item.challenges.length} cleared</small>
            </button>
          ))}
        </div>
      </div>

      {/* Main workspace grid */}
      <div className={`workbench-grid ${navigatorCollapsed ? "navigator-collapsed" : ""}`}>
        {/* Navigator / Schemas sidebar */}
        <aside className="workbench-sidebar navigator-sidebar" aria-label="Navigator">
          <div className="sidebar-header">
            <h4>NAVIGATOR</h4>
            <div className="sidebar-actions">
              <button type="button" className="icon-button" aria-label={navigatorCollapsed ? "Expand navigator" : "Collapse navigator"} aria-expanded={!navigatorCollapsed} onClick={() => setNavigatorCollapsed((collapsed) => !collapsed)}>
                <Icon name={navigatorCollapsed ? "chevron-right" : "chevron-left"} />
              </button>
            </div>
          </div>

          {(isMySQLTrack || trackId === "northwind_python") && (
            <div className="connection-info">
              <div className="connection-status">
                <span className="status-dot" aria-hidden="true" />
                <span>Read-only access</span>
              </div>
              <div className="connection-label">{connectionLabel}</div>
            </div>
          )}

          {curriculumId === "northwind_data" && <SchemaNavigator schema={schema} />}
          <ChallengeExplorer
            track={track}
            trackId={trackId}
            level={track.challenges.findIndex((item) => item.id === challenge.id)}
            completed={completed}
            challengeSearch={challengeSearch}
            onSearchChange={setChallengeSearch}
            onSelectLevel={selectLevel}
            onClearSearch={() => setChallengeSearch("")}
            codeMutationPending={codeMutationPending || previewMutationPending}
          />
        </aside>

        {/* Editor area */}
        <section className="workbench-editor-area" aria-label={`${coding.language.toUpperCase()} learning workspace`}>
          {/* Query tab and toolbar */}
          <div className="query-tab-bar">
            <div className="query-tab active" aria-current="page">
              <span className="tab-icon"><Icon name={isPythonTrack ? "code" : "data"} /></span>
              <span className="tab-label">{isPythonTrack ? "analysis.py" : "query.sql"}</span>
              {draftDirty && <span className="tab-dirty" aria-label="Unsaved changes">●</span>}
            </div>
          </div>

          <div className="query-toolbar" role="toolbar" aria-label={`${coding.language} actions`}>
            <div className="toolbar-group">
              <button
                type="button"
                className="button button-secondary toolbar-button"
                onClick={onPreview}
                disabled={previewMutationPending || codeMutationPending || Boolean(result?.correct)}
                title="Run example (Ctrl+Enter)"
              >
                <Icon name="arrow" /> Run Example
              </button>
              <button
                type="button"
                className="button button-primary toolbar-button"
                onClick={onCheck}
                disabled={codeMutationPending || previewMutationPending || Boolean(result?.correct)}
                title="Run and check (Ctrl+Shift+Enter)"
              >
                <Icon name="check" /> Run and Check
              </button>
            </div>
            <div className="toolbar-group">
              <button
                type="button"
                className="text-button toolbar-button"
                onClick={onReset}
                disabled={codeMutationPending || Boolean(result?.correct) || code === coding.starter_code}
              >
                <Icon name="refresh" /> Reset
              </button>
              {resetSnapshot !== null && <button type="button" className="text-button toolbar-button" onClick={onUndoReset}>Undo reset</button>}
              <button
                type="button"
                className="text-button toolbar-button"
                onClick={onCopyCode}
              >
                <Icon name="notes" /> Copy
              </button>
            </div>
            <div className="toolbar-group toolbar-status">
              <span className="read-only-badge">
                <Icon name="lock" /> Read-only sandbox
              </span>
            </div>
          </div>

          {/* Challenge brief - compact task area */}
          <ChallengeBrief challenge={challenge} isCleared={isCleared} trackId={trackId} />

          {/* SQL Editor */}
          <div className="editor-container" id="query-editor">
            <div className="code-workspace">
              <SyntaxEditor
                id="quest-code"
                language={coding.language}
                value={code}
                onChange={onCodeChange}
                onKeyDown={onKeyDown}
                readOnly={readOnly}
              />
              <div className="code-editor-footnote">
                <span id="quest-editor-help">{sandboxLabel}</span>
              <span id="quest-editor-shortcuts">Ctrl + Enter to preview; Ctrl + Shift + Enter to check</span>
              </div>
            </div>

            {/* Editor actions */}
            <div className="code-editor-actions">
              <span aria-live="polite" className="editor-footnote">
                {draftStorageAvailable ? "Edits save in this browser" : "Edits are not being saved"}
                <span className="separator" aria-hidden="true">&middot;</span>
                Clear this challenge for {challenge.xp} XP
              </span>
            </div>
            <p className="copy-status" aria-live="polite">{copyStatus}</p>
            {draftDirty && <button type="button" className="text-button draft-download" onClick={onDownloadDraft}>Download this draft</button>}
            <p className="preview-hint" aria-live="polite">Run example executes your query against the sample data without checking the answer or awarding XP.</p>
          </div>

          <LearningOutputPanel
            previewResult={previewResult}
            result={result}
            trackId={trackId}
            isCleared={isCleared}
            hintsRevealed={hintsRevealed}
            hints={hints}
            onRevealHint={onRevealHint}
            solution={solution}
            onLoadSolution={onLoadSolution}
            portfolioNote={portfolioNote}
            setPortfolioNote={setPortfolioNote}
            portfolioValidation={portfolioValidation}
            setPortfolioValidation={setPortfolioValidation}
            onDownloadCapstoneReport={onDownloadCapstoneReport}
            challenge={challenge}
          />
          <div className="challenge-footer">
            <span>{isFinished ? "Track complete" : result?.correct ? "Level complete" : `${track.challenges.findIndex((item) => item.id === challenge.id) + 1} of ${track.challenges.length}`}</span>
            {result?.correct && !isFinished && <button type="button" className="button button-primary" onClick={onNext}>Next level <Icon name="chevron-right" /></button>}
          </div>
        </section>
      </div>

      {/* Status bar */}
      <footer className="workbench-statusbar" role="status" aria-label="Workspace status">
        <div className="status-item status-connection">
          <span className={`status-dot ${isMySQLTrack ? "connected" : "legacy"}`} aria-hidden="true" />
          {connectionLabel}
        </div>
        <div className="status-item status-challenge">
          <Icon name="activities" /> {challenge.topic} · Level {track.challenges.findIndex((c) => c.id === challenge.id) + 1} of {track.challenges.length}
        </div>
        <div className="status-item status-draft">
          <Icon name={draftStorageAvailable ? "check" : "close"} />
          {draftStorageAvailable ? "Saved in this browser" : "Edits not saved"}
        </div>
        <div className="status-item status-shortcut">
          <kbd>Ctrl</kbd><kbd>Enter</kbd> Preview
        </div>
      </footer>
    </div>
  );
}
