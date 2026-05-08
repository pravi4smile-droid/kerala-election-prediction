#!/usr/bin/env python3
"""
Standalone predictor â€” reads live_results.json, maps candidates to alliances,
runs predictions, saves live_predictions.json.
No Flask app required.
"""

import os, json, math, re, ast
from datetime import datetime

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "data")
LIVE_FILE   = os.path.join(DATA_DIR, "live_results.json")
PRED_FILE   = os.path.join(DATA_DIR, "live_predictions.json")
DATA_PARSING_DIR = os.path.join(DATA_DIR, "data_parsing")
LIVE_FILE_LEGACY = LIVE_FILE
LIVE_FILE   = os.path.join(DATA_PARSING_DIR, "live_results.json")
PARSED_2021_DIR = os.path.join(DATA_DIR, "2021")
DIR_2026        = os.path.join(DATA_DIR, "2026")
HISTORY_YEARS = (2011, 2016, 2019, 2021, 2024, 2025)
HISTORY_YEAR_WEIGHTS = {2011: 1, 2016: 4, 2019: 5, 2021: 6, 2024: 8, 2025: 10}
APP_FILE    = os.path.join(BASE_DIR, "app.py")
MAX_BOOTH_ROW_VOTES = 2000

# Max multiplier allowed for pattern adjustment (prevents wild extrapolation at round 1)
MAX_ADJ_FACTOR = 4.0

# â”€â”€ Party abbreviation â†’ normalised tokens â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Maps the short codes used in candidates_2026.json to substrings present in
# ECI full party names.  Order matters â€” more specific first.
PARTY_TOKENS = {
    "CPI(M)":  ["communist party of india (marxist)", "cpi(m)", "cpim"],
    "CPI":     ["communist party of india", "cpi"],
    "INC":     ["indian national congress", " inc", "congress(i)", "inc-"],
    "IUML":    ["indian union muslim league", "iuml"],
    "BJP":     ["bharatiya janata party", "bjp"],
    "KC(M)":   ["kerala congress (m)", "kc(m)", "kerala congress(m)", "kerala congress m"],
    "KC(B)":   ["kerala congress (b)", "kc(b)", "kerala congress b"],
    "KC(J)":   ["kerala congress (j)", "kc(j)", "kerala congress j"],
    "KC":      ["kerala congress", "kc"],
    "KEC":     ["kerala congress", "kc"],
    "RSP":     ["revolutionary socialist party", "rsp"],
    "RSP(L)":  ["revolutionary socialist party (leninist)", "rsp(l)", "rsp l"],
    "CMP":     ["communist marxist party", "cmp"],
    "JD(S)":   ["janata dal (secular)", "jds", "jd(s)"],
    "NCP":     ["nationalist congress party", "ncp"],
    "NCP-SP":  ["nationalist congress party", "ncp-sp", "ncp sp", "ncp (sp)"],
    "LJD":     ["loktantrik janata dal", "ljd"],
    "INL":     ["indian national league", "inl"],
    "BDJS":    ["bharath dharma jana sena", "bdjs"],
    "AIADMK":  ["all india anna dravida", "aiadmk"],
    "JKC":     ["janakeeyam", "jkc"],
    "JRS":     ["janasena", "jrs"],
    "Twenty20":["twenty 20", "twenty20"],
    "IND":     ["independent"],
}

# â”€â”€ ECI full party name â†’ alliance â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Used to verify/correct the alliance label after candidate matching.
# If a candidate's ECI party clearly belongs to a different alliance than the
# slot they were matched into, the ECI party classification wins.
_LDF_ECI = [
    "communist party of india",       # covers CPI and CPI(M)
    "kerala congress (m)",
    "kerala congress (b)",
    "nationalist congress party",
    "indian national league",
    "revolutionary socialist party (leninist)",
    "loktantrik janata dal",
    "socialist unity centre",
    "all india forward bloc",
    "kerala socialist party",
    "congress (secular)",
    "janasabha",
]
_UDF_ECI = [
    "indian national congress",
    "indian union muslim league",
    "kerala congress (j)",
    "kerala congress",
    "revolutionary socialist party",
    "revolutionary marxist party of india",
    "communist marxist party",
]
_NDA_ECI = [
    "bharatiya janata party",
    "bharath dharma jana sena",
    "twenty20",
    "twenty 20",
]

def eci_party_alliance(eci_party: str) -> str | None:
    """
    Return the known alliance for an ECI full party name, or None if unknown
    (Independents, small parties not in any major alliance).
    """
    p = eci_party.lower()
    for tok in _LDF_ECI:
        if tok in p:
            return "ldf"
    for tok in _UDF_ECI:
        if tok in p:
            return "udf"
    for tok in _NDA_ECI:
        if tok in p:
            return "nda"
    return None

def norm_party(s: str) -> str:
    return s.lower().strip()

def short_code_matches(short: str, eci_full: str) -> bool:
    """Does the app short party code match an ECI full party name?"""
    eci_n = norm_party(eci_full)
    s_n   = norm_party(short)
    # Direct substring
    if s_n in eci_n or eci_n in s_n:
        return True
    # Token lookup
    tokens = PARTY_TOKENS.get(short, [])
    return any(tok in eci_n for tok in tokens)

def norm_name(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())

def name_score(app_name: str, eci_name: str) -> int:
    """Rough name overlap score."""
    a = norm_name(app_name)
    e = norm_name(eci_name)
    if not a or not e:
        return 0
    # Common substring of length 4+
    score = 0
    for length in range(4, min(len(a), len(e)) + 1):
        for i in range(len(a) - length + 1):
            sub = a[i:i+length]
            if sub in e:
                score = max(score, length)
    return score

def find_eci_candidate(app_name: str, app_party: str, eci_cands: list[dict]) -> dict | None:
    """Find best matching ECI candidate for an app candidate."""
    best, best_score = None, 0

    for ec in eci_cands:
        score = 0
        # Party match (strong signal)
        if short_code_matches(app_party, ec.get("party", "")):
            score += 10
        # Name match
        score += name_score(app_name, ec.get("name", ""))

        if score > best_score:
            best_score = score
            best = ec

    return best if best_score >= 4 else None


# â”€â”€ Load 2021 booth pattern data â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_BOOTH_DATA: dict | None = None
_HISTORY_DATA: dict[int, dict] | None = None
_RAW_META: dict | None = None

