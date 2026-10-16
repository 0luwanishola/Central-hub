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

export type NewsItem = {
  id: string;
  title: string;
  url: string;
  source: string;
  publishedAt: string;
};

export type NewsResponse = {
  items: NewsItem[];
  fetchedAt: string;
  stale: boolean;
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
