#!/usr/bin/env python3
"""
Gradient Boosting vs Ridge regression for Kerala election share correction.

Trains GradientBoostingRegressor (one per alliance) on the same features/data
as ML v1, compares winner accuracy, share MAE, and margin error by round group.
Also runs leave-one-year-out CV to tune n_estimators / max_depth / learning_rate.
"""
from __future__ import annotations
import math
from sklearn.ensemble import GradientBoostingRegressor

from ml_prediction_experiment import (
    load_all_years, build_samples, train_ridge, apply_model,
    winner, margin, TARGETS_FOR_TRAINING, VALIDATION_YEAR, ROUNDS, ROUND_GROUPS,
    Sample, ALLIANCES,
)

# ── Hyperparameter grid for CV ────────────────────────────────────────────────
GB_GRID = [
    {"n_estimators": 100, "max_depth": 3, "learning_rate": 0.1,  "subsample": 0.8},
    {"n_estimators": 200, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8},
    {"n_estimators": 100, "max_depth": 4, "learning_rate": 0.1,  "subsample": 0.8},
    {"n_estimators": 200, "max_depth": 4, "learning_rate": 0.05, "subsample": 0.8},
    {"n_estimators": 100, "max_depth": 2, "learning_rate": 0.1,  "subsample": 1.0},
]


# ── GB model training/inference ───────────────────────────────────────────────

def train_gb(
    samples: list[Sample],
    feature_attr: str = "features",
    **gb_params,
) -> list[GradientBoostingRegressor]:
    """Train one GBR per alliance correction. Returns list of 3 models."""
    X = [getattr(s, feature_attr) for s in samples]
    Ys = [[s.corrected_shares_target[k] for s in samples] for k in range(3)]
    models = []
    for k in range(3):
        m = GradientBoostingRegressor(**gb_params, random_state=42)
        m.fit(X, Ys[k])
        models.append(m)
    return models


def apply_gb(
    sample: Sample,
    models: list[GradientBoostingRegressor],
    feature_attr: str = "features",
) -> list[float]:
    """Apply GB models, add correction to baseline, normalize."""
    x = [getattr(sample, feature_attr)]
    correction = [float(models[k].predict(x)[0]) for k in range(3)]
    shares = [max(0.0, sample.baseline_shares[k] + correction[k]) for k in range(3)]
    total = sum(shares)
    return [v / total for v in shares] if total > 0 else sample.baseline_shares[:]


# ── Evaluation ────────────────────────────────────────────────────────────────

def eval_fn(samples: list[Sample], apply_fn) -> dict:
    rows = []
    for s in samples:
        aw  = winner(s.actual_votes)
        sh  = apply_fn(s)
        pw  = winner(sh)
        ash = [v / max(sum(s.actual_votes), 1) for v in s.actual_votes]
        rows.append({
            "ok":   pw == aw,
            "mae":  sum(abs(sh[i] - ash[i]) for i in range(3)) / 3,
            "merr": abs(margin(sh) - margin(ash)),
        })
    n = len(rows) or 1
    return {
        "n":          n,
        "accuracy":   sum(1 for r in rows if r["ok"]) / n,
        "share_mae":  sum(r["mae"] for r in rows) / n,
        "margin_err": sum(r["merr"] for r in rows) / n,
    }


def cv_gb(
    samples: list[Sample],
    feature_attr: str = "features",
) -> tuple[dict, float]:
    """Leave-one-year-out CV over GB_GRID. Returns (best_params, best_acc)."""
    years = sorted({s.target_year for s in samples})
    if len(years) < 2:
        return GB_GRID[0], 0.0

    best_params, best_score = GB_GRID[0], -1.0

    for params in GB_GRID:
        fold_accs = []
        for held_out in years:
            tr  = [s for s in samples if s.target_year != held_out]
            val = [s for s in samples if s.target_year == held_out]
            if not tr or not val:
                continue
            mdls = train_gb(tr, feature_attr, **params)
            ev   = eval_fn(val, lambda s, m=mdls: apply_gb(s, m, feature_attr))
            fold_accs.append(ev["accuracy"])
        score = sum(fold_accs) / len(fold_accs) if fold_accs else 0.0
        tag   = f"n={params['n_estimators']} d={params['max_depth']} lr={params['learning_rate']}"
        print(f"    {tag:<30}  CV acc: {score*100:.2f}%")
        if score > best_score:
            best_score = score
            best_params = params

    return best_params, best_score


