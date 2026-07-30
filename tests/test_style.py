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
