#!/usr/bin/env python3
"""
Round-by-round seat accumulation simulation: Formula vs ML v1.

For each round R1-R25, projects the winner of each 2026 constituency using:
  (a) the mathematical formula  (baseline_project from ml_prediction_experiment)
  (b) ML v1 correction layer   (lam=2.0, trained on R1-R12 of 2016/2019/2021/2024)

A seat is "called" when assess_call_readiness returns call_ready=True.

Output:
  - Formula seat-accumulation table  (Add/Cum per alliance + False per round)
  - ML v1 seat-accumulation table
  - Delta table (ML minus Formula)
"""

import os, sys
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_SCRIPT_DIR))  # project root for predict_from_eci
sys.path.insert(0, _SCRIPT_DIR)  # data_pipeline for ml_prediction_experiment

from predict_from_eci import assess_call_readiness
from ml_prediction_experiment import (
    load_all_years, baseline_project, build_features, apply_model,
    train_ridge, build_samples, ALLIANCES, TARGETS_FOR_TRAINING, ROUNDS,
    ElectionData, Sample,
)

ALLIANCES_LIST = ["ldf", "udf", "nda"]
MAX_SIM_ROUNDS = 25    # simulate up to this round number


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_2026_live(ed: ElectionData, round_no: int) -> tuple[list[int], int] | None:
    """Alliance-level cumulative votes + total all-candidate votes at end of round_no."""
    if not ed.rounds or round_no > len(ed.rounds):
        return None
    rnd = ed.rounds[round_no - 1]
    cumulative = rnd.get("cumulative", [])
    if not cumulative:
        return None
    # build mapping index -> alliance_index from candidates
    idx_to_ai: dict[int, int] = {}
    for c in ed.candidates:
        a = str(c.get("alliance", "")).lower()
        if a not in ALLIANCES_LIST or not c.get("is_major_alliance"):
            continue
        idx = c.get("index")
        if isinstance(idx, int):
            idx_to_ai[idx] = ALLIANCES_LIST.index(a)
    votes = [0, 0, 0]
    for idx, ai in idx_to_ai.items():
        if idx < len(cumulative):
            votes[ai] += int(cumulative[idx] or 0)
    total_all = sum(int(v or 0) for v in cumulative)
    return (votes, total_all) if sum(votes) > 0 else None


def projected_margin(proj: list[int]) -> tuple[int, int]:
    """Return (winner_idx, margin)."""
    w = max(range(len(proj)), key=lambda i: proj[i])
    sorted_proj = sorted(proj, reverse=True)
    m = sorted_proj[0] - sorted_proj[1] if len(sorted_proj) > 1 else sorted_proj[0]
    return w, m


def confidence_for(pct: float, margin: int, proj_total: int) -> int:
    return min(round(
        pct * 55 +
        (margin / max(proj_total, 1)) * 150 +
        (10 if pct > 0.5 else 0) +
        (5  if pct > 0.7 else 0)
    ), 99)


# ---------------------------------------------------------------------------
# Build shift patterns for assess_call_readiness
# We accumulate per-round deltas (in pp) for each constituency.
# ---------------------------------------------------------------------------

def build_pred_dict(
    projected: list[int],
    pct: float,
    delta_frac: list[float],
    round_no: int,
    tot_rounds: int,
) -> dict:
    """Minimal pred dict accepted by assess_call_readiness."""
    w, m = projected_margin(projected)
    proj_total = sum(projected)
    conf = confidence_for(pct, m, proj_total)
    return {
        "projected": projected,
        "total_projected": proj_total,
        "winner_idx": w,
        "margin": m,
        "confidence": conf,
        "pct_counted": round(pct * 100),
        "formula": {
            "pct": round(pct * 100, 2),
            "delta": [round(d * 100, 2) for d in delta_frac],  # convert to pp for stability check
        },
    }


# ---------------------------------------------------------------------------
# Main simulation
# ---------------------------------------------------------------------------

