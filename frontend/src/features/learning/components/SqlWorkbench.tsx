import { useState, type KeyboardEvent } from "react";
import type { LearningSession, LearningTrack, LearningTrackId, LearningChallenge, LearningCodeResult, LearningReviewItem } from "../../../types";
import { SyntaxEditor } from "../SyntaxEditor";
import { ChallengeBrief } from "./ChallengeBrief";
import { SchemaNavigator } from "./SchemaNavigator";
import { ChallengeExplorer } from "./ChallengeExplorer";
import { LearningOutputPanel } from "./LearningOutputPanel";
import { Icon } from "../../../ui/Icon";

export interface SqlWorkbenchProps {
  session: LearningSession;
  tracks: LearningTrack[];
  moduleTitle: string;
  moduleEyebrow: string;
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
  completed: number[];
  codeMutationPending: boolean;
  previewMutationPending: boolean;
  reviewItems: LearningReviewItem[];
  onOpenReviewItem: (item: LearningReviewItem) => void;
}

function runnerLabels(challenge: LearningChallenge) {
  switch (challenge.runner) {
    case "python_guided":
      return {
        sandbox: "Guided Python runner: instant feedback inside a small, safe language subset",
        connection: "Guided Python · instant feedback",
        badge: "Sandboxed",
      };
    case "python_real":
      return {
        sandbox: "Real Python: an isolated subprocess with a read-only dataset bridge",
        connection: "CPython subprocess · read-only datasets",
        badge: "Isolated runner",
      };
    case "sqlite":
      return challenge.mode === "scratch"
        ? {
            sandbox: "SQLite scratch sandbox: a disposable copy you can create tables and update rows in",
            connection: "SQLite scratch · disposable copy",
            badge: "Scratch sandbox",
          }
        : {
            sandbox: "SQLite read-only sandbox: queries run against the shared datasets",
            connection: "SQLite · read-only datasets",
            badge: "Read-only sandbox",
          };
    default:
      return challenge.coding.language === "python"
        ? {
            sandbox: "Python sandbox: supported language subset with bounded execution",
            connection: "Restricted Python runner",
            badge: "Read-only sandbox",
          }
        : {
            sandbox: "SQL sandbox: read-only queries on the lesson sample tables",
            connection: "SQLite sample tables",
            badge: "Read-only sandbox",
          };
  }
}

export function SqlWorkbench(props: SqlWorkbenchProps) {
  const {
    session,
    tracks,
    moduleTitle,
    moduleEyebrow,
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
    completed,
    codeMutationPending,
    previewMutationPending,
    reviewItems,
    onOpenReviewItem,
  } = props;

  const track = tracks.find((t) => t.id === trackId) ?? tracks[0]!;
  const coding = challenge.coding;
  const hints = coding.hints ?? [];
  const plan = coding.plan ?? [];
  const [navigatorCollapsed, setNavigatorCollapsed] = useState(false);

  const isPathTrack = track.kind === "path";
  const labels = runnerLabels(challenge);
  const challengeIndex = track.challenges.findIndex((item) => item.id === challenge.id);
  const phase = track.phases?.find((item) => item.id === challenge.phase_id);
  const clearedTotal = tracks.reduce((total, item) => total + (session.progress[item.id]?.length ?? 0), 0);
  const challengeTotal = tracks.reduce((total, item) => total + item.challenges.length, 0);

  return (
    <div className="sql-workbench">
      {/* Top bar - Code Quest heading and progress */}
      <header className="workbench-topbar">
        <div className="workbench-brand">
          <span className="eyebrow">{moduleEyebrow}</span>
          <h1>{moduleTitle}</h1>
        </div>
        <div className="workbench-scorebar">
          <div><span className="quest-score-icon"><Icon name="trophy" /></span><span><strong>{session.xp} XP</strong><small>Total points</small></span></div>
          <div><span className="quest-score-icon"><Icon name="check" /></span><span><strong>{clearedTotal} / {challengeTotal}</strong><small>Challenges cleared</small></span></div>
        </div>
      </header>

      {/* Track switcher */}
      <div className="workbench-switchers">
        <div className="track-switcher" role="group" aria-label="Choose a learning track">
          {tracks.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={trackId === item.id}
              className={`track-tab ${trackId === item.id ? "track-tab-active" : ""}`}
              onClick={() => selectTrack(item.id)}
              disabled={codeMutationPending || previewMutationPending}
            >
              <Icon name={item.language === "python" || item.id.includes("python") ? "code" : "data"} />
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

          {isPathTrack && (
            <div className="connection-info">
              <div className="connection-status">
                <span className="status-dot" aria-hidden="true" />
                <span>{labels.connection}</span>
              </div>
              <div className="connection-label">{track.summary}</div>
            </div>
          )}

          {isPathTrack && session.datasets.length > 0 && (
            <SchemaNavigator datasets={session.datasets} activeDatasetId={challenge.dataset?.id} />
          )}

          {reviewItems.length > 0 && (
            <section className="review-queue" aria-label="Practice queue">
              <div className="review-queue-heading">
                <h4>PRACTICE</h4>
                <span>{reviewItems.length} to revisit</span>
              </div>
              <div className="review-queue-items">
                {reviewItems.map((item) => (
                  <button
                    key={`${item.track}:${item.challenge_id}`}
                    type="button"
                    className="review-item"
                    onClick={() => onOpenReviewItem(item)}
                    disabled={codeMutationPending || previewMutationPending}
                    title={`${item.track_name}: ${item.title}`}
                  >
                    <strong>{item.title}</strong>
                    <small>{item.reason === "hint" ? "Revisit without hints" : "Spaced revisit"} · {item.track_name} · {item.phase_name}</small>
                  </button>
                ))}
              </div>
            </section>
          )}

          <ChallengeExplorer
            track={track}
            level={challengeIndex}
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
              <span className="tab-icon"><Icon name={coding.language === "python" ? "code" : "data"} /></span>
              <span className="tab-label">{coding.language === "python" ? "analysis.py" : "query.sql"}</span>
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
                <Icon name="lock" /> {labels.badge}
              </span>
            </div>
          </div>

          {/* Challenge brief - compact task area */}
          <ChallengeBrief challenge={challenge} isCleared={isCleared} />

          {/* Code editor */}
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
                <span id="quest-editor-help">{labels.sandbox}</span>
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
            <p className="preview-hint" aria-live="polite">Run example executes your code without checking the answer or awarding XP.</p>
          </div>

          <LearningOutputPanel
            previewResult={previewResult}
            result={result}
            isPathTrack={isPathTrack}
            isCleared={isCleared}
            hintsRevealed={hintsRevealed}
            hints={hints}
            plan={plan}
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
            <span>{isFinished ? "Track complete" : result?.correct ? "Challenge complete" : `${challengeIndex + 1} of ${track.challenges.length}`}</span>
            {result?.correct && !isFinished && <button type="button" className="button button-primary" onClick={onNext}>Next challenge <Icon name="chevron-right" /></button>}
          </div>
        </section>
      </div>

      {/* Status bar */}
      <footer className="workbench-statusbar" role="status" aria-label="Workspace status">
        <div className="status-item status-connection">
          <span className={`status-dot ${isPathTrack ? "connected" : "legacy"}`} aria-hidden="true" />
          {labels.connection}
        </div>
        <div className="status-item status-challenge">
          <Icon name="activities" /> {phase ? `${phase.name} · ` : ""}{challenge.topic} · {challengeIndex + 1} of {track.challenges.length}
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
