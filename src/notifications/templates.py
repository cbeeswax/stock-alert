"""
Email Templates
===============
HTML and text templates for email alerts.
"""


HTML_HEADER_TEMPLATE = """
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #2c3e50; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #3498db; color: white; }}
        .positive {{ color: green; }}
        .negative {{ color: red; }}
        .alert {{ padding: 10px; margin: 10px 0; border-left: 4px solid #e74c3c; background-color: #ffe6e6; }}
    </style>
</head>
<body>
"""

HTML_FOOTER_TEMPLATE = """
</body>
</html>
"""

TEXT_HEADER = "=" * 80 + "\nTRADING ALERT\n" + "=" * 80 + "\n"
TEXT_FOOTER = "\n" + "=" * 80 + "\nEnd of alert\n" + "=" * 80


def get_html_header() -> str:
    """Get HTML header for emails."""
    return HTML_HEADER_TEMPLATE


def get_html_footer() -> str:
    """Get HTML footer for emails."""
    return HTML_FOOTER_TEMPLATE


def get_text_header() -> str:
    """Get text header for emails."""
    return TEXT_HEADER


def get_text_footer() -> str:
    """Get text footer for emails."""
    return TEXT_FOOTER
