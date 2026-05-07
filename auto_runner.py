#!/usr/bin/env python3
"""
Auto-runner: scrapes ECI every 5 minutes and POSTs predictions to the app.
Run alongside app.py:  python auto_runner.py
"""

import os, json, time, math, requests
from datetime import datetime

BASE_DIR  = os.path.dirname(__file__)
DATA_DIR  = os.path.join(BASE_DIR, "data")
OUT_FILE  = os.path.join(DATA_DIR, "data_parsing", "live_results.json")
PRED_FILE = os.path.join(DATA_DIR, "live_predictions.json")

APP_URL   = "http://localhost:5000"
INTERVAL  = 300   # 5 minutes

# Import scraper
import sys
sys.path.insert(0, BASE_DIR)
from eci_scraper import scrape_all


def load_meta() -> dict:
    """Load constituency meta from the app API."""
    try:
        r = requests.get(f"{APP_URL}/api/constituencies", timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {c["no"]: c for c in data}
    except Exception as e:
        print(f"  [warn] Could not load meta from app: {e}")
    return {}


def map_eci_candidates_to_app(eci_cands: list, app_cands: list) -> list[int | None]:
    """
    Match ECI candidate list (name+party) to app candidate list (ldf/udf/nda order).
    Returns list of indices into eci_cands for [ldf_idx, udf_idx, nda_idx].
    """
    def normalize(s: str) -> str:
        return s.lower().replace(".", "").strip()

    indices = []
    for app_c in app_cands:
        best_match = None
        best_score = 0
        app_name  = normalize(app_c.get("name", ""))
        app_party = normalize(app_c.get("party", ""))
        for j, ec in enumerate(eci_cands):
            ec_name  = normalize(ec.get("name", ""))
            ec_party = normalize(ec.get("party", ""))
            score = 0
            # Name match (last name or full)
            if app_name and ec_name:
                app_parts = app_name.split()
                ec_parts  = ec_name.split()
                common = len(set(app_parts) & set(ec_parts))
                score += common * 3
            # Party match
            if app_party and ec_party and (app_party in ec_party or ec_party in app_party):
                score += 2
            if score > best_score:
                best_score = score
                best_match = j
        indices.append(best_match)
    return indices


def run_predictions(live_data: dict, meta: dict) -> dict:
    """For each constituency with live data, POST to /api/predict and collect results."""
    predictions = {}

    for const_str, result in live_data.items():
        const_no = int(const_str)
        m = meta.get(const_no)
        if not m:
            continue

        eci_cands  = result.get("candidates", [])
        app_cands  = m.get("candidates", [])
        rounds_done = result.get("rounds_completed", 0)

        if rounds_done == 0 or not eci_cands:
            continue

        total_main = m.get("total_main_booths", 200)
        total_rounds_expected = m.get("total_rounds", math.ceil(total_main / 14))

        # Map ECI candidates → app order (ldf, udf, nda)
        eci_idx_map = map_eci_candidates_to_app(eci_cands, app_cands)

        # Build votes array in app order [ldf_votes, udf_votes, nda_votes]
        votes = []
        for idx in eci_idx_map:
            if idx is not None and idx < len(eci_cands):
                votes.append(eci_cands[idx].get("votes", eci_cands[idx].get("total", 0)))
            else:
                votes.append(0)

        if sum(votes) == 0:
            continue

        # Estimate booths counted from rounds done
        booths_per_round = math.ceil(total_main / total_rounds_expected) if total_rounds_expected > 0 else 14
        booths_counted   = min(rounds_done * booths_per_round, total_main)

        try:
            r = requests.post(f"{APP_URL}/api/predict", json={
                "const_no":         const_no,
                "booths_counted":   booths_counted,
                "total_main_booths": total_main,
                "votes":            votes,
                "prediction_year":  2026,
            }, timeout=10)
            if r.status_code == 200:
                pred = r.json()
                predictions[const_str] = {
                    "const_no":      const_no,
                    "name":          m.get("name", ""),
                    "district":      m.get("district", ""),
                    "rounds_done":   rounds_done,
                    "live_votes":    votes,
                    "eci_candidates": [c.get("name") for c in eci_cands],
                    "prediction":    pred,
                    "updated_at":    datetime.now().isoformat(),
                }
        except Exception as e:
            print(f"  [warn] Predict failed for #{const_no}: {e}")

    return predictions


def save_predictions(predictions: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    # Also compute seat tally
    tally = {"ldf": 0, "udf": 0, "nda": 0, "other": 0}
    leading = {}
    for cs, p in predictions.items():
        pred = p.get("prediction", {})
        alliance = pred.get("winner_alliance", "other")
        tally[alliance] = tally.get(alliance, 0) + 1
        leading[cs] = {
            "name":      p["name"],
            "district":  p["district"],
            "winner_alliance": alliance,
            "confidence": pred.get("confidence", 0),
            "margin":    pred.get("margin", 0),
            "rounds_done": p["rounds_done"],
        }

    output = {
        "generated_at": datetime.now().isoformat(),
        "seat_tally":   tally,
        "leading":      leading,
        "full":         predictions,
    }
    with open(PRED_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  Predictions saved → {PRED_FILE}")
    print(f"  Tally: LDF={tally['ldf']} | UDF={tally['udf']} | NDA={tally['nda']}")
    return output


def run_cycle():
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*55}")
    print(f"  Cycle start: {ts}")

    # 1. Scrape ECI
    print("  Scraping ECI results...")
    live_data = scrape_all(verbose=False)

    active = sum(1 for v in live_data.values() if v.get("rounds_completed", 0) > 0)
    print(f"  Active constituencies (with data): {active}/{len(live_data)}")

    if active == 0:
        print("  No live data yet — counting may not have started.")
        return

    # 2. Load app metadata
    print("  Loading constituency metadata...")
    meta = load_meta()

    # 3. Run predictions
    print("  Running predictions...")
    predictions = run_predictions(live_data, meta)
    print(f"  Predictions generated: {len(predictions)}")

    # 4. Save
    save_predictions(predictions)


if __name__ == "__main__":
    print("Kerala Election Auto-Runner")
    print(f"Polling interval: {INTERVAL}s ({INTERVAL//60} minutes)")
    print("Make sure app.py is running at http://localhost:5000")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            run_cycle()
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"  [error] Cycle failed: {e}")

        print(f"  Next run in {INTERVAL//60} minutes...")
        time.sleep(INTERVAL)
