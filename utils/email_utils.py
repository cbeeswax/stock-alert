import os
import smtplib
from email.mime.text import MIMEText
import pandas as pd
from datetime import datetime
from config.trading_config import POSITION_INITIAL_EQUITY, POSITION_RISK_PER_TRADE_PCT

# ============================================================
# Helper: Create HTML table with score-based row coloring
# ============================================================
def df_to_html_table(df, score_column="Score", title="", max_rows=5):
    if df is None or df.empty:
        return f"<p>No {title} today.</p>"

    # --- Sort by score descending if score exists ---
    if score_column and score_column in df.columns:
        df = df.sort_values(by=score_column, ascending=False)

    # --- Limit rows ---
    if max_rows is not None:
        df = df.head(max_rows)

    html = f"<h2>{title}</h2>"
    html += "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;'>"

    # Header
    html += "<tr>"
    for col in df.columns:
        html += (
            "<th style='background-color:#f2f2f2;"
            "font-weight:bold;text-align:center;'>"
            f"{col}</th>"
        )
    html += "</tr>"

    # Rows
    for _, row in df.iterrows():
        score = row.get(score_column, 0) if score_column else 0

        if score_column:
            if score >= 8.5:
                color = "#c6efce"   # green
            elif score >= 6.5:
                color = "#ffeb9c"   # yellow
            else:
                color = "#f4c7c3"   # red
        else:
            color = "#ffffff"      # neutral

        html += f"<tr style='background-color:{color};'>"
        for col in df.columns:
            # Show numbers rounded if float
            val = row[col]
            if isinstance(val, float):
                val = round(val, 2)
            html += f"<td style='text-align:center;'>{val}</td>"
        html += "</tr>"

    html += "</table><br>"
    return html


# ============================================================
# Normalize lists for table-friendly DataFrames
# ============================================================
def normalize_highs_for_table(high_list):
    if not high_list:
        return pd.DataFrame()
    df = pd.DataFrame(high_list)
    preferred_columns = [
        "Ticker", "Company", "Close", "High52", "PctFrom52High",
        "EMA20", "EMA50", "EMA200", "VolumeRatio", "RSI14", "Score", "NormalizedScore",
    ]
    return df[[c for c in preferred_columns if c in df.columns]]


def normalize_watchlist_for_table(watch_list):
    if not watch_list:
        return pd.DataFrame()
    df = pd.DataFrame(watch_list)
    preferred_columns = [
        "Ticker", "Company", "Close", "High52", "PctFrom52High",
        "EMA20", "EMA50", "EMA200", "RSI14",
    ]
    return df[[c for c in preferred_columns if c in df.columns]]


def normalize_generic_for_table(generic_list):
    """For consolidation_list or rs_list where Score/NormalizedScore may exist"""
    if not generic_list:
        return pd.DataFrame()
    return pd.DataFrame(generic_list)  # keep all columns


