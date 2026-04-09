"""
Dollar P&L calculator — reads backtest_trades.json.
Position sized by risk: shares = max_risk / (entry - stop)
Position capped at 20% of portfolio (max_pos).
"""
import json, os, sys

PORTFOLIO = 100_000
MAX_RISK  = 2_000
MAX_POS   = 20_000

if len(sys.argv) > 1:
    trades_path = sys.argv[1]
else:
    trades_path = os.path.join(os.path.dirname(__file__), "..", "data", "predictor", "backtest_trades.json")
with open(trades_path) as f:
    raw_trades = json.load(f)

print(f"Portfolio: ${PORTFOLIO:,}  |  Max risk/trade: ${MAX_RISK:,}  |  Max position: ${MAX_POS:,}")
print()

week_pnl      = {}
week_invested = {}
week_risk     = {}
week_picks    = {}
all_results   = []

for t in raw_trades:
    week    = t["week"]
    ticker  = t["ticker"]
    entry   = t["entry"]
    stop    = t["stop"]
    exit_p  = t["exit"]

    risk_per_share = abs(entry - stop)
    if risk_per_share < 0.01:
        risk_per_share = 0.01
    shares = int(MAX_RISK / risk_per_share)
    pos_val = shares * entry

    capped = ""
    if pos_val > MAX_POS:
        shares  = int(MAX_POS / entry)
        pos_val = shares * entry
        capped  = " [CAPPED]"

    actual_risk = shares * risk_per_share
    dollar_pnl  = shares * (exit_p - entry)
    pnl_pct     = (exit_p - entry) / entry * 100
    result      = "WIN " if dollar_pnl > 50 else ("LOSS" if dollar_pnl < -50 else "flat")

    week_pnl.setdefault(week, 0.0)
    week_invested.setdefault(week, 0.0)
    week_risk.setdefault(week, 0.0)
    week_picks.setdefault(week, 0)

    week_pnl[week]      += dollar_pnl
    week_invested[week] += pos_val
    week_risk[week]     += actual_risk
    week_picks[week]    += 1

    all_results.append({**t, "dollar_pnl": dollar_pnl, "pnl_pct": pnl_pct,
                        "shares": shares, "pos_val": pos_val, "actual_risk": actual_risk,
                        "result": result, "capped": capped})

    print(f"  {week:7}  {ticker:<5}  {shares:>5}sh @ ${entry:<7.2f}  pos=${pos_val:>8,.0f}  "
          f"risk=${actual_risk:>6,.0f}  exit=${exit_p:<7.2f}  "
          f"PnL=${dollar_pnl:>+8,.0f} ({pnl_pct:+5.1f}%)  {result}{capped}")

print()
print("=" * 100)
print(f"{'Week':<10} {'Picks':>6} {'PnL':>10} {'Risk Deployed':>14} {'Capital Used':>13} {'Portfolio':>12}")
print("-" * 100)

cum = PORTFOLIO
WEEK_ORDER = ["Jan 5", "Jan 12", "Jan 19", "Jan 26",
              "Feb 2", "Feb 9", "Feb 17", "Feb 23",
              "Mar 2", "Mar 9", "Mar 16", "Mar 23", "Mar 30"]
# Use only weeks that actually have trades
WEEK_ORDER = [w for w in WEEK_ORDER if w in week_pnl]
for week in WEEK_ORDER:
    pnl   = week_pnl[week]
    cum  += pnl
    print(f"  {week:<10}  {week_picks[week]:>4}  ${pnl:>+9,.0f}  "
          f"${week_risk[week]:>12,.0f}  ${week_invested[week]:>12,.0f}  ${cum:>11,.0f}")

total = sum(week_pnl.values())
print("=" * 100)
print(f"  TOTAL: {len(raw_trades)} picks | PnL = ${total:>+,.0f}  ({total/PORTFOLIO*100:+.1f}%)  "
      f"Final portfolio = ${PORTFOLIO + total:,.0f}")

wins   = [r for r in all_results if r["result"] == "WIN "]
losses = [r for r in all_results if r["result"] == "LOSS"]
print(f"\n  Win rate: {len(wins)}/{len(all_results)} ({len(wins)/len(all_results)*100:.0f}%)")
print(f"  Avg WIN  = ${sum(r['dollar_pnl'] for r in wins)/max(len(wins),1):>+,.0f}  "
      f"Avg LOSS = ${sum(r['dollar_pnl'] for r in losses)/max(len(losses),1):>+,.0f}")

