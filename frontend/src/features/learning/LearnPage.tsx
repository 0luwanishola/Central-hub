import { useEffect, useState, type KeyboardEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LEARNING_SESSION_QUERY_KEY, LEARNING_REVIEW_QUERY_KEY, startLearningSession, submitLearningCode, previewLearningCode, recordLearningEvent, getLearningSolution, getLearningReview } from "../../services/apiClient";
import type { LearningSession, LearningTrack, LearningTrackId, LearningCodeResult, LearningSolution, LearningReviewItem } from "../../types";
import { SqlWorkbench } from "./components/SqlWorkbench";
import { CodeQuestNav } from "../scratch/CodeQuestNav";
import { defaultTrackForModule, getCodeQuestModule, tracksForModule, type CodeQuestModuleId } from "./codeQuestModules";

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

export function LearnPage({ module }: { module: CodeQuestModuleId }) {
  const queryClient = useQueryClient();
  const moduleInfo = getCodeQuestModule(module);
  const { data: session, isLoading, error } = useQuery({
    queryKey: LEARNING_SESSION_QUERY_KEY,
    queryFn: startLearningSession,
    staleTime: 30_000,
  });
  const { data: review } = useQuery({
    queryKey: [LEARNING_REVIEW_QUERY_KEY, session?.learner_id],
    queryFn: () => getLearningReview(session!.learner_id),
    enabled: Boolean(session),
    staleTime: 60_000,
  });
  const [trackId, setTrackId] = useState<LearningTrackId>(() => moduleInfo.defaultTrackId);
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
      if (answer.correct) void queryClient.invalidateQueries({ queryKey: [LEARNING_REVIEW_QUERY_KEY] });
    },
  });

  const previewMutation = useMutation({
    mutationFn: previewLearningCode,
    onSuccess: (answer) => {
      setPreviewResult(answer);
    },
    onError: (error: Error) => {
      setPreviewResult({ correct: false, awarded_xp: 0, xp: 0, progress: {}, output: "", feedback: error.message, preview: true } as LearningCodeResult);
    },
  });

  const moduleTracks: LearningTrack[] = session ? tracksForModule(session.tracks, module) : [];
  const track = moduleTracks.find((item) => item.id === trackId)
    ?? (session ? defaultTrackForModule(session.tracks, module) : undefined)
    ?? moduleTracks[0];
  const activeTrackId = track?.id ?? trackId;
  const challenge = track?.challenges[level];
  const completed = session?.progress[activeTrackId] ?? [];
  const result = codeMutation.data ?? null;
  const isCleared = completed.includes(level);
  const isFinished = track !== undefined && completed.length === track.challenges.length;
  const moduleTrackIds = new Set(moduleTracks.map((item) => item.id));
  const reviewItems = (review?.items ?? []).filter((item) => moduleTrackIds.has(item.track));

  useEffect(() => {
    if (!session) return;
    const available = tracksForModule(session.tracks, module);
    if (available.length === 0 || available.some((item) => item.id === trackId)) return;
    const nextTrack = defaultTrackForModule(session.tracks, module) ?? available[0];
    setTrackId(nextTrack.id);
  }, [session?.learner_id, module]);

  useEffect(() => {
    if (session && track) setLevel(nextAvailableLevel(session.progress[activeTrackId] ?? [], track.challenges.length));
  }, [session?.learner_id, module]);

  useEffect(() => {
    if (!challenge) return;
    const draft = readDraft(draftKey(session?.learner_id ?? "", activeTrackId, level), challenge.coding.starter_code);
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
  }, [activeTrackId, level, session?.learner_id]);

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
      localStorage.setItem(draftKey(session.learner_id, activeTrackId, level), value);
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

  function selectLevel(nextLevel: number) {
    if (codeMutation.isPending || previewMutation.isPending || nextLevel > completed.length) return;
    if (draftDirty && !window.confirm("This draft could not be saved in this browser. Open another level and discard it? You can download it first.")) return;
    setLevel(nextLevel);
  }

  function openReviewItem(item: LearningReviewItem) {
    if (!session || codeMutation.isPending || previewMutation.isPending) return;
    if (draftDirty && !window.confirm("This draft could not be saved in this browser. Open the review challenge and discard it?")) return;
    setTrackId(item.track);
    setLevel(item.level);
  }

  function checkCode() {
    if (!session || !track || !challenge || codeMutation.isPending) return;
    setPreviewResult(null);
    codeMutation.mutate({ learner_id: session.learner_id, track: activeTrackId, level, code });
  }

  function previewCode() {
    if (!session || !track || !challenge || previewMutation.isPending || codeMutation.isPending) return;
    previewMutation.mutate({ learner_id: session.learner_id, track: activeTrackId, level, code });
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
      `**Track:** ${track?.name ?? "Code Quest"}`,
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
      const answer = await getLearningSolution({ learner_id: session.learner_id, track: activeTrackId, challenge_id: challenge.id });
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

  if (isLoading) return (
    <section className="page-wrap learn-page">
      <CodeQuestNav module={module} />
      <div className="loading-line">Loading Code Quest...</div>
    </section>
  );
  if (error || !session || !track || !challenge) return (
    <section className="page-wrap learn-page">
      <CodeQuestNav module={module} />
      <div className="empty-state"><span className="eyebrow">Path unavailable</span><h1>This learning path is unavailable right now.</h1><p>Please try again shortly.</p></div>
    </section>
  );

  return (
    <section className="page-wrap learn-page">
      <CodeQuestNav module={module} />
      <SqlWorkbench
        session={session}
        tracks={moduleTracks}
        moduleTitle={moduleInfo.title}
        moduleEyebrow={moduleInfo.eyebrow}
        trackId={activeTrackId}
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
        completed={completed}
        codeMutationPending={codeMutation.isPending}
        previewMutationPending={previewMutation.isPending}
        reviewItems={reviewItems}
        onOpenReviewItem={openReviewItem}
      />
    </section>
  );
}
