import os
import smtplib
from email.mime.text import MIMEText
import pandas as pd
from datetime import datetime


# ============================================================
# Helper: Create HTML table with score-based row coloring
# ============================================================
def df_to_html_table(df, score_column="Score", title=""):
    if df is None or df.empty:
        return f"<p>No {title} today.</p>"

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
            color = "#ffffff"      # neutral (watchlist)

        html += f"<tr style='background-color:{color};'>"
        for col in df.columns:
            html += f"<td style='text-align:center;'>{row[col]}</td>"
        html += "</tr>"

    html += "</table><br>"
    return html


# ============================================================
# Normalize 52-week lists into table-friendly DataFrame
# ============================================================
def normalize_highs_for_table(high_list):
    if not high_list:
        return pd.DataFrame()

    df = pd.DataFrame(high_list)

    preferred_columns = [
        "Ticker",
        "Company",
        "Close",
        "High52",
        "PctFrom52High",
        "EMA20",
        "EMA50",
        "EMA200",
        "VolumeRatio",
        "RSI14",
        "Score",
    ]

    return df[[c for c in preferred_columns if c in df.columns]]


def normalize_watchlist_for_table(watch_list):
    if not watch_list:
        return pd.DataFrame()

    df = pd.DataFrame(watch_list)

    preferred_columns = [
        "Ticker",
        "Company",
        "Close",
        "High52",
        "PctFrom52High",
        "EMA20",
        "EMA50",
        "EMA200",
        "RSI14",
    ]

    return df[[c for c in preferred_columns if c in df.columns]]


# ============================================================
# Main Email Sender
# ============================================================
def send_email_alert(
    trade_df,
    high_buy_list,
    high_watch_list=None,
    ema_list=None,
    subject_prefix="📊 Market Summary",
    html_body=None,
):
    """
    Sends an HTML email with:
    - EMA crossover pre-buy signals
    - Pre-buy actionable trades
    - 52-week high BUY-ready continuations
    - 52-week near-high WATCHLIST

    All formatting handled here.
    """

    # --------------------------------------------------------
    # Build email body
    # --------------------------------------------------------
    if html_body:
        body_html = html_body
    else:
        body_html = "<h1>📊 Daily Market Scan</h1>"

        # ============================
        # EMA Crossovers
        # ============================
        if ema_list:
            ema_df = pd.DataFrame(ema_list)
            body_html += df_to_html_table(
                ema_df,
                score_column="Score",
                title="📈 EMA Crossovers (Trend Ignition)"
            )
        else:
            body_html += "<p>No EMA crossovers today.</p>"

        # ============================
        # Pre-Buy Actionable Trades
        # ============================
        body_html += df_to_html_table(
            trade_df,
            score_column="Score",
            title="🔥 Pre-Buy Actionable Trades"
        )

        # ============================
        # 52-Week High BUY-READY
        # ============================
        if high_buy_list:
            highs_df = normalize_highs_for_table(high_buy_list)
            body_html += df_to_html_table(
                highs_df,
                score_column="Score",
                title="🚀 52-Week High Continuation (BUY-READY)"
            )
        else:
            body_html += "<p>No BUY-ready 52-week continuation setups today.</p>"

        # ============================
        # 52-Week High WATCHLIST
        # ============================
        if high_watch_list:
            watch_df = normalize_watchlist_for_table(high_watch_list)
            body_html += df_to_html_table(
                watch_df,
                score_column=None,
                title="👀 52-Week Near-High Watchlist"
            )
        else:
            body_html += "<p>No 52-week near-high watchlist stocks today.</p>"

    # --------------------------------------------------------
    # Email credentials
    # --------------------------------------------------------
    sender = os.getenv("EMAIL_SENDER")
    receiver = os.getenv("EMAIL_RECEIVER")
    password = os.getenv("EMAIL_PASSWORD")

    subject = f"{subject_prefix} – {datetime.now().strftime('%Y-%m-%d')}"

    # --------------------------------------------------------
    # Build MIME email
    # --------------------------------------------------------
    msg = MIMEText(body_html, "html")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    # --------------------------------------------------------
    # Send email
    # --------------------------------------------------------
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print(f"✅ Email sent: {subject}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
