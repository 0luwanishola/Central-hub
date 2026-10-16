import type { KeyboardEvent } from "react";
import type { LearningTrackId, LearningSession, LearningChallenge, LearningCodeResult, LearningSchema } from "../../../types";
import { PythonWorkbench } from "./PythonWorkbench";
import { SqlWorkbench } from "./SqlWorkbench";

export interface LearningWorkspaceProps {
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
}

export function LearningWorkspace(props: LearningWorkspaceProps) {
  const { trackId, schema } = props;
  const isPythonTrack = trackId === "python" || trackId === "northwind_python";
  const isMySQLTrack = trackId === "northwind_mysql";

  if (isPythonTrack) {
    return <PythonWorkbench {...props} schema={schema} />;
  }

  return <SqlWorkbench {...props} schema={schema} isMySQLTrack={isMySQLTrack} isPythonTrack={false} />;
}
