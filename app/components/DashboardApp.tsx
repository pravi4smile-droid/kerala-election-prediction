'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { DashboardStatus } from './DashboardStatus';
import { InsightsTab } from './InsightsTab';
import { NdaAlliedTab, NdaTwentyPlusTab } from './NdaTab';
import { RoundLeadsTab } from './RoundLeadsTab';
import { RoundsTab } from './RoundsTab';
import { ScoreboardTab } from './ScoreboardTab';
import { VoteEntryTab } from './VoteEntryTab';
import {
  getConstituencies,
  getLivePredictions,
  getRoundLeadsMatrix,
  getRoundResults,
  getVotesPolled,
  postPrediction,
} from '../lib/election-api';
import { ALLIANCE_COLORS, ALLIANCE_LABELS, ALLIANCES } from '../lib/election-constants';
import {
  boothsAtRound,
  displayStatus,
  effectiveTotalRounds,
  normalizePrediction,
  roundFromBooths,
} from '../lib/election-utils';
import type {
  InsightSortKey,
  LiveDataMap,
  PredictionMap,
  RoundCache,
} from '../lib/election-utils';
import type {
  ActiveTab,
  Alliance,
  Constituency,
  LivePrediction,
  LivePredictionsResponse,
  LocalPrediction,
  RoundLeadsMatrix,
  RoundResults,
  VotePollEntry,
} from '../types/election';

