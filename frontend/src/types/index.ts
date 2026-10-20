export type Tool = {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  ready: boolean;
  requires?: string;
  execution: "client" | "api" | "unavailable";
};

export type LearningTrackId = string;
export type LearningTrackKind = "legacy" | "path";
export type LearningDifficulty = "beginner" | "intermediate" | "advanced";

export type LearningDataset = {
  name: string;
  columns: string[];
  rows: string[][];
};

export type LearningCodingExercise = {
  language: "python" | "sql";
  task: string;
  starter_code: string;
  hints: string[];
  plan?: string[];
  success: string;
};

export type LearningDataSource = {
  name: string;
  variable?: string;
  column?: string;
  limit?: number;
};

export type LearningChallenge = {
  id: string;
  phase_id?: string;
  title: string;
  topic: string;
  difficulty: LearningDifficulty;
  xp: number;
  runner?: string;
  mode?: string;
  business_question?: string;
  concept?: string;
  concept_example?: string;
  predict?: LearningPredictDrill;
  metric_contract?: string;
  documentation_url?: string;
  data_sources?: LearningDataSource[];
  dataset?: { id: string; name: string };
  capstone?: boolean;
  capstone_rubric?: string[];
  datasets?: LearningDataset[];
  coding: LearningCodingExercise;
};

export type LearningPhase = {
  id: string;
  name: string;
  arc: string;
  summary: string;
};

export type LearningTrack = {
  id: LearningTrackId;
  kind?: LearningTrackKind;
  curriculum_id?: string;
  name: string;
  summary: string;
  language?: string;
  phases?: LearningPhase[];
  challenges: LearningChallenge[];
};

export type LearningProgress = Partial<Record<LearningTrackId, number[]>>;

export type LearningDatasetTable = {
  name: string;
  description: string;
  grain: string;
  columns: string[];
  types: Record<string, string>;
  keys: { primary: string[]; foreign: string[] };
};

export type LearningRelationship = {
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  cardinality: string;
};

export type LearningDatasetMetadata = {
  id: string;
  name: string;
  summary: string;
  tables: LearningDatasetTable[];
  relationships: LearningRelationship[];
};

export type LearningSession = {
  learner_id: string;
  xp: number;
  progress: LearningProgress;
  tracks: LearningTrack[];
  datasets: LearningDatasetMetadata[];
};

export type LearningReviewItem = {
  track: LearningTrackId;
  track_name: string;
  challenge_id: string;
  level: number;
  title: string;
  topic: string;
  phase_name: string;
  language: "python" | "sql";
  reason: "hint" | "revisit";
};

export type LearningReviewSet = {
  items: LearningReviewItem[];
  completed: number;
};

export type LearningPredictDrill = {
  prompt: string;
  code: string;
  options: string[];
  answer: number;
  why: string;
};

export type LearningAnswer = {
  correct: boolean;
  awarded_xp: number;
  xp: number;
  progress: LearningProgress;
  hint?: string;
  explanation?: string;
};

export type LearningCodeResult = {
  correct: boolean;
  awarded_xp: number;
  xp: number;
  progress: LearningProgress;
  output: string;
  feedback: string;
  sql_columns?: string[];
  sql_rows?: (string | number | null)[][];
  error_line?: number;
  error_column?: number;
  preview?: boolean;
  mastery_badge_awarded?: boolean;
  coaching?: string[];
};

export type ScratchPythonLimits = {
  timeout_seconds: number;
  max_source_characters: number;
  max_stdout_characters: number;
  max_stderr_characters: number;
  max_files: number;
  max_file_bytes: number;
  max_total_file_bytes: number;
};

export type ScratchPythonFile = {
  name: string;
  content: string;
  truncated: boolean;
  size_bytes?: number;
};

export type ScratchSkippedFile = {
  name: string;
  reason: string;
};

export type ScratchPythonResult = {
  run_id: string;
  status: "completed" | "timeout" | "error";
  stdout: string;
  stderr: string;
  error: string | null;
  error_line: number | null;
  error_kind: "syntax" | "runtime" | "sandbox" | "request" | "timeout" | null;
  duration_ms: number;
  timed_out: boolean;
  truncated: boolean;
  files: ScratchPythonFile[];
  skipped_files: ScratchSkippedFile[];
  limits: ScratchPythonLimits;
};

export type ScratchSqlLimits = {
  max_source_characters: number;
  max_statements: number;
  max_rows_per_statement: number;
  max_cell_characters: number;
  max_response_bytes: number;
  time_cap_ms: number;
  step_cap: number;
  workspace_max_bytes: number;
  workspaces_per_learner: number;
  idle_ttl_seconds: number;
};

export type ScratchSqlWorkspace = {
  workspace_id: string;
  base: string;
  base_name: string;
  expires_in_seconds: number;
  idle_ttl_seconds: number;
  limits: ScratchSqlLimits;
};

export type ScratchSqlStatement = {
  index: number;
  kind: string;
  columns: string[];
  rows: (string | number | null)[][];
  affected_rows: number;
  truncated: boolean;
};

export type ScratchSqlRunResult = {
  workspace_id: string;
  status: "completed" | "timeout" | "error";
  duration_ms: number;
  statements: ScratchSqlStatement[];
  summary: {
    statements: number;
    rows: number;
    affected_rows: number;
    truncated: boolean;
  };
  error: string | null;
  error_statement: number | null;
  error_kind: string | null;
  truncated: boolean;
  workspace: ScratchSqlWorkspace;
};

export type LearningSolution = {
  explanation: string;
  code: string;
  language: "python" | "sql";
  concept?: string;
  capstone_rubric?: string[];
};

export type MatchSide = {
  id?: string | number | null;
  name: string;
  logo?: string | null;
  score?: number | string | null;
};

export type Fixture = {
  id: string;
  kickoff?: string | null;
  venue?: string | null;
  round?: string | null;
  league: string;
  league_logo?: string | null;
  group?: string;
  status_short?: string | null;
  status_long?: string | null;
  elapsed?: number | string | null;
  home: MatchSide;
  away: MatchSide;
  events?: MatchEvent[];
  lineups?: Lineup[];
};

export type MatchEvent = {
  minute?: number | string | null;
  kind: string;
  side?: "home" | "away" | null;
  player?: string | null;
  player_in?: string | null;
  player_out?: string | null;
  assist?: string | null;
  note?: string | null;
  card?: string | null;
};

export type Lineup = {
  team: string;
  logo?: string | null;
  formation?: string | null;
  starters?: { name: string; number?: number | string | null }[];
  bench?: { name: string; number?: number | string | null }[];
};

export type PdfDownload = {
  download_url: string;
  filename: string;
  expires_in_seconds: number;
};

export type PdfSignPreview = {
  token: string;
  page: number;
  pages: number;
  image: string;
  widthPt: number;
  heightPt: number;
};
