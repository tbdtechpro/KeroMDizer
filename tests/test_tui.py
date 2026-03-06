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