export function DashboardApp() {
  const [constituencies, setConstituencies] = useState<Constituency[]>([]);
  const [predictions, setPredictions] = useState<PredictionMap>({});
  const [predictionMeta, setPredictionMeta] = useState<LivePredictionsResponse>({ predictions: {} });
  const [votesPolled, setVotesPolled] = useState<Record<string, VotePollEntry>>({});
  const [liveData, setLiveData] = useState<LiveDataMap>({});
  const [roundCache, setRoundCache] = useState<RoundCache>({});
  const [roundLeads, setRoundLeads] = useState<RoundLeadsMatrix | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('entry');
  const [districtFilter, setDistrictFilter] = useState('');
  const [searchFilter, setSearchFilter] = useState('');
  const [ndaThreshold, setNdaThreshold] = useState(20);
  const [insightAlliance, setInsightAlliance] = useState<Alliance>('ldf');
  const [insightYear, setInsightYear] = useState<number | string>(2021);
  const [insightSort, setInsightSort] = useState<InsightSortKey>('pct_desc');
  const [ndaAlliedYear, setNdaAlliedYear] = useState(2021);
  const [roundLeadsMode, setRoundLeadsMode] = useState<'cumulative' | 'round'>('cumulative');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [constituencyRows, predRows, voteRows] = await Promise.all([
          getConstituencies(),
          getLivePredictions(),
          getVotesPolled().catch(() => ({})),
        ]);
        setConstituencies(constituencyRows);
        setPredictions(predRows.predictions || {});
        setPredictionMeta(predRows);
        setVotesPolled(voteRows);
        const nextLive: LiveDataMap = {};
        constituencyRows.forEach((c) => {
          const pred = predRows.predictions?.[String(c.no)];
          nextLive[c.no] = {
            boothsCounted: pred?.cur_round ? boothsAtRound(c, pred.cur_round, pred) : 0,
            currentRound: pred?.cur_round || null,
            votesCounted: pred?.votes_counted || 0,
            votes: ALLIANCES.map((a) => Number(pred?.live_votes?.[a] || 0)),
            prediction: normalizePrediction(pred, c.candidates),
            status: displayStatus(undefined, pred) as LiveDataMap[number]['status'],
          };
        });
        setLiveData(nextLive);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load election data');
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  const constMap = useMemo(
    () => Object.fromEntries(constituencies.map((c) => [c.no, c])),
    [constituencies],
  );
  const selectedConst = selected ? constMap[selected] : undefined;
  const selectedPred = selected ? predictions[String(selected)] : undefined;

  const ensureRoundResults = useCallback(
    async (no: number) => {
      if (roundCache[no]) return roundCache[no];
      const rows = await getRoundResults(no);
      setRoundCache((prev) => ({ ...prev, [no]: rows }));
      return rows;
    },
    [roundCache],
  );

  const setRound = useCallback(
    async (no: number, round: number) => {
      const c = constMap[no];
      if (!c) return;
      const rd = await ensureRoundResults(no);
      const roundEntry = rd.rounds.find((r) => r.round === round) || rd.rounds[round - 1];
      if (!roundEntry) return;
      const cumulative = roundEntry.cumulative || [];
      const roundVotesCounted = cumulative.reduce((sum, value) => sum + Number(value || 0), 0);
      const pred = predictions[String(no)];
      const mapping = pred?.candidates_mapped || {};
      const normalizedNames = rd.candidates.map((name) =>
        name.toLowerCase().replace(/[.\s]/g, ''),
      );
      const findIndex = (name?: string) => {
        const target = (name || '').toLowerCase().replace(/[.\s]/g, '');
        if (!target) return -1;
        let idx = normalizedNames.findIndex((n) => n === target);
        if (idx >= 0) return idx;
        idx = normalizedNames.findIndex((n) => n.includes(target) || target.includes(n));
        return idx;
      };
      const votes = ALLIANCES.map((alliance) => {
        const primaryIdx = findIndex(mapping[alliance]?.eci_name);
        let total = primaryIdx >= 0 ? Number(roundEntry.cumulative[primaryIdx] || 0) : 0;
        (mapping[alliance]?.allied_names || []).forEach((name) => {
          const alliedIdx = findIndex(name);
          if (alliedIdx >= 0) total += Number(roundEntry.cumulative[alliedIdx] || 0);
        });
        return total;
      });
      setLiveData((prev) => ({
        ...prev,
        [no]: {
          ...(prev[no] || { votes: [0, 0, 0], status: 'pending', boothsCounted: 0 }),
          votes,
          votesCounted: roundVotesCounted,
          currentRound: round,
          boothsCounted: boothsAtRound(c, round, pred, rd),
          status: 'counting',
        },
      }));
    },
    [constMap, ensureRoundResults, predictions],
  );

  const runPredict = useCallback(
    async (no: number) => {
      const c = constMap[no];
      const ld = liveData[no];
      if (!c || !ld) return;
      const pred = await postPrediction({
        const_no: no,
        booths_counted: ld.boothsCounted || 14,
        total_main_booths: c.total_main_booths,
        total_rounds: effectiveTotalRounds(c, predictions[String(no)], roundCache[no]),
        current_round: ld.currentRound || null,
        votes: ld.votes,
      });
      setLiveData((prev) => ({
        ...prev,
        [no]: {
          ...prev[no],
          prediction: normalizePrediction(pred, c.candidates),
          votesCounted: pred.votes_counted || ld.votes.reduce((sum, value) => sum + value, 0),
          status: 'counting',
        },
      }));
    },
    [constMap, liveData, predictions, roundCache],
  );

  const updateVote = useCallback((no: number, index: number, value: number) => {
    setLiveData((prev) => {
      const current = prev[no];
      if (!current) return prev;
      const votes = [...current.votes];
      votes[index] = value;
      return { ...prev, [no]: { ...current, votes, status: 'counting' } };
    });
  }, []);

  const markCalled = useCallback((no: number) => {
    setLiveData((prev) => {
      const current = prev[no];
      if (!current) return prev;
      return { ...prev, [no]: { ...current, status: 'called' } };
    });
  }, []);

  const resetConst = useCallback(
    (no: number) => {
      const c = constMap[no];
      if (!c) return;
      setLiveData((prev) => ({
        ...prev,
        [no]: {
          boothsCounted: 0,
          currentRound: null,
          votesCounted: 0,
          votes: new Array(c.candidates.length).fill(0),
          prediction: null,
          status: 'pending',
        },
      }));
    },
    [constMap],
  );

  const loadRoundLeads = useCallback(async () => {
    if (roundLeads) return;
    setRoundLeads(await getRoundLeadsMatrix());
  }, [roundLeads]);

  if (error) return <DashboardStatus tone="error" message={error} />;
  if (loading) return <DashboardStatus message="Loading election dashboard..." />;

  return (
    <div className="shell">
      <Sidebar
        constituencies={constituencies}
        liveData={liveData}
        predictions={predictions}
        selected={selected}
        districtFilter={districtFilter}
        searchFilter={searchFilter}
        onDistrictFilter={setDistrictFilter}
        onSearchFilter={setSearchFilter}
        onSelect={setSelected}
      />
      <div className="main">
        <Topbar meta={predictionMeta} />
        <TabBar activeTab={activeTab} onTab={setActiveTab} />
        <main className="content">
          <Content
            activeTab={activeTab}
            selected={selected}
            selectedConst={selectedConst}
            selectedPred={selectedPred}
            liveData={liveData}
            votesPolled={votesPolled}
            roundCache={roundCache}
            roundLeads={roundLeads}
            constituencies={constituencies}
            predictions={predictions}
            ndaThreshold={ndaThreshold}
            insightAlliance={insightAlliance}
            insightYear={insightYear}
            insightSort={insightSort}
            ndaAlliedYear={ndaAlliedYear}
            roundLeadsMode={roundLeadsMode}
            onSetRound={setRound}
            onPredict={runPredict}
            onVoteChange={updateVote}
            onMarkCalled={markCalled}
            onReset={resetConst}
            onLoadRounds={ensureRoundResults}
            onLoadRoundLeads={loadRoundLeads}
            onOpenConst={setSelected}
            onNdaThreshold={setNdaThreshold}
            onInsightAlliance={setInsightAlliance}
            onInsightYear={setInsightYear}
            onInsightSort={setInsightSort}
            onNdaAlliedYear={setNdaAlliedYear}
            onRoundLeadsMode={setRoundLeadsMode}
          />
        </main>
      </div>
    </div>
  );
}

