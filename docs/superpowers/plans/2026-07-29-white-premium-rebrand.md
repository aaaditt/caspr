# White Premium Rebrand ("Ink + Verdant") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace caspr-flow's dark "Velvet" theme (espresso/coral/amber) with a white/paper "Ink + Verdant" theme, and replace the plain coral-dot logo with a waveform-bars mark, across every UI surface (webui React app, Qt pill/tray/dialogs) — no layout, feature, or copy changes.

**Architecture:** Two parallel token systems stay in sync: `webui/src/index.css`'s Tailwind `@theme` block (consumed via utility classes across the React app) and `caspr/ui/style.py`'s Python constants (consumed by the remaining Qt surfaces — pill, tray, correction/capture dialogs). Both get repointed to the same seven-color palette; the logo mark (four verdant waveform bars) is added as inline SVG in the React sidebar and as a `QPainter` routine in `caspr/ui/icons.py`.

**Tech Stack:** React 19 + Tailwind CSS v4 (`@theme` custom properties) for `webui/`; PySide6 (`QPainter`/`QSS`) for the remaining Qt surfaces.

**Reference doc:** `docs/superpowers/specs/2026-07-29-white-premium-rebrand-design.md` (approved design).

## Global Constraints

- **Color tokens (exact values — every task below must use these exact names and hex codes, nothing invented ad hoc):**
  - webui Tailwind tokens (`webui/src/index.css`): `--color-paper: #FCFBF9`, `--color-surface: #FFFFFF`, `--color-raised: #F1EEE7`, `--color-hairline: #EAE6DE`, `--color-ink: #1A1815`, `--color-muted: #8A8378`, `--color-faint: #B7AFA0`, `--color-verdant: #28382E`, `--color-ember: #D64545`.
  - Qt constants (`caspr/ui/style.py`): `BG = "#FCFBF9"`, `SURFACE = "#FFFFFF"`, `RAISED = "#F1EEE7"`, `HAIRLINE = "#EAE6DE"`, `ACCENT = "#28382E"`, `CORAL = "#3E5245"` (a lighter verdant tint — kept as a second gradient stop, see below), `FG = "#1A1815"`, `MUTED = "#8A8378"`, `FLAG = "#D64545"`.
- **State-color mapping** (used by both `STATE_COLORS` in `style.py` and the `DOT` map in `Home.tsx`): `loading→muted`, `idle→ink/FG`, `recording→ember/FLAG`, `processing→verdant/ACCENT`, `error→ember/FLAG`, `paused→muted`.
- **Typography is unchanged**: Instrument Serif (display/italic) + Inter (sans). Do not touch font imports or `--font-*` tokens.
- **Keep `caspr/ui/style.py`'s existing constant names** (`BG`, `SURFACE`, `RAISED`, `HAIRLINE`, `ACCENT`, `CORAL`, `FG`, `MUTED`, `FLAG`, `STATE_COLORS`) — only repoint their hex values. `caspr/ui/correct.py`, `caspr/ui/hotkey_capture.py`, `caspr/ui/overlay.py`, `caspr/ui/icons.py`, and `caspr/ui/tray.py` all import these by name; renaming would require touching all five for no benefit.
- **No dark-mode toggle, no new pages/features/copy changes, no layout changes.** This is a palette + logo + component-skin pass only.
- **`webui/dist` is committed to the repo** (the Qt shell loads it directly in production — see `caspr/ui/shell.py:54-55`) — the final task must rebuild it and commit the output.
- Tailwind v4's `@theme` custom properties are consumed by string-matching class names at build time — `tsc -b && vite build` succeeding does **not** guarantee a Tailwind class name is spelled correctly (an unmatched class is silently a no-op, not a build error). Every task must use the *exact* token names from this section, and the final task includes a manual visual pass as the real correctness check.

---

### Task 1: Rewrite webui theme tokens (`index.css`)

**Files:**
- Modify: `webui/src/index.css` (entire file)

**Interfaces:**
- Produces: the 9 Tailwind color tokens listed in Global Constraints, available as `bg-*`/`text-*`/`border-*`/`decoration-*` utility classes (`bg-paper`, `bg-surface`, `bg-raised`, `border-hairline`, `text-ink`, `text-muted`, `text-faint`, `bg-verdant`/`text-verdant`, `bg-ember`/`text-ember`) to every task that follows.

