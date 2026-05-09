#!/usr/bin/env python3
"""
Simulate what a better prediction at Round 5 would look like.
Analyzes root causes of the 9 wrong predictions and tests improved logic.
"""
import json, os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")

with open(os.path.join(DATA_DIR, "live_results.json")) as f:
    results = json.load(f)
cands = {}
for _fn in os.listdir(os.path.join(DATA_DIR, "2026")):
    if not _fn.endswith(".json"):
        continue
    with open(os.path.join(DATA_DIR, "2026", _fn), encoding="utf-8") as f:
        _e = json.load(f)
    _cno = str(_e["const_no"])
    _row = {"name": _e.get("name", ""), "district": _e.get("district", "")}
    for _c in _e.get("candidates_2026", []):
        _a = _c.get("alliance")
        if _a in ("ldf", "udf", "nda") and _c.get("is_major_alliance"):
            _row[_a] = {"name": _c["name"], "party": _c.get("party", "")}
    for _a in ("ldf", "udf", "nda"):
        _row.setdefault(_a, {"name": "", "party": ""})
    cands[_cno] = _row
with open(os.path.join(DATA_DIR, "live_predictions.json")) as f:
    preds_file = json.load(f)
booth_data = {}
booth_dir = os.path.join(DATA_DIR, "2021")
for fname in os.listdir(booth_dir):
    if fname.endswith(".json"):
        with open(os.path.join(booth_dir, fname), encoding="utf-8") as f:
            entry = json.load(f)
        booth_data[int(entry["const_no"])] = entry
preds_data = preds_file.get("predictions", {})


# ── IMPROVED party → alliance classifier ──────────────────────────────────────
# The original code missed: RSP→ldf, CMPKS→ldf, Independent context
LDF_PARTIES = [
    "communist party of india",       # CPI and CPI(M)
    "communist marxist party",         # CMPKS
    "revolutionary socialist party",   # RSP  ← KEY FIX
    "rashtriya janata dal",
    "kerala socialist party",
    "socialist unity centre",
    "all india forward bloc",
    "loktantrik janata dal",
    "kerala revolutionary socialist",
    "janasenapaksham",
]
UDF_PARTIES = [
    "indian national congress",
    "indian union muslim league",
    "kerala congress",                 # KC(M), KC(J), KC
    "revolutionary marxist party of india",
    "indian national league",
    "kerala congress (b)",
]
NDA_PARTIES = [
    "bharatiya janata party",
    "bharath dharma jana sena",
    "bdjs",
]

def classify_party(party: str) -> str:
    p = party.lower()
    for tok in LDF_PARTIES:
        if tok in p:
            return "ldf"
    for tok in UDF_PARTIES:
        if tok in p:
            return "udf"
    for tok in NDA_PARTIES:
        if tok in p:
            return "nda"
    return "other"


# ── Original predict logic (same as predict_from_eci.py) ─────────────────────
def predict_projection(cand_votes: list, cur_round: int, tot_rounds: int, const_no: int):
    if tot_rounds <= 0 or cur_round <= 0:
        return None
    pct = min(cur_round / tot_rounds, 1.0)
    n = len(cand_votes)
    lin_proj = [round(v / pct) for v in cand_votes] if pct > 0 else list(cand_votes)
    projected = lin_proj[:]
    used_pattern = False

    bd = booth_data.get(const_no)
    if bd:
        booths = bd.get("booths", [])
        main_nos = sorted({b["main"] for b in booths if not b.get("is_aux", False)})
        tot_main = len(main_nos)
        booths_counted = min(cur_round * 14, tot_main)
        cutoff_set = set(main_nos[:booths_counted])

        early_booths = [b for b in booths if b["main"] in cutoff_set]
        early_totals = [sum(b["votes"][i] if i < len(b.get("votes", [])) else 0
                           for b in early_booths) for i in range(n)]
        final_totals = [sum(b["votes"][i] if i < len(b.get("votes", [])) else 0
                           for b in booths) for i in range(n)]
        sum_early = sum(early_totals)
        sum_final = sum(final_totals)
        sum_votes = sum(cand_votes)

        if sum(1 for e in early_totals if e > 0) >= 2 and sum_early > 0 and sum_final > 0 and sum_votes > 0:
            share_2021_early = [e / sum_early for e in early_totals]
            share_2026 = [v / sum_votes for v in cand_votes]
            delta = [s26 - s21e for s26, s21e in zip(share_2026, share_2021_early)]

            remaining_2021 = [final_totals[i] - early_totals[i] for i in range(n)]
            sum_remaining_2021 = sum(remaining_2021)

            if sum_remaining_2021 > 0:
                share_remaining_2021 = [r / sum_remaining_2021 for r in remaining_2021]
                damp = min(pct / 0.30, 1.0)
                adj_remaining = [max(0.0, sr + d * damp)
                                for sr, d in zip(share_remaining_2021, delta)]
                tot_adj = sum(adj_remaining)
                if tot_adj > 0:
                    adj_remaining = [s / tot_adj for s in adj_remaining]
                total_linear = sum_votes / pct
                remaining_2026 = total_linear - sum_votes
                projected = [round(cand_votes[i] + adj_remaining[i] * remaining_2026)
                            for i in range(n)]
                used_pattern = True

    return {"projected": projected, "used_pattern": used_pattern}


