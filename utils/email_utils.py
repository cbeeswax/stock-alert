import os
import smtplib
from email.mime.text import MIMEText
import pandas as pd
from datetime import datetime

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
    position_tracker=None,  # 🆕 NEW parameter
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
        body_html = "<h1>📊 Daily Market Scan - Actionable Trades</h1>"
        body_html += f"<p><strong>Config:</strong> 2:1 R/R, ADX≥24, RSI 50-66, Vol≥1.4x | {datetime.now().strftime('%Y-%m-%d')}</p>"

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
            # Select columns for actionable trades
            action_cols = ["Ticker", "Strategy", "Entry", "StopLoss", "Target",
                           "ATR", "SuggestedShares", "FinalScore", "Expectancy"]
            action_df = trade_df[[c for c in action_cols if c in trade_df.columns]]

            body_html += df_to_html_table(
                action_df,
                score_column="FinalScore",
                title=f"🔥 ACTIONABLE TRADES ({len(action_df)} stocks)",
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

    subject = f"{subject_prefix} – {datetime.now().strftime('%Y-%m-%d')}"

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
