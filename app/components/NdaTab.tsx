'use client';

import type { ReactNode } from 'react';
import { ALLIANCE_COLORS, ALLIANCE_LABELS } from '../lib/election-constants';
import type { PredictionMap } from '../lib/election-utils';
import { fmtInt, signed } from '../lib/format';
import type { Alliance, Candidate, Constituency } from '../types/election';

type ChangeRow = {
  c: Constituency;
  cand?: Candidate;
  votes26: number;
  base: number;
  pct26: number | null;
  pctBase: number | null;
  change: number | null;
};

type NdaTwentyRow = ChangeRow & {
  change2016: number | null;
  change2021: number | null;
};

type NdaAlliedRow = ChangeRow & {
  partyGroup: 'BDJS' | 'TTP';
  winnerAlliance?: Alliance;
  winnerName?: string;
  winnerParty?: string;
  margin?: number;
};

function allianceVotes26(c: Constituency, predictions: PredictionMap) {
  const pred = predictions[String(c.no)];
  const live = pred?.live_votes || {};
  const actual = (a: Alliance) => Number(c.candidates.find((x) => x.alliance === a)?.actual2026 || 0);
  return {
    ldf: Number(live.ldf || actual('ldf')),
    udf: Number(live.udf || actual('udf')),
    nda: Number(live.nda || actual('nda')),
  };
}

function allianceVotesForYear(c: Constituency, year: number) {
  const key = `actual${year}` as keyof Candidate;
  const actual = (a: Alliance) => Number(c.candidates.find((x) => x.alliance === a)?.[key] || 0);
  return {
    ldf: actual('ldf'),
    udf: actual('udf'),
    nda: actual('nda'),
  };
}

function pctValue(part: number, total: number): number | null {
  return total > 0 ? (part / total) * 100 : null;
}

function avg(values: Array<number | null | undefined>): number | null {
  const known = values.filter((v): v is number => v != null && !Number.isNaN(v));
  return known.length ? known.reduce((sum, v) => sum + v, 0) / known.length : null;
}

function deltaColor(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return 'var(--muted)';
  return value >= 0 ? '#16a34a' : '#dc2626';
}

function partyLabel(party?: unknown): 'BDJS' | 'TTP' | 'OTHER' {
  const p = String(party || '').toUpperCase().trim();
  if (p === 'BDJS') return 'BDJS';
  if (p === 'TTP' || p.includes('TWENTY')) return 'TTP';
  return 'OTHER';
}

function SummaryBox({
  value,
  label,
  color,
  small = false,
}: {
  value: ReactNode;
  label: string;
  color: string;
  small?: boolean;
}) {
  return (
    <div className="score-box">
      <div className="score-big" style={{ color, fontSize: small ? 26 : undefined }}>
        {value}
      </div>
      <div className="score-lbl">{label}</div>
    </div>
  );
}