// ── Sidebar ──────────────────────────────────────────────────────────────────

function Sidebar(props: {
  constituencies: Constituency[];
  liveData: LiveDataMap;
  predictions: PredictionMap;
  selected: number | null;
  districtFilter: string;
  searchFilter: string;
  onDistrictFilter: (value: string) => void;
  onSearchFilter: (value: string) => void;
  onSelect: (no: number) => void;
}) {
  const districts = [...new Set(props.constituencies.map((c) => c.district))];
  const q = props.searchFilter.toLowerCase();
  const filtered = props.constituencies.filter((c) => {
    if (props.districtFilter && c.district !== props.districtFilter) return false;
    if (q && !c.name.toLowerCase().includes(q) && !String(c.no).includes(q)) return false;
    return true;
  });

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <select
          className="dist-select"
          aria-label="Filter by district"
          value={props.districtFilter}
          onChange={(e) => props.onDistrictFilter(e.target.value)}
        >
          <option value="">All 14 districts</option>
          {districts.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <input
          className="search-box"
          placeholder="Search constituency..."
          aria-label="Search constituency"
          value={props.searchFilter}
          onChange={(e) => props.onSearchFilter(e.target.value)}
        />
      </div>
      <div className="con-list">
        {filtered.map((c) => {
          const pred = normalizePrediction(
            props.liveData[c.no]?.prediction || props.predictions[String(c.no)],
            c.candidates,
          );
          const status = displayStatus(props.liveData[c.no], pred);
          const wa = pred?.winner_alliance || 'ind';
          const badgeCls =
            status === 'called'
              ? `badge-${wa}`
              : pred?.call_ready
              ? 'badge-ready'
              : status === 'counting'
              ? 'badge-counting'
              : 'badge-pending';
          const badgeText =
            status === 'called'
              ? ALLIANCE_LABELS[wa]
              : pred?.call_ready
              ? 'ready'
              : status === 'counting'
              ? 'partial'
              : 'pending';
          return (
            <button
              key={c.no}
              className={`con-item ${status === 'called' ? `called-${wa}` : ''} ${
                props.selected === c.no ? 'active' : ''
              }`}
              onClick={() => props.onSelect(c.no)}
              type="button"
            >
              <span className="con-no">{c.no}</span>
              <span className="con-name">{c.name}</span>
              <span className={`con-badge ${badgeCls}`}>{badgeText}</span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}

// ── Topbar ───────────────────────────────────────────────────────────────────

function Topbar({ meta }: { meta: LivePredictionsResponse }) {
  const tally = meta.called_tally || meta.seat_tally || {};
  return (
    <header className="topbar">
      <div className="topbar-title">Kerala Election Live Predictor 2026</div>
      <div className="live-badge">
        <span className="live-dot" />
        Results
      </div>
      <div className="scoreboard-mini">
        {ALLIANCES.map((a) => (
          <span className="score-chip" key={a}>
            <span className="dot" style={{ background: ALLIANCE_COLORS[a] }} />
            <span style={{ color: ALLIANCE_COLORS[a], fontWeight: 600 }}>{ALLIANCE_LABELS[a]}</span>
            <span className="num">{Number(tally[a] || 0)}</span>
          </span>
        ))}
      </div>
    </header>
  );
}

// ── TabBar ───────────────────────────────────────────────────────────────────

const TABS: Array<{ id: ActiveTab; label: string }> = [
  { id: 'entry',       label: 'Vote entry' },
  { id: 'rounds',      label: 'Rounds' },
  { id: 'round_leads', label: 'Round leads' },
  { id: 'scoreboard',  label: 'Scoreboard' },
  { id: 'ldf_insights',label: 'Insights' },
  { id: 'nda_20plus',  label: 'NDA 20%+' },
  { id: 'nda_allied',  label: 'NDA Allied (BDJS/TTP)' },
];

function TabBar({
  activeTab,
  onTab,
}: {
  activeTab: ActiveTab;
  onTab: (tab: ActiveTab) => void;
}) {
  return (
    <div
      style={{
        padding: '0 20px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <div className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab ${activeTab === tab.id ? 'active' : ''}`}
            aria-current={activeTab === tab.id ? 'page' : undefined}
            onClick={() => onTab(tab.id)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Placeholder ───────────────────────────────────────────────────────────────

function Placeholder() {
  return (
    <div className="placeholder">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <rect x="8" y="12" width="32" height="24" rx="3" stroke="#a89e94" strokeWidth="2" />
        <path d="M16 22h16M16 28h10" stroke="#a89e94" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <h3>Select a constituency</h3>
      <p>
        Choose any of the 140 Kerala assembly constituencies from the left panel to begin entering
        vote counts.
      </p>
    </div>
  );
}

// ── Content router ────────────────────────────────────────────────────────────

type ContentProps = {
  activeTab: ActiveTab;
  selected: number | null;
  selectedConst?: Constituency;
  selectedPred?: LivePrediction;
  liveData: LiveDataMap;
  votesPolled: Record<string, VotePollEntry>;
  roundCache: RoundCache;
  roundLeads: RoundLeadsMatrix | null;
  constituencies: Constituency[];
  predictions: PredictionMap;
  ndaThreshold: number;
  insightAlliance: Alliance;
  insightYear: number | string;
  insightSort: InsightSortKey;
  ndaAlliedYear: number;
  roundLeadsMode: 'cumulative' | 'round';
  onSetRound: (no: number, round: number) => void;
  onPredict: (no: number) => void;
  onVoteChange: (no: number, index: number, value: number) => void;
  onMarkCalled: (no: number) => void;
  onReset: (no: number) => void;
  onLoadRounds: (no: number) => Promise<RoundResults>;
  onLoadRoundLeads: () => Promise<void>;
  onOpenConst: (no: number) => void;
  onNdaThreshold: (value: number) => void;
  onInsightAlliance: (value: Alliance) => void;
  onInsightYear: (value: number | string) => void;
  onInsightSort: (value: InsightSortKey) => void;
  onNdaAlliedYear: (value: number) => void;
  onRoundLeadsMode: (value: 'cumulative' | 'round') => void;
};

function Content(props: ContentProps) {
  if (props.activeTab === 'scoreboard') {
    return (
      <ScoreboardTab
        constituencies={props.constituencies}
        predictions={props.predictions}
        liveData={props.liveData}
        onOpenConst={props.onOpenConst}
      />
    );
  }

  if (props.activeTab === 'round_leads') {
    return (
      <RoundLeadsTab
        data={props.roundLeads}
        mode={props.roundLeadsMode}
        onLoad={props.onLoadRoundLeads}
        onMode={props.onRoundLeadsMode}
        onOpenConst={props.onOpenConst}
      />
    );
  }

  if (props.activeTab === 'ldf_insights') {
    return (
      <InsightsTab
        constituencies={props.constituencies}
        predictions={props.predictions}
        alliance={props.insightAlliance}
        year={props.insightYear}
        sort={props.insightSort}
        onAlliance={props.onInsightAlliance}
        onYear={props.onInsightYear}
        onSort={props.onInsightSort}
        onOpenConst={props.onOpenConst}
      />
    );
  }

  if (props.activeTab === 'nda_20plus') {
    return (
      <NdaTwentyPlusTab
        constituencies={props.constituencies}
        predictions={props.predictions}
        threshold={props.ndaThreshold}
        onThreshold={props.onNdaThreshold}
        onOpenConst={props.onOpenConst}
      />
    );
  }

  if (props.activeTab === 'nda_allied') {
    return (
      <NdaAlliedTab
        constituencies={props.constituencies}
        predictions={props.predictions}
        year={props.ndaAlliedYear}
        onYear={props.onNdaAlliedYear}
        onOpenConst={props.onOpenConst}
      />
    );
  }

  if (!props.selected || !props.selectedConst) return <Placeholder />;

  if (props.activeTab === 'rounds') {
    return (
      <RoundsTab
        key={props.selected}
        constituency={props.selectedConst}
        cached={props.roundCache[props.selected]}
        onLoad={() => props.onLoadRounds(props.selected!)}
      />
    );
  }

  return (
    <VoteEntryTab
      constituency={props.selectedConst}
      live={props.liveData[props.selected]}
      prediction={normalizePrediction(
        props.liveData[props.selected]?.prediction || props.selectedPred,
        props.selectedConst.candidates,
      )}
      votePoll={props.votesPolled[String(props.selected)]}
      roundResults={props.roundCache[props.selected]}
      onSetRound={(round) => props.onSetRound(props.selected!, round)}
      onPredict={() => props.onPredict(props.selected!)}
      onVoteChange={(index, value) => props.onVoteChange(props.selected!, index, value)}
      onMarkCalled={() => props.onMarkCalled(props.selected!)}
      onReset={() => props.onReset(props.selected!)}
    />
  );
}
