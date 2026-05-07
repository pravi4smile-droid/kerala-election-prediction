#!/usr/bin/env python3
"""
Experimental ML correction layer for the Kerala predictor.

This does not change live predictions. It trains a small ridge-regression
correction model on historical simulated rounds and validates on 2026 R1/R2/R3.
No third-party ML dependency is required.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Iterable

from predict_from_eci import HISTORY_YEAR_WEIGHTS, trend_weight


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ALLIANCES = ("ldf", "udf", "nda")
ASSEMBLY_YEARS = (2011, 2016, 2021)
LS_YEARS = (2019, 2024)
TARGETS_FOR_TRAINING = (2016, 2019, 2021, 2024)
VALIDATION_YEAR = 2026
ROUNDS = (1, 2, 3)
BOOTHS_PER_ROUND = 14


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
    features: list[float]


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
        major_indices: dict[int, int] = {}
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
            major_indices[idx] = ai

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

    # Match current vote progress by accumulated all-candidate votes, not just booth count.
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

    patterns = []
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
        },
    )


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


def build_features(round_no: int, baseline_shares: list[float], info: dict, target: ElectionData) -> list[float]:
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


def build_samples(all_data: dict[int, dict[int, ElectionData]], target_years: Iterable[int]) -> list[Sample]:
    samples: list[Sample] = []
    for year in target_years:
        for const_no, target in sorted(all_data.get(year, {}).items()):
            for round_no in ROUNDS:
                live = round_live_votes_2026(target, round_no) if year == 2026 else historical_live_votes(target, round_no)
                if not live:
                    continue
                live_votes, total_counted_all = live
                base = baseline_project(all_data, year, const_no, round_no, live_votes, total_counted_all)
                if not base:
                    continue
                baseline_votes, baseline_shares, info = base
                actual_sum = max(sum(target.final_by_alliance), 1)
                actual_shares = [v / actual_sum for v in target.final_by_alliance]
                features = build_features(round_no, baseline_shares, info, target)
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
                        corrected_shares_target=[actual_shares[i] - baseline_shares[i] for i in range(3)],
                        features=features,
                    )
                )
    return samples


def solve_linear_system(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
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


def train_ridge(samples: list[Sample], lam: float = 1.0) -> list[list[float]]:
    p = len(samples[0].features)
    xtx = [[0.0 for _ in range(p)] for _ in range(p)]
    xty = [[0.0, 0.0, 0.0] for _ in range(p)]
    for s in samples:
        x = s.features
        y = s.corrected_shares_target
        for i in range(p):
            for j in range(p):
                xtx[i][j] += x[i] * x[j]
            for k in range(3):
                xty[i][k] += x[i] * y[k]
    for i in range(1, p):
        xtx[i][i] += lam
    return solve_linear_system(xtx, xty)


def apply_model(sample: Sample, coef: list[list[float]]) -> list[float]:
    correction = [0.0, 0.0, 0.0]
    for i, x in enumerate(sample.features):
        for k in range(3):
            correction[k] += x * coef[i][k]
    shares = [max(0.0, sample.baseline_shares[k] + correction[k]) for k in range(3)]
    total = sum(shares)
    return [v / total for v in shares] if total > 0 else sample.baseline_shares


def winner(values: list[float | int]) -> int:
    return max(range(len(values)), key=lambda i: values[i])


def margin(values: list[float | int]) -> float:
    order = sorted(values, reverse=True)
    return order[0] - order[1] if len(order) > 1 else order[0]


def evaluate(samples: list[Sample], coef: list[list[float]] | None = None) -> dict:
    rows = []
    for s in samples:
        actual_w = winner(s.actual_votes)
        base_w = winner(s.baseline_votes)
        if coef is None:
            pred_shares = s.baseline_shares
        else:
            pred_shares = apply_model(s, coef)
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


def print_round_summary(label: str, samples: list[Sample], coef: list[list[float]] | None = None) -> None:
    print(label)
    print("Round  Samples  Winner acc  Share MAE  Margin err")
    for r in ROUNDS:
        subset = [s for s in samples if s.round_no == r]
        ev = evaluate(subset, coef)
        print(
            f"R{r:<5} {len(subset):>7}  {ev['accuracy']*100:>9.1f}%"
            f"  {ev['share_mae']*100:>8.2f}pp  {ev['margin_error']*100:>9.2f}pp"
        )
    ev = evaluate(samples, coef)
    print(
        f"ALL    {len(samples):>7}  {ev['accuracy']*100:>9.1f}%"
        f"  {ev['share_mae']*100:>8.2f}pp  {ev['margin_error']*100:>9.2f}pp"
    )


def print_changed_2026(samples: list[Sample], coef: list[list[float]]) -> None:
    rows = []
    for s in samples:
        actual_w = winner(s.actual_votes)
        base_w = winner(s.baseline_votes)
        ml_w = winner(apply_model(s, coef))
        if base_w != ml_w:
            rows.append((s, base_w, ml_w, actual_w))
    if not rows:
        print("\nML changed no 2026 R1/R2/R3 winners.")
        return
    print("\n2026 winner changes by ML layer:")
    for s, base_w, ml_w, actual_w in rows[:40]:
        print(
            f"  R{s.round_no} #{s.const_no:03d} {s.name}: "
            f"formula={ALLIANCES[base_w].upper()} -> ML={ALLIANCES[ml_w].upper()} "
            f"actual={ALLIANCES[actual_w].upper()}"
        )
    if len(rows) > 40:
        print(f"  ... {len(rows) - 40} more")


def evaluate_guarded_r1(samples: list[Sample], coef: list[list[float]]) -> dict:
    rows = []
    for s in samples:
        actual_w = winner(s.actual_votes)
        if s.round_no == 1:
            pred_shares = apply_model(s, coef)
        else:
            pred_shares = s.baseline_shares
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


def print_guarded_summary(samples: list[Sample], coef: list[list[float]]) -> None:
    print("\nRecommended guarded policy: ML correction only for R1, formula for R2+")
    print("Round  Samples  Winner acc  Share MAE  Margin err")
    for r in ROUNDS:
        subset = [s for s in samples if s.round_no == r]
        if r == 1:
            ev = evaluate(subset, coef)
        else:
            ev = evaluate(subset)
        print(
            f"R{r:<5} {len(subset):>7}  {ev['accuracy']*100:>9.1f}%"
            f"  {ev['share_mae']*100:>8.2f}pp  {ev['margin_error']*100:>9.2f}pp"
        )
    ev = evaluate_guarded_r1(samples, coef)
    print(
        f"ALL    {len(samples):>7}  {ev['accuracy']*100:>9.1f}%"
        f"  {ev['share_mae']*100:>8.2f}pp  {ev['margin_error']*100:>9.2f}pp"
    )


def main() -> None:
    all_data = load_all_years()
    train = build_samples(all_data, TARGETS_FOR_TRAINING)
    validate = build_samples(all_data, (VALIDATION_YEAR,))
    if not train or not validate:
        raise SystemExit("Not enough samples to train/validate.")

    coef = train_ridge(train, lam=2.0)

    print("=" * 72)
    print("ML prediction correction experiment")
    print("=" * 72)
    print(f"Training targets: {', '.join(map(str, TARGETS_FOR_TRAINING))}")
    print(f"Training samples: {len(train)}")
    print(f"Validation target: {VALIDATION_YEAR}")
    print(f"Validation samples: {len(validate)}")
    print()
    print_round_summary("Baseline formula on 2026 validation", validate)
    print()
    print_round_summary("ML-corrected formula on 2026 validation", validate, coef)
    print_guarded_summary(validate, coef)
    print_changed_2026(validate, coef)


if __name__ == "__main__":
    main()
