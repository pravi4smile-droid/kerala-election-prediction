import type { Candidate, Constituency, LivePrediction, LiveState, LocalPrediction, RoundResults } from '../types/election';
import { ALLIANCES } from './election-constants';

export type LiveDataMap = Record<number, LiveState>;
export type PredictionMap = Record<string, LivePrediction>;
export type RoundCache = Record<number, RoundResults>;
export type InsightSortKey = 'pct_desc' | 'pct_asc' | 'votes_desc' | 'votes_asc' | 'share_desc' | 'votes_2026_desc' | 'number';

export function normalizePrediction(
  pred?: LivePrediction | LocalPrediction | null,
  candidates?: Candidate[],
): LocalPrediction | null {
  if (!pred) return null;
  const projectedList =
    'projectedList' in pred && pred.projectedList
      ? pred.projectedList
      : Array.isArray(pred.projected)
      ? pred.projected.map((v) => Number(v || 0))
      : ALLIANCES.map((a) => {
          const projectedByAlliance = pred.projected as Partial<Record<typeof a, number>> | undefined;
          return Number(projectedByAlliance?.[a] || 0);
        });
  const winnerIdx =
    'winner_idx' in pred && typeof pred.winner_idx === 'number'
      ? pred.winner_idx
      : Math.max(0, candidates?.findIndex((c) => c.alliance === pred.winner_alliance) ?? 0);
  return {
    ...pred,
    projectedList,
    total_projected: projectedList.reduce((sum, v) => sum + v, 0),
    winner_idx: winnerIdx,
  };
}

export function effectiveTotalRounds(
  c?: Constituency,
  pred?: LivePrediction,
  rounds?: RoundResults,
): number {
  return Math.max(
    Number(c?.total_rounds || 1),
    Number(pred?.tot_rounds || 0),
    Number(c?.round_results_rounds || 0),
    Number(rounds?.rounds?.length || 0),
  );
}

export function boothsAtRound(
  c: Constituency,
  roundNo: number,
  pred?: LivePrediction,
  rounds?: RoundResults,
): number {
  const totalMain = Number(c.total_main_booths || 0);
  const totalRounds = effectiveTotalRounds(c, pred, rounds);
  if (!totalMain || !totalRounds) return roundNo * 14;
  return Math.min(Math.ceil((roundNo * totalMain) / totalRounds), totalMain);
}

export function roundFromBooths(
  c: Constituency,
  counted: number,
  pred?: LivePrediction,
  rounds?: RoundResults,
): number {
  const totalMain = Number(c.total_main_booths || 0);
  const totalRounds = effectiveTotalRounds(c, pred, rounds);
  if (!counted || !totalMain || !totalRounds) return pred?.cur_round || 0;
  return Math.min(
    Math.ceil(counted / Math.max(1, Math.ceil(totalMain / totalRounds))),
    totalRounds,
  );
}

export function displayStatus(
  ld?: LiveState,
  pred?: LivePrediction | LocalPrediction | null,
): string {
  if (ld?.status && ld.status !== 'pending') return ld.status;
  if (!pred) return ld?.status || 'pending';
  const done =
    pred.is_called ||
    pred.call_status === 'called' ||
    Number(pred.pct_counted || 0) >= 100 ||
    Boolean(pred.tot_rounds && pred.cur_round && pred.cur_round >= pred.tot_rounds);
  return done ? 'called' : 'counting';
}
