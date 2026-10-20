import { useState, type KeyboardEvent } from "react";
import type { LearningCodeResult } from "../../../types";

interface LearningOutputPanelProps {
  previewResult: LearningCodeResult | null;
  result: LearningCodeResult | null;
  isPathTrack: boolean;
  isCleared: boolean;
  hintsRevealed: number;
  hints: string[];
  plan: string[];
  onRevealHint: () => void;
  solution: { explanation: string; code: string; language: "python" | "sql" } | null;
  onLoadSolution: () => void;
  portfolioNote: string;
  setPortfolioNote: (value: string) => void;
  portfolioValidation: string;
  setPortfolioValidation: (value: string) => void;
  onDownloadCapstoneReport: () => void;
  challenge: { capstone?: boolean; capstone_rubric?: string[]; id: string; title: string; business_question?: string; coding: { language: "python" | "sql" }; metric_contract?: string };
}

function renderOutputContent(result: LearningCodeResult) {
  if (result.sql_columns && result.sql_rows) {
    return (
      <div className="sql-result-table-wrap">
        <span className="result-output-label">Query result</span>
        <div className="sql-result-scroll">
          <table className="sql-result-table">
            <thead>
              <tr>{result.sql_columns.map((col) => <th key={col}>{col}</th>)}</tr>
            </thead>
            <tbody>
              {result.sql_rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>{cell === null ? <em>NULL</em> : String(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {result.sql_rows.length === 0 && <p className="sql-empty-result">(no rows returned)</p>}
      </div>
    );
  }
  if (result.output) {
    return (
      <>
        <span className="result-output-label">Program output</span>
        <pre className="result-output">{result.output}</pre>
      </>
    );
  }
  return null;
}

export function LearningOutputPanel(props: LearningOutputPanelProps) {
  const { previewResult, result, isPathTrack, isCleared, hintsRevealed, hints, plan, onRevealHint, solution, onLoadSolution, portfolioNote, setPortfolioNote, portfolioValidation, setPortfolioValidation, onDownloadCapstoneReport, challenge } = props;

  const showSolutionReview = isCleared && isPathTrack;
  const hasHelp = hints.length > 0 || plan.length > 0;
  const helpTabLabel = plan.length > 0
    ? hints.length > 0
      ? `Plan & hints (${hintsRevealed}/${hints.length})`
      : "Plan"
    : `Hints (${hintsRevealed}/${hints.length})`;
  const [activePanel, setActivePanel] = useState<"results" | "feedback" | "hints">("results");

  function moveTab(event: KeyboardEvent<HTMLButtonElement>) {
    const tabs: Array<"results" | "feedback" | "hints"> = hasHelp
      ? ["results", "feedback", "hints"]
      : ["results", "feedback"];
    const current = tabs.indexOf(activePanel);
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const offset = event.key === "ArrowRight" ? 1 : -1;
    const nextPanel = tabs[(current + offset + tabs.length) % tabs.length];
    setActivePanel(nextPanel);
    document.getElementById(`tab-${nextPanel}`)?.focus();
  }

  return (
    <div className="learning-output-panel" role="region" aria-label="Output and feedback">
      <div className="panel-tabs" role="tablist" aria-label="Output panels">
        <button
          role="tab"
          aria-selected={activePanel === "results"}
          aria-controls="output-results"
          id="tab-results"
          tabIndex={activePanel === "results" ? 0 : -1}
          onClick={() => setActivePanel("results")}
          onKeyDown={moveTab}
          className={activePanel === "results" ? "panel-tab active" : "panel-tab"}
        >
          {challenge.coding.language === "sql" ? "Results" : "Output"}
        </button>
        <button
          role="tab"
          aria-selected={activePanel === "feedback"}
          aria-controls="output-feedback"
          id="tab-feedback"
          tabIndex={activePanel === "feedback" ? 0 : -1}
          onClick={() => setActivePanel("feedback")}
          onKeyDown={moveTab}
          className={activePanel === "feedback" ? "panel-tab active" : "panel-tab"}
        >
          Feedback
        </button>
        {hasHelp && (
          <button
            role="tab"
            aria-selected={activePanel === "hints"}
            aria-controls="output-hints"
            id="tab-hints"
            tabIndex={activePanel === "hints" ? 0 : -1}
            onClick={() => setActivePanel("hints")}
            onKeyDown={moveTab}
            className={activePanel === "hints" ? "panel-tab active" : "panel-tab"}
          >
            {helpTabLabel}
          </button>
        )}
      </div>

      <div role="tabpanel" id="output-results" aria-labelledby="tab-results" className="output-panel" hidden={activePanel !== "results"}>
        {previewResult && previewResult.preview && (
          <div className="answer-feedback answer-feedback-preview" role="status">
            <strong>Preview run</strong>
            {previewResult.error_line && (
              <p className="error-location">
                Error on line {previewResult.error_line}{previewResult.error_column ? `, column ${previewResult.error_column}` : ""}
              </p>
            )}
            <p>{previewResult.feedback}</p>
            {renderOutputContent(previewResult)}
          </div>
        )}

        {result && (
          <div className={`answer-feedback ${result.correct ? "answer-feedback-correct" : "answer-feedback-wrong"}`} role="status">
            <strong>{result.correct ? result.awarded_xp ? `Correct! +${result.awarded_xp} XP` : "Already cleared!" : "Keep going"}</strong>
            {result.mastery_badge_awarded && <p className="mastery-badge">Mastery badge earned: solved without hints</p>}
            {result.error_line && (
              <p className="error-location">Error on line {result.error_line}{result.error_column ? `, column ${result.error_column}` : ""}</p>
            )}
            <p>{result.feedback}</p>
            {result.coaching && result.coaching.length > 0 && (
              <ul className="coach-notes">
                {result.coaching.map((note) => <li key={note}>{note}</li>)}
              </ul>
            )}
            {renderOutputContent(result)}
          </div>
        )}

        {!previewResult && !result && (
          <div className="output-empty">
            <p>Run your code to see output here.</p>
          </div>
        )}
      </div>

      <div role="tabpanel" id="output-feedback" aria-labelledby="tab-feedback" className="output-panel" hidden={activePanel !== "feedback"}>
        <div className="feedback-content">
          {result && (
            <div className={`feedback-item ${result.correct ? "feedback-correct" : "feedback-incorrect"}`}>
              <h4>{result.correct ? "✓ Solution accepted" : "✗ Solution needs work"}</h4>
              <p>{result.feedback}</p>
              {result.coaching && result.coaching.length > 0 && (
                <ul className="coach-notes">
                  {result.coaching.map((note) => <li key={note}>{note}</li>)}
                </ul>
              )}
              {result.awarded_xp && <p className="xp-awarded">+{result.awarded_xp} XP awarded</p>}
            </div>
          )}
          {!result && (
            <p className="feedback-placeholder">Submit your solution to see detailed feedback.</p>
          )}
        </div>
      </div>

      {hasHelp && (
        <div role="tabpanel" id="output-hints" aria-labelledby="tab-hints" className="output-panel" hidden={activePanel !== "hints"}>
          <div className="hints-panel">
            {plan.length > 0 && (
              <details className="plan-card">
                <summary>Plan (pseudo-code) — free to read</summary>
                <p className="plan-note">The plan never counts as a hint and never costs the mastery badge.</p>
                <ol className="plan-list">
                  {plan.map((step, index) => <li key={index}>{step}</li>)}
                </ol>
              </details>
            )}
            <ol id="quest-hint-list" aria-live="polite">
              {hints.slice(0, hintsRevealed).map((hint, index) => (
                <li key={index}>
                  <strong>{index === 0 ? "Nudge" : index === hints.length - 1 ? "Stronger hint" : `Step ${index + 1}`}: </strong>
                  {hint}
                </li>
              ))}
            </ol>
            {hintsRevealed < hints.length && (
              <button type="button" className="text-button" aria-controls="quest-hint-list" aria-expanded={hintsRevealed > 0} onClick={onRevealHint}>
                Reveal next hint
              </button>
            )}
          </div>
        </div>
      )}

      {showSolutionReview && (
        <section className="solution-review">
          <button type="button" className="text-button" onClick={onLoadSolution}>
            {solution ? "Refresh solution walkthrough" : "View solution walkthrough"}
          </button>
          {solution && (
            <div>
              <strong>How it works</strong>
              <p>{solution.explanation}</p>
              {solution.code && (
                <details>
                  <summary>Compare with my code</summary>
                  <pre className="result-output"><code>{solution.code}</code></pre>
                </details>
              )}
            </div>
          )}
        </section>
      )}

      {challenge.capstone && isCleared && result?.correct && (
        <section className="portfolio-export" aria-labelledby="portfolio-heading">
          <h4 id="portfolio-heading">Capstone review</h4>
          <p>Check your result and add a validation note and interpretation. The report stays on your device until you choose to download it.</p>
          {challenge.capstone_rubric && (
            <ul>
              {challenge.capstone_rubric.map((criterion) => <li key={criterion}>{criterion}</li>)}
            </ul>
          )}
          <label htmlFor="portfolio-validation">How did you validate the result?</label>
          <textarea id="portfolio-validation" rows={3} value={portfolioValidation} onChange={(event) => setPortfolioValidation(event.target.value)} maxLength={2000} />
          <label htmlFor="portfolio-note">What does the result tell the business?</label>
          <textarea id="portfolio-note" rows={4} value={portfolioNote} onChange={(event) => setPortfolioNote(event.target.value)} maxLength={2000} />
          <button type="button" className="button button-secondary" onClick={onDownloadCapstoneReport}>Download Markdown report</button>
        </section>
      )}
    </div>
  );
}
