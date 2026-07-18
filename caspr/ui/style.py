"""Shared look: Wispr-like — dark, minimal, rounded, calm. One accent."""

from __future__ import annotations

import html

BG = "#131316"
SURFACE = "#1c1d22"
ACCENT = "#22d3ee"
FG = "#f4f4f5"
MUTED = "#8b8b93"
FLAG = "#ff6b6b"

# One source of truth for state → color, shared by tray, window, and icons.
STATE_COLORS = {
    "loading": MUTED,
    "idle": ACCENT,
    "recording": "#ef4444",
    "processing": "#f59e0b",
    "error": "#dc2626",
    "paused": "#eab308",
}

_STATUS_DOT_QSS = "\n".join(
    f'QLabel#statusDot[state="{state}"] {{ color: {color}; }}'
    for state, color in STATE_COLORS.items()
)

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
QLabel#statValue {{ font-size: 26px; font-weight: 700; }}
QLabel#statusDot {{ font-size: 16px; color: {MUTED}; }}
{_STATUS_DOT_QSS}
QFrame#card {{
    background: {SURFACE};
    border: 1px solid #26272e;
    border-radius: 12px;
}}
QFrame#sidebarFrame {{ background: {BG}; }}
QLabel#brandName {{ font-size: 16px; font-weight: 600; }}
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
QListWidget#sidebar::item:hover {{
    background: #202128;
    color: {FG};
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
QWidget#transparentRow {{ background: transparent; }}
QToolButton {{
    background: transparent; color: {ACCENT}; border: 1px solid #26272e;
    border-radius: 8px; padding: 6px 12px;
}}
QToolButton::menu-indicator {{ image: none; }}
QScrollArea {{ background: {BG}; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #2e2f38; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
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
