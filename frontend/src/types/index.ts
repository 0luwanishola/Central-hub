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

export type LearningTrackId = "python" | "sql";
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

export type LearningChallenge = {
  title: string;
  topic: string;
  difficulty: LearningDifficulty;
  xp: number;
  datasets?: LearningDataset[];
  coding: LearningCodingExercise;
};

export type LearningTrack = {
  id: LearningTrackId;
  name: string;
  summary: string;
  challenges: LearningChallenge[];
};

export type LearningProgress = {
  python: number[];
  sql: number[];
};

export type LearningSession = {
  learner_id: string;
  xp: number;
  progress: LearningProgress;
  tracks: LearningTrack[];
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
