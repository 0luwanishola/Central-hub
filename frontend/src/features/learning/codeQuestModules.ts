import type { LearningTrack } from "../../types";

export type CodeQuestModuleId = "python" | "sql" | "case_files";

export type CodeQuestModule = {
  id: CodeQuestModuleId;
  label: string;
  title: string;
  eyebrow: string;
  detail: string;
  path: string;
  scratch?: string;
  defaultTrackId: string;
  language: "python" | "sql" | "mixed";
};

export const CODE_QUEST_MODULES: CodeQuestModule[] = [
  {
    id: "python",
    label: "Python",
    title: "Python Path",
    eyebrow: "Code Quest · Python",
    detail: "Guided path and free-form scripts",
    path: "/learn/python/path",
    scratch: "/learn/python/scratch",
    defaultTrackId: "python_path",
    language: "python",
  },
  {
    id: "sql",
    label: "SQL",
    title: "SQL Path",
    eyebrow: "Code Quest · SQL",
    detail: "Guided queries and a SQLite workspace",
    path: "/learn/sql/path",
    scratch: "/learn/sql/scratch",
    defaultTrackId: "sql_path",
    language: "sql",
  },
];

export const CASE_FILES_PROJECT: CodeQuestModule = {
  id: "case_files",
  label: "Case Files",
  title: "Case Files",
  eyebrow: "Code Quest · Cross-language project",
  detail: "One mystery, solved with SQL records and Python forensics",
  path: "/learn/case-files",
  defaultTrackId: "case_files",
  language: "mixed",
};

export function getCodeQuestModule(id: CodeQuestModuleId): CodeQuestModule {
  return id === "case_files"
    ? CASE_FILES_PROJECT
    : CODE_QUEST_MODULES.find((module) => module.id === id) ?? CODE_QUEST_MODULES[0];
}

function trackLanguage(track: LearningTrack): string {
  if (track.language) return track.language;
  if (track.id === "python" || track.id.startsWith("python_")) return "python";
  if (track.id === "sql" || track.id.startsWith("sql_")) return "sql";
  if (track.id === "case_files") return "mixed";
  return "unknown";
}

export function tracksForModule(tracks: LearningTrack[], id: CodeQuestModuleId): LearningTrack[] {
  const language = getCodeQuestModule(id).language;
  return tracks.filter((track) => trackLanguage(track) === language);
}

export function defaultTrackForModule(tracks: LearningTrack[], id: CodeQuestModuleId): LearningTrack | undefined {
  const module = getCodeQuestModule(id);
  const available = tracksForModule(tracks, id);
  return available.find((track) => track.id === module.defaultTrackId) ?? available[0];
}
