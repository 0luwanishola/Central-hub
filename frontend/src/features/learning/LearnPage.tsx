import { useEffect, useState, type KeyboardEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LEARNING_SESSION_QUERY_KEY, startLearningSession, submitLearningCode } from "../../services/apiClient";
import type { LearningDataset, LearningDifficulty, LearningSession, LearningTrackId } from "../../types";
import { Icon } from "../../ui/Icon";
import { SyntaxEditor } from "./SyntaxEditor";

function draftKey(learnerId: string, trackId: LearningTrackId, level: number) {
  return `central-hub:code-draft:v1:${learnerId}:${trackId}:${level}`;
}

function readDraft(key: string, starterCode: string): { code: string; storageAvailable: boolean } {
  try {
    return { code: localStorage.getItem(key) ?? starterCode, storageAvailable: true };
  } catch {
    return { code: starterCode, storageAvailable: false };
  }
}

function nextAvailableLevel(completed: number[], total: number): number {
  let next = 0;
  while (next < total && completed.includes(next)) next++;
  return Math.min(next, total - 1);
}

export function LearnPage() {
  const queryClient = useQueryClient();
  const { data: session, isLoading, error } = useQuery({
    queryKey: LEARNING_SESSION_QUERY_KEY,
    queryFn: startLearningSession,
    staleTime: 30_000,
  });
  const [trackId, setTrackId] = useState<LearningTrackId>("python");
  const [level, setLevel] = useState(0);
  const [code, setCode] = useState("");
  const [draftStorageAvailable, setDraftStorageAvailable] = useState(true);
  const [hintsRevealed, setHintsRevealed] = useState(0);
  const codeMutation = useMutation({
    mutationFn: submitLearningCode,
    onSuccess: (answer) => {
      queryClient.setQueryData<LearningSession>(LEARNING_SESSION_QUERY_KEY, (current) => current
        ? { ...current, xp: answer.xp, progress: answer.progress }
        : current);
    },
  });

  const track = session?.tracks.find((item) => item.id === trackId);
  const challenge = track?.challenges[level];
  const completed = session?.progress[trackId] ?? [];
  const result = codeMutation.data;
  const isCleared = completed.includes(level);
  const isFinished = track !== undefined && completed.length === track.challenges.length;
  const totalChallenges = session?.tracks.reduce((total, item) => total + item.challenges.length, 0) ?? 0;
  const clearedChallenges = session ? Object.values(session.progress).reduce((total, levels) => total + levels.length, 0) : 0;

  useEffect(() => {
    if (session) setLevel(nextAvailableLevel(session.progress[trackId], track?.challenges.length ?? 1));
  }, [session?.learner_id]);

  useEffect(() => {
    if (!challenge) return;
    const draft = readDraft(draftKey(session?.learner_id ?? "", trackId, level), challenge.coding.starter_code);
    setCode(draft.code);
    setDraftStorageAvailable(draft.storageAvailable);
    setHintsRevealed(0);
    codeMutation.reset();
  }, [trackId, level, session?.learner_id]);

  function updateCode(value: string) {
    setCode(value);
    if (codeMutation.data || codeMutation.error) codeMutation.reset();
    if (!session) return;
    try {
      localStorage.setItem(draftKey(session.learner_id, trackId, level), value);
      setDraftStorageAvailable(true);
    } catch {
      setDraftStorageAvailable(false);
    }
  }

  function selectTrack(nextTrack: LearningTrackId) {
    if (!session || codeMutation.isPending) return;
    setTrackId(nextTrack);
    setLevel(nextAvailableLevel(session.progress[nextTrack], session.tracks.find((item) => item.id === nextTrack)?.challenges.length ?? 1));
  }

  function selectLevel(nextLevel: number) {
    if (codeMutation.isPending || nextLevel > completed.length) return;
    setLevel(nextLevel);
  }

  function checkCode() {
    if (!session || !track || !challenge || codeMutation.isPending) return;
    codeMutation.mutate({ learner_id: session.learner_id, track: trackId, level, code });
  }

  function goNext() {
    if (!track || level >= track.challenges.length - 1 || !completed.includes(level)) return;
    setLevel(level + 1);
  }

  function handleEditorKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Tab") {
      event.preventDefault();
      const editor = event.currentTarget;
      const start = editor.selectionStart;
      const end = editor.selectionEnd;
      const updated = `${code.slice(0, start)}    ${code.slice(end)}`;
      updateCode(updated);
      requestAnimationFrame(() => editor.setSelectionRange(start + 4, start + 4));
    } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      checkCode();
    } else if (event.key === "Enter") {
      event.preventDefault();
      const editor = event.currentTarget;
      const start = editor.selectionStart;
      const end = editor.selectionEnd;
      const beforeCursor = code.slice(0, start);
      const currentLine = beforeCursor.slice(beforeCursor.lastIndexOf("\n") + 1);
      const indentation = currentLine.match(/^\s*/)?.[0] ?? "";
      const extraIndent = challenge?.coding.language === "python" && /:\s*(?:#.*)?$/.test(currentLine) ? "    " : "";
      const insertion = `\n${indentation}${extraIndent}`;
      updateCode(`${beforeCursor}${insertion}${code.slice(end)}`);
      requestAnimationFrame(() => editor.setSelectionRange(start + insertion.length, start + insertion.length));
    }
  }

  if (isLoading) return <section className="page-wrap learn-page"><div className="loading-line">Loading Code Quest...</div></section>;
  if (error || !session || !track || !challenge) return (
    <section className="page-wrap learn-page">
      <div className="empty-state"><span className="eyebrow">Code Quest unavailable</span><h1>Connect to the learning service.</h1><p>{error instanceof Error ? error.message : "Start the FastAPI backend, then reload this page."}</p></div>
    </section>
  );

  const coding = challenge.coding;
  const hints = coding.hints ?? [];
  const tierNames: Record<LearningDifficulty, string> = {
    beginner: "Beginner",
    intermediate: "Intermediate",
    advanced: "Advanced",
  };
  const tiers: LearningDifficulty[] = ["beginner", "intermediate", "advanced"];
  const tierGroups = tiers.map((difficulty) => ({
    difficulty,
    challenges: track.challenges
      .map((item, index) => ({ item, index }))
      .filter(({ item }) => item.difficulty === difficulty),
  }));

  return (
    <section className="page-wrap learn-page">
      <header className="page-heading">
        <span className="eyebrow">Learn by building</span>
        <h1>Code Quest</h1>
        <p className="muted">Train your Python and SQL skills with quick puzzles, combo challenges, and boss fights. Hints are here when you need a nudge.</p>
      </header>

      <div className="quest-scorebar">
        <div><span className="quest-score-icon"><Icon name="trophy" /></span><span><strong>{session.xp} XP</strong><small>Total points</small></span></div>
        <div><span className="quest-score-icon"><Icon name="check" /></span><span><strong>{clearedChallenges} / {totalChallenges}</strong><small>Challenges cleared</small></span></div>
      </div>

      <div className="track-switcher" role="group" aria-label="Choose a coding track">
        {session.tracks.map((item) => (
          <button key={item.id} type="button" aria-pressed={trackId === item.id} className={`track-tab ${trackId === item.id ? "track-tab-active" : ""}`} onClick={() => selectTrack(item.id)} disabled={codeMutation.isPending}>
            <Icon name={item.id === "python" ? "code" : "data"} /><strong>{item.name}</strong><small>{session.progress[item.id].length} / {item.challenges.length} cleared</small>
          </button>
        ))}
      </div>

      <section className="quest-card" aria-labelledby="quest-heading">
        <div className="quest-card-heading">
          <div><span className="eyebrow">{track.name} track</span><h2 id="quest-heading">{track.name} Quest</h2><p>{track.summary}</p></div>
          <div className="quest-progress"><strong>{completed.length} / {track.challenges.length}</strong><span>levels cleared</span><div className="quest-progress-track"><span style={{ width: `${completed.length / track.challenges.length * 100}%` }} /></div></div>
        </div>

        <nav className="quest-level-groups" aria-label={`${track.name} levels`}>
          {tierGroups.map(({ difficulty, challenges }) => challenges.length > 0 && <div key={difficulty} className={`quest-tier quest-tier-${difficulty}`}>
            <div className="quest-tier-heading"><strong>{tierNames[difficulty]}</strong><span>{challenges.filter(({ index }) => completed.includes(index)).length} / {challenges.length} cleared</span></div>
            <div className="quest-levels">
              {challenges.map(({ item, index }) => {
                const isComplete = completed.includes(index);
                const locked = index > completed.length;
                return <button key={item.title} type="button" className={`quest-level ${index === level ? "quest-level-active" : ""} ${isComplete ? "quest-level-complete" : ""}`} aria-current={index === level ? "step" : undefined} aria-label={`Level ${index + 1}, ${tierNames[item.difficulty]}: ${item.title}${isComplete ? ", completed" : locked ? ", locked" : ""}`} disabled={locked || codeMutation.isPending} onClick={() => selectLevel(index)}><span>{isComplete ? <Icon name="check" /> : locked ? <Icon name="lock" /> : index + 1}</span><small>Level {index + 1}</small></button>;
              })}
            </div>
          </div>)}
        </nav>

        <article className="quest-challenge">
          <div className="challenge-title-row"><div><span className="challenge-topic">{challenge.topic}</span><h3>{challenge.title}</h3></div><div className="challenge-badges"><span className={`difficulty-badge difficulty-${challenge.difficulty}`}>{tierNames[challenge.difficulty]}</span>{isCleared && <span className="completed-badge">Cleared</span>}</div></div>
          {challenge.datasets?.map((dataset) => <DatasetTable key={dataset.name} dataset={dataset} />)}

          <div className="coding-task">
            <span className="coding-task-label">Your task</span>
            <p>{coding.task}</p>
          </div>

          <div className="code-workspace">
            <div className="code-workspace-heading">
              <label htmlFor="quest-code">{coding.language === "python" ? "Python editor" : "SQL editor"}</label>
              <button type="button" className="text-button" onClick={() => { updateCode(coding.starter_code); codeMutation.reset(); }} disabled={codeMutation.isPending || Boolean(result?.correct)}>Reset starter code</button>
            </div>
            <SyntaxEditor
              id="quest-code"
              language={coding.language}
              value={code}
              onChange={updateCode}
              onKeyDown={handleEditorKeyDown}
              readOnly={Boolean(result?.correct) || codeMutation.isPending}
            />
            <div className="code-editor-footnote">
              <span>{coding.language === "python" ? "Python sandbox: loops, algorithms, functions, and recursion" : "SQL sandbox: read-only queries on the sample tables above"}</span>
              <span>Ctrl + Enter to run</span>
            </div>
            <div className="code-editor-actions">
              <button type="button" className="button button-primary" onClick={checkCode} disabled={codeMutation.isPending || Boolean(result?.correct)}>{codeMutation.isPending ? "Running..." : "Run and check"}</button>
              <span aria-live="polite">{draftStorageAvailable ? "Edits save in this browser" : "Edits are not being saved"} · Clear this challenge for {challenge.xp} XP</span>
            </div>
          </div>

          <div className="quest-hints">
            <div className="quest-hints-heading"><strong>Need a hint?</strong><span>{hintsRevealed} / {hints.length} revealed</span></div>
            {hintsRevealed > 0 && <ol>{hints.slice(0, hintsRevealed).map((hint, index) => <li key={index}>{hint}</li>)}</ol>}
            {hintsRevealed < hints.length && <button type="button" className="text-button" onClick={() => setHintsRevealed((shown) => Math.min(shown + 1, hints.length))}>Reveal next hint</button>}
          </div>

          {result && <div className={`answer-feedback ${result.correct ? "answer-feedback-correct" : "answer-feedback-wrong"}`} role="status">
            <strong>{result.correct ? result.awarded_xp ? `Correct! +${result.awarded_xp} XP` : "Already cleared!" : "Keep going"}</strong>
            <p>{result.feedback}</p>
            {result.output && <><span className="result-output-label">Program output</span><pre className="result-output">{result.output}</pre></>}
          </div>}
          {codeMutation.error && <p className="notice notice-error" role="alert">{codeMutation.error.message}</p>}
          <div className="challenge-footer">
            <span>{isFinished && level === track.challenges.length - 1 && result?.correct ? "Track complete - brilliant work!" : result?.correct ? "Level complete" : `${level + 1} of ${track.challenges.length}`}</span>
            {result?.correct && level < track.challenges.length - 1 && <button type="button" className="button button-primary" onClick={goNext}>Next level <Icon name="chevron-right" /></button>}
            {isFinished && level === track.challenges.length - 1 && result?.correct && <span className="quest-finish-mark" aria-label="Track completed"><Icon name="trophy" /></span>}
          </div>
        </article>
      </section>
    </section>
  );
}

function DatasetTable({ dataset }: { dataset: LearningDataset }) {
  return <div className="dataset-wrap"><p className="dataset-caption">Table: <code>{dataset.name}</code></p><div className="dataset-scroll"><table className="dataset-table"><thead><tr>{dataset.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{dataset.rows.map((row, index) => <tr key={`${dataset.name}-${index}`}>{row.map((value, cell) => <td key={`${dataset.name}-${index}-${cell}`}>{value}</td>)}</tr>)}</tbody></table></div></div>;
}
