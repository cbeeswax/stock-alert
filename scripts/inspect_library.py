import json

with open(r"C:\Users\pelac\Git\stock-alert\data\predictor\pattern_library.json") as f:
    lib = json.load(f)

print("Total setups:", lib["total_setups"])
print("Total full patterns:", lib["total_patterns"])
print("Feature win rates count:", len(lib["feature_win_rates"]))
print("Pair win rates count:", len(lib["pair_win_rates"]))

print("\nFeature importance ranking:")
for feat, imp in lib["feature_importance"].items():
    print(f"  {feat:25s}  importance={imp:.4f}")

print("\nAll feature win rates:")
for k, v in sorted(lib["feature_win_rates"].items(), key=lambda x: -abs(x[1]["win_rate"] - 0.5)):
    wr = v["win_rate"]
    cnt = v["count"]
    pnl = v["avg_pnl"]
    print(f"  {k:45s}  WR={wr:.1%}  n={cnt:5d}  avg_pnl={pnl:+.2f}%")

print("\nBest pair win rates (WR>58%, n>=50):")
best_pairs = sorted(lib["pair_win_rates"].items(), key=lambda x: -x[1]["win_rate"])
for k, v in best_pairs[:20]:
    if v["win_rate"] > 0.57 and v["count"] >= 50:
        pnl = v["avg_pnl"]
        print(f"  WR={v['win_rate']:.1%} n={v['count']:4d} avg={pnl:+.1f}%  {k[:90]}")

print("\nWorst pair win rates (WR<42%, n>=50):")
worst_pairs = sorted(lib["pair_win_rates"].items(), key=lambda x: x[1]["win_rate"])
for k, v in worst_pairs[:15]:
    if v["win_rate"] < 0.43 and v["count"] >= 50:
        pnl = v["avg_pnl"]
        print(f"  WR={v['win_rate']:.1%} n={v['count']:4d} avg={pnl:+.1f}%  {k[:90]}")