- [ ] **Step 1: Replace the file**

Replace the entire contents of `webui/src/index.css` with:

```css
@import 'tailwindcss';
@import '@fontsource/inter/400.css';
@import '@fontsource/inter/500.css';
@import '@fontsource/inter/600.css';
@import '@fontsource/instrument-serif/400.css';
@import '@fontsource/instrument-serif/400-italic.css';

@theme {
  --color-paper: #fcfbf9;
  --color-surface: #ffffff;
  --color-raised: #f1eee7;
  --color-hairline: #eae6de;
  --color-ink: #1a1815;
  --color-muted: #8a8378;
  --color-faint: #b7afa0;
  --color-verdant: #28382e;
  --color-ember: #d64545;
  --font-sans: 'Inter', 'Segoe UI', system-ui, sans-serif;
  --font-display: 'Instrument Serif', Georgia, serif;
}

html,
body,
#root {
  height: 100%;
}

body {
  margin: 0;
  color: var(--color-ink);
  font-family: var(--font-sans);
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
  overflow: hidden; /* app window — pages scroll internally */
  user-select: none; /* desktop feel; inputs opt back in */
  background: var(--color-paper);
}

input,
textarea {
  user-select: text;
}

::selection {
  background: rgba(40, 56, 46, 0.16);
}

:focus-visible {
  outline: 2px solid rgba(40, 56, 46, 0.45);
  outline-offset: 2px;
  border-radius: 6px;
}

*::-webkit-scrollbar {
  width: 8px;
}
*::-webkit-scrollbar-thumb {
  background: #ddd7cb;
  border-radius: 4px;
}
*::-webkit-scrollbar-track {
  background: transparent;
}

@keyframes pulse-ring {
  0% {
    transform: scale(0.4);
    opacity: 0.5;
  }
  70%,
  100% {
    transform: scale(1.5);
    opacity: 0;
  }
}

@keyframes wave-bob {
  0%,
  100% {
    height: 26%;
  }
  50% {
    height: var(--h);
  }
}
```

Note: the old radial-gradient coral glow in `body`'s background is dropped entirely — flat `paper` background, consistent with the spec's "restrained, not decorative" direction. `focus-visible` and `::selection` are now verdant-tinted instead of amber-tinted.

- [ ] **Step 2: Typecheck/build to confirm no syntax errors**

Run: `cd webui && npm run build`
Expected: succeeds (this only validates CSS/TS syntax, not that every Tailwind class elsewhere in the app still resolves — later tasks fix those call sites).

- [ ] **Step 3: Commit**

```bash
git add webui/src/index.css
git commit -m "style: replace Velvet theme tokens with Ink + Verdant palette"
```

---

### Task 2: Recolor the Qt-side palette (`caspr/ui/style.py`)

**Files:**
- Modify: `caspr/ui/style.py:9-27` (the `BG`/`SURFACE`/`RAISED`/`HAIRLINE`/`ACCENT`/`CORAL`/`FG`/`MUTED`/`FLAG`/`STATE_COLORS` constants)
- Modify: `caspr/ui/style.py:29-68` (`APP_QSS` — button/input contrast must flip since the base is now light)
- Test: `tests/test_style.py` (update the Velvet guard test to guard the new palette)

**Interfaces:**
- Consumes: nothing new.
- Produces: `BG`, `SURFACE`, `RAISED`, `HAIRLINE`, `ACCENT`, `CORAL`, `FG`, `MUTED`, `FLAG`, `STATE_COLORS`, `APP_QSS` — same names as before, new values, consumed unchanged by `caspr/ui/correct.py`, `caspr/ui/hotkey_capture.py`, `caspr/ui/overlay.py`, `caspr/ui/icons.py`, `caspr/ui/tray.py`.

- [ ] **Step 1: Write the failing test**

Replace `tests/test_style.py` entirely with:

