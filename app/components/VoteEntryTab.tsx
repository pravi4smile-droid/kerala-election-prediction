'use client';

import { ALLIANCE_BG, ALLIANCE_COLORS, ALLIANCE_LABELS, ALLIANCES } from '../lib/election-constants';
import { effectiveTotalRounds, roundFromBooths } from '../lib/election-utils';
import { fmtInt, pct, shortName, signed } from '../lib/format';
import type {
  Candidate,
  Constituency,
  LiveState,
  LocalPrediction,
  RoundResults,
  VotePollEntry,
} from '../types/election';

export function VoteEntryTab(props: {
  constituency: Constituency;
  live: LiveState;
  prediction: LocalPrediction | null;
  votePoll?: VotePollEntry;
  roundResults?: RoundResults;
  onSetRound: (round: number) => void;
  onPredict: () => void;
  onVoteChange: (index: number, value: number) => void;
  onMarkCalled: () => void;
  onReset: () => void;
}) {
  const c = props.constituency;
  const live = props.live || { votes: [0, 0, 0], boothsCounted: 0, status: 'pending' };
  const totalRounds = effectiveTotalRounds(c, props.prediction || undefined, props.roundResults);
  const curRound =
    live.currentRound ||
    props.prediction?.cur_round ||
    roundFromBooths(c, live.boothsCounted, props.prediction || undefined, props.roundResults);
  const votePolled = Number(
    props.votePoll?.votes_polled || props.prediction?.votes_polled || c.votes_polled || 0,
  );
  const votesCounted = Number(
    live.votesCounted || props.prediction?.votes_counted || live.votes.reduce((sum, v) => sum + v, 0),
  );
  const boothPct = Number(c.total_main_booths || 0)
    ? Math.round((live.boothsCounted / Number(c.total_main_booths)) * 100)
    : 0;
  const votePct = votePolled ? Math.min(Math.round((votesCounted / votePolled) * 100), 100) : boothPct;
  const totalVotes = live.votes.reduce((sum, v) => sum + v, 0);

  return (
    <>
      <EntryHeader c={c} votePoll={props.votePoll} totalRounds={totalRounds} />

      <div className="card">
        <div className="card-title">Votes per candidate (running total)</div>
        <div className="round-nav-panel">
          <div className="round-status-line">
            <span>
              Round <strong>{curRound || '-'}</strong> of <strong>{totalRounds}</strong>
            </span>
            <span>
              {fmtInt(live.boothsCounted)} / {fmtInt(Number(c.total_main_booths || 0))} booths -{' '}
              <strong>{boothPct}%</strong>
            </span>
            <span className="vote-count-line">
              {fmtInt(votesCounted)} / {fmtInt(votePolled)} votes - <strong>{votePct}%</strong>
            </span>
          </div>
          <div className="round-btns">
            {Array.from({ length: totalRounds }, (_, i) => i + 1).map((round) => (
              <button
                key={round}
                className={`round-btn ${round === curRound ? 'active' : ''}`}
                onClick={() => props.onSetRound(round)}
                type="button"
              >
                R{round}
              </button>
            ))}
          </div>
          <div className="progress-strip">
            <div className="progress-done" style={{ flex: votePct }} />
            <div className="progress-pending" style={{ flex: Math.max(0, 100 - votePct) }} />
          </div>
        </div>

        {c.candidates.map((cand, idx) => {
          const value = live.votes[idx] || 0;
          return (
            <div className="cand-row" key={`${cand.name}-${idx}`}>
              <div className="alliance-stripe" style={{ background: ALLIANCE_COLORS[cand.alliance] }} />
              <div className="cand-info">
                <div className="cand-nm">{cand.name}</div>
                <div className="cand-party">
                  {cand.party} -{' '}
                  <span className={`tag badge-${cand.alliance}`}>{ALLIANCE_LABELS[cand.alliance]}</span>
                </div>
              </div>
              <input
                className="cand-votes-inp"
                type="number"
                min="0"
                value={value || ''}
                placeholder="0"
                aria-label={`${cand.name} vote count`}
                onChange={(e) => props.onVoteChange(idx, Number(e.target.value || 0))}
              />
              <div className="cand-pct">
                {totalVotes ? `${Math.round((value / totalVotes) * 100)}%` : ''}
              </div>
            </div>
          );
        })}
      </div>

      <div className="action-row">
        <button className="btn btn-primary" onClick={props.onPredict} type="button">
          Predict winner -&gt;
        </button>
        <button className="btn btn-success" onClick={props.onMarkCalled} type="button">
          Mark as called
        </button>
        <button className="btn btn-danger" onClick={props.onReset} type="button">
          Reset
        </button>
      </div>

      {props.prediction && (
        <PredictionCard
          constituency={c}
          prediction={props.prediction}
          liveVotes={live.votes}
        />
      )}
    </>
  );
}

