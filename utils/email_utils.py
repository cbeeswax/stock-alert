import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

def format_summary(ema_list, high_list):
    """
    Builds a detailed, unified summary for email content.
    Always includes both sections, even if empty.
    Shows key metrics: Score, Trend, Volume, RSI, and prices.
    """
    summary = ""

    # --- EMA Crossover Section ---
    summary += "📈 **EMA Crossovers (3–12% above crossover)**\n\n"
    if ema_list:
        for s in ema_list:
            trend_tag = "🔥 Strong Momentum" if s["Score"] >= 8 else "⚡ Steady Trend"
            summary += (
                f"- {s['Ticker']}: +{s['PctAboveCrossover']}% above crossover "
                f"(Crossed {s['CrossoverDate']}, ${s['CrossoverPrice']} → ${s['CurrentPrice']}) "
                f"[EMA20:{s['EMA20']} EMA50:{s['EMA50']} EMA200:{s['EMA200']}] "
                f"[VolRatio:{s['VolumeRatio']} RSI:{s['RSI14']}] "
                f"{trend_tag} | Score: {s['Score']}\n"
            )
    else:
        summary += "No EMA Crossovers with strong momentum today.\n"
    summary += "\n"

    # --- 52-Week High Section ---
    summary += "🚀 **New 52-Week Highs**\n\n"
    if high_list:
        for h in high_list:
            summary += (
                f"- {h['Ticker']} ({h['Company']}): ${h['Close']} on {h['HighDate']} "
                f"[Trend: {h['Trend']} | VolRatio:{h['VolumeRatio']} | RSI:{h['RSI14']}] "
                f"| Score: {h['Score']}\n"
            )
    else:
        summary += "No new 52-week highs today.\n"

    return summary


def send_email_alert(ema_list, high_list, subject_prefix="📊 Market Summary", custom_body=None):
     """
    Sends an email with either a custom body or formatted summary of EMA and 52-week high signals.
    Signals are sorted by Score descending for priority.
    """
    # --- Sort lists by Score descending ---
    if ema_list:
        ema_list = sorted(ema_list, key=lambda x: x.get("Score", 0), reverse=True)
    if high_list:
        high_list = sorted(high_list, key=lambda x: x.get("Score", 0), reverse=True)

    # --- Build email body ---
    body = custom_body or format_summary(ema_list, high_list)

    # --- Email credentials from environment ---
    sender = os.getenv("EMAIL_SENDER")
    receiver = os.getenv("EMAIL_RECEIVER")
    password = os.getenv("EMAIL_PASSWORD")
    subject = f"{subject_prefix} – {datetime.now().strftime('%Y-%m-%d')}"

    # --- Build MIME email ---
    msg = MIMEText(body, "plain")
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