```python
"""Theme invariants: every state the controller can emit has a color."""

from caspr.ui.style import ACCENT, BG, FG, STATE_COLORS

CONTROLLER_STATES = {"loading", "idle", "recording", "processing", "error", "paused"}


def test_state_colors_cover_controller_states():
    assert CONTROLLER_STATES <= set(STATE_COLORS)


def test_ink_verdant_palette_is_light():
    # Guards against a stray revert to the old dark Velvet theme.
    assert BG == "#FCFBF9"
    assert ACCENT == "#28382E"
    assert STATE_COLORS["idle"] == FG
    assert STATE_COLORS["processing"] == ACCENT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_style.py -v`
Expected: FAIL — `BG`/`ACCENT` still hold the old Velvet hex values.

- [ ] **Step 3: Rewrite the constants and QSS**

Replace `caspr/ui/style.py` lines 9-27 (the color constants) with:

```python
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
```

Replace the `APP_QSS` block (lines 29-68 in the original) with:

```python
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
```

(Only the `QPushButton`/`QPushButton:hover` colors, `selection-color`, and the scrollbar handle hex actually change in behavior — the rest is the same structure with the new constants flowing through. Also update the module docstring at the top of the file, which currently reads `"""Shared look for the remaining Qt surfaces (pill, dialogs, tray icons): Velvet — warm espresso, cream text, coral→amber accents. ..."""` — replace `Velvet — warm espresso, cream text, coral→amber accents.` with `Ink + Verdant — warm-white paper, near-black ink text, verdant accent.`)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_style.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite to confirm nothing else broke**

Run: `uv run pytest -q`
Expected: all tests pass (no other test asserts on these hex values per the earlier grep).

- [ ] **Step 6: Commit**

```bash
git add caspr/ui/style.py tests/test_style.py
git commit -m "style: recolor Qt surfaces to Ink + Verdant, flip button contrast for light theme"
```

---

### Task 3: Repaint the app/tray icon as waveform bars (`caspr/ui/icons.py`)

**Files:**
- Modify: `caspr/ui/icons.py:1-71` (imports, `_paint_mic`, `_app_pixmap`)

**Interfaces:**
- Consumes: `BG`, `CORAL`, `ACCENT`, `STATE_COLORS`, `SURFACE`, `HAIRLINE` from `caspr/ui/style.py` (Task 2).
- Produces: `app_icon()` and `tray_icon(state)` — same public signatures as before, now painting the waveform-bars mark instead of the mic capsule. No other file's call sites change.

- [ ] **Step 1: Replace the mic painter with a waveform-bars painter**

In `caspr/ui/icons.py`, change the import line (currently `from .style import BG, CORAL, ACCENT, STATE_COLORS, SURFACE`) to also pull in `HAIRLINE`:

```python
from .style import ACCENT, BG, CORAL, HAIRLINE, STATE_COLORS, SURFACE
```

Replace the `_paint_mic` function (the mic-capsule painter) with:

```python
_BAR_HEIGHTS = (0.24, 0.53, 0.76, 0.41)  # relative to size — tallest bar third


def _paint_waveform(painter: QPainter, size: float) -> None:
    """Four uneven verdant bars — the waveform-bars logo mark."""
    s = size
    bar_w = s * 0.10
    gap = s * 0.065
    total_w = len(_BAR_HEIGHTS) * bar_w + (len(_BAR_HEIGHTS) - 1) * gap
    start_x = (s - total_w) / 2
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(ACCENT))
    for i, h_frac in enumerate(_BAR_HEIGHTS):
        bar_h = s * h_frac
        x = start_x + i * (bar_w + gap)
        y = (s - bar_h) / 2
        painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), bar_w / 2, bar_w / 2)
```

- [ ] **Step 2: Update `_app_pixmap` to call the new painter and use a light border**

In `_app_pixmap`, change:

```python
    painter.setBrush(gradient)
    painter.setPen(QColor("#3a2c22"))
    radius = size * 0.22
    inset = max(0.5, size * 0.02)
    painter.drawRoundedRect(
        QRectF(inset, inset, size - 2 * inset, size - 2 * inset), radius, radius
    )

    _paint_mic(painter, size)
```

to:

