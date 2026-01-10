import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pandas as pd

def format_trade_table_html(trade_df):
    """
    Converts pre-buy actionable trades DataFrame into an HTML table for email.
    """
    if trade_df.empty:
        return "<p>No actionable trades today.</p>"

    html = "<h2>📈 Ready-to-Trade EMA Signals</h2>"
    html += trade_df.to_html(index=False, border=1, justify="center", classes="trade-table")
    return html

def format_highs_html(high_list):
    """
    Converts 52-week highs into an HTML list.
    """
    if not high_list:
        return "<p>No new 52-week highs today.</p>"

    html = "<h2>🚀 New 52-Week Highs</h2><ul>"
    for h in high_list:
        html += (
            f"<li>{h['Ticker']} ({h.get('Company','N/A')}): ${h['Close']} "
            f"on {h.get('HighDate','N/A')} | Trend: {h.get('Trend','N/A')} "
            f"| VolRatio: {h.get('VolumeRatio','N/A')} | RSI: {h.get('RSI14','N/A')} "
            f"| Score: {h.get('Score','N/A')}</li>"
        )
    html += "</ul>"
    return html

def send_email_alert(trade_df, high_list, subject_prefix="📊 Market Summary", custom_body=None):
    """
    Sends an HTML email with actionable trades and 52-week highs.
    If custom_body is provided, uses that instead.
    """
    # --- Build HTML body ---
    if custom_body:
        body_html = custom_body
    else:
        body_html = ""
        body_html += format_trade_table_html(trade_df)
        body_html += "<br><br>"
        body_html += format_highs_html(high_list)

    # --- Email credentials from environment ---
    sender = os.getenv("EMAIL_SENDER")
    receiver = os.getenv("EMAIL_RECEIVER")
    password = os.getenv("EMAIL_PASSWORD")
    subject = f"{subject_prefix} – {datetime.now().strftime('%Y-%m-%d')}"

    # --- Build MIME email ---
    msg = MIMEText(body_html, "html")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    # --- Send email ---
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print(f"✅ Email sent: {subject}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