# ============================================================
# Main Email Sender
# ============================================================
def send_email_alert(
    trade_df,
    all_signals=None,
    high_buy_list=None,
    high_watch_list=None,
    ema_list=None,
    consolidation_list=None,
    rs_list=None,
    subject_prefix="📊 Market Summary",
    html_body=None,
    position_tracker=None,
    action_signals=None,  # 🆕 NEW parameter for exit/action alerts
):
    """
    Sends simplified HTML email with:
    - Open positions (currently held)
    - Actionable trades only (top trades that passed all filters)
    - Watchlist of 10 stocks with strategy names
    """
    if html_body:
        body_html = html_body
    else:
        # Detect if this is position trading
        is_position_trading = not trade_df.empty and "Priority" in trade_df.columns

        if is_position_trading:
            body_html = "<h1>📊 Position Trading Scanner - Long-Term Setups</h1>"
            body_html += f"<p><strong>Config:</strong> 2% risk/trade, 60-150 day holds, RS≥30%, ADX≥30, Vol≥2.5x | {datetime.now().strftime('%Y-%m-%d')}</p>"
        else:
            body_html = "<h1>📊 Daily Market Scan - Actionable Trades</h1>"
            body_html += f"<p><strong>Config:</strong> 2:1 R/R, ADX≥24, RSI 50-66, Vol≥1.4x | {datetime.now().strftime('%Y-%m-%d')}</p>"

        # 🚨 ACTION SIGNALS (HIGHEST PRIORITY - SHOW FIRST)
        if action_signals:
            exits = action_signals.get('exits', [])
            partials = action_signals.get('partials', [])
            pyramids = action_signals.get('pyramids', [])
            warnings = action_signals.get('warnings', [])

            total_actions = len(exits) + len(partials) + len(pyramids)

            if total_actions > 0:
                body_html += "<hr style='border: 3px solid red;'>"
                body_html += f"<h1 style='color: red;'>🚨 ACTION REQUIRED: {total_actions} SIGNAL(S)</h1>"

                # EXITS (Most Urgent)
                if exits:
                    body_html += "<h2 style='color: red;'>🚨 IMMEDIATE EXITS ({}) - ACTION REQUIRED</h2>".format(len(exits))
                    body_html += "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse; width:100%;'>"
                    body_html += "<tr style='background-color:#ffcccc;'>"
                    body_html += "<th>Ticker</th><th>Exit Type</th><th>Reason</th><th>Action</th><th>Current R</th><th>Days</th><th>Entry $</th><th>Current $</th></tr>"

                    for exit_sig in exits:
                        urgency_color = "#ff0000" if exit_sig['urgency'] == 'IMMEDIATE' else "#ff9999"
                        body_html += f"<tr style='background-color:{urgency_color};'>"
                        body_html += f"<td><strong>{exit_sig['ticker']}</strong></td>"
                        body_html += f"<td>{exit_sig['type']}</td>"
                        body_html += f"<td>{exit_sig['reason']}</td>"
                        body_html += f"<td><strong>{exit_sig['action']}</strong></td>"
                        body_html += f"<td>{exit_sig['current_r']:+.2f}R</td>"
                        body_html += f"<td>{exit_sig['days_held']}d</td>"
                        body_html += f"<td>${exit_sig['entry_price']:.2f}</td>"
                        body_html += f"<td>${exit_sig['current_price']:.2f}</td>"
                        body_html += "</tr>"

                    body_html += "</table><br>"

                # PARTIAL PROFITS
                if partials:
                    body_html += "<h2 style='color: green;'>💰 PARTIAL PROFIT TARGETS ({}) - TAKE PROFITS</h2>".format(len(partials))
                    body_html += "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse; width:100%;'>"
                    body_html += "<tr style='background-color:#ccffcc;'>"
                    body_html += "<th>Ticker</th><th>Reason</th><th>Action</th><th>Current R</th><th>Days</th><th>Entry $</th><th>Current $</th></tr>"

                    for partial in partials:
                        body_html += "<tr style='background-color:#e6ffe6;'>"
                        body_html += f"<td><strong>{partial['ticker']}</strong></td>"
                        body_html += f"<td>{partial['reason']}</td>"
                        body_html += f"<td><strong>{partial['action']}</strong></td>"
                        body_html += f"<td>+{partial['current_r']:.2f}R</td>"
                        body_html += f"<td>{partial['days_held']}d</td>"
                        body_html += f"<td>${partial['entry_price']:.2f}</td>"
                        body_html += f"<td>${partial['current_price']:.2f}</td>"
                        body_html += "</tr>"

                    body_html += "</table><br>"

                # PYRAMID OPPORTUNITIES
                if pyramids:
                    body_html += "<h2 style='color: blue;'>📈 PYRAMID OPPORTUNITIES ({}) - ADD TO WINNERS</h2>".format(len(pyramids))
                    body_html += "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse; width:100%;'>"
                    body_html += "<tr style='background-color:#cce5ff;'>"
                    body_html += "<th>Ticker</th><th>Reason</th><th>Action</th><th>Current R</th><th>Days</th><th>Entry $</th><th>Current $</th></tr>"

                    for pyramid in pyramids:
                        body_html += "<tr style='background-color:#e6f2ff;'>"
                        body_html += f"<td><strong>{pyramid['ticker']}</strong></td>"
                        body_html += f"<td>{pyramid['reason']}</td>"
                        body_html += f"<td><strong>{pyramid['action']}</strong></td>"
                        body_html += f"<td>+{pyramid['current_r']:.2f}R</td>"
                        body_html += f"<td>{pyramid['days_held']}d</td>"
                        body_html += f"<td>${pyramid['entry_price']:.2f}</td>"
                        body_html += f"<td>${pyramid['current_price']:.2f}</td>"
                        body_html += "</tr>"

                    body_html += "</table><br>"

                body_html += "<hr style='border: 3px solid red;'>"

        # 🆕 Show Open Positions (if any)
        if position_tracker:
            open_positions = position_tracker.get_all_positions()
            if open_positions:
                pos_data = []
                for ticker, pos in open_positions.items():
                    pos_data.append({
                        "Ticker": ticker,
                        "Entry $": f"${pos.get('entry_price', 0):.2f}",
                        "Entry Date": str(pos.get('entry_date', 'N/A'))[:10],
                        "Strategy": pos.get('strategy', 'Unknown'),
                        "Stop $": f"${pos.get('stop_loss', 0):.2f}" if pos.get('stop_loss', 0) > 0 else "N/A",
                        "Target $": f"${pos.get('target', 0):.2f}" if pos.get('target', 0) > 0 else "N/A",
                    })

                pos_df = pd.DataFrame(pos_data)
                body_html += "<hr>"
                body_html += df_to_html_table(
                    pos_df,
                    score_column=None,
                    title=f"📊 CURRENT OPEN POSITIONS ({len(pos_df)} stocks)",
                    max_rows=None
                )
                body_html += "<hr>"

        # Actionable Trades Only
        if not trade_df.empty:
            # Detect if this is position trading or short-term trading
            is_position_trading = "Priority" in trade_df.columns and "MaxDays" in trade_df.columns

            if is_position_trading:
                # Calculate position sizing for each trade
                # User can update POSITION_INITIAL_EQUITY in config/trading_config.py
                equity = POSITION_INITIAL_EQUITY  # Default $100k
                risk_pct = POSITION_RISK_PER_TRADE_PCT / 100  # 2% default

                body_html += f"<h2>🎯 NEW POSITION TRADES ({len(trade_df)} signals) - ACTION ITEMS</h2>"
                body_html += f"<p><strong>Account Equity:</strong> ${equity:,.0f} | <strong>Risk per Trade:</strong> {risk_pct*100}% = ${equity*risk_pct:,.0f}</p>"
                body_html += "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse; width:100%;'>"
                body_html += "<tr style='background-color:#e6f2ff;'>"
                body_html += "<th>Ticker</th><th>Strategy</th><th>Action</th><th>Shares</th><th>Position $</th>"
                body_html += "<th>Entry $</th><th>Stop $</th><th>Target $</th><th>Risk/Share</th><th>Max Days</th></tr>"

                for idx, row in trade_df.iterrows():
                    ticker = row['Ticker']
                    strategy = row['Strategy']
                    entry = row['Entry']
                    stop = row['StopLoss']
                    target = row['Target']
                    max_days = row.get('MaxDays', 150)

                    # Calculate position sizing
                    risk_amount = equity * risk_pct  # $2,000 default
                    risk_per_share = entry - stop
                    shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
                    position_size = shares * entry

                    # Color code by score
                    score = row.get('Score', 0)
                    if score >= 8:
                        row_color = "#c6efce"  # green
                    elif score >= 6:
                        row_color = "#ffeb9c"  # yellow
                    else:
                        row_color = "#f4c7c3"  # red

                    body_html += f"<tr style='background-color:{row_color};'>"
                    body_html += f"<td><strong>{ticker}</strong></td>"
                    body_html += f"<td>{strategy}</td>"
                    body_html += f"<td><strong>BUY {shares} shares at ${entry:.2f}</strong></td>"
                    body_html += f"<td><strong>{shares}</strong></td>"
                    body_html += f"<td>${position_size:,.0f}</td>"
                    body_html += f"<td>${entry:.2f}</td>"
                    body_html += f"<td>${stop:.2f}</td>"
                    body_html += f"<td>${target:.2f}</td>"
                    body_html += f"<td>${risk_per_share:.2f}</td>"
                    body_html += f"<td>{max_days}d</td>"
                    body_html += "</tr>"

                body_html += "</table>"

                # Add summary instructions
                body_html += "<br><h3>📋 EXECUTION CHECKLIST:</h3>"
                body_html += "<ol>"
                body_html += "<li><strong>Place Orders:</strong> Buy the shares at market or limit order</li>"
                body_html += "<li><strong>Set Stop Loss:</strong> Place stop-loss order at the Stop $ price</li>"
                body_html += "<li><strong>Set Alert:</strong> Set price alert at Target $ for partial profit (30%)</li>"
                body_html += f"<li><strong>Track Position:</strong> Run <code>python manage_positions.py add TICKER ENTRY_PRICE</code></li>"
                body_html += "<li><strong>Monitor Daily:</strong> Next scan will check for exit signals automatically</li>"
                body_html += "</ol><br>"

            else:
                # Short-term trading columns (old system)
                action_cols = ["Ticker", "Strategy", "Entry", "StopLoss", "Target",
                               "ATR", "SuggestedShares", "FinalScore", "Expectancy"]
                score_col = "FinalScore"
                title_prefix = "🔥 ACTIONABLE TRADES"

                action_df = trade_df[[c for c in action_cols if c in trade_df.columns]]

                body_html += df_to_html_table(
                    action_df,
                    score_column=score_col,
                    title=f"{title_prefix} ({len(action_df)} stocks)",
                    max_rows=None  # Show all actionable trades
                )
        else:
            body_html += "<h2>🔥 ACTIONABLE TRADES</h2><p>No actionable trades today.</p>"

        # Watchlist - Top 10 stocks that didn't make the cut
        watchlist_items = []

        # Combine all signals that aren't in actionable trades
        if all_signals:
            actionable_tickers = set(trade_df["Ticker"].tolist()) if not trade_df.empty else set()

            for signal in all_signals:
                ticker = signal.get("Ticker")
                if ticker and ticker not in actionable_tickers:
                    watchlist_items.append({
                        "Ticker": ticker,
                        "Strategy": signal.get("Strategy", "Unknown"),
                        "Score": signal.get("Score", 0)
                    })

        # Sort by score and take top 10
        if watchlist_items:
            watch_df = pd.DataFrame(watchlist_items)
            watch_df = watch_df.sort_values(by="Score", ascending=False).head(10)
            body_html += df_to_html_table(
                watch_df,
                score_column="Score",
                title="👀 WATCHLIST (Top 10 Non-Actionable Signals)",
                max_rows=None
            )
        else:
            body_html += "<h2>👀 WATCHLIST</h2><p>No watchlist stocks today.</p>"

    # Email credentials
    sender = os.getenv("EMAIL_SENDER")
    receiver = os.getenv("EMAIL_RECEIVER")
    password = os.getenv("EMAIL_PASSWORD")

    # Update subject if there are urgent actions
    subject = f"{subject_prefix} – {datetime.now().strftime('%Y-%m-%d')}"
    if action_signals:
        total_actions = len(action_signals.get('exits', [])) + len(action_signals.get('partials', []))
        if total_actions > 0:
            subject = f"🚨 ACTION REQUIRED ({total_actions}) – {subject}"

    # Build MIME email
    msg = MIMEText(body_html, "html")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    # Send email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print(f"✅ Email sent: {subject}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
