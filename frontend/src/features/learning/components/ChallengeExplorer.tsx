import type { ChangeEvent } from "react";
import type { LearningTrack, LearningTrackId, LearningDifficulty } from "../../../types";
import { Icon } from "../../../ui/Icon";

interface ChallengeExplorerProps {
  track: LearningTrack;
  trackId: LearningTrackId;
  level: number;
  completed: number[];
  challengeSearch: string;
  onSearchChange: (value: string) => void;
  onSelectLevel: (level: number) => void;
  onClearSearch: () => void;
  codeMutationPending: boolean;
}

const tierNames: Record<LearningDifficulty, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};
const tiers: LearningDifficulty[] = ["beginner", "intermediate", "advanced"];

export function ChallengeExplorer({
  track,
  trackId,
  level,
  completed,
  challengeSearch,
  onSearchChange,
  onSelectLevel,
  onClearSearch,
  codeMutationPending,
}: ChallengeExplorerProps) {
  const tierGroups = tiers.map((difficulty) => ({
    difficulty,
    challenges: track.challenges
      .map((item, index) => ({ item, index }))
      .filter(({ item }) => item.difficulty === difficulty)
      .filter(({ item }) =>
        !challengeSearch.trim() ||
        `${item.title} ${item.topic} ${item.business_question ?? ""} ${item.concept ?? ""}`
          .toLowerCase()
          .includes(challengeSearch.trim().toLowerCase())
      ),
  }));

  return (
    <nav className="challenge-explorer" aria-label={`${track.name} ${trackId.startsWith("northwind_") ? "Northwind" : "Foundations"} levels`}>
      <div className="explorer-search">
        <label htmlFor="explorer-search">Find a level or topic</label>
        <div className="search-input-wrap">
          <input
            id="explorer-search"
            type="search"
            value={challengeSearch}
            onChange={(event: ChangeEvent<HTMLInputElement>) => onSearchChange(event.target.value)}
            placeholder="Search topics or business questions"
          />
          {challengeSearch && (
            <button type="button" className="search-clear" onClick={onClearSearch} aria-label="Clear search">
              <Icon name="close" />
            </button>
          )}
        </div>
      </div>

      <div className="explorer-tiers">
        {tierGroups.map(({ difficulty, challenges }) =>
          challenges.length > 0 && (
            <div key={difficulty} className={`explorer-tier explorer-tier-${difficulty}`}>
              <div className="explorer-tier-heading">
                <strong>{tierNames[difficulty]}</strong>
                <span>
                  {challenges.filter(({ index }) => completed.includes(index)).length} / {challenges.length} cleared
                </span>
              </div>
              <div className="explorer-levels">
                {challenges.map(({ item, index }) => {
                  const isComplete = completed.includes(index);
                  const locked = index > completed.length;
                  return (
                    <button
                      key={item.title}
                      type="button"
                      className={`explorer-level ${index === level ? "explorer-level-active" : ""} ${isComplete ? "explorer-level-complete" : ""} ${locked ? "explorer-level-locked" : ""}`}
                      aria-current={index === level ? "step" : undefined}
                      aria-label={`Level ${index + 1}, ${tierNames[item.difficulty]}: ${item.title}${isComplete ? ", completed" : locked ? ", locked" : ""}`}
                      aria-disabled={locked || undefined}
                      disabled={locked || codeMutationPending}
                      onClick={() => onSelectLevel(index)}
                    >
                      <span>
                        {isComplete ? <Icon name="check" /> : locked ? <Icon name="lock" /> : index + 1}
                      </span>
                      <small>Level {index + 1}</small>
                    </button>
                  );
                })}
              </div>
            </div>
          )
        )}
        {tierGroups.every(({ challenges }) => challenges.length === 0) && (
          <p className="schema-empty">No levels match that search.</p>
        )}
      </div>
    </nav>
  );
}