def get_booth_data() -> dict:
    global _BOOTH_DATA
    if _BOOTH_DATA is None:
        _BOOTH_DATA = {}
        if os.path.isdir(PARSED_2021_DIR):
            for fname in os.listdir(PARSED_2021_DIR):
                if not fname.endswith(".json"):
                    continue
                with open(os.path.join(PARSED_2021_DIR, fname), encoding="utf-8") as f:
                    entry = json.load(f)
                _BOOTH_DATA[int(entry["const_no"])] = entry
    return _BOOTH_DATA


def history_dirs_for_year(year: int) -> list[str]:
    """Return local data folders for an Assembly or Lok Sabha history year."""
    if year == 2025:
        return [os.path.join(DATA_DIR, "2025_be")]
    ls_dir = os.path.join(DATA_DIR, f"{year}_ls")
    dirs = [ls_dir if year in (2019, 2024) and os.path.isdir(ls_dir) else os.path.join(DATA_DIR, str(year))]
    if year == 2024:
        dirs.extend([
            os.path.join(DATA_DIR, "2024_be"),
            os.path.join(DATA_DIR, "2024_be_ls"),
        ])
    return dirs


def get_history_data() -> dict[int, dict]:
    """Load split booth histories for Assembly and Lok Sabha reference years."""
    global _HISTORY_DATA
    if _HISTORY_DATA is None:
        _HISTORY_DATA = {}
        for year in HISTORY_YEARS:
            year_data = {}
            for year_dir in history_dirs_for_year(year):
                if not os.path.isdir(year_dir):
                    continue
                for fname in os.listdir(year_dir):
                    if not re.fullmatch(r"\d{3}\.json", fname):
                        continue
                    with open(os.path.join(year_dir, fname), encoding="utf-8") as f:
                        entry = json.load(f)
                    year_data[int(entry["const_no"])] = entry
            _HISTORY_DATA[year] = year_data
    return _HISTORY_DATA


def get_raw_meta() -> dict:
    """Read RAW_META from app.py without importing Flask/app side effects."""
    global _RAW_META
    if _RAW_META is None:
        _RAW_META = {}
        if os.path.exists(APP_FILE):
            with open(APP_FILE, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=APP_FILE)
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "RAW_META":
                            rows = ast.literal_eval(node.value)
                            _RAW_META = {row[0]: row for row in rows}
                            return _RAW_META
    return _RAW_META


def build_live_results_from_2026() -> dict:
    """Build the old live_results.json shape directly from split 2026 files."""
    live = {}
    if not os.path.isdir(DIR_2026):
        return live

    for fname in os.listdir(DIR_2026):
        if not re.fullmatch(r"\d{3}\.json", fname):
            continue
        with open(os.path.join(DIR_2026, fname), encoding="utf-8") as f:
            entry = json.load(f)

        cno = int(entry.get("const_no") or fname[:3])
        rounds = entry.get("rounds", []) or []
        totals = list(entry.get("total") or [])
        if rounds:
            cumulative = rounds[-1].get("cumulative", [])
            if cumulative:
                totals = list(cumulative)

        candidates = []
        for cand in entry.get("candidates_2026", []):
            idx = cand.get("index")
            votes = 0
            if isinstance(idx, int) and idx < len(totals):
                votes = int(totals[idx] or 0)
            else:
                votes = int(cand.get("actual_votes_2026") or 0)
            candidates.append({
                "name": cand.get("name", ""),
                "party": cand.get("party", ""),
                "alliance": cand.get("alliance", "other"),
                "index": idx,
                "status": "lost",
                "votes": votes,
                "margin": 0,
            })

        candidates.sort(key=lambda c: -c.get("votes", 0))
        winner_votes = candidates[0]["votes"] if candidates else 0
        runner_votes = candidates[1]["votes"] if len(candidates) > 1 else 0
        for i, cand in enumerate(candidates):
            cand["status"] = "won" if i == 0 else "lost"
            cand["margin"] = cand["votes"] - winner_votes if i else winner_votes - runner_votes

        live[str(cno)] = {
            "const_no": cno,
            "name": entry.get("name", ""),
            "lead_cand": candidates[0]["name"] if candidates else "",
            "trail_cand": candidates[1]["name"] if len(candidates) > 1 else "",
            "margin": winner_votes - runner_votes,
            "round_str": f"{len(rounds)}/{len(rounds)}",
            "cur_round": len(rounds),
            "tot_rounds": len(rounds),
            "status": "Result Declared" if rounds else "Pending",
            "active": bool(rounds and candidates),
            "candidates": candidates,
            "rounds_completed": len(rounds),
            "fetched_at": entry.get("fetched_at", ""),
        }
    return live


def clean_booths(booths: list[dict]) -> list[dict]:
    """
    Drop parser artifacts from PDF footer/summary rows.
    Real Kerala booth numbers are small sequential values; rows like 1514/63690
    are totals accidentally parsed as booth labels and badly distort patterns.
    """
    return [
        b for b in booths
        if 1 <= int(b.get("main", 0)) <= 500
        and sum(b.get("votes", [])) <= MAX_BOOTH_ROW_VOTES
    ]


def historical_entry_matches_constituency(entry: dict, const_no: int) -> bool:
    """
    Reject split historical files whose embedded PDF title points to a different
    constituency number. Example: data/2021/066.json currently contains the
    title "65-WADAKKANCHERY", so it must not be used as Ollur's 2021 pattern.
    """
    title = str(entry.get("name", ""))
    match = re.match(r"\s*(\d+)\s*[-.]", title)
    return not match or int(match.group(1)) == int(const_no)


def booth_alliance_indices(const_no: int, booth_candidates: list[str], n: int) -> list[int] | None:
    """Map [ldf, udf, nda] to candidate columns in the 2021 parsed PDF."""
    raw = get_raw_meta().get(const_no)
    if not raw or not booth_candidates:
        return None

    names = [raw[3][0], raw[4][0], raw[5][0]]
    indices = []
    used = set()
    for name in names[:n]:
        best_i, best_score = None, 0
        for i, cand in enumerate(booth_candidates):
            if i in used:
                continue
            score = name_score(name, cand)
            if score > best_score:
                best_i, best_score = i, score
        if best_i is None or best_score < 4:
            return None
        indices.append(best_i)
        used.add(best_i)
    return indices


