import { useState } from "react";
import type { LearningPredictDrill } from "../../../types";

interface PredictCheckProps {
  drill: LearningPredictDrill;
}

export function PredictCheck({ drill }: PredictCheckProps) {
  const [picked, setPicked] = useState<number | null>(null);
  const answered = picked !== null;
  const isRight = picked === drill.answer;

  return (
    <section className="predict-check" aria-label="Predict the output">
      <div className="predict-heading">
        <strong>Predict first</strong>
        <span>Optional warm-up · no XP, no badge impact</span>
      </div>
      <p className="predict-prompt">{drill.prompt}</p>
      <pre className="predict-code"><code>{drill.code}</code></pre>
      <div className="predict-options">
        {drill.options.map((option, index) => (
          <button
            key={option}
            type="button"
            className={`predict-option ${answered && index === drill.answer ? "predict-option-correct" : ""} ${answered && index === picked && !isRight ? "predict-option-wrong" : ""}`}
            onClick={() => setPicked(index)}
            disabled={answered}
            aria-pressed={picked === index}
          >
            {option}
          </button>
        ))}
      </div>
      {answered && (
        <div className="predict-foot">
          <p className="predict-why" role="status">{isRight ? "✓ Correct. " : "Not quite. "}{drill.why}</p>
          <button type="button" className="text-button" onClick={() => setPicked(null)}>Try again</button>
        </div>
      )}
    </section>
  );
}
