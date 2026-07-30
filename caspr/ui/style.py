"""Shared look for the remaining Qt surfaces (pill, dialogs, tray icons):
Ink + Verdant — warm-white paper, near-black ink text, verdant accent. The main window's
React app carries the same tokens in webui/src/index.css."""

from __future__ import annotations

import html

BG = "#FCFBF9"
SURFACE = "#FFFFFF"
RAISED = "#F1EEE7"
HAIRLINE = "#EAE6DE"
ACCENT = "#28382E"  # verdant — solid accent for Qt widgets
CORAL = "#3E5245"  # lighter verdant tint — gradient partner (waveform, icons)
FG = "#1A1815"
MUTED = "#8A8378"
FLAG = "#D64545"

# One source of truth for state → color, shared by tray, icons, and dialogs.
STATE_COLORS = {
    "loading": MUTED,
    "idle": FG,
    "recording": FLAG,
    "processing": ACCENT,
    "error": FLAG,
    "paused": MUTED,
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
    background: {FG}; color: {BG}; border: none; border-radius: 8px;
    padding: 7px 16px; font-weight: 600;
}}
QPushButton:hover {{ background: {ACCENT}; }}
QPushButton[flat="true"] {{ background: transparent; color: {ACCENT}; }}
QTextEdit, QListWidget, QLineEdit, QComboBox, QDoubleSpinBox {{
    background: {SURFACE}; color: {FG};
    border: 1px solid {HAIRLINE}; border-radius: 10px; padding: 8px;
    selection-background-color: {ACCENT}; selection-color: {BG};
}}
QComboBox::drop-down {{ border: none; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; color: {FG}; border: 1px solid {HAIRLINE};
}}
QCheckBox {{ background: transparent; }}
QMenu {{ background: {SURFACE}; color: {FG}; border: 1px solid {HAIRLINE}; }}
QMenu::item:selected {{ background: {RAISED}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #ddd7cb; border-radius: 4px; min-height: 30px; }}
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