def alliance_indices_from_metadata(entry: dict, year: int, n: int) -> list[int] | None:
    cands = entry.get(f"candidates_{year}", []) or entry.get(f"candidates_{year}_ls", [])
    result = []
    for alliance in ("ldf", "udf", "nda")[:n]:
        idx = next(
            (c.get("index") for c in cands
             if str(c.get("alliance", "")).lower() == alliance and isinstance(c.get("index"), int)),
            None,
        )
        if idx is None:
            return None
        result.append(idx)
    return result


def historical_pattern_for_year(entry: dict, year: int, pct: float, n: int, const_no: int) -> dict | None:
    if not entry or not historical_entry_matches_constituency(entry, const_no):
        return None

    booths = clean_booths(entry.get("booths", []))
    if not booths:
        return None

    idx_map = alliance_indices_from_metadata(entry, year, n)
    if (not idx_map or len(idx_map) != n) and year == 2021:
        idx_map = booth_alliance_indices(const_no, entry.get("candidates", []), n)
    if not idx_map or len(idx_map) != n:
        return None

    main_nos = sorted({b["main"] for b in booths if not b.get("is_aux", False)})
    if not main_nos:
        return None

    def booth_total(b):
        votes = b.get("votes", [])
        return sum(votes[idx] if idx < len(votes) else 0 for idx in idx_map)

    total_all = sum(booth_total(b) for b in booths)
    if total_all <= 0:
        return None

    target = pct * total_all
    running = 0
    cutoff_set = set()
    for bn in main_nos:
        running += sum(booth_total(b) for b in booths if b["main"] == bn)
        cutoff_set.add(bn)
        if running >= target:
            break

    early_booths = [b for b in booths if b["main"] in cutoff_set]
    early_totals = [
        sum(b.get("votes", [])[idx] if idx < len(b.get("votes", [])) else 0 for b in early_booths)
        for idx in idx_map
    ]
    final_totals = [
        sum(b.get("votes", [])[idx] if idx < len(b.get("votes", [])) else 0 for b in booths)
        for idx in idx_map
    ]

    sum_early = sum(early_totals)
    sum_final = sum(final_totals)
    remaining = [final_totals[i] - early_totals[i] for i in range(n)]
    sum_remaining = sum(remaining)
    if sum_early <= 0 or sum_final <= 0 or sum_remaining <= 0:
        return None
    if sum(1 for e in early_totals if e > 0) < 2:
        return None

    return {
        "year": year,
        "total_all": total_all,
        "sum_early": sum_early,
        "share_early": [v / sum_early for v in early_totals],
        "share_remaining": [v / sum_remaining for v in remaining],
    }


def average_patterns(patterns: list[dict], key: str, n: int) -> list[float]:
    total_weight = sum(HISTORY_YEAR_WEIGHTS.get(p["year"], 1) for p in patterns)
    return [
        sum(p[key][i] * HISTORY_YEAR_WEIGHTS.get(p["year"], 1) for p in patterns) / total_weight
        for i in range(n)
    ]


def cap_projection(projected: list[int], actual: list[int], cap: int) -> list[int]:
    """Keep rounded projections within a known vote total without going below counted votes."""
    if cap <= 0 or sum(projected) <= cap:
        return projected
    adjusted = projected[:]
    diff = sum(adjusted) - cap
    while diff > 0:
        candidates = [i for i, v in enumerate(adjusted) if v > actual[i]]
        if not candidates:
            break
        i = max(candidates, key=lambda j: adjusted[j] - actual[j])
        adjusted[i] -= 1
        diff -= 1
    return adjusted


def trend_weight(cur_round: int) -> float:
    """Use the current swing aggressively: partial in R1/R2, full from R3."""
    if cur_round <= 1:
        return 0.9
    if cur_round == 2:
        return 0.95
    return 1.0


