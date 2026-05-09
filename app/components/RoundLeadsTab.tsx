'use client';

import { useEffect } from 'react';
import { DashboardStatus } from './DashboardStatus';
import { ALLIANCE_COLORS, ALLIANCE_LABELS, ALLIANCES } from '../lib/election-constants';
import { fmtInt } from '../lib/format';
import type { Alliance, RoundLeadsMatrix } from '../types/election';

export function RoundLeadsTab({
  data,
  mode,
  onLoad,
  onMode,
  onOpenConst,
}: {
  data: RoundLeadsMatrix | null;
  mode: 'cumulative' | 'round';
  onLoad: () => Promise<void>;
  onMode: (mode: 'cumulative' | 'round') => void;
  onOpenConst: (no: number) => void;
}) {
  useEffect(() => { void onLoad(); }, [onLoad]);

  if (!data) return <DashboardStatus message="Loading round leads..." />;

  const rounds = data.rounds?.length
    ? data.rounds
    : Array.from({ length: Number(data.max_round || 0) }, (_, i) => i + 1);
  const tallyByRound = mode === 'round' ? data.delta_tally_by_round : data.tally_by_round;
  const maxRound = rounds[rounds.length - 1] || 1;
  const lastTally = tallyByRound?.[String(maxRound)] || {};
  const isCumul = mode === 'cumulative';

  const counted =
    Number(lastTally.ldf || 0) + Number(lastTally.udf || 0) + Number(lastTally.nda || 0);
  const otherCount = isCumul ? Math.max(0, 140 - counted) : Number(lastTally.other || 0);

  const chartW = 760;
  const chartH = 240;
  const pad = { l: 42, r: 18, t: 16, b: 32 };
  const innerW = chartW - pad.l - pad.r;
  const innerH = chartH - pad.t - pad.b;
  const yMax = 140;
  const xFor = (r: number) => pad.l + ((r - 1) / Math.max(maxRound - 1, 1)) * innerW;
  const yFor = (v: number) => pad.t + innerH - (v / yMax) * innerH;

  return (
    <div className="card">
      <div className="card-title">Round-by-round leading alliance</div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span
          style={{
            fontSize: 11,
            color: 'var(--muted)',
            fontWeight: 600,
            letterSpacing: '.05em',
            textTransform: 'uppercase',
          }}
        >
          View
        </span>
        <button
          className={`round-btn ${isCumul ? 'active' : ''}`}
          onClick={() => onMode('cumulative')}
          type="button"
        >
          Cumulative
        </button>
        <button
          className={`round-btn ${!isCumul ? 'active' : ''}`}
          onClick={() => onMode('round')}
          type="button"
        >
          Round Only
        </button>
        <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 6 }}>
          {isCumul
            ? 'Seats leading after each cumulative round (carries forward when constituency finishes)'
            : 'Seats leading in each individual round only — matrix empty once constituency completes'}
        </span>
      </div>

      <div className="lead-chart-wrap">
        <svg
          className="lead-chart"
          viewBox={`0 0 ${chartW} ${chartH}`}
          preserveAspectRatio="none"
        >
          {[0, 35, 70, 105, 140].map((yv) => {
            const y = yFor(yv);
            return (
              <g key={yv}>
                <line className="lead-chart-grid" x1={pad.l} y1={y} x2={chartW - pad.r} y2={y} />
                <text x="8" y={y + 3}>{yv}</text>
              </g>
            );
          })}
          {rounds
            .filter((r) => r === 1 || r === maxRound || r % 2 === 0)
            .map((r) => (
              <text key={r} x={xFor(r) - 8} y={chartH - 10}>
                R{r}
              </text>
            ))}
          {ALLIANCES.map((a) => {
            const points = rounds
              .map((r) => {
                const v = Number(tallyByRound?.[String(r)]?.[a] || 0);
                return `${xFor(r).toFixed(1)},${yFor(v).toFixed(1)}`;
              })
              .join(' ');
            return (
              <g key={a}>
                <polyline className="lead-chart-line" stroke={ALLIANCE_COLORS[a]} points={points} />
                {rounds.map((r) => {
                  const v = Number(tallyByRound?.[String(r)]?.[a] || 0);
                  return (
                    <circle
                      key={r}
                      className="lead-chart-point"
                      cx={xFor(r)}
                      cy={yFor(v)}
                      r="3"
                      fill={ALLIANCE_COLORS[a]}
                    >
                      <title>
                        R{r} {ALLIANCE_LABELS[a]}: {v}
                      </title>
                    </circle>
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="lead-summary">
        {ALLIANCES.map((a) => (
          <span className="score-chip" key={a}>
            <span className="dot" style={{ background: ALLIANCE_COLORS[a] }} />
            <span>{ALLIANCE_LABELS[a]}</span>
            <span className="num">{Number(lastTally[a] || 0)}</span>
          </span>
        ))}
        {otherCount > 0 && (
          <span className="score-chip">
            <span className="dot" style={{ background: ALLIANCE_COLORS.ind }} />
            <span>IND</span>
            <span className="num">{otherCount}</span>
          </span>
        )}
        <span style={{ fontSize: 11, color: 'var(--muted)', alignSelf: 'center', marginLeft: 4 }}>
          {isCumul
            ? `= ${counted + otherCount} seats at R${maxRound}`
            : `= ${counted + otherCount} constituencies active at R${maxRound}`}
        </span>
      </div>

      <div className="lead-matrix-wrap">
        <table className="lead-matrix">
          <thead>
            <tr>
              <th className="const-head">Constituency</th>
              {rounds.map((r) => <th key={r}>R{r}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.const_no}>
                <td className="const-cell" onClick={() => onOpenConst(row.const_no)}>
                  <span style={{ fontFamily: 'var(--mono)', color: 'var(--muted)' }}>
                    {row.const_no.toString().padStart(3, '0')}
                  </span>{' '}
                  {row.name}
                  <span className="lead-district">{row.district}</span>
                </td>
                {rounds.map((round) => {
                  const item = row.rounds.find((r) => r.round === round);
                  if (!item || item.carried) return <td key={round} className="lead-cell empty" />;
                  const displayAlliance = isCumul
                    ? item.alliance
                    : item.delta_alliance || item.alliance;
                  const displayName = isCumul
                    ? item.leader_name
                    : item.delta_leader_name || item.leader_name;
                  const displayParty = isCumul
                    ? item.leader_party
                    : item.delta_leader_party || item.leader_party;
                  const displayVotes = isCumul ? item.votes : (item.delta_votes ?? item.votes);
                  const a = (['ldf', 'udf', 'nda'] as Alliance[]).includes(
                    displayAlliance as Alliance,
                  )
                    ? (displayAlliance as Alliance)
                    : ('other' as Alliance);
                  const modeLabel = isCumul ? 'cumulative lead' : 'round votes lead';
                  return (
                    <td
                      key={round}
                      className={`lead-cell ${a}`}
                      title={`${row.name} R${round} ${modeLabel}: ${displayName || '-'} (${displayParty || ''}) ${fmtInt(displayVotes)}`}
                    >
                      {ALLIANCE_LABELS[a] || 'IND'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
