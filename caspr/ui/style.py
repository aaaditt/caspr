"""Shared look for the remaining Qt surfaces (pill, dialogs, tray icons):
Velvet — warm espresso, cream text, coral→amber accents. The main window's
React app carries the same tokens in webui/src/index.css."""

from __future__ import annotations

import html

BG = "#151110"
SURFACE = "#1c1715"
RAISED = "#241d1a"
HAIRLINE = "#2a221d"
ACCENT = "#ffb74d"  # amber — solid accent for Qt widgets
CORAL = "#ff8a65"  # gradient partner (waveform, icons)
FG = "#f6efe7"
MUTED = "#9c8f85"
FLAG = "#ff5c49"

# One source of truth for state → color, shared by tray, icons, and dialogs.
STATE_COLORS = {
    "loading": MUTED,
    "idle": ACCENT,
    "recording": "#ff5c49",
    "processing": "#e8a13c",
    "error": "#e05252",
    "paused": "#b8a06a",
}

APP_QSS = f"""
QWidget {{
    font-family: 'Segoe UI Variable', 'Segoe UI';
    font-size: 14px;
    background: {BG};
    color: {FG};
}}
QLabel {{ background: transparent; }}
QLabel#h1 {{ font-size: 22px; font-weight: 600; }}
QLabel#caption {{ color: {MUTED}; font-size: 12px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#note {{ color: {MUTED}; font-size: 11px; }}
QFrame#card {{
    background: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-radius: 12px;
}}
QPushButton {{
    background: {ACCENT}; color: #2b1a09; border: none; border-radius: 8px;
    padding: 7px 16px; font-weight: 600;
}}
QPushButton:hover {{ background: #ffc76e; }}
QPushButton[flat="true"] {{ background: transparent; color: {ACCENT}; }}
QTextEdit, QListWidget, QLineEdit, QComboBox, QDoubleSpinBox {{
    background: {SURFACE}; color: {FG};
    border: 1px solid {HAIRLINE}; border-radius: 10px; padding: 8px;
    selection-background-color: {ACCENT}; selection-color: #2b1a09;
}}
QComboBox::drop-down {{ border: none; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; color: {FG}; border: 1px solid {HAIRLINE};
}}
QCheckBox {{ background: transparent; }}
QMenu {{ background: {SURFACE}; color: {FG}; border: 1px solid {HAIRLINE}; }}
QMenu::item:selected {{ background: {RAISED}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #2e2620; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""


def flagged_html(text: str, spans: list[tuple[int, int]]) -> str:
    """Escape text and wrap flagged spans in ember for rich-text labels."""
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
