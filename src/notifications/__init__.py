"""Notifications - email alerts and formatting"""

from .email import send_email_alert
from .formatter import format_trade_for_email, format_trades_for_email
from .templates import get_html_header, get_html_footer, get_text_header, get_text_footer

__all__ = [
    "send_email_alert",
    "format_trade_for_email",
    "format_trades_for_email",
    "get_html_header",
    "get_html_footer",
    "get_text_header",
    "get_text_footer",
]

