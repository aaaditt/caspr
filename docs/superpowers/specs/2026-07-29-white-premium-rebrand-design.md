# White Premium Rebrand — "Ink + Verdant"

*2026-07-29 — approved design.*

## Motivation

The current "Velvet" theme (warm espresso/coral/amber, shipped 2026-07-18) no
longer fits — Aadit wants a white/premium aesthetic, and specifically wants to
move away from orange/amber as an accent. The current "logo" is just the
italic-serif "caspr" wordmark plus a plain coral dot next to it, which reads
as unfinished rather than a considered mark.

Aadit compiled a full UI walkthrough of the real Wispr Flow desktop app
(`WISPR-~1.MD`, repo root) as reference. Key finding from that doc: Wispr's
own accent color is amber/orange too — so the brief isn't "copy Wispr's
palette," it's "borrow the premium-editorial *structure* (warm neutral base,
serif+sans pairing, one restrained accent) but land on white instead of
cream, with a different accent than orange."

Two decisions were made via the brainstorming visual companion (mockups in
`.superpowers/brainstorm/`, gitignored):
- **Accent**: Ink + Verdant (deep forest green) over Ink + Signal Navy and
  pure monochrome — chosen by Aadit directly.
- **Logo mark**: Waveform bars (four uneven vertical rounded bars) over a
  refined monoline mic, a serif "c" monogram, and concentric pulse rings —
  chosen by Aadit directly.

## Color tokens

| Token | Value | Role |
|---|---|---|
| `paper` (bg) | `#FCFBF9` | App background |
| `surface` | `#FFFFFF` | Cards, raised panels |
| `ink` | `#1A1815` | Primary text, primary buttons, active nav |
| `muted` | `#8A8378` | Secondary text, timestamps, inactive nav |
| `hairline` | `#EAE6DE` | Borders |
| `verdant` | `#28382E` | The one accent — active states, logo mark, focus ring, links |

Not implemented: a `verdant-soft` token (`verdant` @ 8–10% alpha) was planned for
hover backgrounds, but the implementation plan simplified this away — hover
fills use `raised` instead, and nothing in the shipped code references
`verdant-soft`.

State colors (functional signals, not brand color — kept close to universal
convention rather than reusing the accent for everything):

| Controller state | Color |
|---|---|
| `idle` | `ink` |
| `recording` | `#D64545` (muted red, replaces the old neon coral) |
| `processing` | `verdant` |
| `error` | `#D64545` |
| `paused` | `muted` |
| `loading` | `muted` |

## Typography

**Unchanged**: Instrument Serif (display/headlines, italic for emphasis) +
Inter (UI/body). This pairing is already in the codebase and is exactly the
"premium editorial" pairing that makes Wispr read premium per Aadit's notes —
it has nothing to do with the orange being removed, so it stays as-is.

## Logo mark — Waveform bars

Four vertical rounded bars of varying height, verdant, replacing the current
plain coral dot next to the wordmark and the gradient mic-capsule app icon.

Used in:
- **App/taskbar icon and tray icon** (`caspr/ui/icons.py`): repainted as the
  waveform-bars mark on a paper rounded-square, replacing
  `_paint_mic`'s gradient mic-capsule. The state badge dot (bottom-right,
  used by `tray_icon(state)`) keeps its own functional color per the state
  table above.
- **Sidebar wordmark** (`webui/src/components/Sidebar.tsx`): the mark sits
  next to "caspr" where the coral dot currently is.
- **Recording pill's live waveform** — the floating pill is a Qt widget
  (`caspr/ui/overlay.py`'s `Waveform` class, a CORAL→ACCENT gradient bar
  meter painted with `QPainter`), *not* the React `webui/src/components/
  Waveform.tsx` component (that one is a separate live-level meter shown on
  the Home page inside the main window). Both get recolored to verdant,
  independently — the effect is that the pill's live waveform, the Home
  page's live meter, and the static logo mark all share the same bars
  motif, which reads as deliberate brand consistency rather than
  coincidence.

## Surfaces & components

- **Elevation via soft shadow + hairline**, not flat dark panels: cards,
  sidebar, and the pill get a subtle shadow (`0 2px 12px rgba(0,0,0,.06)`
  order of magnitude) for a "premium light UI" depth cue, on top of the
  existing 1px hairline border.
