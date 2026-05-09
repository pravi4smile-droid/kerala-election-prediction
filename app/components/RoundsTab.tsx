'use client';

import { useEffect, useState } from 'react';
import { DashboardStatus } from './DashboardStatus';
import { ALLIANCE_COLORS, ALLIANCES } from '../lib/election-constants';
import { fmtInt, shortName } from '../lib/format';
import type { Alliance, Constituency, RoundResults } from '../types/election';

type HistoricalRound = {
  share_2026?: Partial<Record<Alliance, number>>;
  share_2021?: Partial<Record<Alliance, number>>;
  delta?: Partial<Record<Alliance, number>>;
};

function HistoricalShareCells({ round }: { round: HistoricalRound }) {
  return (
    <>
      {ALLIANCES.map((alliance, idx) => {
        const current = round.share_2026?.[alliance];
        const previous = round.share_2021?.[alliance];
        const delta = round.delta?.[alliance];
        return (
          <td
            key={alliance}
            style={{
              borderLeft: idx === 0 ? '2px solid var(--border)' : undefined,
              fontSize: 12,
              whiteSpace: 'nowrap',
            }}
          >
            <span style={{ fontWeight: 600 }}>{current ?? '-'}%</span>
            <span style={{ color: 'var(--muted)' }}> / {previous ?? '-'}%</span>
            {delta != null ? (
              <span
                style={{
                  color: delta > 0 ? '#16a34a' : delta < 0 ? '#dc2626' : 'var(--muted)',
                  fontWeight: 600,
                }}
              >
                {' '}
                {delta >= 0 ? '+' : ''}
                {delta}
              </span>
            ) : null}
          </td>
        );
      })}
    </>
  );
}

