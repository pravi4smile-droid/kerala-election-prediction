'use client';

import { ALLIANCE_BG, ALLIANCE_COLORS, ALLIANCE_LABELS } from '../lib/election-constants';
import type { InsightSortKey, PredictionMap } from '../lib/election-utils';
import { shortName } from '../lib/format';
import type { Alliance, Candidate, Constituency } from '../types/election';

const YEAR_LABELS: Record<string | number, string> = {
  2021: '2021',
  2016: '2016',
  2011: '2011',
  '2019ls': '2019 LS',
  '2024ls': '2024 LS',
};

const YEARS: Array<{ value: number | string; label: string }> = [
  { value: 2021, label: '2021' },
  { value: 2016, label: '2016' },
  { value: 2011, label: '2011' },
  { value: '2019ls', label: '2019 LS' },
  { value: '2024ls', label: '2024 LS' },
];

function pctOf(part: number, total: number): number | null {
  return total > 0 ? (part / total) * 100 : null;
}
function deltaColor(v: number | null): string {
  return v == null ? 'var(--muted)' : v >= 0 ? '#16a34a' : '#dc2626';
}
function voteDelta(v: number | null): string {
  return v == null ? '-' : `${v >= 0 ? '+' : ''}${Math.round(v).toLocaleString()}`;
}
function pctDelta(v: number | null): string {
  return v == null ? '-' : `${v >= 0 ? '+' : ''}${v.toFixed(1)} pp`;
}

function yearVotes(
  c: Constituency,
  yr: number | string,
): { ldf: number; udf: number; nda: number; total: number } {
  const key = `actual${yr}` as keyof Candidate;
  const ldf = Number(c.candidates.find((x) => x.alliance === 'ldf')?.[key] || 0);
  const udf = Number(c.candidates.find((x) => x.alliance === 'udf')?.[key] || 0);
  const nda = Number(c.candidates.find((x) => x.alliance === 'nda')?.[key] || 0);
  return { ldf, udf, nda, total: ldf + udf + nda };
}