- **Sidebar**: `paper` background, matching the page rather than standing
  out as a distinct white surface — separated from the content area only
  by the hairline border on its right edge; active nav item = `ink`
  background + white text; inactive = `muted` text.
- **Recording pill overlay**: paper/white pill, soft shadow, verdant
  waveform bars (see above).
- **Buttons**: primary = `ink` background / white text (was amber
  background / dark text); flat/secondary = `verdant` text, transparent
  background.
- **Inputs**: white/paper fields, hairline borders, `verdant` focus ring
  (replaces the amber focus ring in `index.css`'s `:focus-visible`).
- **Scrollbars**: gray thumb on transparent track (light-mode equivalent of
  the current dark thumb).

## Scope — files touched

- `webui/src/index.css` — replace the `@theme` token block (espresso/
  surface/raised/hairline/cream/ink/muted/faint/coral/amber/ember) with the
  new paper/surface/ink/muted/hairline/verdant tokens; update `body`
  background, `::selection`, `:focus-visible`, scrollbar colors.
- `webui/src/components/Sidebar.tsx` — hardcoded `bg-[#181312]` → token;
  add the waveform-bars mark next to the wordmark.
- `webui/src/components/Waveform.tsx` — recolor bars to verdant.
- `webui/src/pages/Home.tsx` — hardcoded state-badge colors
  (`bg-[#e05252]`, `bg-[#b8a06a]`) and the peachy stat-number color
  (`text-[#ffd7b8]`) → tokens.
- `webui/src/pages/Dictionary.tsx`, `History.tsx`, `Settings.tsx` — shared
  hardcoded focus-border hex (`#3a3028`) → token.
- `caspr/ui/style.py` — `APP_QSS` and the `BG`/`SURFACE`/`RAISED`/
  `HAIRLINE`/`ACCENT`/`CORAL`/`FG`/`MUTED`/`FLAG`/`STATE_COLORS` constants,
  repointed to the light palette's hex values. **Keep the existing constant
  names** rather than renaming them — `correct.py`, `hotkey_capture.py`,
  `overlay.py`, `icons.py`, and `tray.py` all import from this module by
  name (verified via grep), and none of them need their own edits beyond
  what's listed below if the names survive. `CORAL`/`ACCENT` specifically
  currently form a two-stop gradient (coral→amber) used by `overlay.py`'s
  `Waveform` bars and `icons.py`'s mic capsule; repoint both to two verdant
  tones (e.g. a slightly lighter verdant for `CORAL`, base verdant for
  `ACCENT`) so that existing gradient code keeps working unchanged, just
  monochrome-verdant instead of coral-to-amber.
- `caspr/ui/icons.py` — `_paint_mic` replaced with a waveform-bars painter;
  `_app_pixmap`'s background gradient becomes paper-on-white.
- `caspr/ui/overlay.py` — no direct color edits expected (its `Waveform`
  and `Pill` painting both source colors from `style.py`'s constants), but
  visually verify the gradient bars and pill fill/shadow read correctly
  once `style.py` changes land.
- `tests/test_style.py` — `test_velvet_palette_is_warm` updated to guard the
  new palette's values instead of Velvet's (same purpose: catch an
  accidental revert).

## Non-goals

- No dark-mode toggle. This fully replaces Velvet as the only theme, the
  same way Velvet fully replaced the original Qt-widget look — not an
  additional mode to maintain.
- No new pages or features inspired by the Wispr walkthrough doc (Insights
  dashboard, gamification/unlock mechanics, Style/Transforms/Scratchpad,
  keycap shortcut badges). This is a palette + logo + component-skin pass on
  the existing 4 pages (Home/History/Dictionary/Settings) and Qt surfaces,
  not a feature expansion.
- No copywriting/microcopy changes.
- No changes to layout/structure of any page — same nav, same sections, same
  information architecture, just re-themed.

## Verification

This is a visual change with no meaningful new business logic to unit test.
Verification is: update `test_style.py`'s hex-guard assertions to the new
palette (keeps its regression-guard purpose), then run the app
(`CASPR_UI_DEV=1` for the webui dev server, plus the Qt shell) and visually
check every page, the pill in each controller state, the tray icon, and
Settings' hotkey UI.