export function RoundsTab({
  constituency,
  cached,
  onLoad,
}: {
  constituency: Constituency;
  cached?: RoundResults;
  onLoad: () => Promise<RoundResults>;
}) {
  const [data, setData] = useState<RoundResults | undefined>(cached);
  const [loading, setLoading] = useState(!cached);

  useEffect(() => {
    if (cached) {
      setData(cached);
      setLoading(false);
      return;
    }
    let cancelled = false;
    onLoad()
      .then((rows) => { if (!cancelled) setData(rows); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [cached, onLoad]);

  if (loading) return <DashboardStatus message="Loading round data..." />;
  if (!data) return <div className="card">No round data available.</div>;

  const candidates = data.candidates || [];
  const parties = data.candidate_parties || [];
  const candidateAlliances = data.candidate_alliances || [];
  const rounds = data.rounds || [];
  const roundIncrement = (round: RoundResults['rounds'][number]) =>
    round.incremental || round.increment || [];
  const totals = rounds[rounds.length - 1]?.cumulative || [];
  const palette = [
    '#1a4d8c', '#0f766e', '#9a3412', '#7c3aed',
    '#2d6a4f', '#b45309', '#be123c', '#1d4ed8', '#991b1b', '#6d28d9',
  ];
  const colorFor = (idx: number) => {
    const alliance = candidateAlliances[idx];
    if (alliance && alliance in ALLIANCE_COLORS) return ALLIANCE_COLORS[alliance];
    return palette[idx % palette.length];
  };
  const colors = candidates.map((_, idx) => colorFor(idx));
  const maxRoundTotal = Math.max(
    ...rounds.map((r) => roundIncrement(r).reduce((sum, v) => sum + Number(v || 0), 0)),
    1,
  );
  const sortedIdx = totals.map((v, i) => ({ v, i })).sort((a, b) => b.v - a.v).map((x) => x.i);
  const showIdx = sortedIdx.slice(0, 4);
  const hasOthers = candidates.length > showIdx.length;
  const hasHistoricalShares = rounds.some((r) => 'share_2021' in r);

  const cumulativeRows = (() => {
    const acc = new Array<number>(candidates.length).fill(0);
    return rounds.map((round) => {
      roundIncrement(round).forEach((value, idx) => {
        acc[idx] = Number(acc[idx] || 0) + Number(value || 0);
      });
      return acc.slice();
    });
  })();

  return (
    <>
      <div className="card">
        <div className="card-title">{constituency.name} — Round-wise ECI vote data</div>
        <p style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 12 }}>
          {rounds.length} rounds · {candidates.length} candidates · Source:{' '}
          {data.source || 'results.eci.gov.in'} ·{' '}
          {data.fetched_at ? new Date(data.fetched_at).toLocaleString() : 'cached'}
        </p>

        <div className="round-legend">
          {candidates.map((name, idx) => (
            <span className="round-legend-item" key={`${name}-${idx}`}>
              <span className="round-legend-dot" style={{ background: colors[idx] }} />
              <span>{shortName(name)}</span>
              <span style={{ color: 'var(--muted)', fontSize: 11 }}>{parties[idx] || ''}</span>
            </span>
          ))}
        </div>

        <div className="round-chart-wrap">
          <div className="round-chart">
            {rounds.map((round) => {
              const inc = roundIncrement(round);
              const total = inc.reduce((sum, v) => sum + Number(v || 0), 0);
              const barHeight = Math.round((total / maxRoundTotal) * 76);
              return (
                <div
                  className="round-col"
                  key={round.round}
                  title={`R${round.round}: ${fmtInt(total)} votes`}
                >
                  {inc.map((value, idx) => {
                    const segH = total > 0 ? Math.round((Number(value || 0) / total) * barHeight) : 0;
                    return segH > 0 ? (
                      <div
                        key={idx}
                        className="round-bar-seg"
                        style={{ height: segH, background: colors[idx] }}
                      />
                    ) : null;
                  })}
                  <span className="round-col-lbl">R{round.round}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="round-table">
            <thead>
              <tr>
                <th>Round</th>
                {showIdx.map((idx) => (
                  <th key={idx} style={{ color: colors[idx] }}>
                    {shortName(candidates[idx])}
                    <br />
                    <span style={{ fontWeight: 400, color: 'var(--muted)', fontSize: 10 }}>
                      {parties[idx] || ''}
                    </span>
                  </th>
                ))}
                {hasOthers ? <th>Others</th> : null}
                <th>Round total</th>
                <th>Leader (cumul.)</th>
                {hasHistoricalShares ? (
                  <>
                    <th style={{ color: 'var(--ldf)', borderLeft: '2px solid var(--border)' }}>
                      LDF
                      <br />
                      <span style={{ fontWeight: 400, color: 'var(--muted)', fontSize: 10 }}>
                        26% / 21% / delta
                      </span>
                    </th>
                    <th style={{ color: 'var(--udf)' }}>
                      UDF
                      <br />
                      <span style={{ fontWeight: 400, color: 'var(--muted)', fontSize: 10 }}>
                        26% / 21% / delta
                      </span>
                    </th>
                    <th style={{ color: 'var(--nda)' }}>
                      NDA
                      <br />
                      <span style={{ fontWeight: 400, color: 'var(--muted)', fontSize: 10 }}>
                        26% / 21% / delta
                      </span>
                    </th>
                  </>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {rounds.map((round, roundIdx) => {
                const inc = roundIncrement(round);
                const cumulative = cumulativeRows[roundIdx];
                const leaders = cumulative.map((v, i) => ({ v, i })).sort((a, b) => b.v - a.v);
                const lead = leaders[0];
                const margin = Number(leaders[0]?.v || 0) - Number(leaders[1]?.v || 0);
                const roundTotal = inc.reduce((sum, v) => sum + Number(v || 0), 0);
                const others = sortedIdx
                  .slice(showIdx.length)
                  .reduce((sum, idx) => sum + Number(inc[idx] || 0), 0);
                return (
                  <tr key={round.round}>
                    <td style={{ color: 'var(--muted)' }}>R{round.round}</td>
                    {showIdx.map((idx) => (
                      <td
                        key={idx}
                        style={
                          lead?.i === idx ? { fontWeight: 600, color: colors[idx] } : undefined
                        }
                      >
                        {Number(inc[idx] || 0) ? fmtInt(inc[idx]) : '-'}
                      </td>
                    ))}
                    {hasOthers ? (
                      <td style={{ color: 'var(--muted)' }}>{others ? fmtInt(others) : '-'}</td>
                    ) : null}
                    <td style={{ fontWeight: 500 }}>{roundTotal ? fmtInt(roundTotal) : '-'}</td>
                    <td style={{ color: colors[lead?.i || 0], fontWeight: 500 }}>
                      {shortName(candidates[lead?.i || 0], 1)} +{fmtInt(margin)}
                    </td>
                    {hasHistoricalShares ? (
                      <HistoricalShareCells round={round as unknown as HistoricalRound} />
                    ) : null}
                  </tr>
                );
              })}
              <tr style={{ background: 'var(--surface2)', fontWeight: 600 }}>
                <td>Total</td>
                {showIdx.map((idx) => <td key={idx}>{fmtInt(totals[idx])}</td>)}
                {hasOthers ? (
                  <td>
                    {fmtInt(
                      sortedIdx
                        .slice(showIdx.length)
                        .reduce((sum, idx) => sum + Number(totals[idx] || 0), 0),
                    )}
                  </td>
                ) : null}
                <td>{fmtInt(totals.reduce((sum, v) => sum + Number(v || 0), 0))}</td>
                <td />
                {hasHistoricalShares ? (
                  <HistoricalShareCells
                    round={rounds[rounds.length - 1] as unknown as HistoricalRound}
                  />
                ) : null}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
