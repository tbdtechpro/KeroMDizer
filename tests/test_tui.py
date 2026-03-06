# tests/test_tui.py
from tui import AppModel, Screen
import bubbletea as tea


def test_screen_enum_has_required_screens():
    assert hasattr(Screen, 'MAIN')
    assert hasattr(Screen, 'FOLDER_BROWSER')
    assert hasattr(Screen, 'PROVIDER_SELECT')
    assert hasattr(Screen, 'CONFIRM')
    assert hasattr(Screen, 'RUN')
    assert hasattr(Screen, 'SETTINGS')
    assert hasattr(Screen, 'REVIEW')


def test_appmodel_initial_screen_is_main():
    m = AppModel()
    assert m.screen == Screen.MAIN


import lipgloss as _lipgloss  # for strip_ansi


def _strip(s: str) -> str:
    return _lipgloss.strip_ansi(s)


def test_main_view_contains_all_menu_items():
    m = AppModel()
    m.width, m.height = 80, 24
    v = _strip(m.view())
    assert 'Import' in v
    assert 'Settings' in v
    assert 'Review' in v


def test_main_cursor_moves_down():
    m = AppModel()
    m, _ = m.update(tea.KeyMsg(key='down'))
    assert m.menu_cursor == 1


def test_main_cursor_moves_up():
    m = AppModel()
    m.menu_cursor = 1
    m, _ = m.update(tea.KeyMsg(key='up'))
    assert m.menu_cursor == 0


def test_main_cursor_wraps_down():
    m = AppModel()
    m.menu_cursor = 2  # last item
    m, _ = m.update(tea.KeyMsg(key='down'))
    assert m.menu_cursor == 0


def test_main_cursor_wraps_up():
    m = AppModel()
    m.menu_cursor = 0
    m, _ = m.update(tea.KeyMsg(key='up'))
    assert m.menu_cursor == 2


def test_main_q_quits():
    m = AppModel()
    m, cmd = m.update(tea.KeyMsg(key='q'))
    assert cmd is tea.quit_cmd


def test_main_enter_import_goes_to_folder_browser():
    m = AppModel()
    m.menu_cursor = 0  # Import
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.FOLDER_BROWSER


def test_main_enter_settings_goes_to_settings():
    m = AppModel()
    m.menu_cursor = 1  # Settings
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.SETTINGS


def test_main_enter_review_goes_to_review():
    m = AppModel()
    m.menu_cursor = 2  # Review
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.REVIEW
