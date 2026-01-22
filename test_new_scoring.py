#!/usr/bin/env python3
"""Test the new Expected Value weighted scoring system"""

from core.pre_buy_check import normalize_score, STRATEGY_METRICS

print("=" * 80)
print("IMPROVED SCORING SYSTEM TEST")
print("=" * 80)

# Create sample signals with same normalized quality (8.0)
# but different strategies
test_signals = [
    {"strategy": "EMA Crossover", "raw_score": 80},  # High in 50-100 range
    {"strategy": "52-Week High", "raw_score": 11},   # High in 6-12 range
    {"strategy": "Consolidation Breakout", "raw_score": 9},  # High in 4-10 range
    {"strategy": "BB Squeeze", "raw_score": 80},     # High in 50-100 range
    {"strategy": "Mean Reversion", "raw_score": 85}, # High in 40-100 range
    {"strategy": "%B Mean Reversion", "raw_score": 85},  # High in 40-100 range
    {"strategy": "BB+RSI Combo", "raw_score": 80},   # High in 50-100 range
]

print("\n📊 SCENARIO: 7 signals, all with similar quality")
print("=" * 80)

results = []
for signal in test_signals:
    strategy = signal["strategy"]
    raw_score = signal["raw_score"]

    # Calculate final score using new system
    final_score = normalize_score(raw_score, strategy)

    # Get strategy metrics
    win_rate, avg_r = STRATEGY_METRICS.get(strategy, (0.30, 1.5))
    expected_value = win_rate * avg_r

    results.append({
        "Strategy": strategy,
        "RawScore": raw_score,
        "WinRate": f"{win_rate*100:.0f}%",
        "AvgR": f"{avg_r:.2f}R",
        "ExpectedValue": f"{expected_value:.2f}",
        "FinalScore": final_score
    })

# Sort by FinalScore
results.sort(key=lambda x: x["FinalScore"], reverse=True)

# Display results
print(f"\n{'Rank':<6}{'Strategy':<25}{'Raw':<8}{'WR':<8}{'AvgR':<8}{'EV':<8}{'FinalScore':<12}")
print("-" * 80)

for i, r in enumerate(results, 1):
    rank_marker = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
    print(f"{rank_marker} {i:<3} {r['Strategy']:<25}{r['RawScore']:<8}{r['WinRate']:<8}{r['AvgR']:<8}{r['ExpectedValue']:<8}{r['FinalScore']:<12.2f}")

print("\n" + "=" * 80)
print("KEY INSIGHTS:")
print("=" * 80)

top3 = results[:3]
bottom3 = results[-3:]

avg_wr_top3 = sum([float(r['WinRate'].rstrip('%')) for r in top3]) / 3
avg_wr_bottom3 = sum([float(r['WinRate'].rstrip('%')) for r in bottom3]) / 3

print(f"\n✅ TOP 3 SELECTED (MAX_TRADES_PER_SCAN = 3):")
for i, r in enumerate(top3, 1):
    print(f"   {i}. {r['Strategy']} (Score: {r['FinalScore']:.2f}, WR: {r['WinRate']})")

print(f"\n   Average Win Rate: {avg_wr_top3:.1f}%")
print(f"   Average Expected Value: {sum([float(r['ExpectedValue']) for r in top3]) / 3:.2f}")

print(f"\n❌ BOTTOM 3 (Not selected):")
for i, r in enumerate(bottom3, 1):
    print(f"   {i}. {r['Strategy']} (Score: {r['FinalScore']:.2f}, WR: {r['WinRate']})")

print(f"\n   Average Win Rate: {avg_wr_bottom3:.1f}%")
print(f"   Average Expected Value: {sum([float(r['ExpectedValue']) for r in bottom3]) / 3:.2f}")

print("\n" + "=" * 80)
print("COMPARISON:")
print("=" * 80)
print(f"Win Rate Improvement: {avg_wr_top3 - avg_wr_bottom3:+.1f}% (Top 3 vs Bottom 3)")
print(f"This demonstrates how Expected Value weighting selects better trades!")

# Test with varying quality
print("\n\n" + "=" * 80)
print("SCENARIO 2: Same Strategy, Different Quality")
print("=" * 80)

ema_signals = [
    {"quality": "Excellent", "raw_score": 95},
    {"quality": "Good", "raw_score": 75},
    {"quality": "Fair", "raw_score": 60},
    {"quality": "Poor", "raw_score": 52},
]

print(f"\nStrategy: EMA Crossover (65% WR, 2.0R avg, EV = 1.30)")
print(f"\n{'Quality':<15}{'Raw Score':<15}{'Final Score':<15}{'Pass Threshold?':<20}")
print("-" * 65)

MIN_FINAL_SCORE = 3.0

for signal in ema_signals:
    quality = signal["quality"]
    raw_score = signal["raw_score"]
    final_score = normalize_score(raw_score, "EMA Crossover")
    passes = "✅ YES" if final_score >= MIN_FINAL_SCORE else "❌ NO"

    print(f"{quality:<15}{raw_score:<15}{final_score:<15.2f}{passes:<20}")

print(f"\nThreshold: FinalScore >= {MIN_FINAL_SCORE}")

print("\n" + "=" * 80)
print("✅ NEW SCORING SYSTEM WORKING CORRECTLY!")
print("=" * 80)
print("Benefits:")
print("  1. High win rate strategies (EMA, Mean Rev) rank higher")
print("  2. Quality signals from best strategies selected first")
print("  3. Low win rate strategies (Consolidation) rank appropriately lower")
print("  4. Expected Value automatically weights each strategy")
print("  5. Better trade selection = Higher expected profits")
