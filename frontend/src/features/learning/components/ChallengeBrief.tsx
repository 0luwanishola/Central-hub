import type { LearningChallenge, LearningDataset, LearningDifficulty } from "../../../types";
import { Icon } from "../../../ui/Icon";

interface ChallengeBriefProps {
  challenge: LearningChallenge;
  isCleared: boolean;
  trackId: "python" | "sql" | "northwind_mysql" | "northwind_python";
}

const tierNames: Record<LearningDifficulty, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

function DatasetTable({ dataset }: { dataset: LearningDataset }) {
  return (
    <div className="dataset-wrap">
      <p className="dataset-caption">Table: <code>{dataset.name}</code></p>
      <div className="dataset-scroll">
        <table className="dataset-table">
          <thead>
            <tr>{dataset.columns.map((column) => <th key={column}>{column}</th>)}</tr>
          </thead>
          <tbody>
            {dataset.rows.map((row, index) => (
              <tr key={`${dataset.name}-${index}`}>
                {row.map((value, cell) => (
                  <td key={`${dataset.name}-${index}-${cell}`}>{value}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ChallengeBrief({ challenge, isCleared, trackId }: ChallengeBriefProps) {
  const coding = challenge.coding;

  return (
    <div className="challenge-brief">
      <div className="challenge-title-row">
        <div>
          <span className="challenge-topic">{challenge.topic}</span>
          <h3>{challenge.title}</h3>
        </div>
        <div className="challenge-badges">
          <span className={`difficulty-badge difficulty-${challenge.difficulty}`}>{tierNames[challenge.difficulty]}</span>
          {isCleared && <span className="completed-badge">Cleared</span>}
        </div>
      </div>

      {challenge.datasets?.map((dataset) => <DatasetTable key={dataset.name} dataset={dataset} />)}

      {challenge.business_question && (
        <div className="business-question">
          <span className="coding-task-label">Business question</span>
          <p>{challenge.business_question}</p>
        </div>
      )}

      {challenge.concept && (
        <div className="concept-card">
          <strong>{challenge.topic}</strong>
          <p>{challenge.concept}</p>
          {challenge.concept_example && (
            <details className="concept-example">
              <summary>Before you start: small example</summary>
              <pre><code>{challenge.concept_example}</code></pre>
            </details>
          )}
        </div>
      )}

      {challenge.metric_contract && (
        <details className="metric-contract">
          <summary>Metric definition and assumptions</summary>
          <p>{challenge.metric_contract}</p>
        </details>
      )}

      <div className="coding-task">
        <span className="coding-task-label">Your task</span>
        <p>{coding.task}</p>
        {challenge.data_sources && (
          <p className="data-source-note">
            Relevant tables: {challenge.data_sources.map((source) => <code key={source.name}>{source.name}</code>)}
            {trackId === "northwind_python" && " (up to 100 rows per table)"}
          </p>
        )}
        {challenge.documentation_url && (
          <a className="official-doc-link" href={challenge.documentation_url} target="_blank" rel="noreferrer">
            Read the official documentation <Icon name="arrow" />
          </a>
        )}
      </div>
    </div>
  );
}