function EntryHeader({
  c,
  votePoll,
  totalRounds,
}: {
  c: Constituency;
  votePoll?: VotePollEntry;
  totalRounds: number;
}) {
  const boothDerived = Number(
    c.booth_derived_rounds || Math.ceil(Number(c.total_main_booths || 0) / 14),
  );
  const extraRounds = Math.max(totalRounds - boothDerived, 0);
  return (
    <div className="entry-header">
      <h2>{c.name}</h2>
      <div className="entry-meta">
        <span>{c.district}</span>
        <span>
          {fmtInt(Number(c.total_main_booths || 0))} main booths - {totalRounds} rounds
          {extraRounds ? ` (${boothDerived} booth-derived + ${extraRounds} ECI)` : ''}
        </span>
        {votePoll?.electorate ? (
          <span>
            Electorate: {fmtInt(votePoll.electorate)} - Turnout: {votePoll.turnout_pct}% - Polled:{' '}
            {fmtInt(votePoll.votes_polled)}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function PredictionCard({
  constituency,
  prediction,
  liveVotes,
}: {
  constituency: Constituency;
  prediction: LocalPrediction;
  liveVotes: number[];
}) {
  const winner =
    constituency.candidates[prediction.winner_idx || 0] || constituency.candidates[0];
  const wa = prediction.winner_alliance || winner.alliance;
  const projected =
    prediction.projectedList ||
    (Array.isArray(prediction.projected)
      ? prediction.projected.map((v) => Number(v || 0))
      : ALLIANCES.map((a) => {
          const projectedByAlliance = prediction.projected as Partial<Record<typeof a, number>> | undefined;
          return Number(projectedByAlliance?.[a] || 0);
        }));
  const totalProjected = projected.reduce((sum, v) => sum + v, 0);
  const sorted = projected.map((v, i) => ({ v, i })).sort((a, b) => b.v - a.v);
  const max = Math.max(...projected, 1);
  const isFinalCount =
    (prediction as { formula?: { projection_method?: string } }).formula?.projection_method ===
    'final_count';
  const marginLabel = isFinalCount ? 'Margin' : 'Projected margin';
  const confR = 24;
  const confCirc = 2 * Math.PI * confR;
  const confDash = ((prediction.confidence || 0) / 100) * confCirc;

  return (
    <div className="pred-card">
      <div className="pred-banner" style={{ background: ALLIANCE_BG[wa] }}>
        <div className="conf-circle">
          <svg width="56" height="56" viewBox="0 0 56 56">
            <circle
              cx="28" cy="28" r={confR} fill="none"
              stroke={`${ALLIANCE_COLORS[wa]}22`} strokeWidth="5"
            />
            <circle
              cx="28" cy="28" r={confR} fill="none"
              stroke={ALLIANCE_COLORS[wa]} strokeWidth="5"
              strokeDasharray={`${confDash.toFixed(1)} ${confCirc.toFixed(1)}`}
              strokeLinecap="round"
            />
          </svg>
          <div className="conf-val" style={{ color: ALLIANCE_COLORS[wa] }}>
            {prediction.confidence}%
          </div>
        </div>
        <div>
          <div className="pred-winner-name" style={{ color: ALLIANCE_COLORS[wa] }}>
            {prediction.winner_name || winner.name}
          </div>
          <div className="pred-meta">
            {prediction.winner_party || winner.party} -{' '}
            <span className={`tag badge-${wa}`}>{ALLIANCE_LABELS[wa]}</span>
          </div>
          <div className="pred-margin" style={{ color: ALLIANCE_COLORS[wa] }}>
            {marginLabel}: <strong>{fmtInt(prediction.margin)}</strong> votes
          </div>
          <div className="pred-meta">
            {prediction.pct_counted || 0}% votes counted
            {prediction.votes_polled
              ? ` (${fmtInt(prediction.votes_counted)} / ${fmtInt(prediction.votes_polled)})`
              : ''}
          </div>
          <div
            className={`call-indicator ${
              prediction.call_status === 'called'
                ? 'call-called'
                : prediction.call_status === 'ready_to_call'
                ? 'call-ready'
                : prediction.call_status === 'too_early'
                ? 'call-early'
                : prediction.call_status === 'too_close'
                ? 'call-close'
                : prediction.call_ready
                ? 'call-ready'
                : 'call-watch'
            }`}
          >
            {prediction.call_label || 'Watching Trend'}{' '}
            <span>
              {prediction.call_confidence || 'Medium'}
              {prediction.call_reason ? ` - ${prediction.call_reason}` : ''}
            </span>
          </div>
        </div>
      </div>

      <div className="prediction-insights">
        <SwingStability prediction={prediction} />
        <CallTimeline prediction={prediction} />
      </div>

      <div className="pred-bars">
        {sorted.map(({ v, i }) => {
          const cand = constituency.candidates[i];
          return (
            <div className="bar-item" key={`${cand?.name}-${i}`}>
              <div className="bar-labels">
                <span
                  className="bar-name"
                  style={{ color: ALLIANCE_COLORS[cand?.alliance || 'ind'] }}
                >
                  {i === prediction.winner_idx ? '* ' : ''}
                  {cand?.name}{' '}
                  <span style={{ fontWeight: 400, color: 'var(--muted)', fontSize: 11 }}>
                    {cand?.party}
                  </span>
                </span>
                <span className="bar-votes">
                  {fmtInt(v)} - {pct(v, totalProjected)}
                </span>
              </div>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{
                    width: `${(v / max) * 100}%`,
                    background: ALLIANCE_COLORS[cand?.alliance || 'ind'],
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <ReferenceRows cands={constituency.candidates} />
      <HowCalculated
        cands={constituency.candidates}
        prediction={prediction}
        liveVotes={liveVotes}
        projected={projected}
      />
    </div>
  );
}

function SwingStability({ prediction }: { prediction: LocalPrediction }) {
  const patterns = prediction.shift_patterns || [];
  if (patterns.length < 2) {
    return (
      <div className="insight-panel">
        <div className="insight-title">
          Swing Stability <strong>Not enough rounds</strong>
        </div>
      </div>
    );
  }

  const series = ALLIANCES.map((a, idx) => ({
    a,
    values: patterns.map((row) => Number(row?.[idx])).filter((v) => Number.isFinite(v)),
  })).filter((s) => s.values.length >= 2);

  const stability = prediction.shift_stability as
    | { stable_all?: boolean; stable_recent?: boolean }
    | undefined;
  const stableText = stability?.stable_all
    ? 'All-round pattern intact'
    : stability?.stable_recent
    ? 'Recent rounds stable'
    : 'Pattern still moving';

  const w = 300, h = 72, left = 8, right = 8, top = 7, bottom = 14;
  const allValues = series.flatMap((s) => s.values);
  const minV = Math.min(-5, ...allValues);
  const maxV = Math.max(5, ...allValues);
  const pad = Math.max(2, (maxV - minV) * 0.12);
  const lo = minV - pad;
  const hi = maxV + pad;
  const len = series[0]?.values.length || 1;
  const xFor = (i: number) =>
    left + (len <= 1 ? 0 : (i * (w - left - right)) / (len - 1));
  const yFor = (v: number) => top + ((hi - v) / (hi - lo || 1)) * (h - top - bottom);
  const zeroY = yFor(0);

  return (
    <div className="insight-panel">
      <div className="insight-title">
        Swing Stability <strong>{stableText}</strong>
      </div>
      <svg className="swing-chart" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        <line
          className="swing-axis"
          x1={left} y1={zeroY.toFixed(1)}
          x2={w - right} y2={zeroY.toFixed(1)}
        />
        {series.map((s) => {
          const points = s.values
            .map((v, i) => `${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}`)
            .join(' ');
          return (
            <g key={s.a}>
              <polyline className="swing-line" stroke={ALLIANCE_COLORS[s.a]} points={points} />
              {s.values.map((v, i) => {
                if (i !== 0 && i !== s.values.length - 1) return null;
                return (
                  <circle
                    key={i}
                    className="swing-point"
                    cx={xFor(i).toFixed(1)}
                    cy={yFor(v).toFixed(1)}
                    r="3"
                    fill={ALLIANCE_COLORS[s.a]}
                  >
                    <title>
                      R{i + 1} {ALLIANCE_LABELS[s.a]} {v >= 0 ? '+' : ''}
                      {v.toFixed(1)}pp
                    </title>
                  </circle>
                );
              })}
            </g>
          );
        })}
      </svg>
      <div className="swing-legend">
        {series.map((s) => {
          const v = s.values[s.values.length - 1];
          return (
            <span key={s.a}>
              <span className="dot" style={{ background: ALLIANCE_COLORS[s.a] }} />
              {ALLIANCE_LABELS[s.a]} {signed(Number(v || 0), 'pp')}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function CallTimeline({ prediction }: { prediction: LocalPrediction }) {
  const timeline = prediction.call_timeline?.timeline || [];
  const readySince = prediction.ready_since_round;
  const currentRound = timeline[timeline.length - 1]?.round;
  const note = readySince
    ? `First ready at R${readySince}; current R${currentRound}`
    : timeline.length
    ? `Not ready before R${currentRound}`
    : 'Timeline unavailable';
  return (
    <div className="insight-panel">
      <div className="insight-title">
        Call Readiness{' '}
        <strong>{readySince ? `Ready since R${readySince}` : 'Not crossed'}</strong>
      </div>
      <div className="call-timeline">
        {timeline.map((item) => (
          <span
            key={item.round}
            className={`call-step${item.ready ? ' ready' : ''}${item.status === 'called' ? ' called' : ''}${item.round === currentRound ? ' current' : ''}`}
            title={`R${item.round}: ${item.label}, margin ${fmtInt(item.margin)}`}
          />
        ))}
      </div>
      <div className="call-timeline-note">{note}</div>
    </div>
  );
}

function ReferenceRows({ cands }: { cands: Candidate[] }) {
  const refs: [string, string, string][] = [
    ['2011', 'actual2011', 'party2011'],
    ['2016', 'actual2016', 'party2016'],
    ['2019 LS', 'actual2019ls', 'party2019ls'],
    ['2021', 'actual2021', 'party2021'],
    ['2024 LS', 'actual2024ls', 'party2024ls'],
  ];
  return (
    <>
      {refs.map(([label, valueKey, partyKey]) => {
        const rows = cands.filter((c) => Number(c[valueKey] || 0) > 0);
        if (!rows.length) return null;
        return (
          <div className="actual-row" key={label}>
            <span className="lbl">{label} ref:</span>
            {rows.map((cand) => (
              <span key={`${label}-${cand.name}`} style={{ color: ALLIANCE_COLORS[cand.alliance] }}>
                {String(cand[partyKey] || cand.party)}{' '}
                <strong>{fmtInt(Number(cand[valueKey] || 0))}</strong>
              </span>
            ))}
          </div>
        );
      })}
    </>
  );
}

function numericArray(value: unknown): number[] {
  return Array.isArray(value) ? value.map((v) => Number(v || 0)) : [];
}

function numberOrDash(value: unknown, suffix = '') {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-';
  return `${value}${suffix}`;
}

function deltaColor(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return 'var(--muted)';
  return value >= 0 ? '#16a34a' : '#dc2626';
}

function HowCalculated({
  cands,
  prediction,
  liveVotes,
  projected,
}: {
  cands: Candidate[];
  prediction: LocalPrediction;
  liveVotes: number[];
  projected: number[];
}) {
  const votesCounted = Number(prediction.votes_counted || 0);
  const votesPolled = Number(prediction.votes_polled || 0);
  const formula = (prediction.formula || {}) as Record<string, unknown>;
  if (!votesCounted || !votesPolled) return null;

  const method = String(formula.projection_method || '');
  const usedPattern = Boolean(prediction.used_pattern || prediction.used_pdf_pattern || formula.share_2021_early);
  const label =
    method === 'final_count'
      ? 'final counted result'
      : usedPattern
      ? 'historical booth pattern'
      : 'linear - no historical booth data';

  return (
    <details className="how-calc">
      <summary>
        <span aria-hidden="true">▸</span>
        How calculated ({label})
      </summary>
      <div className="how-calc-body">
        {method === 'final_count' ? (
          <FinalCountCalc cands={cands} projected={projected} />
        ) : usedPattern ? (
          <PatternCalc
            cands={cands}
            prediction={prediction}
            liveVotes={liveVotes}
            projected={projected}
            formula={formula}
          />
        ) : (
          <LinearCalc
            cands={cands}
            liveVotes={liveVotes}
            projected={projected}
            votesCounted={votesCounted}
            votesPolled={votesPolled}
          />
        )}
      </div>
    </details>
  );
}

function FinalCountCalc({ cands, projected }: { cands: Candidate[]; projected: number[] }) {
  return (
    <>
      <div className="calc-steps">
        <strong>Counting complete</strong>
        <br />
        The result is using counted ECI totals directly. No historical pattern or linear scaling is applied.
      </div>
      <table className="calc-table">
        <thead>
          <tr>
            <th>Candidate</th>
            <th>Counted total</th>
          </tr>
        </thead>
        <tbody>
          {cands.map((cand, i) => (
            <tr key={cand.name}>
              <td style={{ color: ALLIANCE_COLORS[cand.alliance] }}>{shortName(cand.name)}</td>
              <td>{fmtInt(projected[i] || 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function PatternCalc({
  cands,
  prediction,
  liveVotes,
  projected,
  formula,
}: {
  cands: Candidate[];
  prediction: LocalPrediction;
  liveVotes: number[];
  projected: number[];
  formula: Record<string, unknown>;
}) {
  const votesCounted = Number(prediction.votes_counted || 0);
  const votesPolled = Number(prediction.votes_polled || 0);
  const pctExact = votesPolled ? ((votesCounted / votesPolled) * 100).toFixed(2) : '0.00';
  const remaining = Math.max(0, votesPolled - votesCounted);
  const years = Array.isArray(formula.history_years) ? formula.history_years.map(String) : ['2021'];
  const weights = formula.history_weights as Record<string, unknown> | undefined;
  const weightLabel =
    weights && years.length
      ? `; weights ${years.map((y) => `${y}:${weights[y] ?? 1}`).join(', ')}`
      : '';
  const primaryYear = years.includes('2021') ? '2021' : years[years.length - 1] || '2021';
  const patternLabel = years.length > 1 ? `${years.join('/')} average` : `${years[0]} pattern`;
  const earlyShare = numericArray(formula.share_2021_early);
  const share2026 = numericArray(formula.share_2026);
  const delta = numericArray(formula.delta);
  const remainingShare = numericArray(formula.share_remaining_2021);
  const adjusted = numericArray(formula.adj_remaining);
  const fromRemaining = numericArray(formula.proj_from_remaining);

  return (
    <>
      <div className="calc-steps">
        <strong>Step 1 - % counted</strong>
        <br />
        {fmtInt(votesCounted)} / {fmtInt(votesPolled)} = <strong>{pctExact}%</strong>
        {'  '}Remaining: <strong>{fmtInt(remaining)} votes</strong>
        {'  '}Trend weight: <strong>{String(formula.trend_weight ?? formula.damp ?? '-')}</strong>
        <span className="muted"> ({String(formula.trend_weight_rule || 'R1=0.90, R2=0.95, R3+=1.00')})</span>
        <br />
        <strong>Step 2 - historical booths at same {pctExact}% point</strong>
        <br />
        Using {patternLabel}; reference volume shown from {primaryYear}:{' '}
        {fmtInt(Number(formula.total_2021_early || 0))} early votes of{' '}
        {fmtInt(Number(formula.total_2021_all || 0))} total - weighted early shares per candidate
        {weightLabel}
        <br />
        <strong>Step 3 - Swing</strong> = 2026 share - historical early average
        <br />
        <strong>Step 4 - historical remaining average</strong> from booths not yet counted at same point
        <br />
        <strong>Step 5 - Adjusted remaining share</strong> = historical remaining average + swing x trend weight
        <br />
        <strong>Step 6 - Projected remaining</strong> = adjusted share x {fmtInt(remaining)}
        <br />
        <strong>Step 7 - Final</strong> = actual counted + projected remaining
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="calc-table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Counted</th>
              <th>Hist early%</th>
              <th>2026 share%</th>
              <th>Swing</th>
              <th>Hist rem%</th>
              <th>Adj rem%</th>
              <th>Proj. remaining</th>
              <th>Final</th>
            </tr>
          </thead>
          <tbody>
            {cands.map((cand, i) => (
              <tr key={cand.name}>
                <td style={{ color: ALLIANCE_COLORS[cand.alliance] }}>{shortName(cand.name)}</td>
                <td>{fmtInt(liveVotes[i] || 0)}</td>
                <td className="muted-cell">{numberOrDash(earlyShare[i], '%')}</td>
                <td>{numberOrDash(share2026[i], '%')}</td>
                <td style={{ color: deltaColor(delta[i]) }}>{signed(delta[i], 'pp')}</td>
                <td className="muted-cell">{numberOrDash(remainingShare[i], '%')}</td>
                <td className="muted-cell">{numberOrDash(adjusted[i], '%')}</td>
                <td className="muted-cell">{fmtInt(fromRemaining[i] ?? Math.max(0, (projected[i] || 0) - (liveVotes[i] || 0)))}</td>
                <td style={{ color: ALLIANCE_COLORS[cand.alliance], fontWeight: 700 }}>{fmtInt(projected[i] || 0)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td>Total</td>
              <td>{fmtInt(votesCounted)}</td>
              <td colSpan={5} />
              <td>{fmtInt(remaining)}</td>
              <td>{fmtInt(votesPolled)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}

function LinearCalc({
  cands,
  liveVotes,
  projected,
  votesCounted,
  votesPolled,
}: {
  cands: Candidate[];
  liveVotes: number[];
  projected: number[];
  votesCounted: number;
  votesPolled: number;
}) {
  const multiplier = votesCounted ? votesPolled / votesCounted : 0;
  return (
    <>
      <div className="calc-steps">
        <strong>No historical booth data</strong> for this constituency - using linear scale.
        <br />
        Scale factor = {fmtInt(votesPolled)} / {fmtInt(votesCounted)} ={' '}
        <strong>{multiplier.toFixed(4)}x</strong> (assumes each candidate&apos;s current share holds for
        all remaining votes)
      </div>
      <table className="calc-table">
        <thead>
          <tr>
            <th>Candidate</th>
            <th>Counted</th>
            <th>x factor</th>
            <th>Projected</th>
          </tr>
        </thead>
        <tbody>
          {cands.map((cand, i) => (
            <tr key={cand.name}>
              <td style={{ color: ALLIANCE_COLORS[cand.alliance] }}>{shortName(cand.name)}</td>
              <td>{fmtInt(liveVotes[i] || 0)}</td>
              <td className="muted-cell">x {multiplier.toFixed(4)}</td>
              <td style={{ color: ALLIANCE_COLORS[cand.alliance], fontWeight: 700 }}>{fmtInt(projected[i] || 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