def assess_call_readiness(
    pred: dict,
    cur_round: int,
    tot_rounds: int,
    live_votes: list[int] | None = None,
    previous_leaders: list[int] | None = None,
    previous_shift_patterns: list[list[float]] | None = None,
) -> dict:
    """Classify whether a projection is ready to call, too early, or too close."""
    margin = int(pred.get("margin", 0) or 0)
    pct = pred.get("formula", {}).get("pct", pred.get("pct_counted", 0) or 0)
    raw_conf = int(pred.get("confidence", 0) or 0)
    winner_idx = pred.get("winner_idx", 0)
    live_leader_idx = None
    if live_votes:
        live_leader_idx = max(range(len(live_votes)), key=lambda i: live_votes[i])

    def verdict(status, label, text_conf, ready, reason, pct_conf):
        return {
            "call_status": status,
            "call_label": label,
            "call_confidence": text_conf,
            "call_confidence_pct": pct_conf,
            "confidence": pct_conf,
            "raw_confidence": raw_conf,
            "call_ready": ready,
            "call_reason": reason,
        }

    if cur_round >= tot_rounds or pct >= 99.5 or pred.get("formula", {}).get("projection_method") == "final_count":
        return verdict("called", "Called", "Final", True, "Counting complete", 99)

    sorted_idx = sorted(
        range(len(pred.get("projected", []) or live_votes or [])),
        key=lambda i: -(pred.get("projected", []) or live_votes or [])[i],
    )
    top_indices = sorted(set(([winner_idx] + sorted_idx[:3])[:3]))

    def shift_stable(patterns: list[list[float]], min_rounds: int, recent_only: bool) -> bool:
        if len(patterns) < min_rounds:
            return False
        check = patterns[-min_rounds:] if recent_only else patterns
        for idx in top_indices:
            vals = [row[idx] for row in check if idx < len(row)]
            if len(vals) < min_rounds:
                return False
            signs = []
            for value in vals:
                if value > 1.0:
                    signs.append(1)
                elif value < -1.0:
                    signs.append(-1)
                else:
                    signs.append(0)
            # A real stable shift means the same side is over/under-performing
            # historical early share each round. Tiny +/-1pp noise is neutral.
            non_neutral = [s for s in signs if s != 0]
            if non_neutral and len(set(non_neutral)) > 1:
                return False
            if not non_neutral and max(vals) - min(vals) > 3.0:
                return False
        return True

    shift_patterns = list(previous_shift_patterns or [])
    if not shift_patterns and pred.get("formula", {}).get("delta"):
        shift_patterns = [pred["formula"]["delta"]]
    stable_recent = shift_stable(shift_patterns, 2, True)
    stable_all = shift_stable(shift_patterns, 3, False)
    projected_stable_all = stable_all

    if margin >= 20000:
        return verdict(
            "ready_to_call", "Ready to Call", "High", True,
            "Projected margin is above 20,000 votes",
            max(raw_conf, 98),
        )
    if cur_round >= 2 and pct >= 25 and stable_recent and margin >= 12000:
        return verdict(
            "ready_to_call", "Ready to Call", "High", True,
            "More than 25% counted, recent rounds show a consistent vote-shift pattern, and projected margin is above 12,000 votes",
            max(raw_conf, 96),
        )
    if cur_round >= 2 and stable_recent and margin >= 8000:
        return verdict(
            "ready_to_call", "Ready to Call", "High", True,
            "Recent rounds show a consistent vote-shift pattern and projected margin is above 8,000 votes",
            max(raw_conf, 95),
        )
    if cur_round >= 3 and pct >= 50 and stable_all and margin >= 4000:
        return verdict(
            "ready_to_call", "Ready to Call", "Medium", True,
            "More than 50% counted, rounds follow a consistent vote-shift pattern, and projected margin is above 4,000 votes",
            max(raw_conf, 92),
        )
    if cur_round >= 3 and pct >= 90 and projected_stable_all and margin >= 1500:
        return verdict(
            "ready_to_call", "Ready to Call", "Medium", True,
            "More than 90% counted, the vote-shift pattern is intact, and projected margin is above 1,500 votes",
            max(raw_conf, 95),
        )
    if cur_round >= 3 and pct >= 75 and projected_stable_all and margin >= 3500:
        return verdict(
            "ready_to_call", "Ready to Call", "Medium", True,
            "More than 75% counted, the vote-shift pattern is intact, and projected margin is above 3,500 votes",
            max(raw_conf, 90),
        )
    if cur_round >= 12 and projected_stable_all and margin >= 3500:
        return verdict(
            "ready_to_call", "Ready to Call", "Medium", True,
            "Round 12 or later, the vote-shift pattern is intact, and projected margin is above 3,500 votes",
            max(raw_conf, 88),
        )
    if cur_round >= 10 and pct >= 70 and projected_stable_all and margin >= 2500:
        return verdict(
            "ready_to_call", "Ready to Call", "Medium", True,
            "Round 10 or later, more than 70% counted, the vote-shift pattern is intact, and projected margin is above 2,500 votes",
            max(raw_conf, 87),
        )
    if cur_round >= 15 and projected_stable_all and margin >= 2500:
        return verdict(
            "ready_to_call", "Ready to Call", "Medium", True,
            "Round 15 or later, the vote-shift pattern is intact, and projected margin is above 2,500 votes",
            max(raw_conf, 86),
        )
    if cur_round <= 1 or pct < 15:
        return verdict(
            "too_early", "Too Early to Call", "Low", False,
            "Needs more counted votes before calling",
            min(raw_conf, 35),
        )
    if margin < 5000:
        return verdict(
            "too_close", "Too Close to Call", "Low", False,
            "Projected margin is below 5,000 votes",
            min(raw_conf, 55),
        )
    return verdict(
        "watching", "Watching Trend", "Medium", False,
        "Projection has a lead, but call thresholds are not met yet",
        max(min(raw_conf, 79), 60),
    )