def group_results(val_full, apply_fn):
    gcols = []
    for _, rrange in ROUND_GROUPS:
        rset   = [r for r in rrange if r in ROUNDS]
        subset = [s for s in val_full if s.round_no in rset]
        gcols.append(eval_fn(subset, apply_fn)["accuracy"] * 100)
    ev = eval_fn(val_full, apply_fn)
    return gcols, ev


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    all_data   = load_all_years()
    train_full = build_samples(all_data, TARGETS_FOR_TRAINING, rounds=ROUNDS)
    val_full   = build_samples(all_data, (VALIDATION_YEAR,),   rounds=ROUNDS)
    print(f"  Train: {len(train_full)}  Val: {len(val_full)}\n")

    # ── Baseline: Ridge v1 ────────────────────────────────────────────────
    print("Training Ridge v1 (lam=2.0)...")
    coef_ridge = train_ridge(train_full, lam=2.0, feature_attr="features")

    # ── GB cross-validation ───────────────────────────────────────────────
    print("\nCross-validating GB hyperparameters (leave-one-year-out)...")
    best_params, best_cv = cv_gb(train_full, feature_attr="features")
    print(f"\n  Best params: {best_params}  (CV acc: {best_cv*100:.2f}%)")

    # ── Train final GB with best params ───────────────────────────────────
    print("\nTraining final GB model on full training set...")
    gb_models = train_gb(train_full, feature_attr="features", **best_params)

    # ── Also try v2 features with GB ──────────────────────────────────────
    print("\nCross-validating GB with v2 features (30 features)...")
    best_params_v2, best_cv_v2 = cv_gb(train_full, feature_attr="features_v2")
    print(f"\n  Best v2 params: {best_params_v2}  (CV acc: {best_cv_v2*100:.2f}%)")
    print("Training final GB-v2 model...")
    gb_models_v2 = train_gb(train_full, feature_attr="features_v2", **best_params_v2)

    # ── Comparison table ──────────────────────────────────────────────────
    print("\n" + "=" * 82)
    print("RESULTS: Ridge v1 vs Gradient Boosting -- 2026 validation (R1-R12)")
    print("=" * 82)
    HDR = f"{'Model':<20}  {'R1-3':>7}  {'R4-6':>7}  {'R7-9':>7}  {'R10-12':>8}  {'ALL':>7}  {'MAE':>7}  {'MarErr':>8}"
    print(HDR)
    print("-" * 82)

    models_to_eval = [
        ("Formula",      lambda s: s.baseline_shares,                                      "features"),
        ("Ridge v1",     lambda s: apply_model(s, coef_ridge, "features"),                  "features"),
        ("GB v1",        lambda s: apply_gb(s, gb_models, "features"),                      "features"),
        ("GB v2 (30f)",  lambda s: apply_gb(s, gb_models_v2, "features_v2"),               "features_v2"),
    ]

    for label, fn, _ in models_to_eval:
        gcols, ev = group_results(val_full, fn)
        print(
            f"{label:<20}  {gcols[0]:>6.1f}%  {gcols[1]:>6.1f}%  {gcols[2]:>6.1f}%"
            f"  {gcols[3]:>7.1f}%  {ev['accuracy']*100:>6.1f}%"
            f"  {ev['share_mae']*100:>6.2f}pp  {ev['margin_err']*100:>7.2f}pp"
        )

    # ── Per-round detail for GB v1 ────────────────────────────────────────
    print("\n" + "=" * 82)
    print("PER-ROUND: Ridge v1 vs GB v1 (winner accuracy)")
    print("=" * 82)
    print(f"{'Round':<6}  {'Samples':>7}  {'Formula':>9}  {'Ridge v1':>9}  {'GB v1':>9}  {'GB v2':>9}")
    print("-" * 62)
    for r in ROUNDS:
        subset = [s for s in val_full if s.round_no == r]
        if not subset:
            continue
        f_acc  = eval_fn(subset, lambda s: s.baseline_shares)["accuracy"] * 100
        r_acc  = eval_fn(subset, lambda s, c=coef_ridge: apply_model(s, c, "features"))["accuracy"] * 100
        gb_acc = eval_fn(subset, lambda s, m=gb_models: apply_gb(s, m, "features"))["accuracy"] * 100
        g2_acc = eval_fn(subset, lambda s, m=gb_models_v2: apply_gb(s, m, "features_v2"))["accuracy"] * 100
        print(f"R{r:<5}  {len(subset):>7}  {f_acc:>8.1f}%  {r_acc:>8.1f}%  {gb_acc:>8.1f}%  {g2_acc:>8.1f}%")

    # ── Seats where GB changes the winner call ────────────────────────────
    print("\n" + "=" * 82)
    print("SEATS WHERE GB v1 DISAGREES WITH RIDGE (winner flip) -- early rounds R1-R3")
    print("=" * 82)
    early = [s for s in val_full if s.round_no <= 3]
    print(f"  {'Rd':<3}  {'#':>4}  {'Constituency':<28}  {'Ridge':>6}  {'GB':>6}  {'Actual':>7}  {'Result'}")
    print(f"  {'-'*3}  {'-'*4}  {'-'*28}  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*8}")
    flip_count = 0
    for s in early:
        r_sh  = apply_model(s, coef_ridge, "features")
        gb_sh = apply_gb(s, gb_models, "features")
        r_w   = winner(r_sh)
        gb_w  = winner(gb_sh)
        if r_w != gb_w:
            aw = winner(s.actual_votes)
            r_ok  = "OK" if r_w  == aw else "WRONG"
            gb_ok = "OK" if gb_w == aw else "WRONG"
            print(
                f"  R{s.round_no:<2}  {s.const_no:>4}  {s.name:<28}  "
                f"{ALLIANCES[r_w].upper():>6}  {ALLIANCES[gb_w].upper():>6}  "
                f"{ALLIANCES[aw].upper():>7}   Rd:{r_ok} GB:{gb_ok}"
            )
            flip_count += 1
    if flip_count == 0:
        print("  (no disagreements at R1-R3)")
    print(f"\n  Total flips at R1-R3: {flip_count}")


if __name__ == "__main__":
    main()
