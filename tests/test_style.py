"""Theme invariants: every state the controller can emit has a color."""

from caspr.ui.style import ACCENT, BG, STATE_COLORS

CONTROLLER_STATES = {"loading", "idle", "recording", "processing", "error", "paused"}


def test_state_colors_cover_controller_states():
    assert CONTROLLER_STATES <= set(STATE_COLORS)


def test_velvet_palette_is_warm():
    # Guards against a stray revert to the old cyan-on-charcoal theme.
    assert BG == "#151110"
    assert ACCENT == "#ffb74d"
    assert STATE_COLORS["idle"] == ACCENT