def simulate():
    print("Loading historical + 2026 data...")
    all_data = load_all_years()
    data_2026 = all_data.get(2026, {})
    if not data_2026:
        print("No 2026 data — check data/2026/")
        return

    print(f"  2026 constituencies loaded: {len(data_2026)}")

    # ── Train ML v1 on R1-R12 ──────────────────────────────────────────────
    print("Training ML v1 (lam=2.0, R1-R12 of 2016/2019/2021/2024)...")
    train_samples = build_samples(all_data, TARGETS_FOR_TRAINING, rounds=ROUNDS)
    if not train_samples:
        print("No training samples — check data directories.")
        return
    ml_coef = train_ridge(train_samples, lam=2.0, feature_attr="features")
    print(f"  Trained on {len(train_samples)} samples")
    print()

    # ── Determine actual winners ───────────────────────────────────────────
    actual_winner: dict[int, int] = {}  # const_no -> alliance index
    for cno, ed in data_2026.items():
        if sum(ed.final_by_alliance) > 0:
            actual_winner[cno] = max(range(3), key=lambda i: ed.final_by_alliance[i])

    tot_rounds_map = {cno: len(ed.rounds) for cno, ed in data_2026.items() if ed.rounds}

    # ── Per-constituency state ─────────────────────────────────────────────
    # called[cno] = (round_called, predicted_ai)
    formula_called: dict[int, tuple[int, int]] = {}
    ml_called:      dict[int, tuple[int, int]] = {}
    # Accumulated shift patterns for stability check
    shift_pats: dict[int, list[list[float]]] = {cno: [] for cno in data_2026}

    # ── Round-by-round loop ────────────────────────────────────────────────
    max_round = min(
        max(tot_rounds_map.values(), default=0),
        MAX_SIM_ROUNDS,
    )
    for round_no in range(1, max_round + 1):
        for cno, ed in sorted(data_2026.items()):
            # Skip if both already called
            if cno in formula_called and cno in ml_called:
                continue

            tot_rounds = tot_rounds_map.get(cno, 0)
            if tot_rounds == 0:
                continue

            live = get_2026_live(ed, round_no)
            if not live:
                continue
            live_votes, total_counted = live

            base = baseline_project(
                all_data, 2026, cno, round_no, live_votes, total_counted
            )
            if not base:
                continue
            baseline_proj, baseline_shares, info = base

            pct_frac  = info["pct"]
            delta_frac = info["delta"]   # fraction scale (0-1)

            # Update shift patterns with current round delta (in pp for assess_call_readiness)
            delta_pp = [d * 100 for d in delta_frac]
            shift_pats[cno].append(delta_pp)
            prev_shifts = shift_pats[cno][:-1]  # patterns from *previous* rounds only

            # ── Formula call ───────────────────────────────────────────────
            if cno not in formula_called:
                pred_f = build_pred_dict(baseline_proj, pct_frac, delta_frac, round_no, tot_rounds)
                call_f = assess_call_readiness(
                    pred_f, round_no, tot_rounds,
                    live_votes=live_votes,
                    previous_leaders=None,
                    previous_shift_patterns=prev_shifts,
                )
                if call_f["call_ready"]:
                    formula_called[cno] = (round_no, pred_f["winner_idx"])

            # ── ML v1 call ─────────────────────────────────────────────────
            if cno not in ml_called:
                sample = Sample(
                    target_year=2026,
                    const_no=cno,
                    name=ed.name,
                    round_no=round_no,
                    pct=pct_frac,
                    live_votes=live_votes,
                    actual_votes=ed.final_by_alliance,
                    baseline_votes=baseline_proj,
                    baseline_shares=baseline_shares,
                    corrected_shares_target=[0.0, 0.0, 0.0],
                    features=build_features(round_no, baseline_shares, info, ed),
                )
                ml_shares = apply_model(sample, ml_coef, feature_attr="features")
                proj_total = max(sum(baseline_proj), 1)
                ml_proj = [round(ml_shares[i] * proj_total) for i in range(3)]

                pred_m = build_pred_dict(ml_proj, pct_frac, delta_frac, round_no, tot_rounds)
                call_m = assess_call_readiness(
                    pred_m, round_no, tot_rounds,
                    live_votes=live_votes,
                    previous_leaders=None,
                    previous_shift_patterns=prev_shifts,
                )
                if call_m["call_ready"]:
                    ml_called[cno] = (round_no, pred_m["winner_idx"])

    # ── Force-call any remaining seats at their last available round ───────
    for cno, ed in data_2026.items():
        tot_rounds = tot_rounds_map.get(cno, 0)
        if tot_rounds == 0:
            continue
        final_round = min(tot_rounds, MAX_SIM_ROUNDS)
        live = get_2026_live(ed, final_round)
        if not live:
            continue
        live_votes, total_counted = live

        base = baseline_project(all_data, 2026, cno, final_round, live_votes, total_counted)
        if base:
            baseline_proj, baseline_shares, info = base
            if cno not in formula_called:
                w, _ = projected_margin(baseline_proj)
                formula_called[cno] = (final_round + 1, w)   # +1 = effectively "very late"
            if cno not in ml_called:
                sample = Sample(
                    target_year=2026, const_no=cno, name=ed.name,
                    round_no=final_round, pct=info["pct"],
                    live_votes=live_votes, actual_votes=ed.final_by_alliance,
                    baseline_votes=baseline_proj, baseline_shares=baseline_shares,
                    corrected_shares_target=[0.0, 0.0, 0.0],
                    features=build_features(final_round, baseline_shares, info, ed),
                )
                ml_shares = apply_model(sample, ml_coef, feature_attr="features")
                proj_total = max(sum(baseline_proj), 1)
                ml_proj = [round(ml_shares[i] * proj_total) for i in range(3)]
                w, _ = projected_margin(ml_proj)
                ml_called[cno] = (final_round + 1, w)

    # ── Build per-round stats ──────────────────────────────────────────────
    sim_rounds = list(range(1, max_round + 2))   # +1 to capture forced calls

    def round_stats(called: dict[int, tuple[int, int]]) -> list[dict]:
        rows = []
        cum = [0, 0, 0]
        cum_false = 0
        for r in sim_rounds:
            add = [0, 0, 0]
            add_false = 0
            for cno, (rc, ai) in called.items():
                if rc == r:
                    add[ai] += 1
                    if ai != actual_winner.get(cno, -1):
                        add_false += 1
            cum = [cum[i] + add[i] for i in range(3)]
            cum_false += add_false
            rows.append({
                "round": r,
                "add": add[:], "add_total": sum(add),
                "cum": cum[:], "cum_total": sum(cum),
                "cum_false": cum_false,
            })
        return rows

    f_rows = round_stats(formula_called)
    m_rows = round_stats(ml_called)

    # ── Print tables ───────────────────────────────────────────────────────
    HDR  = f"{'Round':<7}{'Add LDF':>8}{'Add UDF':>8}{'Add NDA':>8}{'Add Tot':>8}  {'Cum LDF':>8}{'Cum UDF':>8}{'Cum NDA':>8}{'Cum Tot':>9}{'False':>7}"
    SEP  = "-" * 83

    def print_table(label: str, rows: list[dict]) -> None:
        print("=" * 83)
        print(label)
        print("=" * 83)
        print(HDR)
        print(SEP)
        for row in rows:
            if row["add_total"] == 0 and row["cum_total"] == 0:
                continue
            r = row["round"]
            rlabel = f"R{r}" if r <= MAX_SIM_ROUNDS else "FINAL"
            a = row["add"]
            c = row["cum"]
            print(
                f"{rlabel:<7}{a[0]:>8}{a[1]:>8}{a[2]:>8}{row['add_total']:>8}"
                f"  {c[0]:>8}{c[1]:>8}{c[2]:>8}{row['cum_total']:>9}{row['cum_false']:>7}"
            )
        last = next((r for r in reversed(rows) if r["cum_total"] > 0), rows[-1])
        print(SEP)
        c = last["cum"]
        print(
            f"{'TOTAL':<7}{'':<8}{'':<8}{'':<8}{'':<8}"
            f"  {c[0]:>8}{c[1]:>8}{c[2]:>8}{last['cum_total']:>9}{last['cum_false']:>7}"
        )
        print()

    print_table("FORMULA  — R1-R{} seat accumulation (2026 simulation)".format(max_round), f_rows)
    print_table("ML v1    — R1-R{} seat accumulation (lam=2.0, trained R1-R12)".format(max_round), m_rows)

    # Delta table
    print("=" * 83)
    print("DELTA (ML v1 minus Formula)  — positive = ML calls more / earlier")
    print("=" * 83)
    DHDR = f"{'Round':<7}{'dAddLDF':>8}{'dAddUDF':>8}{'dAddNDA':>8}{'dAddTot':>8}  {'dCumLDF':>8}{'dCumUDF':>8}{'dCumNDA':>8}{'dCumTot':>9}{'dFalse':>7}"
    print(DHDR)
    print(SEP)
    any_delta = False
    for f, m in zip(f_rows, m_rows):
        da = [m["add"][i] - f["add"][i] for i in range(3)]
        dc = [m["cum"][i] - f["cum"][i] for i in range(3)]
        dat = m["add_total"] - f["add_total"]
        dct = m["cum_total"] - f["cum_total"]
        df  = m["cum_false"]  - f["cum_false"]
        if all(v == 0 for v in da + dc + [dat, dct, df]):
            continue
        any_delta = True
        r = f["round"]
        rlabel = f"R{r}" if r <= MAX_SIM_ROUNDS else "FINAL"
        print(
            f"{rlabel:<7}{da[0]:>+8}{da[1]:>+8}{da[2]:>+8}{dat:>+8}"
            f"  {dc[0]:>+8}{dc[1]:>+8}{dc[2]:>+8}{dct:>+9}{df:>+7}"
        )
    if not any_delta:
        print("  (no difference — ML and Formula call seats identically)")

    # Summary
    f_last = next((r for r in reversed(f_rows) if r["cum_total"] > 0), f_rows[-1])
    m_last = next((r for r in reversed(m_rows) if r["cum_total"] > 0), m_rows[-1])
    print()
    print("=" * 83)
    print("SUMMARY")
    print("=" * 83)
    print(f"  Formula : {f_last['cum_total']:3d}/140 seats called, {f_last['cum_false']:2d} false calls")
    print(f"  ML v1   : {m_last['cum_total']:3d}/140 seats called, {m_last['cum_false']:2d} false calls")
    delta_calls = m_last["cum_total"] - f_last["cum_total"]
    delta_false = m_last["cum_false"] - f_last["cum_false"]
    print(f"  Delta   : {delta_calls:+d} seat calls,  {delta_false:+d} false calls")

    # ── Seats where Formula and ML disagree on ALLIANCE ───────────────────
    print()
    print("=" * 83)
    print("SEATS WHERE FORMULA AND ML v1 PREDICT DIFFERENT WINNER")
    print("=" * 83)
    disagree = []
    for cno in sorted(formula_called):
        f_rc, f_ai = formula_called.get(cno, (-1, -1))
        m_rc, m_ai = ml_called.get(cno, (-1, -1))
        if f_ai != m_ai:
            act = actual_winner.get(cno, -1)
            disagree.append((cno, data_2026[cno].name, f_rc, f_ai, m_rc, m_ai, act))

    if not disagree:
        print("  None — both models predict the same alliance for all 140 seats.")
    else:
        print(f"  {'#':>4} {'Constituency':<30} {'F-Rd':>5} {'F-Win':>6} {'M-Rd':>5} {'M-Win':>6} {'Actual':>7} {'Result'}")
        print(f"  {'-'*4} {'-'*30} {'-'*5} {'-'*6} {'-'*5} {'-'*6} {'-'*7} {'-'*8}")
        for cno, name, f_rc, f_ai, m_rc, m_ai, act in disagree:
            f_win = ALLIANCES[f_ai].upper() if f_ai >= 0 else "---"
            m_win = ALLIANCES[m_ai].upper() if m_ai >= 0 else "---"
            actual = ALLIANCES[act].upper() if act >= 0 else "---"
            f_ok = "OK" if f_ai == act else "WRONG"
            m_ok = "OK" if m_ai == act else "WRONG"
            print(f"  {cno:>4} {name:<30} R{f_rc:<4} {f_win:>6} R{m_rc:<4} {m_win:>6} {actual:>7}   F:{f_ok} M:{m_ok}")


if __name__ == "__main__":
    simulate()
