#!/usr/bin/env python3
"""
Improved ML correction layer for the Kerala predictor (v2).

Improvements over v1:
  1. Extended features: historical variance across reference years,
     swing magnitude, live/baseline leader agreement, quadratic terms.
  2. Per-round models: R1 / R2 / R3 trained independently so each
     round gets its own correction weights.
  3. Cross-validated lambda: leave-one-year-out on training data,
     tuned separately per round for v2 models.

No live predictions are changed by this script.
Train on {2016, 2019, 2021, 2024}, validate on 2026 R1/R2/R3 actual results.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Iterable

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)
import sys as _sys
_sys.path.insert(0, BASE_DIR)
from predict_from_eci import HISTORY_YEAR_WEIGHTS, trend_weight

DATA_DIR = os.path.join(BASE_DIR, "data")
ALLIANCES = ("ldf", "udf", "nda")
LS_YEARS = (2019, 2024)
TARGETS_FOR_TRAINING = (2016, 2019, 2021, 2024)
VALIDATION_YEAR = 2026
ROUNDS = tuple(range(1, 13))   # R1-R12 (76% counted at R12 in 2026)
ROUNDS_EARLY = (1, 2, 3)       # original early-round subset for comparison
BOOTHS_PER_ROUND = 14
LAMBDA_CANDIDATES = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0]
ROUND_GROUPS = [
    ("R1-3 ", range(1, 4)),
    ("R4-6 ", range(4, 7)),
    ("R7-9 ", range(7, 10)),
    ("R10-12", range(10, 13)),
]


# â"€â"€ Data structures â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

@dataclass
class ElectionData:
    year: int
    const_no: int
    name: str
    candidates_key: str
    candidates: list[dict]
    booths: list[dict]
    final_by_alliance: list[int]
    final_total_all: int
    major_total: int
    votes_polled: int
    rounds: list[dict] | None = None


@dataclass
class Sample:
    target_year: int
    const_no: int
    name: str
    round_no: int
    pct: float
    live_votes: list[int]
    actual_votes: list[int]
    baseline_votes: list[int]
    baseline_shares: list[float]
    corrected_shares_target: list[float]
    features: list[float]                              # v1: 19 features
    features_v2: list[float] = field(default_factory=list)  # v2: 30 features


# â"€â"€ Data loading â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def norm_alliance(value: object) -> str:
    a = str(value or "").strip().lower()
    return a if a in ALLIANCES else "other"


def year_dir(year: int) -> str:
    if year in LS_YEARS:
        return os.path.join(DATA_DIR, f"{year}_ls")
    return os.path.join(DATA_DIR, str(year))


def candidates_key(year: int) -> str:
    return f"candidates_{year}_ls" if year in LS_YEARS else f"candidates_{year}"


def load_year(year: int) -> dict[int, ElectionData]:
    folder = year_dir(year)
    out: dict[int, ElectionData] = {}
    if not os.path.isdir(folder):
        return out

    key = candidates_key(year)
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(folder, fname)
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)

        cands = entry.get(key, [])
        totals = entry.get("booth_summary", {}).get("candidate_totals", [])
        if not totals and year == 2026:
            totals = [c.get(f"actual_votes_{year}", 0) for c in cands]

        final_by_alliance = [0, 0, 0]
        for c in cands:
            a = norm_alliance(c.get("alliance"))
            if a not in ALLIANCES or not c.get("is_major_alliance"):
                continue
            idx = c.get("index")
            if not isinstance(idx, int):
                continue
            votes = 0
            if 0 <= idx < len(totals):
                votes = int(totals[idx] or 0)
            else:
                votes = int(c.get(f"actual_votes_{year}", 0) or 0)
            ai = ALLIANCES.index(a)
            final_by_alliance[ai] += votes

        if sum(final_by_alliance) <= 0:
            continue

        final_total_all = sum(int(v or 0) for v in totals) if totals else sum(final_by_alliance)
        votes_polled = (
            entry.get("turnout", {}).get("votes_polled")
            or entry.get("booth_summary", {}).get("total_votes_in_candidate_columns")
            or final_total_all
        )

        out[int(entry["const_no"])] = ElectionData(
            year=year,
            const_no=int(entry["const_no"]),
            name=entry.get("name", ""),
            candidates_key=key,
            candidates=cands,
            booths=entry.get("booths", []) or [],
            final_by_alliance=final_by_alliance,
            final_total_all=final_total_all,
            major_total=sum(final_by_alliance),
            votes_polled=int(votes_polled or final_total_all),
            rounds=entry.get("rounds") if year == 2026 else None,
        )
    return out


def load_all_years() -> dict[int, dict[int, ElectionData]]:
    return {year: load_year(year) for year in (2011, 2016, 2019, 2021, 2024, 2026)}


# â"€â"€ Pattern extraction â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def alliance_index_map(data: ElectionData) -> dict[int, int]:
    mapping = {}
    for c in data.candidates:
        a = norm_alliance(c.get("alliance"))
        idx = c.get("index")
        if a in ALLIANCES and c.get("is_major_alliance") and isinstance(idx, int):
            mapping[idx] = ALLIANCES.index(a)
    return mapping


def historical_pattern(data: ElectionData, pct: float) -> tuple[list[float], list[float]] | None:
    if not data.booths:
        return None
    mapping = alliance_index_map(data)
    if not mapping:
        return None

    main_nos = sorted({b.get("main") for b in data.booths if not b.get("is_aux", False)})
    if not main_nos:
        return None

    target_votes = max(data.final_total_all * pct, 1)
    counted_mains: set[int] = set()
    running = 0
    for main_no in main_nos:
        rows = [b for b in data.booths if b.get("main") == main_no]
        running += sum(sum(int(x or 0) for x in b.get("votes", [])) for b in rows)
        counted_mains.add(main_no)
        if running >= target_votes:
            break

    early = [0, 0, 0]
    final = [0, 0, 0]
    for b in data.booths:
        votes = b.get("votes", [])
        for idx, ai in mapping.items():
            if idx < len(votes):
                v = int(votes[idx] or 0)
                final[ai] += v
                if b.get("main") in counted_mains:
                    early[ai] += v

    early_total = sum(early)
    remaining = [max(final[i] - early[i], 0) for i in range(3)]
    remaining_total = sum(remaining)
    if early_total <= 0 or remaining_total <= 0 or sum(final) <= 0:
        return None
    return (
        [v / early_total for v in early],
        [v / remaining_total for v in remaining],
    )


def weighted_average(patterns: list[tuple[int, list[float], list[float]]], part: int) -> list[float]:
    sums = [0.0, 0.0, 0.0]
    wsum = 0.0
    for year, early, remaining in patterns:
        weight = HISTORY_YEAR_WEIGHTS.get(year, 1)
        vec = early if part == 0 else remaining
        for i in range(3):
            sums[i] += vec[i] * weight
        wsum += weight
    return [v / wsum for v in sums] if wsum else [1 / 3, 1 / 3, 1 / 3]


def reference_years_for(target_year: int) -> list[int]:
    return [y for y in (2011, 2016, 2019, 2021, 2024) if y < target_year]


def _std_dev(vals: list[float]) -> float:
    """Population std dev across reference-year historical pattern values."""
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


# â"€â"€ Baseline projection (shared by both v1 and v2) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def baseline_project(
    all_data: dict[int, dict[int, ElectionData]],
    target_year: int,
    const_no: int,
    round_no: int,
    live_votes: list[int],
    total_counted_all: int,
) -> tuple[list[int], list[float], dict] | None:
    target = all_data[target_year].get(const_no)
    if not target or sum(live_votes) <= 0:
        return None

    pct = min(total_counted_all / max(target.votes_polled, 1), 1.0)
    if pct <= 0:
        return None

    patterns: list[tuple[int, list[float], list[float]]] = []
    for ref_year in reference_years_for(target_year):
        ref = all_data.get(ref_year, {}).get(const_no)
        if not ref:
            continue
        pat = historical_pattern(ref, pct)
        if pat:
            early, remaining = pat
            patterns.append((ref_year, early, remaining))

    sum_live = sum(live_votes)
    live_share = [v / sum_live for v in live_votes]

    if patterns:
        hist_early = weighted_average(patterns, 0)
        hist_remaining = weighted_average(patterns, 1)

        # Per-year variance -- measures how consistent historical patterns are.
        # High variance â†' patterns disagree across years â†' baseline is less reliable.
        std_hist_early = [_std_dev([p[1][i] for p in patterns]) for i in range(3)]
        std_hist_remaining = [_std_dev([p[2][i] for p in patterns]) for i in range(3)]

        damp = trend_weight(round_no)
        delta = [live_share[i] - hist_early[i] for i in range(3)]
        adj_remaining = [max(0.0, hist_remaining[i] + delta[i] * damp) for i in range(3)]
        adj_sum = sum(adj_remaining)
        if adj_sum > 0:
            adj_remaining = [v / adj_sum for v in adj_remaining]
        remaining_votes = max(target.votes_polled - sum_live, 0)
        projected = [round(live_votes[i] + adj_remaining[i] * remaining_votes) for i in range(3)]
    else:
        projected = [round(v / pct) for v in live_votes]
        hist_early = [1 / 3, 1 / 3, 1 / 3]
        hist_remaining = [1 / 3, 1 / 3, 1 / 3]
        std_hist_early = [0.0, 0.0, 0.0]
        std_hist_remaining = [0.0, 0.0, 0.0]
        delta = [live_share[i] - hist_early[i] for i in range(3)]

    proj_sum = max(sum(projected), 1)
    return (
        projected,
        [v / proj_sum for v in projected],
        {
            "pct": pct,
            "live_share": live_share,
            "hist_early": hist_early,
            "hist_remaining": hist_remaining,
            "delta": delta,
            "history_count": len(patterns),
            "std_hist_early": std_hist_early,        # NEW: pattern reliability indicator
            "std_hist_remaining": std_hist_remaining,  # NEW: pattern reliability indicator
        },
    )


# â"€â"€ Live vote extraction â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def historical_live_votes(data: ElectionData, round_no: int) -> tuple[list[int], int] | None:
    if not data.booths:
        return None
    mapping = alliance_index_map(data)
    if not mapping:
        return None
    main_nos = sorted({b.get("main") for b in data.booths if not b.get("is_aux", False)})
    cutoff = set(main_nos[: round_no * BOOTHS_PER_ROUND])
    if not cutoff:
        return None
    votes = [0, 0, 0]
    total_all = 0
    for b in data.booths:
        if b.get("main") not in cutoff:
            continue
        row_votes = b.get("votes", [])
        total_all += sum(int(v or 0) for v in row_votes)
        for idx, ai in mapping.items():
            if idx < len(row_votes):
                votes[ai] += int(row_votes[idx] or 0)
    return (votes, total_all) if sum(votes) > 0 else None


def round_live_votes_2026(data: ElectionData, round_no: int) -> tuple[list[int], int] | None:
    if not data.rounds or round_no > len(data.rounds):
        return None
    mapping = alliance_index_map(data)
    cumulative = data.rounds[round_no - 1].get("cumulative", [])
    votes = [0, 0, 0]
    for idx, ai in mapping.items():
        if idx < len(cumulative):
            votes[ai] += int(cumulative[idx] or 0)
    total_all = sum(int(v or 0) for v in cumulative)
    return (votes, total_all) if sum(votes) > 0 else None


# â"€â"€ Feature engineering â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def build_features(
    round_no: int, baseline_shares: list[float], info: dict, target: ElectionData
) -> list[float]:
    """Original v1 feature vector (19 features). Unchanged for backward compat."""
    live = info["live_share"]
    hist_e = info["hist_early"]
    hist_r = info["hist_remaining"]
    delta = info["delta"]
    sorted_base = sorted(baseline_shares, reverse=True)
    sorted_live = sorted(live, reverse=True)
    return [
        1.0,
        round_no / 3.0,
        info["pct"],
        info["history_count"] / 5.0,
        target.major_total / max(target.votes_polled, 1),
        sorted_base[0] - sorted_base[1],
        sorted_live[0] - sorted_live[1],
        *baseline_shares,
        *live,
        *hist_e,
        *hist_r,
        *delta,
    ]


def build_features_v2(
    round_no: int, baseline_shares: list[float], info: dict, target: ElectionData
) -> list[float]:
    """Extended v2 feature vector (30 features = v1 + 11 new).

    New features capture:
    - Historical variance across reference years (pattern reliability)
    - Swing magnitude (how large is the 2026 departure from history)
    - Live-vs-baseline leader agreement
    - Quadratic terms for nonlinear relationships
    """
    live = info["live_share"]
    hist_e = info["hist_early"]
    hist_r = info["hist_remaining"]
    delta = info["delta"]
    std_e = info.get("std_hist_early", [0.0, 0.0, 0.0])
    std_r = info.get("std_hist_remaining", [0.0, 0.0, 0.0])

    sorted_base = sorted(baseline_shares, reverse=True)
    sorted_live = sorted(live, reverse=True)
    abs_delta = [abs(d) for d in delta]
    live_leader = max(range(3), key=lambda i: live[i])
    base_leader = max(range(3), key=lambda i: baseline_shares[i])

    return [
        # â"€â"€ Original 19 â"€â"€
        1.0,
        round_no / 3.0,
        info["pct"],
        info["history_count"] / 5.0,
        target.major_total / max(target.votes_polled, 1),
        sorted_base[0] - sorted_base[1],
        sorted_live[0] - sorted_live[1],
        *baseline_shares,
        *live,
        *hist_e,
        *hist_r,
        *delta,
        # â"€â"€ New 11 â"€â"€
        *std_e,                                       # historical early variance per alliance (3)
        *std_r,                                       # historical remaining variance per alliance (3)
        max(abs_delta),                               # largest per-alliance swing (1)
        sum(abs_delta),                               # total swing magnitude (1)
        float(live_leader == base_leader),            # live leader agrees with baseline winner (1)
        (sorted_base[0] - sorted_base[1]) ** 2,      # quadratic projected margin (1)
        info["pct"] ** 2,                             # quadratic vote-% term (1)
    ]


# â"€â"€ Sample building â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def build_samples(
    all_data: dict[int, dict[int, ElectionData]],
    target_years: Iterable[int],
    rounds: tuple[int, ...] = ROUNDS,
) -> list[Sample]:
    samples: list[Sample] = []
    for year in target_years:
        for const_no, target in sorted(all_data.get(year, {}).items()):
            for round_no in rounds:
                live = (
                    round_live_votes_2026(target, round_no)
                    if year == 2026
                    else historical_live_votes(target, round_no)
                )
                if not live:
                    continue
                live_votes, total_counted_all = live
                base = baseline_project(all_data, year, const_no, round_no, live_votes, total_counted_all)
                if not base:
                    continue
                baseline_votes, baseline_shares, info = base
                actual_sum = max(sum(target.final_by_alliance), 1)
                actual_shares = [v / actual_sum for v in target.final_by_alliance]
                samples.append(
                    Sample(
                        target_year=year,
                        const_no=const_no,
                        name=target.name,
                        round_no=round_no,
                        pct=info["pct"],
                        live_votes=live_votes,
                        actual_votes=target.final_by_alliance,
                        baseline_votes=baseline_votes,
                        baseline_shares=baseline_shares,
                        corrected_shares_target=[
                            actual_shares[i] - baseline_shares[i] for i in range(3)
                        ],
                        features=build_features(round_no, baseline_shares, info, target),
                        features_v2=build_features_v2(round_no, baseline_shares, info, target),
                    )
                )
    return samples


# â"€â"€ Linear algebra â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def solve_linear_system(
    a: list[list[float]], b: list[list[float]]
) -> list[list[float]]:
    n = len(a)
    m = len(b[0])
    aug = [a[i][:] + b[i][:] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            continue
        aug[col], aug[pivot] = aug[pivot], aug[col]
        div = aug[col][col]
        aug[col] = [v / div for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor:
                aug[r] = [aug[r][c] - factor * aug[col][c] for c in range(n + m)]
    return [row[n:] for row in aug]


# â"€â"€ Model training â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def train_ridge(
    samples: list[Sample],
    lam: float = 1.0,
    feature_attr: str = "features",
) -> list[list[float]]:
    """Ridge regression: predict share correction from features."""
    if not samples:
        return []
    p = len(getattr(samples[0], feature_attr))
    xtx = [[0.0] * p for _ in range(p)]
    xty = [[0.0, 0.0, 0.0] for _ in range(p)]
    for s in samples:
        x = getattr(s, feature_attr)
        y = s.corrected_shares_target
        for i in range(p):
            for j in range(p):
                xtx[i][j] += x[i] * x[j]
            for k in range(3):
                xty[i][k] += x[i] * y[k]
    for i in range(1, p):
        xtx[i][i] += lam
    return solve_linear_system(xtx, xty)


def apply_model(
    sample: Sample,
    coef: list[list[float]],
    feature_attr: str = "features",
) -> list[float]:
    """Apply ridge model to get corrected share predictions."""
    x = getattr(sample, feature_attr)
    correction = [0.0, 0.0, 0.0]
    for i, xi in enumerate(x):
        for k in range(3):
            correction[k] += xi * coef[i][k]
    shares = [max(0.0, sample.baseline_shares[k] + correction[k]) for k in range(3)]
    total = sum(shares)
    return [v / total for v in shares] if total > 0 else sample.baseline_shares


def train_ridge_loglinear(
    samples: list[Sample],
    lam: float = 1.0,
    feature_attr: str = "features",
) -> list[list[float]]:
    """Ridge regression with log-ratio targets: log(actual_share) - log(baseline_share).
    Inference uses softmax so predictions always live on the simplex (no clipping needed)."""
    if not samples:
        return []
    _CLIP = 1e-4
    p = len(getattr(samples[0], feature_attr))
    xtx = [[0.0] * p for _ in range(p)]
    xty = [[0.0, 0.0, 0.0] for _ in range(p)]
    for s in samples:
        x = getattr(s, feature_attr)
        actual_sum = max(sum(s.actual_votes), 1)
        actual_sh = [v / actual_sum for v in s.actual_votes]
        y = [
            math.log(max(actual_sh[k], _CLIP)) - math.log(max(s.baseline_shares[k], _CLIP))
            for k in range(3)
        ]
        for i in range(p):
            for j in range(p):
                xtx[i][j] += x[i] * x[j]
            for k in range(3):
                xty[i][k] += x[i] * y[k]
    for i in range(1, p):
        xtx[i][i] += lam
    return solve_linear_system(xtx, xty)


def apply_model_loglinear(
    sample: Sample,
    coef: list[list[float]],
    feature_attr: str = "features",
) -> list[float]:
    """Apply log-linear model: softmax(log(baseline_shares) + correction)."""
    _CLIP = 1e-4
    x = getattr(sample, feature_attr)
    log_corr = [0.0, 0.0, 0.0]
    for i, xi in enumerate(x):
        for k in range(3):
            log_corr[k] += xi * coef[i][k]
    log_sh = [math.log(max(sample.baseline_shares[k], _CLIP)) + log_corr[k] for k in range(3)]
    max_log = max(log_sh)
    exp_sh = [math.exp(v - max_log) for v in log_sh]
    total = sum(exp_sh)
    return [v / total for v in exp_sh] if total > 0 else sample.baseline_shares


def train_ridge_2out(
    samples: list[Sample],
    lam: float = 1.0,
    feature_attr: str = "features",
) -> list[list[float]]:
    """2-output ridge: predict LDF and UDF corrections only; NDA = -(LDF+UDF).
    Returns a p×3 coefficient matrix identical to train_ridge when targets sum to 0
    (verified by algebra: beta_0+beta_1+beta_2 = (X'X+lI)^{-1} X'(y0+y1+y2) = 0)."""
    if not samples:
        return []
    p = len(getattr(samples[0], feature_attr))
    xtx = [[0.0] * p for _ in range(p)]
    xty = [[0.0, 0.0] for _ in range(p)]
    for s in samples:
        x = getattr(s, feature_attr)
        y = s.corrected_shares_target
        for i in range(p):
            for j in range(p):
                xtx[i][j] += x[i] * x[j]
            for k in range(2):
                xty[i][k] += x[i] * y[k]
    for i in range(1, p):
        xtx[i][i] += lam
    coef2 = solve_linear_system(xtx, xty)
    # Expand: NDA correction = -(LDF + UDF)
    return [[row[0], row[1], -(row[0] + row[1])] for row in coef2]


def apply_model_2out(
    sample: Sample,
    coef: list[list[float]],
    feature_attr: str = "features",
) -> list[float]:
    """Apply 2-output model (coef already has 3 columns; identical to apply_model)."""
    return apply_model(sample, coef, feature_attr)


# â"€â"€ Metrics â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def winner(values: list[float | int]) -> int:
    return max(range(len(values)), key=lambda i: values[i])


def margin(values: list[float | int]) -> float:
    order = sorted(values, reverse=True)
    return order[0] - order[1] if len(order) > 1 else order[0]


# â"€â"€ Evaluation â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def evaluate(
    samples: list[Sample],
    coef: list[list[float]] | None = None,
    feature_attr: str = "features",
) -> dict:
    rows = []
    for s in samples:
        actual_w = winner(s.actual_votes)
        base_w = winner(s.baseline_votes)
        if coef is None:
            pred_shares = s.baseline_shares
        else:
            pred_shares = apply_model(s, coef, feature_attr)
        pred_w = winner(pred_shares)
        actual_share = [v / max(sum(s.actual_votes), 1) for v in s.actual_votes]
        share_mae = sum(abs(pred_shares[i] - actual_share[i]) for i in range(3)) / 3
        rows.append(
            {
                "sample": s,
                "correct": pred_w == actual_w,
                "base_correct": base_w == actual_w,
                "pred_w": pred_w,
                "actual_w": actual_w,
                "share_mae": share_mae,
                "margin_error": abs(margin(pred_shares) - margin(actual_share)),
            }
        )
    n = len(rows) or 1
    return {
        "rows": rows,
        "accuracy": sum(1 for r in rows if r["correct"]) / n,
        "share_mae": sum(r["share_mae"] for r in rows) / n,
        "margin_error": sum(r["margin_error"] for r in rows) / n,
    }


# â"€â"€ Cross-validation â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def cross_validate_lambda(
    samples: list[Sample],
    lambda_candidates: list[float],
    feature_attr: str = "features_v2",
) -> tuple[float, float]:
    """Leave-one-training-year-out CV. Returns (best_lambda, best_cv_winner_accuracy)."""
    training_years = sorted({s.target_year for s in samples})
    if len(training_years) < 2:
        return lambda_candidates[0], 0.0

    best_lam, best_score = lambda_candidates[0], -1.0

    for lam in lambda_candidates:
        fold_accs = []
        for held_out in training_years:
            train_fold = [s for s in samples if s.target_year != held_out]
            val_fold = [s for s in samples if s.target_year == held_out]
            if not train_fold or not val_fold:
                continue
            coef = train_ridge(train_fold, lam, feature_attr)
            if not coef:
                continue
            ev = evaluate(val_fold, coef, feature_attr)
            fold_accs.append(ev["accuracy"])
        if fold_accs:
            score = sum(fold_accs) / len(fold_accs)
            if score > best_score:
                best_score = score
                best_lam = lam

    return best_lam, best_score


# â"€â"€ Display helpers â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def _row(label: str, n: int, acc: float, mae: float, merr: float) -> None:
    print(
        f"{label:<6} {n:>7}  {acc*100:>9.1f}%"
        f"  {mae*100:>8.2f}pp  {merr*100:>9.2f}pp"
    )


def print_round_summary(
    label: str,
    samples: list[Sample],
    coef: list[list[float]] | None = None,
    feature_attr: str = "features",
) -> None:
    print(label)
    print("Round  Samples  Winner acc  Share MAE  Margin err")
    for r in ROUNDS:
        subset = [s for s in samples if s.round_no == r]
        ev = evaluate(subset, coef, feature_attr)
        _row(f"R{r}", len(subset), ev["accuracy"], ev["share_mae"], ev["margin_error"])
    ev = evaluate(samples, coef, feature_attr)
    _row("ALL", len(samples), ev["accuracy"], ev["share_mae"], ev["margin_error"])


def print_per_round_summary(
    label: str,
    samples: list[Sample],
    per_round_coefs: dict[int, list[list[float]]],
    feature_attr: str = "features_v2",
) -> None:
    """Show per-round results using round-specific models."""
    print(label)
    print("Round  Samples  Winner acc  Share MAE  Margin err")
    all_rows: list[dict] = []
    for r in ROUNDS:
        subset = [s for s in samples if s.round_no == r]
        coef = per_round_coefs.get(r)
        ev = evaluate(subset, coef, feature_attr)
        _row(f"R{r}", len(subset), ev["accuracy"], ev["share_mae"], ev["margin_error"])
        all_rows.extend(ev["rows"])
    n = len(all_rows) or 1
    tot_acc = sum(1 for r in all_rows if r["correct"]) / n
    tot_mae = sum(r["share_mae"] for r in all_rows) / n
    tot_merr = sum(r["margin_error"] for r in all_rows) / n
    _row("ALL", n, tot_acc, tot_mae, tot_merr)


def print_winner_changes(
    label: str,
    samples: list[Sample],
    coef: list[list[float]],
    feature_attr: str = "features",
) -> None:
    changes = []
    for s in samples:
        actual_w = winner(s.actual_votes)
        base_w = winner(s.baseline_votes)
        ml_w = winner(apply_model(s, coef, feature_attr))
        if base_w != ml_w:
            changes.append((s, base_w, ml_w, actual_w))
    if not changes:
        print(f"\n{label}: no winner changes.")
        return
    correct = sum(1 for _, bw, mw, aw in changes if mw == aw)
    wrong = sum(1 for _, bw, mw, aw in changes if mw != aw)
    print(f"\n{label}  (correct={correct}, wrong={wrong}):")
    for s, bw, mw, aw in changes[:30]:
        ok = "+" if mw == aw else "-"
        print(
            f"  [{ok}] R{s.round_no} #{s.const_no:03d} {s.name}: "
            f"formula={ALLIANCES[bw].upper()} -> ML={ALLIANCES[mw].upper()} "
            f"actual={ALLIANCES[aw].upper()}"
        )
    if len(changes) > 30:
        print(f"  ... {len(changes) - 30} more")


# â"€â"€ Guarded-policy helpers â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def evaluate_guarded_r1(samples: list[Sample], coef: list[list[float]]) -> dict:
    """Original guarded policy: ML for R1, formula for R2/R3 (v1 features)."""
    rows = []
    for s in samples:
        actual_w = winner(s.actual_votes)
        pred_shares = apply_model(s, coef, "features") if s.round_no == 1 else s.baseline_shares
        pred_w = winner(pred_shares)
        actual_share = [v / max(sum(s.actual_votes), 1) for v in s.actual_votes]
        rows.append(
            {
                "sample": s,
                "correct": pred_w == actual_w,
                "share_mae": sum(abs(pred_shares[i] - actual_share[i]) for i in range(3)) / 3,
                "margin_error": abs(margin(pred_shares) - margin(actual_share)),
            }
        )
    n = len(rows) or 1
    return {
        "rows": rows,
        "accuracy": sum(1 for r in rows if r["correct"]) / n,
        "share_mae": sum(r["share_mae"] for r in rows) / n,
        "margin_error": sum(r["margin_error"] for r in rows) / n,
    }


def evaluate_guarded_v2(
    samples: list[Sample],
    per_round_coefs: dict[int, list[list[float]]],
    use_ml_for: set[int],
    feature_attr: str = "features_v2",
) -> dict:
    """Flexible guarded policy: use ML for rounds in use_ml_for, formula otherwise."""
    rows = []
    for s in samples:
        actual_w = winner(s.actual_votes)
        coef = per_round_coefs.get(s.round_no) if s.round_no in use_ml_for else None
        pred_shares = apply_model(s, coef, feature_attr) if coef else s.baseline_shares
        pred_w = winner(pred_shares)
        actual_share = [v / max(sum(s.actual_votes), 1) for v in s.actual_votes]
        rows.append(
            {
                "sample": s,
                "correct": pred_w == actual_w,
                "share_mae": sum(abs(pred_shares[i] - actual_share[i]) for i in range(3)) / 3,
                "margin_error": abs(margin(pred_shares) - margin(actual_share)),
            }
        )
    n = len(rows) or 1
    return {
        "rows": rows,
        "accuracy": sum(1 for r in rows if r["correct"]) / n,
        "share_mae": sum(r["share_mae"] for r in rows) / n,
        "margin_error": sum(r["margin_error"] for r in rows) / n,
    }


# ── Grouped evaluation helper ─────────────────────────────────────────────────

def eval_rounds(
    samples: list[Sample],
    round_set,
    coef: list[list[float]] | None = None,
    feature_attr: str = "features",
    per_round_coefs: dict[int, list[list[float]]] | None = None,
) -> dict:
    """Evaluate a specific set of rounds, using per-round models if provided."""
    all_rows: list[dict] = []
    for r in round_set:
        subset = [s for s in samples if s.round_no == r]
        if not subset:
            continue
        c = per_round_coefs.get(r) if per_round_coefs else coef
        ev = evaluate(subset, c, feature_attr)
        all_rows.extend(ev["rows"])
    n = len(all_rows) or 1
    return {
        "n": n,
        "accuracy": sum(1 for r in all_rows if r["correct"]) / n,
        "share_mae": sum(r["share_mae"] for r in all_rows) / n,
        "margin_error": sum(r["margin_error"] for r in all_rows) / n,
    }


def print_grouped_summary(
    label: str,
    samples: list[Sample],
    coef: list[list[float]] | None = None,
    feature_attr: str = "features",
    per_round_coefs: dict[int, list[list[float]]] | None = None,
    rounds: tuple[int, ...] = ROUNDS,
) -> None:
    print(label)
    print("Group   Samples  Winner acc  Share MAE  Margin err")
    for gname, rrange in ROUND_GROUPS:
        rset = [r for r in rrange if r in rounds]
        if not rset:
            continue
        ev = eval_rounds(samples, rset, coef, feature_attr, per_round_coefs)
        if ev["n"] == 0:
            continue
        _row(gname, ev["n"], ev["accuracy"], ev["share_mae"], ev["margin_error"])
    ev_all = eval_rounds(samples, rounds, coef, feature_attr, per_round_coefs)
    _row("ALL   ", ev_all["n"], ev_all["accuracy"], ev_all["share_mae"], ev_all["margin_error"])


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    sep = "=" * 72
    print("Loading historical data...")
    all_data = load_all_years()

    # Full R1-R12 datasets (new experiment)
    train_full  = build_samples(all_data, TARGETS_FOR_TRAINING, rounds=ROUNDS)
    val_full    = build_samples(all_data, (VALIDATION_YEAR,),   rounds=ROUNDS)

    # Early R1-R3 only (original experiment for comparison)
    train_early = build_samples(all_data, TARGETS_FOR_TRAINING, rounds=ROUNDS_EARLY)
    val_early   = build_samples(all_data, (VALIDATION_YEAR,),   rounds=ROUNDS_EARLY)

    if not train_full or not val_full:
        raise SystemExit("Not enough samples -- check data directories.")

    n_feat_v1 = len(train_full[0].features)
    n_feat_v2 = len(train_full[0].features_v2)
    print(f"Training R1-R12 : {len(train_full)} samples  ({len(train_full)//len(ROUNDS)} avg/round)")
    print(f"Training R1-R3  : {len(train_early)} samples (original)")
    print(f"Validation R1-R12: {len(val_full)} samples ({len(val_full)//len(ROUNDS)} avg/round)")
    print(f"Features : v1={n_feat_v1}  v2={n_feat_v2}")
    print()

    # ── 1. Baseline formula across R1-R12 ──────────────────────────────────
    print(sep)
    print("1. BASELINE FORMULA -- 2026 validation R1-R12")
    print()
    print("Round  Samples  Winner acc  Share MAE  Margin err")
    for r in ROUNDS:
        subset = [s for s in val_full if s.round_no == r]
        if not subset:
            continue
        ev = evaluate(subset)
        _row(f"R{r}", len(subset), ev["accuracy"], ev["share_mae"], ev["margin_error"])
    print_grouped_summary("Grouped:", val_full, rounds=ROUNDS)
    print()

    # ── 2. ML v1 single model: compare R1-R3 training vs R1-R12 training ──
    print(sep)
    print("2. IMPACT OF ADDING R4-R12 TO TRAINING (v1 features, lam=2.0)")
    print("   Comparing models trained on R1-R3 only vs R1-R12, evaluated on R1-R3 validation")
    print()
    coef_v1_early = train_ridge(train_early, lam=2.0, feature_attr="features")
    coef_v1_full  = train_ridge(train_full,  lam=2.0, feature_attr="features")

    print("Model             R1 acc    R2 acc    R3 acc   ALL(R1-3) acc")
    for label, coef in [("Formula (no ML)", None), ("v1 trained R1-3 ", coef_v1_early), ("v1 trained R1-12", coef_v1_full)]:
        accs = []
        for r in ROUNDS_EARLY:
            subset = [s for s in val_early if s.round_no == r]
            ev = evaluate(subset, coef, "features")
            accs.append(ev["accuracy"] * 100)
        ev_all = evaluate(val_early, coef, "features")
        print(f"  {label}  {accs[0]:>6.1f}%   {accs[1]:>6.1f}%   {accs[2]:>6.1f}%     {ev_all['accuracy']*100:>6.1f}%")
    print()
    print("Margin error (pp):")
    for label, coef in [("Formula (no ML)", None), ("v1 trained R1-3 ", coef_v1_early), ("v1 trained R1-12", coef_v1_full)]:
        merrs = []
        for r in ROUNDS_EARLY:
            subset = [s for s in val_early if s.round_no == r]
            ev = evaluate(subset, coef, "features")
            merrs.append(ev["margin_error"] * 100)
        ev_all = evaluate(val_early, coef, "features")
        print(f"  {label}  {merrs[0]:>5.2f}pp  {merrs[1]:>5.2f}pp  {merrs[2]:>5.2f}pp    {ev_all['margin_error']*100:>5.2f}pp")
    print()

    # ── 3. ML v1 per-round across R1-R12 (trained on R1-R12) ──────────────
    print(sep)
    print("3. ML v1 SINGLE MODEL (trained on R1-R12) -- full round evaluation")
    print("Round  Samples  Winner acc  Share MAE  Margin err")
    for r in ROUNDS:
        subset = [s for s in val_full if s.round_no == r]
        if not subset:
            continue
        ev = evaluate(subset, coef_v1_full, "features")
        _row(f"R{r}", len(subset), ev["accuracy"], ev["share_mae"], ev["margin_error"])
    print_grouped_summary("Grouped:", val_full, coef=coef_v1_full, feature_attr="features", rounds=ROUNDS)
    print()

    # ── 4. ML v2 per-round models with CV lambda across R1-R12 ────────────
    print(sep)
    print("4. ML v2 PER-ROUND MODELS (30 features, CV lambda per round)")
    print("   Cross-validating lambda for each round...")
    per_round_coefs: dict[int, list[list[float]]] = {}
    per_round_lambdas: dict[int, float] = {}
    cv_pr_acc: dict[int, float] = {}
    baseline_cv: dict[int, float] = {}

    for r in ROUNDS:
        train_r = [s for s in train_full if s.round_no == r]
        best_lam_r, cv_ml_r = cross_validate_lambda(train_r, LAMBDA_CANDIDATES, "features_v2")
        per_round_coefs[r]  = train_ridge(train_r, lam=best_lam_r, feature_attr="features_v2")
        per_round_lambdas[r] = best_lam_r
        cv_pr_acc[r] = cv_ml_r
        # CV baseline (formula) for same round
        training_years = sorted({s.target_year for s in train_r})
        fold_accs = []
        for held_out in training_years:
            val_fold = [s for s in train_r if s.target_year == held_out]
            if val_fold:
                fold_accs.append(evaluate(val_fold)["accuracy"])
        baseline_cv[r] = sum(fold_accs) / len(fold_accs) if fold_accs else 0.0
        print(f"  R{r:>2}: lam={best_lam_r:>5}  CV formula={baseline_cv[r]*100:>5.1f}%  CV ML={cv_ml_r*100:>5.1f}%")

    print()
    print("Validation results:")
    print("Round  Samples  Winner acc  Share MAE  Margin err")
    for r in ROUNDS:
        subset = [s for s in val_full if s.round_no == r]
        if not subset:
            continue
        ev = evaluate(subset, per_round_coefs.get(r), "features_v2")
        _row(f"R{r}", len(subset), ev["accuracy"], ev["share_mae"], ev["margin_error"])
    print_grouped_summary("Grouped:", val_full, per_round_coefs=per_round_coefs, feature_attr="features_v2", rounds=ROUNDS)
    print()

    # ── 5. Guarded policy: use ML only where CV shows benefit ─────────────
    use_ml_for: set[int] = {r for r in ROUNDS if cv_pr_acc[r] >= baseline_cv[r]}
    print(sep)
    print("5. GUARDED POLICY (ML v2 per-round only where CV improves winner accuracy)")
    print()
    print(f"  {'Round':>5}  {'Pct':>5}  {'CV Formula':>10}  {'CV ML v2':>9}  {'Decision':>8}")
    for r in ROUNDS:
        pct_label = f"~{round((r / len(ROUNDS)) * 76)}%"  # approx vote % at this round
        decision = "ML" if r in use_ml_for else "formula"
        print(f"  R{r:>2}   {pct_label:>5}  {baseline_cv[r]*100:>9.1f}%  {cv_pr_acc[r]*100:>8.1f}%  {decision:>8}")
    print()
    print("Validation results with guarded policy:")
    print("Round  Samples  Winner acc  Share MAE  Margin err  Source")
    all_c, all_mae, all_merr, all_n = 0.0, 0.0, 0.0, 0
    for r in ROUNDS:
        subset = [s for s in val_full if s.round_no == r]
        if not subset:
            continue
        if r in use_ml_for:
            ev = evaluate(subset, per_round_coefs.get(r), "features_v2")
            src = "ML v2"
        else:
            ev = evaluate(subset)
            src = "Formula"
        n = len(subset)
        all_c += ev["accuracy"] * n
        all_mae += ev["share_mae"] * n
        all_merr += ev["margin_error"] * n
        all_n += n
        print(
            f"R{r:<5} {n:>7}  {ev['accuracy']*100:>9.1f}%"
            f"  {ev['share_mae']*100:>8.2f}pp  {ev['margin_error']*100:>9.2f}pp"
            f"  {src}"
        )
    if all_n:
        print(f"ALL    {all_n:>7}  {all_c/all_n*100:>9.1f}%"
              f"  {all_mae/all_n*100:>8.2f}pp  {all_merr/all_n*100:>9.2f}pp")
    print()

    # ── 6. Full comparison table ───────────────────────────────────────────
    print(sep)
    print("6. SUMMARY TABLE -- winner accuracy by round group")
    print()
    print(f"{'Group':>7}  {'Formula':>8}  {'v1 R1-3':>8}  {'v1 R1-12':>9}  {'v2 per-R':>9}  {'Guarded':>8}")
    for gname, rrange in ROUND_GROUPS:
        rset = [r for r in rrange if r in ROUNDS]
        if not rset:
            continue
        f_ev  = eval_rounds(val_full, rset)
        v1e   = eval_rounds(val_early if all(r <= 3 for r in rset) else val_full, rset, coef_v1_early, "features")
        v1f   = eval_rounds(val_full, rset, coef_v1_full, "features")
        v2pr  = eval_rounds(val_full, rset, per_round_coefs=per_round_coefs, feature_attr="features_v2")
        grd   = eval_rounds(val_full, rset, per_round_coefs={r: per_round_coefs[r] if r in use_ml_for else None for r in rset}, feature_attr="features_v2")
        print(
            f"{gname:>7}  {f_ev['accuracy']*100:>7.1f}%  {v1e['accuracy']*100:>7.1f}%"
            f"  {v1f['accuracy']*100:>8.1f}%  {v2pr['accuracy']*100:>8.1f}%  {grd['accuracy']*100:>7.1f}%"
        )
    # All rounds
    f_all  = eval_rounds(val_full, ROUNDS)
    v1f_all = eval_rounds(val_full, ROUNDS, coef_v1_full, "features")
    v2pr_all = eval_rounds(val_full, ROUNDS, per_round_coefs=per_round_coefs, feature_attr="features_v2")
    grd_all  = eval_rounds(val_full, ROUNDS, per_round_coefs={r: per_round_coefs[r] if r in use_ml_for else None for r in ROUNDS}, feature_attr="features_v2")
    print(f"{'ALL':>7}  {f_all['accuracy']*100:>7.1f}%  {'N/A':>7}  {v1f_all['accuracy']*100:>8.1f}%  {v2pr_all['accuracy']*100:>8.1f}%  {grd_all['accuracy']*100:>7.1f}%")
    print()
    print("Margin error by round group:")
    print(f"{'Group':>7}  {'Formula':>8}  {'v1 R1-12':>9}  {'v2 per-R':>9}  {'Guarded':>8}")
    for gname, rrange in ROUND_GROUPS:
        rset = [r for r in rrange if r in ROUNDS]
        if not rset:
            continue
        f_ev  = eval_rounds(val_full, rset)
        v1f   = eval_rounds(val_full, rset, coef_v1_full, "features")
        v2pr  = eval_rounds(val_full, rset, per_round_coefs=per_round_coefs, feature_attr="features_v2")
        grd   = eval_rounds(val_full, rset, per_round_coefs={r: per_round_coefs[r] if r in use_ml_for else None for r in rset}, feature_attr="features_v2")
        print(
            f"{gname:>7}  {f_ev['margin_error']*100:>7.2f}pp  {v1f['margin_error']*100:>8.2f}pp"
            f"  {v2pr['margin_error']*100:>8.2f}pp  {grd['margin_error']*100:>7.2f}pp"
        )
    f_all_m  = eval_rounds(val_full, ROUNDS)
    v1f_all_m = eval_rounds(val_full, ROUNDS, coef_v1_full, "features")
    v2pr_all_m = eval_rounds(val_full, ROUNDS, per_round_coefs=per_round_coefs, feature_attr="features_v2")
    grd_all_m  = eval_rounds(val_full, ROUNDS, per_round_coefs={r: per_round_coefs[r] if r in use_ml_for else None for r in ROUNDS}, feature_attr="features_v2")
    print(f"{'ALL':>7}  {f_all_m['margin_error']*100:>7.2f}pp  {v1f_all_m['margin_error']*100:>8.2f}pp"
          f"  {v2pr_all_m['margin_error']*100:>8.2f}pp  {grd_all_m['margin_error']*100:>7.2f}pp")
    print()

    # ── 7. Winner changes on R1-R3 (guarded v2 per-round, R1-R12 trained) ─
    print(sep)
    print("7. WINNER CHANGES -- R1-R3 with guarded ML (v2 per-round, R1-R12 trained)")
    for r in ROUNDS_EARLY:
        subset = [s for s in val_full if s.round_no == r]
        if r in use_ml_for and per_round_coefs.get(r):
            print_winner_changes(f"R{r} (ML v2 per-round)", subset, per_round_coefs[r], "features_v2")
        else:
            ev_r = evaluate(subset)
            print(f"\nR{r} (Formula, {ev_r['accuracy']*100:.1f}% acc -- ML not selected by CV)")

    # ── 8. Constraint experiment: additive vs log-linear vs 2-out ─────────
    print()
    print(sep)
    print("8. CONSTRAINT EXPERIMENT -- Improvement #3")
    print("   Additive (current) | Log-linear (softmax) | 2-out constrained")
    print("   All: lam=2.0, v1 features, trained on R1-R12, evaluated on 2026 R1-R12")
    print()

    coef_ll   = train_ridge_loglinear(train_full, lam=2.0, feature_attr="features")
    coef_2out = train_ridge_2out(train_full,      lam=2.0, feature_attr="features")

    def _eval_fn(samples: list[Sample], apply_fn) -> dict:
        rows = []
        for s in samples:
            actual_w   = winner(s.actual_votes)
            pred_sh    = apply_fn(s)
            pred_w     = winner(pred_sh)
            actual_sh  = [v / max(sum(s.actual_votes), 1) for v in s.actual_votes]
            smae       = sum(abs(pred_sh[i] - actual_sh[i]) for i in range(3)) / 3
            merr       = abs(margin(pred_sh) - margin(actual_sh))
            rows.append({"correct": pred_w == actual_w, "smae": smae, "merr": merr})
        n = len(rows) or 1
        return {
            "n": n,
            "accuracy":     sum(1 for r in rows if r["correct"]) / n,
            "share_mae":    sum(r["smae"] for r in rows) / n,
            "margin_error": sum(r["merr"] for r in rows) / n,
        }

    _models = [
        ("Formula    ", lambda s:           s.baseline_shares),
        ("Additive v1", lambda s, c=coef_v1_full: apply_model(s, c, "features")),
        ("Log-linear ", lambda s, c=coef_ll:      apply_model_loglinear(s, c, "features")),
        ("2-out      ", lambda s, c=coef_2out:     apply_model_2out(s, c, "features")),
    ]

    print(f"{'Model':<14}  {'R1-3':>7}  {'R4-6':>7}  {'R7-9':>7}  {'R10-12':>8}  {'ALL':>7}  {'MAE':>7}  {'MarErr':>8}")
    for _label, _fn in _models:
        _gcols = []
        for _, _rrange in ROUND_GROUPS:
            _rset   = [r for r in _rrange if r in ROUNDS]
            _subset = [s for s in val_full if s.round_no in _rset]
            _gcols.append(_eval_fn(_subset, _fn)["accuracy"] * 100)
        _ev = _eval_fn(val_full, _fn)
        print(
            f"{_label}  {_gcols[0]:>6.1f}%  {_gcols[1]:>6.1f}%  {_gcols[2]:>6.1f}%"
            f"  {_gcols[3]:>7.1f}%  {_ev['accuracy']*100:>6.1f}%"
            f"  {_ev['share_mae']*100:>6.2f}pp  {_ev['margin_error']*100:>7.2f}pp"
        )
    print()
    print("  Note: '2-out' derives NDA = -(LDF+UDF). If it matches 'Additive v1'")
    print("  exactly, the zero-sum constraint is already implicit (proven by algebra).")
    print("  Log-linear avoids share-clipping by working in log-ratio space.")


if __name__ == "__main__":
    main()



