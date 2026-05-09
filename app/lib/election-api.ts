import type {
  Constituency,
  LivePredictionsResponse,
  LocalPrediction,
  RoundLeadsMatrix,
  RoundResults,
  VotePollEntry,
} from '../types/election';

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    cache: 'no-store',
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getConstituencies() {
  return apiJson<Constituency[]>('/api/constituencies');
}

export function getLivePredictions() {
  return apiJson<LivePredictionsResponse>('/api/live_predictions');
}

export function getVotesPolled() {
  return apiJson<Record<string, VotePollEntry>>('/api/votes_polled');
}

export function getRoundResults(no: number) {
  return apiJson<RoundResults>(`/api/round_results/${no}`);
}

export function getRoundLeadsMatrix() {
  return apiJson<RoundLeadsMatrix>('/api/round_leads_matrix');
}

export function postPrediction(payload: {
  const_no: number;
  booths_counted: number;
  total_main_booths?: number;
  total_rounds: number;
  current_round?: number | null;
  votes: number[];
}) {
  return apiJson<LocalPrediction>('/api/predict', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
