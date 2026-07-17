"""Theme invariants: every state the controller can emit has a color."""

from caspr.ui.style import APP_QSS, STATE_COLORS

CONTROLLER_STATES = {"loading", "idle", "recording", "processing", "error", "paused"}


def test_state_colors_cover_controller_states():
    assert CONTROLLER_STATES <= set(STATE_COLORS)


def test_status_dot_rules_generated_per_state():
    for state in STATE_COLORS:
        assert f'QLabel#statusDot[state="{state}"]' in APP_QSS