# ── SIMULATION ────────────────────────────────────────────────────────────────
SIM_ROUND = 5

sim_results = []

for cid, eci in results.items():
    cno = int(cid)
    candidates = eci.get("candidates", [])
    if not candidates:
        continue
    tot_rounds = eci.get("tot_rounds", 0)
    if tot_rounds == 0:
        continue

    final_votes = {c["name"]: c.get("votes", 0) for c in candidates}
    sim_pct = min(SIM_ROUND / tot_rounds, 1.0)
    sim_votes = {name: round(v * sim_pct) for name, v in final_votes.items()}

    # Actual final winner
    actual_winner = max(candidates, key=lambda c: c.get("votes", 0))
    actual_alliance = classify_party(actual_winner["party"])

    # ── Method 1 (OLD): Force into ldf/udf/nda slots using candidates_2026 app data ──
    app_meta = cands.get(cid, {})
    alliance_sim_old = {"ldf": 0, "udf": 0, "nda": 0}
    for a in ["ldf", "udf", "nda"]:
        ac = app_meta.get(a, {})
        app_name = ac.get("name", "").lower()
        # Find best match in actual candidates
        best_v = 0
        for c in candidates:
            if any(tok in c["name"].lower() for tok in app_name.split()[:2] if len(tok) > 3):
                best_v = max(best_v, sim_votes.get(c["name"], 0))
        if best_v == 0 and candidates:
            # fallback: top candidate by party match
            for c in candidates:
                if classify_party(c.get("party", "")) == a:
                    best_v = max(best_v, sim_votes.get(c["name"], 0))
        alliance_sim_old[a] = best_v

    old_pred_alliance = max(["ldf", "udf", "nda"], key=lambda a: alliance_sim_old[a])
    old_correct = (old_pred_alliance == actual_alliance)

    # ── Method 2 (BETTER ALLIANCE): same as old but classify actual party properly ──
    alliance_sim_new = {"ldf": 0, "udf": 0, "nda": 0, "other": 0}
    alliance_top_cand = {}
    for c in candidates:
        a = classify_party(c.get("party", ""))
        sv = sim_votes.get(c["name"], 0)
        if sv > alliance_sim_new.get(a, 0):
            alliance_sim_new[a] = sv
            alliance_top_cand[a] = c

    best_a = max(alliance_sim_new, key=lambda a: alliance_sim_new[a])
    new_correct = (best_a == actual_alliance)

    # ── Method 3 (LEADER-BASED): Just pick the round-5 leader, classify their party ──
    leader_at_r5 = max(candidates, key=lambda c: sim_votes.get(c["name"], 0))
    leader_alliance = classify_party(leader_at_r5.get("party", ""))
    leader_correct = (leader_alliance == actual_alliance)

    # ── Method 4 (BOOTH PATTERN + BETTER CLASSIFY): Apply booth projection at r5 ──
    # Use top-3 candidates by final votes, apply booth pattern
    top3 = sorted(candidates, key=lambda c: -c.get("votes", 0))[:3]
    top3_sim_votes = [sim_votes.get(c["name"], 0) for c in top3]
    proj = predict_projection(top3_sim_votes, SIM_ROUND, tot_rounds, cno)
    if proj:
        winner_idx = max(range(len(top3)), key=lambda i: proj["projected"][i])
        proj_winner = top3[winner_idx]
        proj_alliance = classify_party(proj_winner.get("party", ""))
        proj_correct = (proj_alliance == actual_alliance)
    else:
        proj_winner = leader_at_r5
        proj_alliance = leader_alliance
        proj_correct = leader_correct

    sim_results.append({
        "name": eci.get("name", cid),
        "cid": cid,
        "tot_rounds": tot_rounds,
        "sim_pct": round(sim_pct * 100),
        "actual_winner": actual_winner["name"],
        "actual_party": actual_winner["party"],
        "actual_alliance": actual_alliance,
        "leader_at_r5": leader_at_r5["name"],
        "leader_party": leader_at_r5.get("party", ""),
        "old_pred": old_pred_alliance,
        "old_correct": old_correct,
        "new_pred": best_a,
        "new_correct": new_correct,
        "leader_pred": leader_alliance,
        "leader_correct": leader_correct,
        "proj_pred": proj_alliance,
        "proj_correct": proj_correct,
    })