function NdaSummaryCard({
  title,
  controls,
  children,
  note,
}: {
  title: string;
  controls?: ReactNode;
  children: ReactNode;
  note: string;
}) {
  return (
    <div
      className="card"
      style={{
        marginBottom: 14,
        borderColor: `${ALLIANCE_COLORS.nda}44`,
        background: `${ALLIANCE_COLORS.nda}0f`,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          marginBottom: 12,
        }}
      >
        <div className="card-title" style={{ marginBottom: 0 }}>
          {title}
        </div>
        {controls}
      </div>
      <div className="score-grid" style={{ marginBottom: 10, gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
        {children}
      </div>
      <p style={{ fontSize: 11, color: 'var(--muted)', margin: 0 }}>{note}</p>
    </div>
  );
}

function ChangeTable({
  title,
  rows,
  controls,
  onOpenConst,
}: {
  title: string;
  rows: ChangeRow[];
  controls?: React.ReactNode;
  onOpenConst: (no: number) => void;
}) {
  return (
    <div className="card">
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
          marginBottom: 12,
        }}
      >
        <div className="card-title">{title}</div>
        {controls ? <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>{controls}</div> : null}
      </div>
      {rows.length === 0 ? (
        <div className="placeholder" style={{ minHeight: 180, border: '1px dashed var(--border)' }}>
          <h3>No seats in this view</h3>
          <p>Adjust the filters or check that final vote data is loaded.</p>
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="results-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Constituency</th>
                <th>Candidate</th>
                <th style={{ textAlign: 'right' }}>Base votes</th>
                <th style={{ textAlign: 'right' }}>Base %</th>
                <th style={{ textAlign: 'right' }}>2026 votes</th>
                <th style={{ textAlign: 'right' }}>2026 %</th>
                <th style={{ textAlign: 'right' }}>Change</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.c.no} onClick={() => onOpenConst(r.c.no)} style={{ cursor: 'pointer' }}>
                  <td>{r.c.no}</td>
                  <td>
                    {r.c.name}
                    <br />
                    <span style={{ color: 'var(--muted)', fontSize: 10 }}>{r.c.district}</span>
                  </td>
                  <td>
                    {r.cand?.name || '-'}
                    <br />
                    <span style={{ color: 'var(--muted)', fontSize: 10 }}>{r.cand?.party || '-'}</span>
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmtInt(r.base)}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>
                    {r.pctBase == null ? '-' : `${r.pctBase.toFixed(1)}%`}
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>
                    {fmtInt(r.votes26)}
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>
                    {r.pct26 == null ? '-' : `${r.pct26.toFixed(1)}%`}
                  </td>
                  <td
                    style={{
                      textAlign: 'right',
                      fontFamily: 'var(--mono)',
                      color: deltaColor(r.change),
                    }}
                  >
                    {signed(r.change, ' pp')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AlliedGroupSection({
  party,
  fullName,
  rows,
  year,
  onOpenConst,
}: {
  party: 'BDJS' | 'TTP';
  fullName: string;
  rows: NdaAlliedRow[];
  year: number;
  onOpenConst: (no: number) => void;
}) {
  if (!rows.length) return null;

  const sorted = [...rows].sort((a, b) => {
    if (a.change == null && b.change == null) return a.c.no - b.c.no;
    if (a.change == null) return 1;
    if (b.change == null) return -1;
    return a.change - b.change;
  });
  const avgBase = avg(sorted.map((r) => r.pctBase));
  const avg26 = avg(sorted.map((r) => r.pct26));
  const avgChange = avgBase != null && avg26 != null ? avg26 - avgBase : null;
  const ldfWins = sorted.filter((r) => r.winnerAlliance === 'ldf').length;
  const udfWins = sorted.filter((r) => r.winnerAlliance === 'udf').length;
  const ndaWins = sorted.filter((r) => r.winnerAlliance === 'nda').length;

  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <div className="card-title">
        {party} - {fullName} - {rows.length} seats
      </div>
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginBottom: 12, fontSize: 13 }}>
        <div>
          <span style={{ color: 'var(--muted)' }}>Winners: </span>
          <strong style={{ color: ALLIANCE_COLORS.ldf }}>LDF {ldfWins}</strong>
          {'  '}
          <strong style={{ color: ALLIANCE_COLORS.udf }}>UDF {udfWins}</strong>
          {'  '}
          <strong style={{ color: ALLIANCE_COLORS.nda }}>NDA {ndaWins}</strong>
        </div>
        <div>
          <span style={{ color: 'var(--muted)' }}>Avg NDA vote delta: </span>
          <strong style={{ color: deltaColor(avgChange) }}>{signed(avgChange, ' pp')}</strong>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="results-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Constituency</th>
              <th>NDA candidate</th>
              <th style={{ textAlign: 'right' }}>{year} NDA votes</th>
              <th style={{ textAlign: 'right' }}>{year} NDA%</th>
              <th style={{ textAlign: 'right' }}>2026 NDA votes</th>
              <th style={{ textAlign: 'right' }}>2026 NDA%</th>
              <th style={{ textAlign: 'right' }}>Change</th>
              <th>Winner</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => {
              const wa = r.winnerAlliance;
              return (
                <tr key={r.c.no} onClick={() => onOpenConst(r.c.no)} style={{ cursor: 'pointer' }}>
                  <td style={{ fontFamily: 'var(--mono)', color: 'var(--muted)' }}>{r.c.no}</td>
                  <td>
                    {r.c.name}
                    <br />
                    <span style={{ color: 'var(--muted)', fontSize: 10 }}>{r.c.district}</span>
                  </td>
                  <td>
                    {r.cand?.name || '-'}
                    <br />
                    <span style={{ color: 'var(--muted)', fontSize: 10 }}>{r.cand?.party || '-'}</span>
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', color: 'var(--muted)' }}>
                    {fmtInt(r.base)}
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', color: 'var(--muted)' }}>
                    {r.pctBase == null ? '-' : `${r.pctBase.toFixed(1)}%`}
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', color: ALLIANCE_COLORS.nda, fontWeight: 700 }}>
                    {fmtInt(r.votes26)}
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>
                    {r.pct26 == null ? '-' : `${r.pct26.toFixed(1)}%`}
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', color: deltaColor(r.change), fontWeight: 700 }}>
                    {signed(r.change, ' pp')}
                  </td>
                  <td>
                    {wa ? <span className={`tag badge-${wa}`}>{ALLIANCE_LABELS[wa] || wa}</span> : '-'}
                    <span style={{ marginLeft: 6, fontSize: 11 }}>
                      {r.winnerName || ''}
                    </span>
                    {r.margin ? (
                      <span style={{ marginLeft: 6, color: 'var(--muted)', fontFamily: 'var(--mono)', fontSize: 10 }}>
                        +{fmtInt(r.margin)}
                      </span>
                    ) : null}
                  </td>
                </tr>
              );
            })}
            <tr style={{ background: 'var(--surface2)', fontWeight: 700, fontSize: 12 }}>
              <td colSpan={4} style={{ color: 'var(--muted)' }}>
                Average - {sorted.length} seats
              </td>
              <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', color: 'var(--muted)' }}>
                {avgBase == null ? '-' : `${avgBase.toFixed(1)}%`}
              </td>
              <td />
              <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>
                {avg26 == null ? '-' : `${avg26.toFixed(1)}%`}
              </td>
              <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', color: deltaColor(avgChange) }}>
                {signed(avgChange, ' pp')}
              </td>
              <td />
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function NdaTwentyPlusTab({
  constituencies,
  predictions,
  threshold,
  onThreshold,
  onOpenConst,
}: {
  constituencies: Constituency[];
  predictions: PredictionMap;
  threshold: number;
  onThreshold: (v: number) => void;
  onOpenConst: (no: number) => void;
}) {
  const rows: NdaTwentyRow[] = constituencies
    .map((c) => {
      const cand = c.candidates.find((x) => x.alliance === 'nda');
      const votes26 = allianceVotes26(c, predictions);
      const total26 = votes26.ldf + votes26.udf + votes26.nda;
      const pct26 = pctValue(votes26.nda, total26);
      const votes2016 = allianceVotesForYear(c, 2016);
      const total2016 = votes2016.ldf + votes2016.udf + votes2016.nda;
      const pct2016 = pctValue(votes2016.nda, total2016);
      const votes2021 = allianceVotesForYear(c, 2021);
      const total2021 = votes2021.ldf + votes2021.udf + votes2021.nda;
      const pct2021 = pctValue(votes2021.nda, total2021);
      return {
        c,
        cand,
        votes26: votes26.nda,
        base: votes2021.nda,
        pct26,
        pctBase: pct2021,
        change: pct26 != null && pct2021 != null ? pct26 - pct2021 : null,
        change2016: pct26 != null && pct2016 != null ? pct26 - pct2016 : null,
        change2021: pct26 != null && pct2021 != null ? pct26 - pct2021 : null,
      };
    })
    .filter((r) => r.pct26 != null && r.pct26 >= threshold)
    .sort((a, b) => Number(b.pct26 || 0) - Number(a.pct26 || 0));

  const avgNda = avg(rows.map((r) => r.pct26));
  const avgChange2016 = avg(rows.map((r) => r.change2016));
  const avgChange2021 = avg(rows.map((r) => r.change2021));
  const controls = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 280 }}>
      <span style={{ fontSize: 12, color: 'var(--muted)' }}>Threshold</span>
      <input
        type="range"
        min="20"
        max="50"
        step="5"
        value={threshold}
        onChange={(e) => onThreshold(Number(e.target.value))}
        style={{ accentColor: ALLIANCE_COLORS.nda, flex: 1 }}
      />
      <span style={{ fontFamily: 'var(--mono)', color: ALLIANCE_COLORS.nda, fontWeight: 700 }}>
        {threshold}%
      </span>
    </div>
  );

  return (
    <>
      <NdaSummaryCard
        title="NDA vote share seats - 2026 final results"
        controls={controls}
        note="Sorted high to low by 2026 NDA vote share. Percentages use LDF + UDF + NDA alliance totals."
      >
        <SummaryBox value={rows.length} label={`Seats at/above ${threshold}%`} color={ALLIANCE_COLORS.nda} />
        <SummaryBox
          value={avgNda == null ? '-' : `${avgNda.toFixed(1)}%`}
          label="Avg 2026 NDA%"
          color={ALLIANCE_COLORS.nda}
          small
        />
        <SummaryBox value={signed(avgChange2016, ' pp')} label="Avg vs 2016" color={deltaColor(avgChange2016)} small />
        <SummaryBox value={signed(avgChange2021, ' pp')} label="Avg vs 2021" color={deltaColor(avgChange2021)} small />
      </NdaSummaryCard>
      <ChangeTable title={`NDA seats at/above ${threshold}% in 2026`} rows={rows} onOpenConst={onOpenConst} />
    </>
  );
}