```python
    painter.setBrush(gradient)
    painter.setPen(QColor(HAIRLINE))
    radius = size * 0.22
    inset = max(0.5, size * 0.02)
    painter.drawRoundedRect(
        QRectF(inset, inset, size - 2 * inset, size - 2 * inset), radius, radius
    )

    _paint_waveform(painter, size)
```

(The gradient itself, `SURFACE→BG`, is untouched — with the new light values it's a near-imperceptible white-to-paper gradient, which is intentional: subtle depth rather than a visible two-tone.)

- [ ] **Step 3: Sanity-check it paints without error**

No automated test exists for this module (painting requires a live `QApplication`, and no test in the suite currently constructs one — this matches the approved spec's verification section, which calls for manual visual QA here, not new Qt test infra). Run a quick manual import check instead:

Run: `uv run python -c "from PySide6.QtWidgets import QApplication; app = QApplication([]); from caspr.ui.icons import app_icon, tray_icon; print(app_icon().pixmap(32,32).isNull()); print(tray_icon('recording').pixmap(32,32).isNull())"`
Expected: prints `False` twice (a non-null pixmap was produced for both).

- [ ] **Step 4: Commit**

```bash
git add caspr/ui/icons.py
git commit -m "style: repaint app/tray icon as waveform bars instead of mic capsule"
```

---

### Task 4: Recolor and re-mark the sidebar (`Sidebar.tsx`)

**Files:**
- Modify: `webui/src/components/Sidebar.tsx` (entire file)

**Interfaces:**
- Consumes: Tailwind tokens from Task 1 (`paper`, `ink`, `muted`, `hairline`, `verdant`).
- Produces: no new exports — `Sidebar`'s props (`page`, `onNavigate`) are unchanged.

- [ ] **Step 1: Replace the file**

Replace the entire contents of `webui/src/components/Sidebar.tsx` with:

```tsx
import { bridge } from '../bridge'

export type Page = 'home' | 'history' | 'dictionary' | 'settings'

const NAV: { id: Page; label: string; icon: React.ReactNode }[] = [
  {
    id: 'home',
    label: 'Home',
    icon: <path d="M2.5 8.5 8 3.5l5.5 5V14h-3.8v-3.6H6.3V14H2.5z" />,
  },
  {
    id: 'history',
    label: 'History',
    icon: (
      <>
        <circle cx="8" cy="8" r="5.8" />
        <path d="M8 4.8V8l2.2 2.2" />
      </>
    ),
  },
  {
    id: 'dictionary',
    label: 'Dictionary',
    icon: <path d="M3.2 13.2a1.8 1.8 0 0 1 1.8-1.8h7.8V1.8H5A1.8 1.8 0 0 0 3.2 3.6zm0 0A1.8 1.8 0 0 0 5 15h7.8v-3.6" />,
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: (
      <>
        <path d="M2 5h12M2 11h12" />
        <circle cx="6" cy="5" r="1.7" fill="var(--color-paper)" />
        <circle cx="10.5" cy="11" r="1.7" fill="var(--color-paper)" />
      </>
    ),
  },
]

function LogoMark() {
  return (
    <svg width="14" height="14" viewBox="0 0 34 34" className="shrink-0">
      <rect x="6" y="13" width="3.5" height="8" rx="1.75" fill="var(--color-verdant)" />
      <rect x="12" y="8" width="3.5" height="18" rx="1.75" fill="var(--color-verdant)" />
      <rect x="18" y="4" width="3.5" height="26" rx="1.75" fill="var(--color-verdant)" />
      <rect x="24" y="10" width="3.5" height="14" rx="1.75" fill="var(--color-verdant)" />
    </svg>
  )
}

export function Sidebar({ page, onNavigate }: { page: Page; onNavigate: (p: Page) => void }) {
  return (
    <aside className="flex w-47 shrink-0 flex-col border-r border-hairline bg-paper shadow-[2px_0_12px_rgba(0,0,0,0.03)]">
      <div
        className="flex items-baseline gap-2 px-5 pt-5 pb-6"
        style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
        onMouseDown={(e) => {
          if (e.button === 0) bridge()?.win_drag()
        }}
      >
        <span className="font-display text-[21px] italic leading-none">caspr</span>
        <LogoMark />
      </div>
      <nav className="flex flex-col gap-0.5 px-2.5">
        {NAV.map((item) => {
          const active = item.id === page
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`flex items-center gap-2.5 rounded-[10px] px-3 py-2 text-left text-[13.5px] transition-colors ${
                active ? 'bg-ink font-medium text-paper' : 'text-muted hover:text-ink'
              }`}
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
                strokeLinecap="round"
                className={active ? 'text-verdant' : ''}
              >
                {item.icon}
              </svg>
              {item.label}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}
```

Changes from the original: sidebar background `bg-[#181312]` → `bg-paper` (matches the page background, separated only by the hairline border, per the design doc); added a subtle right-edge `shadow-[2px_0_12px_rgba(0,0,0,0.03)]` (the design doc's "Surfaces & components" section calls for shadow-based elevation on cards, sidebar, and the pill — the pill already has one via `caspr/ui/overlay.py`'s painted penumbra, this adds the sidebar's); the settings-glyph "punch" circles' `fill="var(--color-espresso)"` → `fill="var(--color-paper)"` (must match whatever sits directly behind the icon — that's now `paper`, not the retired `espresso`); the plain coral dot next to the wordmark replaced with `LogoMark`, the four-bar waveform mark at tray-icon proportions; active nav item goes from `bg-raised font-medium text-cream` to `bg-ink font-medium text-paper` (dark pill, light text, per the design doc's "Sidebar" section); active nav icon color `text-amber` → `text-verdant`.

- [ ] **Step 2: Typecheck**

Run: `cd webui && npm run build`
Expected: succeeds.

- [ ] **Step 3: Commit**

```bash
git add webui/src/components/Sidebar.tsx
git commit -m "style: recolor sidebar to Ink + Verdant, add waveform-bars logo mark"
```

---

### Task 5: Recolor `TitleBar.tsx`/`Waveform.tsx`, add shadow to `Card.tsx`

**Files:**
- Modify: `webui/src/components/TitleBar.tsx:17` (one hardcoded token reference)
- Modify: `webui/src/components/Waveform.tsx:23` (gradient)
- Modify: `webui/src/components/Card.tsx:9` (add elevation shadow)

**Interfaces:**
- Consumes: Tailwind tokens from Task 1.
- Produces: no signature changes to any of the three components.

- [ ] **Step 1: Fix `TitleBar.tsx`**

Change line 17 from:

```tsx
        className="grid h-7 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-raised hover:text-cream"
```

to:

```tsx
        className="grid h-7 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-raised hover:text-ink"
```

(Only the minimize button needs this — the close button's `hover:text-ember` on line 27 needs no edit, since `ember` is a token name that survives Task 1 with a new value.)

- [ ] **Step 2: Fix `Waveform.tsx`**

Change line 23 from:

```tsx
            className="w-[3px] rounded-full bg-gradient-to-b from-coral to-amber"
```

to:

```tsx
            className="w-[3px] rounded-full bg-gradient-to-b from-verdant to-verdant/60"
```

(`coral`/`amber` retire along with the two-tone accent pairing; a single-hue top-to-bottom fade using Tailwind's built-in `/opacity` modifier replaces it — no new CSS token needed. Also update the file's doc comment on line 4, which currently reads `/** Ember VU meter. ... */` — change `Ember VU meter.` to `Verdant VU meter.` to match.)

- [ ] **Step 3: Add elevation shadow to `Card.tsx`**

Change:

```tsx
    <div className={`rounded-[18px] border border-hairline bg-surface ${className}`}>
```

to:

```tsx
    <div className={`rounded-[18px] border border-hairline bg-surface shadow-[0_2px_12px_rgba(0,0,0,0.06)] ${className}`}>
```

(`Card` is the shared component behind every panel on the Home and Settings pages — this is where the design doc's "cards ... get a subtle shadow" applies. `History`/`Dictionary` don't use `Card`, so they get no shadow, matching the doc's scope.)

- [ ] **Step 4: Typecheck**

Run: `cd webui && npm run build`
Expected: succeeds.

- [ ] **Step 5: Commit**

```bash
git add webui/src/components/TitleBar.tsx webui/src/components/Waveform.tsx webui/src/components/Card.tsx
git commit -m "style: recolor title bar and waveform meter, add card elevation shadow"
```

---

### Task 6: Recolor `Home.tsx` (state dots, pulse ring, stat numbers)

**Files:**
- Modify: `webui/src/pages/Home.tsx:18-25` (the `DOT` map)
- Modify: `webui/src/pages/Home.tsx:73-79` (the pulse-ring span)
- Modify: `webui/src/pages/Home.tsx:105` (stat number color)

**Interfaces:**
- Consumes: Tailwind tokens from Task 1; `verdant`/`ember` state-color convention from Global Constraints.
- Produces: no signature changes.

- [ ] **Step 1: Replace the `DOT` map**

Change:

```tsx
const DOT: Record<string, string> = {
  loading: 'bg-muted',
  idle: 'bg-amber shadow-[0_0_12px_rgba(255,183,77,.8)]',
  recording: 'bg-ember shadow-[0_0_14px_rgba(255,92,73,.9)]',
  processing: 'bg-coral shadow-[0_0_12px_rgba(255,138,101,.8)]',
  error: 'bg-[#e05252] shadow-[0_0_12px_rgba(224,82,82,.8)]',
  paused: 'bg-[#b8a06a]',
}
```

to:

```tsx
const DOT: Record<string, string> = {
  loading: 'bg-muted',
  idle: 'bg-ink',
  recording: 'bg-ember shadow-[0_0_14px_rgba(214,69,69,.55)]',
  processing: 'bg-verdant shadow-[0_0_12px_rgba(40,56,46,.45)]',
  error: 'bg-ember shadow-[0_0_12px_rgba(214,69,69,.55)]',
  paused: 'bg-muted',
}
```

(Follows the state-color mapping in Global Constraints. `idle`/`paused`/`loading` are neutral now — no glow, since a glowing shadow implies an active/alert state and these aren't; `recording`/`processing`/`error` keep a soft glow tuned to the new hex values.)

- [ ] **Step 2: Replace the pulse-ring span**

Change:

```tsx
          {(effective === 'idle' || effective === 'recording') && (
            <span
              className={`absolute inset-[-5px] rounded-full opacity-40 [animation:pulse-ring_2.6s_ease-out_infinite] ${
                effective === 'recording' ? 'bg-ember' : 'bg-amber'
              }`}
            />
          )}
```

to:

```tsx
          {(effective === 'idle' || effective === 'recording') && (
            <span
              className={`absolute inset-[-5px] rounded-full opacity-40 [animation:pulse-ring_2.6s_ease-out_infinite] ${
                effective === 'recording' ? 'bg-ember' : 'bg-verdant'
              }`}
            />
          )}
```

(The idle state's dot itself is neutral `ink`, but its breathing pulse ring stays accented — verdant instead of amber — so "listening ready" still reads as a soft, deliberate affordance rather than losing the animation entirely.)

- [ ] **Step 3: Fix the stat number color**

Change line 105 from:

```tsx
            <div className="text-[26px] font-semibold tabular-nums leading-none text-[#ffd7b8]">
```

to:

```tsx
            <div className="text-[26px] font-semibold tabular-nums leading-none text-ink">
```

(The peachy accent color retires — stat numbers read as plain primary text now, consistent with "verdant is the one accent, used sparingly," not decorative on every large number.)

- [ ] **Step 4: Typecheck**

Run: `cd webui && npm run build`
Expected: succeeds.

- [ ] **Step 5: Commit**

```bash
git add webui/src/pages/Home.tsx
git commit -m "style: recolor Home page state dots, pulse ring, and stat numbers"
```

---

### Task 7: Recolor `Dictionary.tsx` and `History.tsx`

**Files:**
- Modify: `webui/src/pages/Dictionary.tsx:51`
- Modify: `webui/src/pages/History.tsx:23,80,107`

**Interfaces:**
- Consumes: Tailwind tokens from Task 1.
- Produces: no signature changes.

- [ ] **Step 1: Fix `Dictionary.tsx`**

Change line 51 from:

```tsx
          className="mb-3 rounded-xl border border-hairline bg-surface px-4 py-2.5 text-[13.5px] text-cream placeholder:text-faint focus:border-[#3a3028] focus:outline-none"
```

to:

```tsx
          className="mb-3 rounded-xl border border-hairline bg-surface px-4 py-2.5 text-[13.5px] text-ink placeholder:text-faint focus:border-verdant focus:outline-none"
```

(`text-cream`→`text-ink` since `cream` retires as the primary-text token; the hardcoded `#3a3028` focus-border hex → the `verdant` token, giving every focused input the one accent color instead of an invented one-off hex. No other line in this file needs changes — `text-faint`, `hover:bg-raised`, `hover:text-ember`, `text-muted`, `text-ink` all resolve correctly automatically once Task 1's tokens are in place.)

- [ ] **Step 2: Fix `History.tsx`**

Change line 23 from:

```tsx
        danger ? 'hover:text-ember' : 'hover:text-cream'
```

to:

```tsx
        danger ? 'hover:text-ember' : 'hover:text-ink'
```

Change line 80 from:

```tsx
        className="w-full rounded-xl border border-hairline bg-surface px-4 py-2.5 text-[13.5px] text-cream placeholder:text-faint focus:border-[#3a3028] focus:outline-none"
```

to:

```tsx
        className="w-full rounded-xl border border-hairline bg-surface px-4 py-2.5 text-[13.5px] text-ink placeholder:text-faint focus:border-verdant focus:outline-none"
```

Change line 107 from:

```tsx
                    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-amber">
```

to:

```tsx
                    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-verdant">
```

(The "copied" checkmark confirmation icon uses the one accent color instead of the retired amber.)

- [ ] **Step 3: Typecheck**

Run: `cd webui && npm run build`
Expected: succeeds.

- [ ] **Step 4: Commit**

```bash
git add webui/src/pages/Dictionary.tsx webui/src/pages/History.tsx
git commit -m "style: recolor Dictionary and History pages to Ink + Verdant"
```

---

### Task 8: Recolor `Settings.tsx`

**Files:**
- Modify: `webui/src/pages/Settings.tsx:40,70,74,130,194,246,373`

**Interfaces:**
- Consumes: Tailwind tokens from Task 1.
- Produces: no signature changes.

- [ ] **Step 1: Fix the `Select` component's focus/text color (line 40)**

Change:

```tsx
        className="appearance-none rounded-[10px] border border-hairline bg-raised py-1.5 pl-3 pr-8 text-[13px] text-cream focus:border-[#3a3028] focus:outline-none"
```

to:

```tsx
        className="appearance-none rounded-[10px] border border-hairline bg-raised py-1.5 pl-3 pr-8 text-[13px] text-ink focus:border-verdant focus:outline-none"
```

- [ ] **Step 2: Fix the `Toggle` component (lines 70 and 74)**

Change:

```tsx
      className={`relative h-[22px] w-[38px] rounded-full transition-colors ${
        checked ? 'bg-gradient-to-r from-coral to-amber' : 'bg-raised border border-hairline'
      }`}
```

to:

```tsx
      className={`relative h-[22px] w-[38px] rounded-full transition-colors ${
        checked ? 'bg-verdant' : 'bg-raised border border-hairline'
      }`}
```

(The checked-state gradient becomes a solid `verdant` fill — there's only one accent color now, so the two-stop gradient has no second color to gradient toward.)

Change:

```tsx
        className={`absolute top-[3px] h-4 w-4 rounded-full bg-cream transition-all ${
```

to:

```tsx
        className={`absolute top-[3px] h-4 w-4 rounded-full bg-paper transition-all ${
```

(The toggle knob was `cream`, the old primary-foreground token; its role — "a light circle that reads clearly against both the on and off track colors" — maps to `paper`, not `ink`.)

- [ ] **Step 3: Fix the shared `inputCls` constant (line 130) and its 3 usages (lines 291, 318, 373 in the new numbering do not need separate edits — they consume `inputCls` or the class list already fixed here)**

Change:

```tsx
const inputCls =
  'rounded-[10px] border border-hairline bg-raised px-3 py-1.5 text-[13px] text-cream focus:border-[#3a3028] focus:outline-none'
```

to:

```tsx
const inputCls =
  'rounded-[10px] border border-hairline bg-raised px-3 py-1.5 text-[13px] text-ink focus:border-verdant focus:outline-none'
```

- [ ] **Step 4: Fix the "Remove" button hover accent (line 194)**

Change:

```tsx
              className="rounded-[10px] border border-hairline px-2.5 py-1.5 text-[12px] text-muted transition-colors hover:bg-raised hover:text-coral"
```

to:

```tsx
              className="rounded-[10px] border border-hairline px-2.5 py-1.5 text-[12px] text-muted transition-colors hover:bg-raised hover:text-ember"
```

(This is a destructive "Remove" action — `ember`, the functional danger-red, reads more correctly here than the old decorative `coral`, which is retiring anyway.)

- [ ] **Step 5: Fix the shortcut "keycap" badge color (line 246)**

Change:

```tsx
          <span className="rounded-lg border border-hairline bg-raised px-3 py-1.5 text-[12.5px] font-medium tracking-wide text-amber">
```

to:

```tsx
          <span className="rounded-lg border border-hairline bg-raised px-3 py-1.5 text-[12.5px] font-medium tracking-wide text-verdant">
```

- [ ] **Step 6: Fix the pill-linger input (line 373)**

Change:

```tsx
            className="w-20 rounded-[10px] border border-hairline bg-raised px-3 py-1.5 text-right text-[13px] text-cream focus:border-[#3a3028] focus:outline-none"
```

to:

```tsx
            className="w-20 rounded-[10px] border border-hairline bg-raised px-3 py-1.5 text-right text-[13px] text-ink focus:border-verdant focus:outline-none"
```

- [ ] **Step 7: Typecheck**

Run: `cd webui && npm run build`
Expected: succeeds.

- [ ] **Step 8: Commit**

```bash
git add webui/src/pages/Settings.tsx
git commit -m "style: recolor Settings page to Ink + Verdant"
```

---

### Task 9: Build, full test run, and manual visual QA

**Files:**
- Modify: `webui/dist/**` (regenerated build output — committed to the repo)

**Interfaces:**
- Consumes: everything from Tasks 1-8.
- Produces: nothing further downstream — this is the final integration/verification task.

- [ ] **Step 1: Rebuild the production webui bundle**

Run: `cd webui && npm run build`
Expected: succeeds; `webui/dist/assets/` now contains new hashed filenames (Vite content-hashes its output, so old filenames disappear and new ones appear — that's expected, not a bug).

- [ ] **Step 2: Run the full Python test suite**

Run: `uv run pytest -q`
Expected: all tests pass (157 before this plan's Task 2 test-name change; still 157 after — `test_velvet_palette_is_warm` was replaced by `test_ink_verdant_palette_is_light`, no count change).

- [ ] **Step 3: Manual visual QA**

Run the app in dev mode for fast iteration: `CASPR_UI_DEV=1 uv run python -m caspr` (starts the Vite dev server per `caspr/ui/shell.py`'s doc comment), or run the production build as shipped.

Check, by eye, against the design doc's Section 2 (`docs/superpowers/specs/2026-07-29-white-premium-rebrand-design.md`):
- Sidebar: paper background, waveform-bars mark next to "caspr", active nav item is a solid ink pill with paper text, inactive items are muted with ink on hover.
- Home page: state dot colors match the state table (trigger each state if possible — at minimum confirm idle and recording by holding the hotkey), stat numbers are plain ink, live waveform meter is verdant.
- History/Dictionary pages: white input fields with hairline borders, verdant focus-border on click, ink primary text, muted/faint secondary text.
- Settings page: toggles are solid verdant when on, the shortcut badge is verdant text on a raised chip, the "Remove" button hovers to ember (red).
- The floating pill (hold the hotkey, or trigger `caspr --wav <file>` if available) shows a paper/white capsule with a verdant waveform while recording.
- Tray icon and taskbar icon show the four-bar waveform mark, not the old mic capsule.
- No orange/amber/coral or dark-espresso color visible anywhere.

- [ ] **Step 4: Commit the rebuilt dist**

```bash
git add webui/dist
git commit -m "build: rebuild webui dist with Ink + Verdant theme"
```

- [ ] **Step 5: Push**

```bash
git push origin main
```
