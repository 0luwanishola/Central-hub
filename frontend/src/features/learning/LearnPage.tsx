import { useEffect, useState, type KeyboardEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LEARNING_SESSION_QUERY_KEY, startLearningSession, submitLearningCode, previewLearningCode, recordLearningEvent, getLearningSolution } from "../../services/apiClient";
import type { LearningCurriculumId, LearningSession, LearningTrackId, LearningCodeResult, LearningSolution } from "../../types";
import { LearningWorkspace } from "./components/LearningWorkspace";

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
  const [curriculumId, setCurriculumId] = useState<LearningCurriculumId>("legacy");
  const [level, setLevel] = useState(0);
  const [code, setCode] = useState("");
  const [resetSnapshot, setResetSnapshot] = useState<string | null>(null);
  const [draftStorageAvailable, setDraftStorageAvailable] = useState(true);
  const [draftDirty, setDraftDirty] = useState(false);
  const [hintsRevealed, setHintsRevealed] = useState(0);
  const [previewResult, setPreviewResult] = useState<LearningCodeResult | null>(null);
  const [portfolioNote, setPortfolioNote] = useState("");
  const [portfolioValidation, setPortfolioValidation] = useState("");
  const [challengeSearch, setChallengeSearch] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const [solution, setSolution] = useState<LearningSolution | null>(null);

  const codeMutation = useMutation({
    mutationFn: submitLearningCode,
    onSuccess: (answer) => {
      queryClient.setQueryData<LearningSession>(LEARNING_SESSION_QUERY_KEY, (current) => current
        ? { ...current, xp: answer.xp, progress: answer.progress }
        : current);
    },
  });

  const previewMutation = useMutation({
    mutationFn: previewLearningCode,
    onSuccess: (answer) => {
      setPreviewResult(answer);
    },
    onError: (error: Error) => {
      setPreviewResult({ correct: false, awarded_xp: 0, xp: 0, progress: { python: [], sql: [] }, output: "", feedback: error.message, preview: true } as LearningCodeResult);
    },
  });

  const track = session?.tracks.find((item) => item.id === trackId);
  const curriculumTracks = session?.tracks.filter((item) => item.curriculum_id === curriculumId) ?? [];
  const challenge = track?.challenges[level];
  const completed = session?.progress[trackId] ?? [];
  const result = codeMutation.data ?? null;
  const isCleared = completed.includes(level);
  const isFinished = track !== undefined && completed.length === track.challenges.length;

  useEffect(() => {
    if (session) setLevel(nextAvailableLevel(session.progress[trackId] ?? [], track?.challenges.length ?? 1));
  }, [session?.learner_id]);

  useEffect(() => {
    if (!challenge) return;
    const draft = readDraft(draftKey(session?.learner_id ?? "", trackId, level), challenge.coding.starter_code);
    setCode(draft.code);
    setDraftStorageAvailable(draft.storageAvailable);
    setDraftDirty(false);
    setHintsRevealed(0);
    setResetSnapshot(null);
    setPreviewResult(null);
    setPortfolioNote("");
    setPortfolioValidation("");
    setSolution(null);
    codeMutation.reset();
  }, [trackId, level, session?.learner_id]);

  useEffect(() => {
    if (!draftDirty) return;
    function warnBeforeLeaving(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", warnBeforeLeaving);
    return () => window.removeEventListener("beforeunload", warnBeforeLeaving);
  }, [draftDirty]);

  function updateCode(value: string, keepResetUndo = false) {
    setCode(value);
    if (!keepResetUndo) setResetSnapshot(null);
    if (codeMutation.data || codeMutation.error) codeMutation.reset();
    if (!session) return;
    try {
      localStorage.setItem(draftKey(session.learner_id, trackId, level), value);
      setDraftStorageAvailable(true);
      setDraftDirty(false);
    } catch {
      setDraftStorageAvailable(false);
      setDraftDirty(true);
    }
  }

  function selectTrack(nextTrack: LearningTrackId) {
    if (!session || codeMutation.isPending || previewMutation.isPending) return;
    if (draftDirty && !window.confirm("This draft could not be saved in this browser. Switch tracks and discard it? You can download it first.")) return;
    setTrackId(nextTrack);
    setLevel(nextAvailableLevel(session.progress[nextTrack] ?? [], session.tracks.find((item) => item.id === nextTrack)?.challenges.length ?? 1));
  }

  function selectCurriculum(nextCurriculum: LearningCurriculumId) {
    if (!session || codeMutation.isPending || previewMutation.isPending) return;
    if (draftDirty && !window.confirm("This draft could not be saved in this browser. Switch curricula and discard it? You can download it first.")) return;
    const nextTrack = session.tracks.find((item) => item.curriculum_id === nextCurriculum);
    if (!nextTrack) return;
    setCurriculumId(nextCurriculum);
    setTrackId(nextTrack.id);
    setLevel(nextAvailableLevel(session.progress[nextTrack.id] ?? [], nextTrack.challenges.length));
  }

  function selectLevel(nextLevel: number) {
    if (codeMutation.isPending || previewMutation.isPending || nextLevel > completed.length) return;
    if (draftDirty && !window.confirm("This draft could not be saved in this browser. Open another level and discard it? You can download it first.")) return;
    setLevel(nextLevel);
  }

  function checkCode() {
    if (!session || !track || !challenge || codeMutation.isPending) return;
    setPreviewResult(null);
    codeMutation.mutate({ learner_id: session.learner_id, track: trackId, level, code });
  }

  function previewCode() {
    if (!session || !track || !challenge || previewMutation.isPending || codeMutation.isPending) return;
    previewMutation.mutate({ learner_id: session.learner_id, track: trackId, level, code });
  }

  function resetStarterCode() {
    if (!challenge || code === challenge.coding.starter_code || codeMutation.isPending || result?.correct) return;
    setResetSnapshot(code);
    updateCode(challenge.coding.starter_code, true);
    codeMutation.reset();
  }

  function undoStarterReset() {
    if (resetSnapshot === null) return;
    const previousCode = resetSnapshot;
    setResetSnapshot(null);
    updateCode(previousCode, true);
    codeMutation.reset();
  }

  function goNext() {
    if (!track || level >= track.challenges.length - 1 || !completed.includes(level)) return;
    if (draftDirty && !window.confirm("This draft could not be saved in this browser. Continue and discard it? You can download it first.")) return;
    setLevel(level + 1);
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

  function downloadDraft() {
    if (!challenge) return;
    const extension = challenge.coding.language === "python" ? "py" : "sql";
    const url = URL.createObjectURL(new Blob([code], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${challenge.id}-draft.${extension}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function revealNextHint() {
    if (!challenge) return;
    setHintsRevealed((shown) => Math.min(shown + 1, challenge.coding.hints.length));
    if (session) void recordLearningEvent(session.learner_id, challenge.id, "hint_open").catch(() => undefined);
  }

  function downloadCapstoneReport() {
    if (!challenge || !result?.correct) return;
    const report = [
      `# ${challenge.title}`,
      "",
      `**Track:** ${track?.name ?? "Northwind Data Professional"}`,
      `**Business question:** ${challenge.business_question ?? challenge.coding.task}`,
      `**Metric and assumptions:** ${challenge.metric_contract ?? "Not specified"}`,
      "",
      "## My solution",
      "```" + challenge.coding.language,
      code,
      "```",
      "",
      "## Validation notes",
      portfolioValidation.trim() || "Validation notes not added.",
      "",
      "## Bounded result",
      result.output || "No text output.",
      "",
      "## My interpretation",
      portfolioNote.trim() || "Add your interpretation before sharing this report.",
      "",
    ].join("\n");
    const url = URL.createObjectURL(new Blob([report], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${challenge.id}-analysis.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function loadSolution() {
    if (!session || !challenge || !isCleared) return;
    try {
      const answer = await getLearningSolution({ learner_id: session.learner_id, track: trackId, challenge_id: challenge.id });
      setSolution(answer);
    } catch (error) {
      setSolution({ explanation: error instanceof Error ? error.message : "Solution could not be loaded.", code: "", language: challenge.coding.language });
    }
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
    } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && event.shiftKey) {
      event.preventDefault();
      checkCode();
    } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      previewCode();
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

  return (
    <section className="page-wrap learn-page">
      <LearningWorkspace
        session={session}
        trackId={trackId}
        challenge={challenge}
        code={code}
        onCodeChange={updateCode}
        onKeyDown={handleEditorKeyDown}
        readOnly={Boolean(result?.correct) || codeMutation.isPending}
        previewResult={previewResult}
        result={result}
        isCleared={isCleared}
        isFinished={isFinished}
        hintsRevealed={hintsRevealed}
        onRevealHint={revealNextHint}
        onPreview={previewCode}
        onCheck={checkCode}
        onReset={resetStarterCode}
        onUndoReset={undoStarterReset}
        resetSnapshot={resetSnapshot}
        draftStorageAvailable={draftStorageAvailable}
        draftDirty={draftDirty}
        onDownloadDraft={downloadDraft}
        onCopyCode={copyCode}
        copyStatus={copyStatus}
        onNext={goNext}
        solution={solution}
        onLoadSolution={loadSolution}
        portfolioNote={portfolioNote}
        setPortfolioNote={setPortfolioNote}
        portfolioValidation={portfolioValidation}
        setPortfolioValidation={setPortfolioValidation}
        onDownloadCapstoneReport={downloadCapstoneReport}
        challengeSearch={challengeSearch}
        setChallengeSearch={setChallengeSearch}
        selectLevel={selectLevel}
        selectTrack={selectTrack}
        selectCurriculum={selectCurriculum}
        curriculumId={curriculumId}
        curriculumTracks={curriculumTracks}
        completed={completed}
        schema={session.schema}
        codeMutationPending={codeMutation.isPending}
        previewMutationPending={previewMutation.isPending}
      />
    </section>
  );
}