export function NdaAlliedTab({
  constituencies,
  predictions,
  year,
  onYear,
  onOpenConst,
}: {
  constituencies: Constituency[];
  predictions: PredictionMap;
  year: number;
  onYear: (year: number) => void;
  onOpenConst: (no: number) => void;
}) {
  const actualKey = `actual${year}` as keyof Candidate;
  const rows: NdaAlliedRow[] = constituencies
    .map((c) => {
      const cand = c.candidates.find((x) => x.alliance === 'nda' && partyLabel(x.party || x.party2021 || x.party2016) !== 'OTHER');
      if (!cand) return null;
      const group = partyLabel(cand.party || cand.party2021 || cand.party2016);
      if (group === 'OTHER') return null;
      const votes26 = allianceVotes26(c, predictions);
      const total26 = votes26.ldf + votes26.udf + votes26.nda;
      const totalBase = c.candidates.reduce((sum, x) => sum + Number(x[actualKey] || 0), 0);
      const base = Number(cand[actualKey] || 0);
      const pred = predictions[String(c.no)];
      const ranked = (['ldf', 'udf', 'nda'] as Array<'ldf' | 'udf' | 'nda'>)
        .map((a) => ({ a, votes: votes26[a] }))
        .sort((a, b) => b.votes - a.votes);
      const winnerAlliance = pred?.called_winner_alliance || pred?.winner_alliance || ranked[0]?.a;
      return {
        c,
        cand,
        partyGroup: group,
        votes26: votes26.nda,
        base,
        pct26: pctValue(votes26.nda, total26),
        pctBase: pctValue(base, totalBase),
        change: totalBase && total26 ? (votes26.nda / total26) * 100 - (base / totalBase) * 100 : null,
        winnerAlliance,
        winnerName: pred?.called_winner_name || pred?.winner_name || '',
        winnerParty: pred?.called_winner_party || pred?.winner_party || '',
        margin: Number(pred?.margin || 0),
      };
    })
    .filter(Boolean) as NdaAlliedRow[];

  const ldfWins = rows.filter((r) => r.winnerAlliance === 'ldf').length;
  const udfWins = rows.filter((r) => r.winnerAlliance === 'udf').length;
  const ndaWins = rows.filter((r) => r.winnerAlliance === 'nda').length;
  const avgBase = avg(rows.map((r) => r.pctBase));
  const avg26 = avg(rows.map((r) => r.pct26));
  const overallChange = avgBase != null && avg26 != null ? avg26 - avgBase : null;
  const bdjsRows = rows.filter((r) => r.partyGroup === 'BDJS');
  const ttpRows = rows.filter((r) => r.partyGroup === 'TTP');
  const controls = (
    <div style={{ display: 'flex', gap: 4 }}>
      <button className={`round-btn ${year === 2016 ? 'active' : ''}`} onClick={() => onYear(2016)} type="button">
        2016
      </button>
      <button className={`round-btn ${year === 2021 ? 'active' : ''}`} onClick={() => onYear(2021)} type="button">
        2021
      </button>
    </div>
  );

  return (
    <>
      <NdaSummaryCard
        title={`NDA allied seats - BDJS (${bdjsRows.length}) + TTP / Twenty20 (${ttpRows.length}) - ${year} vs 2026`}
        controls={controls}
        note={`Final counts from ECI. ${year}% comes from official ${year} results; 2026% comes from final ECI vote totals.`}
      >
        <SummaryBox value={ldfWins} label="LDF won" color={ALLIANCE_COLORS.ldf} />
        <SummaryBox value={udfWins} label="UDF won" color={ALLIANCE_COLORS.udf} />
        <SummaryBox value={ndaWins} label="NDA won" color={ALLIANCE_COLORS.nda} />
        <SummaryBox value={signed(overallChange, ' pp')} label="Avg NDA vote change" color={deltaColor(overallChange)} small />
      </NdaSummaryCard>
      <AlliedGroupSection
        party="BDJS"
        fullName="Bharath Dharma Jana Sena"
        rows={bdjsRows}
        year={year}
        onOpenConst={onOpenConst}
      />
      <AlliedGroupSection
        party="TTP"
        fullName="Twenty20 Party"
        rows={ttpRows}
        year={year}
        onOpenConst={onOpenConst}
      />
    </>
  );
}

export { ChangeTable };
export type { ChangeRow };
