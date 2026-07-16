"""Shared look: Wispr-like — dark, minimal, rounded, calm. One accent."""

from __future__ import annotations

import html

BG = "#131316"
SURFACE = "#1c1d22"
ACCENT = "#22d3ee"
FG = "#f4f4f5"
MUTED = "#8b8b93"
FLAG = "#ff6b6b"

# Kept for the pill, which predates the rename.
BG_DARK = SURFACE
FG_LIGHT = FG

APP_QSS = f"""
QWidget {{
    font-family: 'Segoe UI Variable', 'Segoe UI';
    font-size: 14px;
    background: {BG};
    color: {FG};
}}
QLabel {{ background: transparent; }}
QFrame#card {{
    background: {SURFACE};
    border: 1px solid #26272e;
    border-radius: 12px;
}}
QListWidget#sidebar {{
    background: {BG};
    border: none;
    padding-top: 8px;
    outline: none;
}}
QListWidget#sidebar::item {{
    padding: 10px 18px;
    border-radius: 8px;
    margin: 2px 10px;
    color: {MUTED};
}}
QListWidget#sidebar::item:selected {{
    background: {SURFACE};
    color: {FG};
}}
QPushButton {{
    background: {ACCENT}; color: #06272c; border: none; border-radius: 8px;
    padding: 7px 16px; font-weight: 600;
}}
QPushButton:hover {{ background: #67e2f4; }}
QPushButton[flat="true"] {{ background: transparent; color: {ACCENT}; }}
QTextEdit, QListWidget, QLineEdit, QComboBox, QDoubleSpinBox {{
    background: {SURFACE}; color: {FG};
    border: 1px solid #26272e; border-radius: 10px; padding: 8px;
    selection-background-color: {ACCENT}; selection-color: #06272c;
}}
QComboBox::drop-down {{ border: none; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; color: {FG}; border: 1px solid #26272e;
}}
QCheckBox {{ background: transparent; }}
QMenu {{ background: {SURFACE}; color: {FG}; border: 1px solid #26272e; }}
QMenu::item:selected {{ background: {BG}; }}
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
