import os
import smtplib
from email.mime.text import MIMEText
import pandas as pd
from datetime import datetime

# --- Helper to color-code rows based on Score ---
def style_score(row, score_column="Score"):
    score = row.get(score_column, 0)
    if score >= 8:
        color = "#c6efce"  # green
    elif score >= 6:
        color = "#ffeb9c"  # yellow
    else:
        color = "#f4c7c3"  # red
    return [f'background-color: {color}'] * len(row)

# --- Format DataFrame as HTML table with color coding ---
def df_to_html_table(df, score_column="Score", title=""):
    if df.empty:
        return f"<p>No {title} today.</p>"

    styled = df.style.apply(style_score, axis=1, score_column=score_column)\
                     .set_table_attributes('border="1" style="border-collapse: collapse;"')\
                     .set_table_styles([
                         {'selector': 'th', 'props': [('background-color', '#d9d9d9'), ('padding', '4px')]}
                     ])\
                     .render()
    html = f"<h2>{title}</h2>{styled}"
    return html

# --- Format 52-week highs as HTML list ---
def highs_to_html(high_list):
    if not high_list:
        return "<p>No new 52-week highs today.</p>"

    html = "<h2>🚀 New 52-Week Highs</h2><ul>"
    for h in high_list:
        html += f"<li>{h['Ticker']} ({h.get('Company','N/A')}): ${h['Close']} | Score: {h.get('Score','N/A')}</li>"
    html += "</ul>"
    return html

# --- Main function to send email ---
def send_email_alert(trade_df, high_list, ema_list=None, subject_prefix="📊 Market Summary", html_body=None):
    """
    Sends an HTML email with:
    - EMA crossovers
    - Pre-buy actionable trades
    - 52-week highs
    All formatting is handled internally.
    """
    # --- Build HTML body if not provided ---
    if html_body:
        body_html = html_body
    else:
        body_html = "<h1>📊 Daily Market Scan</h1>"

        # EMA Crossovers
        if ema_list:
            ema_df = pd.DataFrame(ema_list)
            body_html += df_to_html_table(ema_df, score_column="Score", title="📈 EMA Crossovers")
        else:
            body_html += "<p>No EMA crossovers today.</p>"

        # Pre-Buy Actionable Trades
        body_html += df_to_html_table(trade_df, score_column="Score", title="🔥 Pre-Buy Actionable Trades")

        # 52-Week Highs
        body_html += highs_to_html(high_list)

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
