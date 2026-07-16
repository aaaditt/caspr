"""Shared look: Wispr-like — minimal, rounded, calm."""

from __future__ import annotations

import html

ACCENT = "#4a90d9"
FLAG = "#ff6b6b"
BG_DARK = "#1c1d22"
FG_LIGHT = "#f4f4f5"

APP_QSS = f"""
QWidget {{ font-family: 'Segoe UI Variable', 'Segoe UI'; font-size: 14px; }}
QDialog, QTabWidget::pane {{ background: {FG_LIGHT}; }}
QPushButton {{
    background: {ACCENT}; color: white; border: none; border-radius: 8px;
    padding: 7px 16px;
}}
QPushButton:hover {{ background: #3b7fc4; }}
QPushButton[flat="true"] {{ background: transparent; color: {ACCENT}; }}
QTextEdit, QListWidget, QLineEdit {{
    background: white; border: 1px solid #e4e4e7; border-radius: 10px; padding: 8px;
}}
QTabBar::tab {{ padding: 8px 18px; border: none; }}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}
"""


def flagged_html(text: str, spans: list[tuple[int, int]]) -> str:
    """Escape text and wrap flagged spans in red for rich-text labels."""
    out, prev = [], 0
    for start, end in spans:
        out.append(html.escape(text[prev:start]))
        out.append(
            f'<span style="color:{FLAG};text-decoration:underline">'
            f"{html.escape(text[start:end])}</span>"
        )
        prev = end
    out.append(html.escape(text[prev:]))
    return "".join(out)
