export type Alliance = 'ldf' | 'udf' | 'nda' | 'ind' | 'other';

export type Candidate = {
  name: string;
  party: string;
  alliance: Alliance;
  actual2026?: number;
  actual2021?: number;
  actual2016?: number;
  actual2011?: number;
  actual2019ls?: number;
  actual2024ls?: number;
  [key: string]: unknown;
};

export type Constituency = {
  no: number;
  name: string;
  district: string;
  candidates: Candidate[];
  total_main_booths?: number;
  total_rounds?: number;
  booth_derived_rounds?: number;
  round_results_rounds?: number;
  electorate?: number;
  votes_polled?: number;
  turnout_pct?: number;
  [key: string]: unknown;
};

export type CandidateMapping = {
  eci_name?: string;
  eci_party?: string;
  votes?: number;
  allied_votes?: number;
  allied_names?: string[];
};

export type CallTimelineItem = {
  round: number;
  status: string;
  label: string;
  ready: boolean;
  confidence: number;
  margin: number;
  winner_idx: number;
  pct_counted: number;
};

export type LivePrediction = {
  const_no: number;
  name: string;
  district?: string;
  cur_round?: number;
  tot_rounds?: number;
  live_votes?: Partial<Record<Alliance, number>>;
  projected?: Partial<Record<Alliance, number>> | number[];
  winner_alliance: Alliance;
  winner_name?: string;
  winner_party?: string;
  margin: number;
  confidence: number;
  call_status?: string;
  call_label?: string;
  call_confidence?: string;
  call_ready?: boolean;
  call_reason?: string;
  pct_counted?: number;
  votes_counted?: number;
  votes_polled?: number;
  used_pattern?: boolean;
  used_pdf_pattern?: boolean;
  formula?: Record<string, unknown>;
  shift_patterns?: number[][];
  shift_stability?: Record<string, unknown>;
  call_timeline?: {
    ready_since_round?: number | null;
    timeline?: CallTimelineItem[];
  };
  ready_since_round?: number | null;
  is_called?: boolean;
  called_winner_alliance?: Alliance;
  called_winner_name?: string;
  called_winner_party?: string;
  candidates_mapped?: Partial<Record<Alliance, CandidateMapping>>;
};

export type LivePredictionsResponse = {
  predictions: Record<string, LivePrediction>;
  seat_tally?: Partial<Record<Alliance, number>>;
  called_tally?: Partial<Record<Alliance, number>>;
  called_count?: number;
  generated_at?: string;
};

export type RoundResults = {
  name: string;
  district?: string;
  source?: string;
  fetched_at?: string;
  candidates: string[];
  candidate_parties?: string[];
  candidate_alliances?: Alliance[];
  rounds: Array<{
    round: number;
    increment?: number[];
    incremental?: number[];
    cumulative: number[];
    total?: number;
  }>;
};

export type RoundLeadsMatrix = {
  max_round?: number;
  rounds?: number[];
  rows: Array<{
    const_no: number;
    name: string;
    district?: string;
    rounds: Array<{
      round: number;
      alliance?: Alliance;
      delta_alliance?: Alliance;
      leader_name?: string;
      leader_party?: string;
      delta_leader_name?: string;
      delta_leader_party?: string;
      votes?: number;
      delta_votes?: number;
      carried?: boolean;
    }>;
  }>;
  tally_by_round?: Record<string, Partial<Record<Alliance, number>>>;
  delta_tally_by_round?: Record<string, Partial<Record<Alliance, number>>>;
};

export type VotePollEntry = {
  electorate?: number;
  votes_polled?: number;
  turnout_pct?: number;
};

export type LocalPrediction = LivePrediction & {
  projectedList?: number[];
  total_projected?: number;
  winner_idx?: number;
};

export type LiveState = {
  boothsCounted: number;
  currentRound?: number | null;
  votesCounted?: number;
  votes: number[];
  prediction?: LocalPrediction | null;
  status: 'pending' | 'counting' | 'called';
};

export type ActiveTab =
  | 'entry'
  | 'rounds'
  | 'round_leads'
  | 'scoreboard'
  | 'ldf_insights'
  | 'nda_20plus'
  | 'nda_allied';
