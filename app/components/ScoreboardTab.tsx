'use client';

import { ALLIANCE_COLORS, ALLIANCE_LABELS, ALLIANCES } from '../lib/election-constants';
import { displayStatus, normalizePrediction } from '../lib/election-utils';
import type { LiveDataMap, PredictionMap } from '../lib/election-utils';
import { cleanName, fmtInt } from '../lib/format';
import type { Alliance, Constituency } from '../types/election';

export function ScoreboardTab({
  constituencies,
  predictions,
  liveData,
  onOpenConst,
}: {
  constituencies: Constituency[];
  predictions: PredictionMap;
  liveData: LiveDataMap;
  onOpenConst: (no: number) => void;
}) {
  const called = constituencies.filter((c) => {
    const status = displayStatus(
      liveData[c.no],
      normalizePrediction(liveData[c.no]?.prediction || predictions[String(c.no)], c.candidates),
    );
    return status === 'called';
  });
  const counting = constituencies.filter((c) => {
    const status = displayStatus(
      liveData[c.no],
      normalizePrediction(liveData[c.no]?.prediction || predictions[String(c.no)], c.candidates),
    );
    return status === 'counting';
  });
  const pending = constituencies.length - called.length - counting.length;

  const tally = ALLIANCES.reduce(
    (acc, a) => {
      acc[a] = called.filter((c) => {
        const pred = normalizePrediction(
          liveData[c.no]?.prediction || predictions[String(c.no)],
          c.candidates,
        );
        const wa = pred?.called_winner_alliance || pred?.winner_alliance;
        return wa === a;
      }).length;
      return acc;
    },
    {} as Record<Alliance, number>,
  );

  const majPct = ((71 / 140) * 100).toFixed(1);

  return (
    <>
      <div className="score-grid">
        {ALLIANCES.map((a) => (
          <div className="score-box" key={a} style={{ borderColor: `${ALLIANCE_COLORS[a]}44` }}>
            <div className="score-big" style={{ color: ALLIANCE_COLORS[a] }}>{tally[a]}</div>
            <div className="score-lbl">{ALLIANCE_LABELS[a]} seats</div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-title">Alliance tally — majority is 71</div>
        {ALLIANCES.map((a) => (
          <div className="tally-bar-row" key={a}>
            <div className="tally-name" style={{ color: ALLIANCE_COLORS[a] }}>
              {ALLIANCE_LABELS[a]}
            </div>
            <div className="tally-track">
              <div
                className="tally-fill"
                style={{
                  width: `${((tally[a] / 140) * 100).toFixed(1)}%`,
                  background: ALLIANCE_COLORS[a],
                }}
              />
              <div className="majority-line" style={{ left: `${majPct}%` }} />
            </div>
            <div className="tally-num">{tally[a]}</div>
          </div>
        ))}
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8 }}>
          {called.length} of 140 called &nbsp;·&nbsp; {counting.length} counting &nbsp;·&nbsp;{' '}
          {pending} pending
        </div>
      </div>

      {called.length > 0 && (
        <div className="card">
          <div className="card-title">Called results</div>
          <div style={{ overflowX: 'auto' }}>
            <table className="results-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Constituency</th>
                  <th>District</th>
                  <th>Winner</th>
                  <th>Alliance</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {called.map((c) => {
                  const pred = normalizePrediction(
                    liveData[c.no]?.prediction || predictions[String(c.no)],
                    c.candidates,
                  );
                  const wa = (pred?.called_winner_alliance ||
                    pred?.winner_alliance ||
                    'ind') as Alliance;
                  const winnerName =
                    pred?.called_winner_name ||
                    pred?.winner_name ||
                    c.candidates[pred?.winner_idx || 0]?.name ||
                    '-';
                  return (
                    <tr key={c.no} onClick={() => onOpenConst(c.no)} style={{ cursor: 'pointer' }}>
                      <td style={{ fontFamily: 'var(--mono)' }}>{c.no}</td>
                      <td style={{ fontWeight: 500 }}>{c.name}</td>
                      <td style={{ color: 'var(--muted)' }}>{c.district}</td>
                      <td>{cleanName(winnerName)}</td>
                      <td>
                        <span className={`tag badge-${wa}`}>{ALLIANCE_LABELS[wa] || wa}</span>
                      </td>
                      <td style={{ fontFamily: 'var(--mono)' }}>{pred?.confidence ?? '-'}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
