#!/usr/bin/env python3
"""
Booth Count Analysis Tool
Compares 2021 vs 2026 booth counts and generates statistics and reports.

Usage: python analyze_booth_changes.py
"""

import os, json, statistics

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_SCRIPT_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
DIR_2021 = os.path.join(DATA_DIR, "2021")
DIR_2026 = os.path.join(DATA_DIR, "2026")


def load_booth_counts():
    booths_2021, booths_2026 = {}, {}
    for fname in os.listdir(DIR_2021):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(DIR_2021, fname), encoding="utf-8") as f:
            e = json.load(f)
        bc = e.get("booth_summary", {}).get("main_booths")
        if bc:
            booths_2021[str(e["const_no"])] = bc
    for fname in os.listdir(DIR_2026):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(DIR_2026, fname), encoding="utf-8") as f:
            e = json.load(f)
        bc = e.get("booth_count")
        if bc:
            booths_2026[str(e["const_no"])] = bc
    return booths_2021, booths_2026


def main():
    print("=" * 70)
    print("  Kerala Election — Booth Count Analysis (2021 vs 2026)")
    print("=" * 70)

    # Load data
    if not os.path.isdir(DIR_2021):
        print(f"\n✗ {DIR_2021} not found. Run split_2021_booth_data.py")
        return
    if not os.path.isdir(DIR_2026):
        print(f"\n✗ {DIR_2026} not found. Run split_2026_round_results.py")
        return

    booths_2021, booths_2026 = load_booth_counts()

    if not booths_2021:
        print("\n✗ No 2021 booth counts found in data/2021/ files")
        return
    if not booths_2026:
        print("\n✗ No 2026 booth counts found in data/2026/ files. Run download_2026_booth_list.py")
        return
    
    # Analyze changes
    changes = []
    for const_no_str in sorted(int(k) for k in booths_2021.keys()):
        const_no_str = str(const_no_str)
        b21 = booths_2021.get(const_no_str, 0)
        b26 = booths_2026.get(const_no_str, 0)
        
        if b21 > 0:
            diff = b26 - b21
            pct_change = (diff / b21) * 100
            scaling = b26 / b21 if b21 > 0 else 1.0
            changes.append({
                "const_no": int(const_no_str),
                "b21": b21,
                "b26": b26,
                "diff": diff,
                "pct": pct_change,
                "scaling": scaling,
                "category": "increase" if diff > 0 else ("decrease" if diff < 0 else "same")
            })
    
    if not changes:
        print("\n✗ No valid comparison data")
        return
    
    # Statistics
    print("\n📊 OVERALL STATISTICS:")
    print(f"   Total constituencies: {len(changes)}")
    print(f"   Total booths 2021: {sum(c['b21'] for c in changes)}")
    print(f"   Total booths 2026: {sum(c['b26'] for c in changes)}")
    print(f"   Net change: {sum(c['diff'] for c in changes):+d} booths")
    
    pct_changes = [c['pct'] for c in changes]
    print(f"\n   Avg booth change: {statistics.mean(pct_changes):+.2f}%")
    print(f"   Median booth change: {statistics.median(pct_changes):+.2f}%")
    print(f"   Max increase: {max([c['pct'] for c in changes if c['pct'] > 0], default=0):.2f}%")
    print(f"   Max decrease: {min([c['pct'] for c in changes if c['pct'] < 0], default=0):.2f}%")
    
    # Category breakdown
    increases = [c for c in changes if c['diff'] > 0]
    decreases = [c for c in changes if c['diff'] < 0]
    same = [c for c in changes if c['diff'] == 0]
    
    print(f"\n🔄 CHANGE DISTRIBUTION:")
    print(f"   Increased booths: {len(increases)} constituencies")
    print(f"   Decreased booths: {len(decreases)} constituencies")
    print(f"   Unchanged: {len(same)} constituencies")
    
    # Top increases
    print(f"\n📈 TOP 10 BOOTH INCREASES:")
    sorted_inc = sorted(increases, key=lambda x: x['pct'], reverse=True)[:10]
    for i, c in enumerate(sorted_inc, 1):
        print(f"   {i:2d}. Const {c['const_no']:3d}: {c['b21']:3d} → {c['b26']:3d} "
              f"({c['diff']:+3d}, {c['pct']:+5.1f}%, ×{c['scaling']:.3f})")
    
    # Top decreases
    if decreases:
        print(f"\n📉 TOP 10 BOOTH DECREASES:")
        sorted_dec = sorted(decreases, key=lambda x: x['pct'])[:10]
        for i, c in enumerate(sorted_dec, 1):
            print(f"   {i:2d}. Const {c['const_no']:3d}: {c['b21']:3d} → {c['b26']:3d} "
                  f"({c['diff']:+3d}, {c['pct']:+5.1f}%, ×{c['scaling']:.3f})")
    
    # Scaling factor ranges
    print(f"\n📊 SCALING FACTOR DISTRIBUTION:")
    scaling_factors = [c['scaling'] for c in changes]
    scaling_ranges = {
        "< 0.8 (>20% decrease)": len([s for s in scaling_factors if s < 0.8]),
        "0.8 - 0.9 (10-20% decrease)": len([s for s in scaling_factors if 0.8 <= s < 0.9]),
        "0.9 - 1.0 (0-10% decrease)": len([s for s in scaling_factors if 0.9 <= s < 1.0]),
        "1.0 (no change)": len([s for s in scaling_factors if s == 1.0]),
        "1.0 - 1.1 (0-10% increase)": len([s for s in scaling_factors if 1.0 < s <= 1.1]),
        "1.1 - 1.2 (10-20% increase)": len([s for s in scaling_factors if 1.1 < s <= 1.2]),
        "1.2 - 1.5 (20-50% increase)": len([s for s in scaling_factors if 1.2 < s <= 1.5]),
        "> 1.5 (>50% increase)": len([s for s in scaling_factors if s > 1.5]),
    }
    
    for range_name, count in scaling_ranges.items():
        if count > 0:
            pct = (count / len(scaling_factors)) * 100
            print(f"   {range_name}: {count:3d} constituencies ({pct:5.1f}%)")
    
    # Sampling implications
    print(f"\n💡 SAMPLING IMPLICATIONS:")
    print(f"   When using 2021 data to predict 2026:")
    print(f"   - Constituencies with +30% booths: votes scale up by ~1.3x")
    print(f"   - Constituencies with -10% booths: votes scale down by ~0.9x")
    print(f"   - Larger samples (more booths): potentially more stable per-booth patterns")
    
    # Export detailed CSV
    csv_file = os.path.join(DATA_DIR, "booth_changes_analysis.csv")
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("Constituency_No,Booths_2021,Booths_2026,Absolute_Change,Percent_Change,Scaling_Factor\n")
        for c in sorted(changes, key=lambda x: x['const_no']):
            f.write(f"{c['const_no']},{c['b21']},{c['b26']},{c['diff']:+d},{c['pct']:+.2f}%,{c['scaling']:.4f}\n")
    
    print(f"\n✓ Detailed analysis saved to: {csv_file}")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