# â”€â”€ Prediction logic â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def predict(votes: list[int], cur_round: int, tot_rounds: int,
            const_no: int | None = None,
            votes_polled: int = 0, total_counted: int = 0) -> dict:
    """
    Share-shift projection against averaged 2011/2016/2019 LS/2021/2024 LS booth patterns.

    pct = total_counted / votes_polled when available (vote-based, accurate).
    Falls back to cur_round / tot_rounds (round-based) if turnout data missing.

    Method:
      1. Find historical booths covering the same vote-% point in each year
      2. Average historical early and remaining shares by alliance
      3. Apply the current swing to the averaged historical remaining shares
      4. Project remaining 2026 votes, add to actual counted.
    """
    if tot_rounds <= 0 or cur_round <= 0:
        return {}

    if votes_polled > 0 and total_counted > 0:
        pct = min(total_counted / votes_polled, 1.0)
    else:
        pct = min(cur_round / tot_rounds, 1.0)
    n   = len(votes)

    sum_votes = sum(votes)
    if sum_votes > 0 and cur_round >= tot_rounds:
        projected = list(votes)
        total_proj = sum_votes
        sorted_idx = sorted(range(len(projected)), key=lambda i: -projected[i])
        w = sorted_idx[0]
        r2 = sorted_idx[1] if len(sorted_idx) > 1 else 0
        margin = projected[w] - projected[r2]
        result = {
            "projected": projected,
            "total_projected": total_proj,
            "winner_idx": w,
            "margin": margin,
            "confidence": 99,
            "pct_counted": round(pct * 100),
            "used_pattern": False,
            "linear_winner_idx": w,
            "pattern_differs": False,
            "formula": {
                "pct": round(pct * 100, 2),
                "sum_votes": sum_votes,
                "remaining_2026": max((votes_polled or sum_votes) - sum_votes, 0),
                "proj_from_remaining": [0 for _ in votes],
                "projection_method": "final_count",
            },
        }
        result.update(assess_call_readiness(result, cur_round, tot_rounds, votes))
        return result

    # Linear baseline â€” used as fallback and to anchor total projection
    lin_proj     = [round(v / pct) for v in votes] if pct > 0 else list(votes)
    projected    = lin_proj[:]
    used_pattern = False
    formula      = {}           # intermediate values returned for UI display

    # Multi-year booth-pattern shift. Each available history year contributes
    # one early/remaining pattern, then the current swing is applied to the
    # averaged remaining pattern.
    if const_no and pct > 0 and sum_votes > 0:
        histories = get_history_data()
        patterns = []
        for year in HISTORY_YEARS:
            pattern = historical_pattern_for_year(
                histories.get(year, {}).get(const_no, {}),
                year,
                pct,
                n,
                const_no,
            )
            if pattern:
                patterns.append(pattern)

        if patterns:
            share_hist_early = average_patterns(patterns, "share_early", n)
            share_hist_remaining = average_patterns(patterns, "share_remaining", n)
            share_2026 = [v / sum_votes for v in votes]
            delta = [
                s26 - hist_early
                for s26, hist_early in zip(share_2026, share_hist_early)
            ]

            damp = trend_weight(cur_round)
            adj_remaining = [
                max(0.0, hist_remaining + d * damp)
                for hist_remaining, d in zip(share_hist_remaining, delta)
            ]
            tot_adj = sum(adj_remaining)
            if tot_adj > 0:
                adj_remaining = [s / tot_adj for s in adj_remaining]

                if votes_polled > 0:
                    remaining_2026 = max(votes_polled - sum_votes, 0)
                else:
                    remaining_2026 = (sum_votes / pct) - sum_votes

                projected = [
                    round(votes[i] + adj_remaining[i] * remaining_2026)
                    for i in range(n)
                ]
                used_pattern = True
                final_remaining = [max(projected[i] - votes[i], 0) for i in range(n)]
                primary = next((p for p in patterns if p["year"] == 2021), patterns[-1])

                formula = {
                    "pct": round(pct * 100, 2),
                    "damp": round(damp, 3),
                    "trend_weight": round(damp, 3),
                    "trend_weight_rule": "R1=0.90, R2=0.95, R3+=1.00",
                    "sum_votes": sum_votes,
                    "remaining_2026": round(remaining_2026),
                    "history_years": [p["year"] for p in patterns],
                    "history_count": len(patterns),
                    "history_weights": {
                        str(p["year"]): HISTORY_YEAR_WEIGHTS.get(p["year"], 1)
                        for p in patterns
                    },
                    "historical_early_by_year": {
                        str(p["year"]): [round(s * 100, 2) for s in p["share_early"]]
                        for p in patterns
                    },
                    "historical_remaining_by_year": {
                        str(p["year"]): [round(s * 100, 2) for s in p["share_remaining"]]
                        for p in patterns
                    },
                    "total_2021_early": round(primary["sum_early"]),
                    "total_2021_all": round(primary["total_all"]),
                    "share_2021_early": [round(s * 100, 2) for s in share_hist_early],
                    "share_2026": [round(s * 100, 2) for s in share_2026],
                    "delta": [round(d * 100, 2) for d in delta],
                    "share_remaining_2021": [
                        round(s * 100, 2) for s in share_hist_remaining
                    ],
                    "adj_remaining": [round(s * 100, 2) for s in adj_remaining],
                    "proj_from_remaining": final_remaining,
                    "projection_method": "multi_year_pattern",
                }

    total_proj = sum(projected)
    if votes_polled > 0:
        projected = cap_projection(projected, votes, max(votes_polled, sum_votes))
        total_proj = sum(projected)
    if formula:
        formula["proj_from_remaining"] = [
            max(projected[i] - votes[i], 0) for i in range(len(projected))
        ]
    sorted_idx = sorted(range(len(projected)), key=lambda i: -projected[i])
    w  = sorted_idx[0]
    r2 = sorted_idx[1] if len(sorted_idx) > 1 else 0
    margin = projected[w] - projected[r2]

    conf = min(round(
        pct * 55 +
        (margin / max(total_proj, 1)) * 150 +
        (10 if pct > 0.5 else 0) +
        (5  if pct > 0.7 else 0)
    ), 99)

    lin_winner = sorted(range(n), key=lambda i: -lin_proj[i])[0]

    result = {
        "projected":         projected,
        "total_projected":   total_proj,
        "winner_idx":        w,
        "margin":            margin,
        "confidence":        conf,
        "pct_counted":       round(pct * 100),
        "used_pattern":      used_pattern,
        "linear_winner_idx": lin_winner,
        "pattern_differs":   used_pattern and (w != lin_winner),
        "formula":           formula,
    }
    result.update(assess_call_readiness(result, cur_round, tot_rounds, votes))
    return result


