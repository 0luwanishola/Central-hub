import type { ChangeEvent } from "react";
import type { LearningTrack, LearningDifficulty } from "../../../types";
import { Icon } from "../../../ui/Icon";

interface ChallengeExplorerProps {
  track: LearningTrack;
  level: number;
  completed: number[];
  challengeSearch: string;
  onSearchChange: (value: string) => void;
  onSelectLevel: (level: number) => void;
  onClearSearch: () => void;
  codeMutationPending: boolean;
}

type ExplorerGroup = {
  key: string;
  label: string;
  arc?: string;
  challenges: { item: LearningTrack["challenges"][number]; index: number }[];
};

const tierNames: Record<LearningDifficulty, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};
const tiers: LearningDifficulty[] = ["beginner", "intermediate", "advanced"];

function matchesSearch(item: LearningTrack["challenges"][number], search: string): boolean {
  if (!search) return true;
  return `${item.title} ${item.topic} ${item.business_question ?? ""} ${item.concept ?? ""}`
    .toLowerCase()
    .includes(search);
}

export function ChallengeExplorer({
  track,
  level,
  completed,
  challengeSearch,
  onSearchChange,
  onSelectLevel,
  onClearSearch,
  codeMutationPending,
}: ChallengeExplorerProps) {
  const search = challengeSearch.trim().toLowerCase();
  const indexed = track.challenges.map((item, index) => ({ item, index }));

  const groups: ExplorerGroup[] = track.phases?.length
    ? track.phases.map((phase) => ({
        key: phase.id,
        label: phase.name,
        arc: phase.arc,
        challenges: indexed.filter(({ item }) => item.phase_id === phase.id),
      }))
    : tiers.map((difficulty) => ({
        key: difficulty,
        label: tierNames[difficulty],
        challenges: indexed.filter(({ item }) => item.difficulty === difficulty),
      }));

  const visibleGroups = groups
    .map((group) => ({ ...group, challenges: group.challenges.filter(({ item }) => matchesSearch(item, search)) }))
    .filter((group) => group.challenges.length > 0);

  return (
    <nav className="challenge-explorer" aria-label={`${track.name} challenges`}>
      <div className="explorer-search">
        <label htmlFor="explorer-search">Find a challenge or topic</label>
        <div className="search-input-wrap">
          <input
            id="explorer-search"
            type="search"
            value={challengeSearch}
            onChange={(event: ChangeEvent<HTMLInputElement>) => onSearchChange(event.target.value)}
            placeholder="Search topics or tasks"
          />
          {challengeSearch && (
            <button type="button" className="search-clear" onClick={onClearSearch} aria-label="Clear search">
              <Icon name="close" />
            </button>
          )}
        </div>
      </div>

      <div className="explorer-tiers">
        {visibleGroups.map((group) => (
          <div key={group.key} className={`explorer-tier ${track.phases?.length ? "explorer-phase" : `explorer-tier-${group.key}`}`}>
            <div className="explorer-tier-heading">
              <strong>{group.label}</strong>
              <span>
                {group.challenges.filter(({ index }) => completed.includes(index)).length} / {group.challenges.length} cleared
              </span>
            </div>
            {group.arc && <p className="phase-arc">{group.arc}</p>}
            <div className="explorer-levels">
              {group.challenges.map(({ item, index }) => {
                const isComplete = completed.includes(index);
                const locked = index > completed.length;
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`explorer-level ${index === level ? "explorer-level-active" : ""} ${isComplete ? "explorer-level-complete" : ""} ${locked ? "explorer-level-locked" : ""}`}
                    aria-current={index === level ? "step" : undefined}
                    aria-label={`Challenge ${index + 1}, ${item.title}${isComplete ? ", completed" : locked ? ", locked" : ""}`}
                    aria-disabled={locked || undefined}
                    disabled={locked || codeMutationPending}
                    onClick={() => onSelectLevel(index)}
                    title={item.title}
                  >
                    <span>
                      {isComplete ? <Icon name="check" /> : locked ? <Icon name="lock" /> : index + 1}
                    </span>
                    <small>{item.title}</small>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
        {visibleGroups.length === 0 && (
          <p className="schema-empty">No challenges match that search.</p>
        )}
      </div>
    </nav>
  );
}
