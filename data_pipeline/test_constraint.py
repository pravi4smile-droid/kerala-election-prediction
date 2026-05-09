#!/usr/bin/env python3
from ml_prediction_experiment import (
    load_all_years, build_samples, train_ridge, train_ridge_loglinear,
    train_ridge_2out, apply_model, apply_model_loglinear, apply_model_2out,
    winner, margin, TARGETS_FOR_TRAINING, VALIDATION_YEAR, ROUNDS, ROUND_GROUPS,
)

print("Loading data...")
all_data = load_all_years()
train_full = build_samples(all_data, TARGETS_FOR_TRAINING, rounds=ROUNDS)
val_full   = build_samples(all_data, (VALIDATION_YEAR,),   rounds=ROUNDS)
print(f"Train: {len(train_full)}  Val: {len(val_full)}")
print()

coef_v1   = train_ridge(train_full, lam=2.0, feature_attr="features")
coef_ll   = train_ridge_loglinear(train_full, lam=2.0, feature_attr="features")
coef_2out = train_ridge_2out(train_full, lam=2.0, feature_attr="features")


def eval_fn(samples, apply_fn):
    rows = []
    for s in samples:
        aw  = winner(s.actual_votes)
        sh  = apply_fn(s)
        pw  = winner(sh)
        ash = [v / max(sum(s.actual_votes), 1) for v in s.actual_votes]
        rows.append({
            "ok": pw == aw,
            "mae": sum(abs(sh[i] - ash[i]) for i in range(3)) / 3,
            "merr": abs(margin(sh) - margin(ash)),
        })
    n = len(rows) or 1
    return (
        sum(1 for r in rows if r["ok"]) / n,
        sum(r["mae"] for r in rows) / n,
        sum(r["merr"] for r in rows) / n,
    )


models = [
    ("Formula    ", lambda s: s.baseline_shares),
    ("Additive v1", lambda s: apply_model(s, coef_v1, "features")),
    ("Log-linear ", lambda s: apply_model_loglinear(s, coef_ll, "features")),
    ("2-out      ", lambda s: apply_model_2out(s, coef_2out, "features")),
]

hdr = f"{'Model':<14}  {'R1-3':>7}  {'R4-6':>7}  {'R7-9':>7}  {'R10-12':>8}  {'ALL':>7}  {'MAE':>7}  {'MarErr':>8}"
print(hdr)
print("-" * len(hdr))
for label, fn in models:
    gcols = []
    for _, rrange in ROUND_GROUPS:
        rset   = [r for r in rrange if r in ROUNDS]
        subset = [s for s in val_full if s.round_no in rset]
        acc, _, _ = eval_fn(subset, fn)
        gcols.append(acc * 100)
    acc, mae, merr = eval_fn(val_full, fn)
    print(
        f"{label}  {gcols[0]:>6.1f}%  {gcols[1]:>6.1f}%  {gcols[2]:>6.1f}%"
        f"  {gcols[3]:>7.1f}%  {acc*100:>6.1f}%  {mae*100:>6.2f}pp  {merr*100:>7.2f}pp"
    )

print()
max_diff = max(
    abs(coef_v1[i][k] - coef_2out[i][k])
    for i in range(len(coef_v1)) for k in range(3)
)
print(f"Max coef diff (Additive v1 vs 2-out): {max_diff:.2e}")
print("=> If ~1e-14, the zero-sum constraint is already implicit in ridge (proven by algebra).")
print()
print("Log-linear uses softmax inference -- no share clipping needed.")
print("If it scores lower, log-transform amplifies noise in small NDA shares (clipped to 1e-4).")