# â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def round_leader_history_from_2026(const_no: int, upto_round: int) -> list[int]:
    """Return cumulative major-alliance live leaders by round for one 2026 seat."""
    path = os.path.join(DIR_2026, f"{const_no:03d}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        entry = json.load(f)

    candidate_alliances = {
        c.get("index"): c.get("alliance")
        for c in entry.get("candidates_2026", [])
        if c.get("alliance") in ("ldf", "udf", "nda")
    }
    leaders = []
    for rr in (entry.get("rounds", []) or [])[:upto_round]:
        cumulative = rr.get("cumulative", [])
        totals = [0, 0, 0]
        for idx, alliance in candidate_alliances.items():
            if isinstance(idx, int) and idx < len(cumulative):
                totals[["ldf", "udf", "nda"].index(alliance)] += int(cumulative[idx] or 0)
        if sum(totals) > 0:
            leaders.append(max(range(3), key=lambda i: totals[i]))
    return leaders


def projected_winner_history_from_2026(const_no: int, upto_round: int) -> list[int]:
    """Return projected major-alliance winners by round for one 2026 seat."""
    path = os.path.join(DIR_2026, f"{const_no:03d}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        entry = json.load(f)

    alliances = ["ldf", "udf", "nda"]
    candidate_alliances = {
        c.get("index"): c.get("alliance")
        for c in entry.get("candidates_2026", [])
        if c.get("alliance") in alliances
    }
    leaders = []
    rounds = entry.get("rounds", []) or []
    votes_polled = (entry.get("turnout") or {}).get("votes_polled", 0)
    for r, rr in enumerate(rounds[:upto_round], start=1):
        cumulative = rr.get("cumulative", [])
        votes = [0, 0, 0]
        for idx, alliance in candidate_alliances.items():
            if isinstance(idx, int) and idx < len(cumulative):
                votes[alliances.index(alliance)] += int(cumulative[idx] or 0)
        if sum(votes) <= 0:
            continue
        pred = predict(
            votes,
            r,
            len(rounds),
            const_no=const_no,
            votes_polled=votes_polled,
            total_counted=sum(int(x or 0) for x in cumulative),
        )
        if pred:
            leaders.append(pred["winner_idx"])
    return leaders


def shift_pattern_history_from_2026(const_no: int, upto_round: int) -> list[list[float]]:
    """Return per-round swing-vs-history deltas in LDF/UDF/NDA order."""
    path = os.path.join(DIR_2026, f"{const_no:03d}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        entry = json.load(f)

    alliances = ["ldf", "udf", "nda"]
    candidate_alliances = {
        c.get("index"): c.get("alliance")
        for c in entry.get("candidates_2026", [])
        if c.get("alliance") in alliances
    }
    patterns = []
    rounds = entry.get("rounds", []) or []
    votes_polled = (entry.get("turnout") or {}).get("votes_polled", 0)
    for r, rr in enumerate(rounds[:upto_round], start=1):
        cumulative = rr.get("cumulative", [])
        votes = [0, 0, 0]
        for idx, alliance in candidate_alliances.items():
            if isinstance(idx, int) and idx < len(cumulative):
                votes[alliances.index(alliance)] += int(cumulative[idx] or 0)
        if sum(votes) <= 0:
            continue
        pred = predict(
            votes,
            r,
            len(rounds),
            const_no=const_no,
            votes_polled=votes_polled,
            total_counted=sum(int(x or 0) for x in cumulative),
        )
        delta = pred.get("formula", {}).get("delta")
        if delta and len(delta) >= 3:
            patterns.append(delta)
    return patterns


def summarize_shift_stability(
    patterns: list[list[float]],
    top_indices: list[int] | None = None,
) -> dict:
    """Summarize whether swing direction is stable for the main alliances."""
    alliances = ["ldf", "udf", "nda"]
    if top_indices is None:
        top_indices = [0, 1, 2]

    def sign(value: float) -> int:
        if value > 1.0:
            return 1
        if value < -1.0:
            return -1
        return 0

    def stable_for(check: list[list[float]], min_rounds: int) -> bool:
        if len(check) < min_rounds:
            return False
        for idx in top_indices:
            vals = [row[idx] for row in check if idx < len(row)]
            if len(vals) < min_rounds:
                return False
            signs = [sign(v) for v in vals]
            non_neutral = [s for s in signs if s != 0]
            if non_neutral and len(set(non_neutral)) > 1:
                return False
            if not non_neutral and max(vals) - min(vals) > 3.0:
                return False
        return True

    by_alliance = {}
    for idx, alliance in enumerate(alliances):
        vals = [row[idx] for row in patterns if idx < len(row)]
        non_neutral = [sign(v) for v in vals if sign(v) != 0]
        by_alliance[alliance] = {
            "rounds": len(vals),
            "current_delta": round(vals[-1], 2) if vals else None,
            "min_delta": round(min(vals), 2) if vals else None,
            "max_delta": round(max(vals), 2) if vals else None,
            "stable_direction": len(set(non_neutral)) <= 1 if non_neutral else True,
        }

    return {
        "rounds": len(patterns),
        "stable_recent": stable_for(patterns[-2:], 2),
        "stable_all": stable_for(patterns, 3),
        "alliances": by_alliance,
    }


def call_readiness_timeline_from_2026(const_no: int, upto_round: int) -> dict:
    """Replay rounds and return when the aggressive call criteria first passed."""
    path = os.path.join(DIR_2026, f"{const_no:03d}.json")
    if not os.path.exists(path):
        return {"ready_since_round": None, "timeline": []}
    with open(path, encoding="utf-8") as f:
        entry = json.load(f)

    alliances = ["ldf", "udf", "nda"]
    candidate_alliances = {
        c.get("index"): c.get("alliance")
        for c in entry.get("candidates_2026", [])
        if c.get("alliance") in alliances
    }
    rounds = entry.get("rounds", []) or []
    votes_polled = (entry.get("turnout") or {}).get("votes_polled", 0)
    leaders: list[int] = []
    patterns: list[list[float]] = []
    timeline = []

    for r, rr in enumerate(rounds[:upto_round], start=1):
        cumulative = rr.get("cumulative", [])
        votes = [0, 0, 0]
        for idx, alliance in candidate_alliances.items():
            if isinstance(idx, int) and idx < len(cumulative):
                votes[alliances.index(alliance)] += int(cumulative[idx] or 0)
        if sum(votes) <= 0:
            continue

        pred = predict(
            votes,
            r,
            len(rounds),
            const_no=const_no,
            votes_polled=votes_polled,
            total_counted=sum(int(x or 0) for x in cumulative),
        )
        if not pred:
            continue

        leaders.append(pred.get("winner_idx", 0))
        delta = pred.get("formula", {}).get("delta")
        if delta and len(delta) >= 3:
            patterns.append(delta)
        readiness = assess_call_readiness(pred, r, len(rounds), votes, leaders[:], patterns[:])
        timeline.append({
            "round": r,
            "status": readiness.get("call_status", "watching"),
            "label": readiness.get("call_label", "Watching Trend"),
            "ready": bool(readiness.get("call_ready", False)),
            "confidence": readiness.get("confidence", pred.get("confidence", 0)),
            "margin": int(pred.get("margin", 0) or 0),
            "winner_idx": int(pred.get("winner_idx", 0) or 0),
            "pct_counted": pred.get("pct_counted", 0),
        })

    ready_since = next(
        (t["round"] for t in timeline if t["ready"] and t["status"] in ("ready_to_call", "called")),
        None,
    )
    return {"ready_since_round": ready_since, "timeline": timeline}


def run():
    # Build live-style inputs from split 2026 files.  The old live_results.json
    # scraper output is no longer required once data/2026 has complete rounds.
    live = build_live_results_from_2026()
    if not live:
        print("No 2026 round JSON data found.")
        return {}

    cands_2026 = {}
    vpoll = {}
    if os.path.isdir(DIR_2026):
        for _fn in os.listdir(DIR_2026):
            if not _fn.endswith(".json"):
                continue
            with open(os.path.join(DIR_2026, _fn), encoding="utf-8") as _f:
                _e = json.load(_f)
            _cno = str(_e["const_no"])
            if _e.get("turnout"):
                vpoll[_cno] = _e["turnout"]
            _row = {"name": _e.get("name", ""), "district": _e.get("district", "")}
            _major_by_alliance = {"ldf": [], "udf": [], "nda": []}
            for _c in _e.get("candidates_2026", []):
                _a = _c.get("alliance")
                if _a in ("ldf", "udf", "nda") and _c.get("is_major_alliance"):
                    _major_by_alliance[_a].append(_c)
            for _a in ("ldf", "udf", "nda"):
                _major_by_alliance[_a].sort(
                    key=lambda c: int(c.get("actual_votes_2026") or 0),
                    reverse=True,
                )
                primary = _major_by_alliance[_a][0] if _major_by_alliance[_a] else {}
                _row[_a] = {"name": primary.get("name", ""), "party": primary.get("party", "")}
                extras = _major_by_alliance[_a][1:]
                if extras:
                    _row[f"{_a}_allied"] = [
                        {"name": c.get("name", ""), "party": c.get("party", "")}
                        for c in extras
                    ]
            cands_2026[_cno] = _row

    predictions = {}
    unmatched   = []
    alliances   = ["ldf", "udf", "nda"]

    for cno_str, eci in live.items():
        if not eci.get("active"):
            continue

        cno       = int(cno_str)
        eci_cands = eci.get("candidates", [])
        if not eci_cands:
            continue

        cur_round  = eci.get("cur_round", 0)
        tot_rounds = eci.get("tot_rounds", 0)
        if cur_round <= 0 or tot_rounds <= 0:
            continue

        app_meta = cands_2026.get(cno_str, {})
        district = app_meta.get("district", "")
        const_name = app_meta.get("name", eci.get("name", ""))

        # Map each alliance to an ECI candidate
        matched = {}   # alliance â†’ eci candidate dict
        votes   = []   # [ldf_votes, udf_votes, nda_votes]
        allied_names = {}  # alliance â†’ [extra ECI candidate names matched]

        for alliance in alliances:
            ac = app_meta.get(alliance, {})
            app_name  = ac.get("name", "").strip()
            app_party = ac.get("party", "").strip()
            # Skip empty slots â€” don't let an empty string accidentally match everything
            if not app_name and not app_party:
                matched[alliance] = None
                votes.append(0)
                continue
            ec = find_eci_candidate(app_name, app_party, eci_cands)
            matched[alliance] = ec
            votes.append(ec["votes"] if ec else 0)

        # â”€â”€ Allied candidates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # candidates_2026.json may declare extra candidates allied to an alliance:
        #   "udf_allied": [{"name": "...", "party": "..."}]
        # Their ECI votes are added on top of the main alliance candidate's votes.
        allied_extra = {}  # alliance â†’ extra_votes
        for alliance in alliances:
            extra_list = app_meta.get(f"{alliance}_allied", [])
            extra_votes = 0
            extra_nms = []
            for extra_ac in extra_list:
                ec_extra = find_eci_candidate(
                    extra_ac.get("name", ""),
                    extra_ac.get("party", ""),
                    eci_cands,
                )
                if ec_extra:
                    extra_votes += ec_extra.get("votes", 0)
                    extra_nms.append(ec_extra["name"])
            if extra_votes:
                allied_extra[alliance] = extra_votes
                allied_names[alliance] = extra_nms
                # Add to votes array for this alliance
                idx = alliances.index(alliance)
                votes[idx] += extra_votes

        # Fallback: if all three are zero, assign top-3 ECI candidates in order
        if sum(votes) == 0 and len(eci_cands) >= 3:
            sorted_ec = sorted(eci_cands, key=lambda c: -c.get("votes", 0))
            for i, alliance in enumerate(alliances):
                matched[alliance] = sorted_ec[i] if i < len(sorted_ec) else None
                votes[i] = sorted_ec[i]["votes"] if i < len(sorted_ec) else 0

        if sum(votes) == 0:
            continue

        # Total ECI votes counted (all candidates, not just alliance slots)
        total_counted  = sum(c.get("votes", 0) for c in eci_cands)
        vp_entry       = vpoll.get(cno_str, {})
        votes_polled_v = vp_entry.get("votes_polled", 0)

        pred = predict(votes, cur_round, tot_rounds, const_no=cno,
                       votes_polled=votes_polled_v, total_counted=total_counted)
        if not pred:
            continue
        winner_history = projected_winner_history_from_2026(cno, cur_round)
        shift_patterns = shift_pattern_history_from_2026(cno, cur_round)
        projected = pred.get("projected", []) or votes
        top_indices = sorted(
            range(len(projected)),
            key=lambda i: -projected[i],
        )[:3]
        shift_stability = summarize_shift_stability(shift_patterns, top_indices)
        call_timeline = call_readiness_timeline_from_2026(cno, cur_round)
        pred.update(assess_call_readiness(
            pred,
            cur_round,
            tot_rounds,
            votes,
            winner_history,
            shift_patterns,
        ))

        winner_alliance = alliances[pred["winner_idx"]]
        winner_ec       = matched.get(winner_alliance)

        # â”€â”€ Alliance sanity check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # If the winner's ECI party clearly belongs to a different alliance than
        # the slot they were matched into (e.g. RSP matched into udf slot),
        # reclassify using the known partyâ†’alliance table.
        if winner_ec:
            known_a = eci_party_alliance(winner_ec.get("party", ""))
            if known_a and known_a != winner_alliance:
                winner_alliance = known_a
        # Independents in a properly matched alliance slot are alliance-backed;
        # keep the slot label (ldf/udf/nda) rather than marking 'other'.

        # Detect upset: pattern winner â‰  current ECI leader
        eci_cands       = eci.get("candidates", [])
        eci_leader_cand = next((c for c in eci_cands if c.get("status") == "leading"), None)
        eci_lead_alliance = None
        if eci_leader_cand:
            for a, cm in {a: {"eci_name": matched[a]["name"] if matched[a] else ""}
                          for a in alliances}.items():
                if norm_name(cm["eci_name"]) == norm_name(eci_leader_cand.get("name", "")):
                    eci_lead_alliance = a
                    break

        # Not a real upset if the pattern winner and ECI leader are literally
        # the same person (can happen when an Independent is reclassified from
        # a named alliance slot to "other" while eci_lead_alliance keeps the slot).
        same_candidate = (
            winner_ec is not None and
            eci_leader_cand is not None and
            norm_name(winner_ec.get("name", "")) == norm_name(eci_leader_cand.get("name", ""))
        )
        is_upset = (
            pred["used_pattern"] and
            eci_lead_alliance is not None and
            winner_alliance != eci_lead_alliance and
            not same_candidate
        )

        predictions[cno_str] = {
            "const_no":        cno,
            "name":            const_name,
            "district":        district,
            "cur_round":       cur_round,
            "tot_rounds":      tot_rounds,
            "live_votes":      {a: votes[i] for i, a in enumerate(alliances)},
            "projected":       {a: pred["projected"][i] for i, a in enumerate(alliances)},
            "winner_alliance": winner_alliance,
            "winner_name":     winner_ec["name"] if winner_ec else "",
            "winner_party":    winner_ec["party"] if winner_ec else "",
            "margin":          pred["margin"],
            "confidence":      pred["confidence"],
            "call_status":     pred.get("call_status", "watching"),
            "call_label":      pred.get("call_label", "Watching Trend"),
            "call_confidence": pred.get("call_confidence", "Medium"),
            "call_ready":      pred.get("call_ready", False),
            "call_reason":     pred.get("call_reason", ""),
            "pct_counted":     pred["pct_counted"],
            "votes_counted":   total_counted,
            "votes_polled":    votes_polled_v,
            "used_pattern":    pred["used_pattern"],
            "formula":         pred.get("formula", {}),
            "shift_patterns":   shift_patterns,
            "shift_stability":  shift_stability,
            "call_timeline":    call_timeline,
            "ready_since_round": call_timeline.get("ready_since_round"),
            "is_upset":        is_upset,
            "eci_lead_alliance": eci_lead_alliance,
            "eci_leader_name": eci_leader_cand["name"] if eci_leader_cand else "",
            "candidates_mapped": {
                a: {
                    "app_name":  app_meta.get(a, {}).get("name", ""),
                    "app_party": app_meta.get(a, {}).get("party", ""),
                    "eci_name":  matched[a]["name"] if matched[a] else "?",
                    "eci_party": matched[a]["party"] if matched[a] else "?",
                    "votes":     matched[a]["votes"] if matched[a] else 0,
                    "allied_votes":  allied_extra.get(a, 0),
                    "allied_names":  allied_names.get(a, []),
                } for a in alliances
            },
            "updated_at": datetime.now().isoformat(),
        }

        # Warn about unmatched candidates
        for alliance in alliances:
            if not matched[alliance] or matched[alliance]["votes"] == 0:
                unmatched.append(f"{cno_str}/{const_name}/{alliance}")

    # â”€â”€ Mark called (all rounds complete) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    called_tally = {"ldf": 0, "udf": 0, "nda": 0, "other": 0}
    for cno_str, eci in live.items():
        if eci.get("cur_round", 0) < eci.get("tot_rounds", 1) or eci.get("tot_rounds", 0) == 0:
            if cno_str in predictions:
                predictions[cno_str]["is_called"] = False
            continue
        cands = sorted(eci.get("candidates", []), key=lambda c: -c.get("votes", 0))
        if not cands:
            continue
        winner_eci = cands[0]
        # Classify final winner against the known 2026 candidate/alliance slots first.
        # Some alliance-backed winners are listed by ECI as Independent, so raw party
        # alone would incorrectly push them into "other".
        if winner_eci.get("alliance") in alliances:
            called_alliance = winner_eci["alliance"]
        else:
            app_meta = cands_2026.get(cno_str, {})
            best_a, best_s = "other", 0
            for a in alliances:
                s = name_score(winner_eci["name"], app_meta.get(a, {}).get("name", ""))
                if s > best_s:
                    best_s, best_a = s, a
            if best_s >= 5:
                called_alliance = best_a
            else:
                known_a = eci_party_alliance(winner_eci.get("party", ""))
                if known_a:
                    called_alliance = known_a
                elif "independent" in winner_eci.get("party", "").lower():
                    called_alliance = "other"
                else:
                    called_alliance = "other"
        called_tally[called_alliance] = called_tally.get(called_alliance, 0) + 1
        if cno_str in predictions:
            actual_margin = cands[0].get("votes", 0) - (cands[1].get("votes", 0) if len(cands) > 1 else 0)
            predictions[cno_str].update({
                "is_called":             True,
                # Once counting is complete, top-level winner fields must be
                # final ECI result fields, not the earlier projection winner.
                "winner_alliance":       called_alliance,
                "winner_name":           winner_eci["name"],
                "winner_party":          winner_eci["party"],
                "margin":                actual_margin,
                "confidence":            99,
                "called_winner_name":    winner_eci["name"],
                "called_winner_party":   winner_eci["party"],
                "called_winner_alliance": called_alliance,
                "called_votes":          winner_eci["votes"],
                "call_status":           "called",
                "call_label":            "Called",
                "call_confidence":       "Final",
                "call_ready":            True,
                "call_reason":           "Counting complete",
            })

    # Seat tally
    tally = {"ldf": 0, "udf": 0, "nda": 0, "other": 0}
    for p in predictions.values():
        wa = p.get("called_winner_alliance") if p.get("is_called") else p["winner_alliance"]
        tally[wa] = tally.get(wa, 0) + 1

    upsets = {k: v for k, v in predictions.items() if v.get("is_upset")}
    called_count = sum(1 for p in predictions.values() if p.get("is_called"))

    output = {
        "generated_at": datetime.now().isoformat(),
        "total_active": len(predictions),
        "seat_tally":   tally,
        "called_count": called_count,
        "called_tally": called_tally,
        "upset_count":  len(upsets),
        "predictions":  predictions,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PRED_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  Predictions: {len(predictions)} constituencies")
    print(f"  Tally  ->  LDF: {tally['ldf']}  |  UDF: {tally['udf']}  |  NDA: {tally['nda']}")
    print(f"  Upsets (pattern overrides current leader): {len(upsets)}")
    for k, u in sorted(upsets.items(), key=lambda x: -x[1].get('confidence', 0))[:10]:
        lbl = {'ldf':'LDF','udf':'UDF','nda':'NDA'}
        print(f"    [{u['const_no']:>3}] {u['name']:<22} ECI:{lbl.get(u['eci_lead_alliance'],'-')} -> Pred:{lbl.get(u['winner_alliance'],'-')}  Round {u['cur_round']}/{u['tot_rounds']}  conf={u['confidence']}%")
    if unmatched:
        print(f"  Unmatched slots: {len(unmatched)} (fallback used)")
    print(f"  Saved -> {PRED_FILE}")
    return output


if __name__ == "__main__":
    run()