export function InsightsTab(props: {
  constituencies: Constituency[];
  predictions: PredictionMap;
  alliance: Alliance;
  year: number | string;
  sort: InsightSortKey;
  onAlliance: (a: Alliance) => void;
  onYear: (y: number | string) => void;
  onSort: (s: InsightSortKey) => void;
  onOpenConst: (no: number) => void;
}) {
  const a = props.alliance;
  const baseYear = props.year;
  const sortKey = props.sort;
  const allianceColor = ALLIANCE_COLORS[a] || ALLIANCE_COLORS.ldf;
  const allianceBg = ALLIANCE_BG[a] || ALLIANCE_BG.ldf;
  const allianceLabel = ALLIANCE_LABELS[a] || a.toUpperCase();
  const baseYearLabel = YEAR_LABELS[baseYear] || String(baseYear);

  const rows = props.constituencies
    .map((c) => {
      const pred = props.predictions[String(c.no)];
      const get26 = (al: string) =>
        Number(c.candidates.find((x) => x.alliance === al)?.actual2026 ?? 0);
      const votes26 = get26(a);
      const total26 = get26('ldf') + get26('udf') + get26('nda');
      const base = yearVotes(c, baseYear);
      const baseVotes = base[a as 'ldf' | 'udf' | 'nda'];
      const pct26 = pctOf(votes26, total26);
      const pctBase = pctOf(baseVotes, base.total);
      const ranked = (['ldf', 'udf', 'nda'] as Alliance[])
        .map((al) => ({ al, v: get26(al) }))
        .sort((x, y) => y.v - x.v);
      const cand = c.candidates.find((x) => x.alliance === a);
      const basePartyKey = `party${baseYear}` as keyof Candidate;
      return {
        no: c.no,
        name: c.name,
        district: c.district,
        candName: cand?.name || '',
        candParty: cand?.party || '',
        baseParty: String(cand?.[basePartyKey] || '-'),
        votes26,
        votesBase: baseVotes,
        pct26,
        pctBase,
        voteChange: total26 > 0 && base.total > 0 ? votes26 - baseVotes : null,
        pctChange: pct26 != null && pctBase != null ? pct26 - pctBase : null,
        winnerAlliance: (pred?.called_winner_alliance ||
          pred?.winner_alliance ||
          ranked[0]?.al) as Alliance,
        winnerName:
          pred?.called_winner_name ||
          pred?.winner_name ||
          ALLIANCE_LABELS[ranked[0]?.al] ||
          '',
        hasData: total26 > 0 && base.total > 0,
      };
    })
    .filter((r) => r.hasData);

  type Row = typeof rows[0];
  const sorters: Record<string, (x: Row, y: Row) => number> = {
    pct_desc:        (x, y) => (y.pctChange   ?? -999)       - (x.pctChange   ?? -999),
    pct_asc:         (x, y) => (x.pctChange   ?? 999)        - (y.pctChange   ?? 999),
    votes_desc:      (x, y) => (y.voteChange  ?? -999999999) - (x.voteChange  ?? -999999999),
    votes_asc:       (x, y) => (x.voteChange  ?? 999999999)  - (y.voteChange  ?? 999999999),
    share_desc:      (x, y) => (y.pct26       ?? 0)          - (x.pct26       ?? 0),
    votes_2026_desc: (x, y) => y.votes26 - x.votes26,
    number:          (x, y) => x.no - y.no,
  };
  rows.sort(sorters[sortKey] || sorters.pct_desc);

  const maxAbsPct = Math.max(1, ...rows.map((r) => Math.abs(r.pctChange || 0)));
  const totalVoteChange = rows.reduce((s, r) => s + (r.voteChange || 0), 0);
  const avgPctChange = rows.length
    ? rows.reduce((s, r) => s + (r.pctChange ?? 0), 0) / rows.length
    : null;
  const gained = rows.filter((r) => (r.pctChange || 0) > 0).length;
  const lost = rows.filter((r) => (r.pctChange || 0) < 0).length;

  return (
    <>
      <div
        className="card"
        style={{ marginBottom: 14, borderColor: `${allianceColor}44`, background: `${allianceBg}44` }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            marginBottom: 12,
          }}
        >
          <div className="card-title" style={{ marginBottom: 0 }}>
            {allianceLabel} vote change insights — {baseYearLabel} vs 2026
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: 11,
                color: 'var(--muted)',
                fontWeight: 600,
                letterSpacing: '.05em',
                textTransform: 'uppercase',
              }}
            >
              Alliance
            </span>
            {(['ldf', 'udf', 'nda'] as Alliance[]).map((al) => (
              <button
                key={al}
                className={`round-btn ${al === a ? 'active' : ''}`}
                style={
                  al !== a
                    ? { borderColor: ALLIANCE_COLORS[al], color: ALLIANCE_COLORS[al] }
                    : undefined
                }
                onClick={() => props.onAlliance(al)}
                type="button"
              >
                {ALLIANCE_LABELS[al]}
              </button>
            ))}
            <span
              style={{
                fontSize: 11,
                color: 'var(--muted)',
                fontWeight: 600,
                letterSpacing: '.05em',
                textTransform: 'uppercase',
                marginLeft: 4,
              }}
            >
              vs
            </span>
            {YEARS.map((yr) => (
              <button
                key={yr.value}
                className={`round-btn ${baseYear === yr.value ? 'active' : ''}`}
                onClick={() => props.onYear(yr.value)}
                type="button"
              >
                {yr.label}
              </button>
            ))}
            <select
              className="dist-select"
              style={{ width: 'auto', minWidth: 190 }}
              value={sortKey}
              onChange={(e) => props.onSort(e.target.value as InsightSortKey)}
            >
              <option value="pct_desc">Share gain high to low</option>
              <option value="pct_asc">Share loss high to low</option>
              <option value="votes_desc">Vote gain high to low</option>
              <option value="votes_asc">Vote loss high to low</option>
              <option value="share_desc">2026 {allianceLabel}% high to low</option>
              <option value="votes_2026_desc">2026 {allianceLabel} votes high to low</option>
              <option value="number">Constituency number</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 10 }}>
          <div className="score-box">
            <div className="score-big" style={{ color: allianceColor }}>{rows.length}</div>
            <div className="score-lbl">Seats compared</div>
          </div>
          <div className="score-box">
            <div className="score-big" style={{ fontSize: 26, color: deltaColor(avgPctChange) }}>
              {pctDelta(avgPctChange)}
            </div>
            <div className="score-lbl">Avg {allianceLabel} share change</div>
          </div>
          <div className="score-box">
            <div className="score-big" style={{ fontSize: 26, color: deltaColor(totalVoteChange) }}>
              {voteDelta(totalVoteChange)}
            </div>
            <div className="score-lbl">Total {allianceLabel} vote change</div>
          </div>
          <div className="score-box">
            <div className="score-big" style={{ fontSize: 26, color: allianceColor }}>
              {gained} / {lost}
            </div>
            <div className="score-lbl">Share gain / loss seats</div>
          </div>
        </div>

        <p style={{ fontSize: 11, color: 'var(--muted)', margin: 0 }}>
          Vote share uses LDF + UDF + NDA alliance totals for each year. Final 2026 values come
          from ECI round totals.
        </p>
      </div>

      <div className="card">
        <div className="card-title">
          {allianceLabel} — all 140 seats sorted by selected metric
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="results-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Constituency</th>
                <th>{allianceLabel} candidate</th>
                <th style={{ textAlign: 'right' }}>{baseYearLabel} votes</th>
                <th style={{ textAlign: 'right' }}>2026 votes</th>
                <th style={{ textAlign: 'right' }}>Vote change</th>
                <th style={{ minWidth: 190 }}>{allianceLabel} share change</th>
                <th style={{ textAlign: 'right' }}>{baseYearLabel}%</th>
                <th style={{ textAlign: 'right' }}>2026%</th>
                <th>Winner</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const barW = Math.max(4, (Math.abs(r.pctChange || 0) / maxAbsPct) * 100);
                const positive = (r.pctChange || 0) >= 0;
                return (
                  <tr
                    key={r.no}
                    onClick={() => props.onOpenConst(r.no)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td style={{ fontFamily: 'var(--mono)', color: 'var(--muted)' }}>{r.no}</td>
                    <td style={{ fontWeight: 500 }}>
                      {r.name}
                      <br />
                      <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400 }}>
                        {r.district}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, fontWeight: 500 }}>
                      {r.candName}
                      <br />
                      <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400 }}>
                        2026 {r.candParty || '-'} — {baseYearLabel} {r.baseParty}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--mono)', textAlign: 'right', color: 'var(--muted)' }}>
                      {r.votesBase.toLocaleString()}
                    </td>
                    <td
                      style={{
                        fontFamily: 'var(--mono)',
                        textAlign: 'right',
                        fontWeight: 600,
                        color: allianceColor,
                      }}
                    >
                      {r.votes26.toLocaleString()}
                    </td>
                    <td
                      style={{
                        fontFamily: 'var(--mono)',
                        textAlign: 'right',
                        fontWeight: 600,
                        color: deltaColor(r.voteChange),
                      }}
                    >
                      {voteDelta(r.voteChange)}
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap' }}>
                        <div className="bar-track" style={{ height: 12, width: 112, minWidth: 112 }}>
                          <div
                            className="bar-fill"
                            style={{
                              width: `${barW.toFixed(1)}%`,
                              background: positive ? '#16a34a' : '#dc2626',
                            }}
                          />
                        </div>
                        <span
                          style={{
                            fontFamily: 'var(--mono)',
                            fontWeight: 600,
                            color: deltaColor(r.pctChange),
                            minWidth: 52,
                            textAlign: 'right',
                          }}
                        >
                          {pctDelta(r.pctChange)}
                        </span>
                      </div>
                    </td>
                    <td style={{ fontFamily: 'var(--mono)', textAlign: 'right', color: 'var(--muted)' }}>
                      {r.pctBase != null ? `${r.pctBase.toFixed(1)}%` : '-'}
                    </td>
                    <td style={{ fontFamily: 'var(--mono)', textAlign: 'right', fontWeight: 600 }}>
                      {r.pct26 != null ? `${r.pct26.toFixed(1)}%` : '-'}
                    </td>
                    <td>
                      <span className={`tag badge-${r.winnerAlliance}`}>
                        {ALLIANCE_LABELS[r.winnerAlliance] || r.winnerAlliance}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