total = len(sim_results)
old_acc = sum(1 for r in sim_results if r["old_correct"])
new_acc = sum(1 for r in sim_results if r["new_correct"])
leader_acc = sum(1 for r in sim_results if r["leader_correct"])
proj_acc = sum(1 for r in sim_results if r["proj_correct"])

print("=" * 65)
print("  ROUND-5 PREDICTION SIMULATION — KERALA 2026 ASSEMBLY ELECTION")
print("=" * 65)
print(f"\n  Simulating: Round {SIM_ROUND} (avg ~{round(SIM_ROUND / 16 * 100)}% votes counted)\n")

print(f"  Method 1 — OLD (force top-3 into ldf/udf/nda slots):")
print(f"    Correct: {old_acc}/{total} = {old_acc/total*100:.1f}%\n")

print(f"  Method 2 — FIXED ALLIANCE MAP (better party→alliance table):")
print(f"    Correct: {new_acc}/{total} = {new_acc/total*100:.1f}%\n")

print(f"  Method 3 — LEADER-BASED (who's leading at round 5 → classify):")
print(f"    Correct: {leader_acc}/{total} = {leader_acc/total*100:.1f}%\n")

print(f"  Method 4 — BOOTH PATTERN + FIXED ALLIANCE (best combo):")
print(f"    Correct: {proj_acc}/{total} = {proj_acc/total*100:.1f}%\n")

print("-" * 65)
print("  WRONG at round 5 (Method 3 — Leader-based):")
for r in sim_results:
    if not r["leader_correct"]:
        print(f"    {r['name']}: leader={r['leader_pred']} actual={r['actual_alliance']}")
        print(f"      r5 leader: {r['leader_at_r5']} ({r['leader_party']})")
        print(f"      actual:    {r['actual_winner']} ({r['actual_party']})")

print()
print("-" * 65)
print("  WRONG at round 5 (Method 4 — Booth Pattern + Fixed Alliance):")
for r in sim_results:
    if not r["proj_correct"]:
        print(f"    {r['name']}: pred={r['proj_pred']} actual={r['actual_alliance']}")
        print(f"      r5 leader: {r['leader_at_r5']} ({r['leader_party']})")
        print(f"      actual:    {r['actual_winner']} ({r['actual_party']})")

print()
print("=" * 65)
print("  FINAL RESULT ACCURACY (last state of live_results.json):")
old_final = sum(1 for cid, pred in preds_data.items()
    if pred.get("winner_alliance") == classify_party(
        next((c["party"] for c in results.get(cid, {}).get("candidates", [])
              if c["status"] in ("leading","won")), "")))
print(f"    Actual predictions file: {old_final}/140 = {old_final/140*100:.1f}%")
print("=" * 65)
