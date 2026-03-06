# tests/test_tui.py
from tui import AppModel, Screen, _ClipboardMsg, _ConvCountMsg, _ProgressMsg, _DoneMsg, _RunErrorMsg
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


def _make_fb_model(tmp_path) -> AppModel:
    """Helper: AppModel at FOLDER_BROWSER with tmp_path as current dir."""
    m = AppModel()
    m.screen = Screen.FOLDER_BROWSER
    m.width, m.height = 80, 24
    m.fb_dir = tmp_path
    m.fb_text_mode = False
    m._fb_refresh()
    return m


def test_fb_refresh_lists_dirs_first(tmp_path):
    (tmp_path / 'zfile.txt').write_text('x')
    (tmp_path / 'adir').mkdir()
    m = _make_fb_model(tmp_path)
    names = [e.name for e in m.fb_entries]
    assert names.index('adir') < names.index('zfile.txt')


def test_fb_refresh_hides_dotfiles(tmp_path):
    (tmp_path / '.hidden').mkdir()
    (tmp_path / 'visible').mkdir()
    m = _make_fb_model(tmp_path)
    names = [e.name for e in m.fb_entries]
    assert '.hidden' not in names
    assert 'visible' in names


def test_fb_cursor_moves_down(tmp_path):
    (tmp_path / 'a').mkdir()
    (tmp_path / 'b').mkdir()
    m = _make_fb_model(tmp_path)
    m, _ = m.update(tea.KeyMsg(key='down'))
    assert m.fb_cursor == 1


def test_fb_cursor_clamps_at_bottom(tmp_path):
    (tmp_path / 'only').mkdir()
    m = _make_fb_model(tmp_path)
    m.fb_cursor = 0
    m, _ = m.update(tea.KeyMsg(key='down'))
    assert m.fb_cursor == 0  # only one entry, stays


def test_fb_enter_descends_into_dir(tmp_path):
    sub = tmp_path / 'subdir'
    sub.mkdir()
    m = _make_fb_model(tmp_path)
    # cursor is on subdir (first and only dir entry)
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.fb_dir == sub


def test_fb_backspace_goes_up(tmp_path):
    sub = tmp_path / 'subdir'
    sub.mkdir()
    m = _make_fb_model(tmp_path)
    m.fb_dir = sub
    m._fb_refresh()
    m, _ = m.update(tea.KeyMsg(key='backspace'))
    assert m.fb_dir == tmp_path


def test_fb_space_selects_folder_advances_to_provider_select(tmp_path):
    m = _make_fb_model(tmp_path)
    m, _ = m.update(tea.KeyMsg(key=' '))
    assert m.screen == Screen.PROVIDER_SELECT
    assert m.cf_folder == tmp_path


def test_fb_esc_returns_to_main(tmp_path):
    m = _make_fb_model(tmp_path)
    m, _ = m.update(tea.KeyMsg(key='escape'))
    assert m.screen == Screen.MAIN


def test_fb_view_shows_current_dir(tmp_path):
    m = _make_fb_model(tmp_path)
    assert str(tmp_path) in _strip(m.view())


def test_fb_slash_activates_text_mode(tmp_path):
    m = _make_fb_model(tmp_path)
    m, _ = m.update(tea.KeyMsg(key='/'))
    assert m.fb_text_mode is True


def test_fb_text_mode_typing_builds_input(tmp_path):
    m = _make_fb_model(tmp_path)
    m.fb_text_mode = True
    for ch in 'abc':
        m, _ = m.update(tea.KeyMsg(key=ch))
    assert m.fb_text_input == 'abc'


def test_fb_text_mode_backspace_deletes(tmp_path):
    m = _make_fb_model(tmp_path)
    m.fb_text_mode = True
    m.fb_text_input = 'ab'
    m, _ = m.update(tea.KeyMsg(key='backspace'))
    assert m.fb_text_input == 'a'


def test_fb_text_mode_esc_returns_to_browse(tmp_path):
    m = _make_fb_model(tmp_path)
    m.fb_text_mode = True
    m, _ = m.update(tea.KeyMsg(key='escape'))
    assert m.fb_text_mode is False


def test_fb_text_mode_enter_valid_path_advances(tmp_path):
    m = _make_fb_model(tmp_path)
    m.fb_text_mode = True
    m.fb_text_input = str(tmp_path)
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.PROVIDER_SELECT


def test_fb_text_mode_enter_invalid_path_shows_error(tmp_path):
    m = _make_fb_model(tmp_path)
    m.fb_text_mode = True
    m.fb_text_input = '/nonexistent/path/xyz'
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.FOLDER_BROWSER
    assert 'error' in m.fb_status


def test_fb_clipboard_msg_appends_to_input(tmp_path):
    m = _make_fb_model(tmp_path)
    m.fb_text_mode = True
    m.fb_text_input = '/home/'
    m, _ = m.update(_ClipboardMsg(text='matt'))
    assert 'matt' in m.fb_text_input


def test_fb_enter_on_file_advances_to_provider_select(tmp_path):
    """Enter pressed when cursor is on a file selects the current folder."""
    (tmp_path / 'conversations.json').write_text('[]')
    m = _make_fb_model(tmp_path)
    # Navigate into tmp_path so fb_entries contains the json file
    m.fb_dir = tmp_path
    m._fb_refresh()
    # Cursor should be on conversations.json (a file, not a dir)
    assert not m.fb_entries[0].is_dir()
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.PROVIDER_SELECT


def test_fb_detected_badge_shown_when_conversations_json_exists(tmp_path):
    """Export folder detection badge appears when conversations.json is present."""
    (tmp_path / 'conversations.json').write_text('[]')
    m = _make_fb_model(tmp_path)
    m.fb_dir = tmp_path
    m._fb_refresh()
    v = _strip(m.view())
    assert 'detected' in v.lower() or '✓' in v


def test_fb_detected_badge_absent_when_no_conversations_json(tmp_path):
    """No badge shown for a plain folder without conversations.json."""
    m = _make_fb_model(tmp_path)
    m.fb_dir = tmp_path
    m._fb_refresh()
    v = _strip(m.view())
    assert 'Export folder detected' not in v


def _make_ps_model(tmp_path) -> AppModel:
    m = AppModel()
    m.screen = Screen.PROVIDER_SELECT
    m.width, m.height = 80, 24
    m.cf_folder = tmp_path
    m.ps_cursor = 0
    return m


def test_ps_view_shows_all_options(tmp_path):
    m = _make_ps_model(tmp_path)
    v = _strip(m.view())
    assert 'auto' in v
    assert 'chatgpt' in v
    assert 'deepseek' in v


def test_ps_right_cycles_to_next(tmp_path):
    m = _make_ps_model(tmp_path)
    m, _ = m.update(tea.KeyMsg(key='right'))
    assert m.ps_cursor == 1


def test_ps_left_wraps(tmp_path):
    m = _make_ps_model(tmp_path)
    m.ps_cursor = 0
    m, _ = m.update(tea.KeyMsg(key='left'))
    assert m.ps_cursor == 2  # wraps to 'deepseek'


def test_ps_enter_sets_provider_and_advances(tmp_path):
    m = _make_ps_model(tmp_path)
    m.ps_cursor = 1  # chatgpt
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.cf_provider == 'chatgpt'
    assert m.screen == Screen.CONFIRM


def test_ps_enter_auto_uses_detected_provider(tmp_path):
    # tmp_path has no user.json → detects as 'chatgpt'
    m = _make_ps_model(tmp_path)
    m.ps_cursor = 0  # auto
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.cf_provider == 'chatgpt'
    assert m.screen == Screen.CONFIRM


def test_ps_esc_returns_to_folder_browser(tmp_path):
    m = _make_ps_model(tmp_path)
    m, _ = m.update(tea.KeyMsg(key='escape'))
    assert m.screen == Screen.FOLDER_BROWSER


def _make_cf_model(tmp_path) -> AppModel:
    m = AppModel()
    m.screen = Screen.CONFIRM
    m.width, m.height = 80, 24
    m.cf_folder = tmp_path
    m.cf_provider = 'chatgpt'
    m.cf_conv_count = None
    m.cf_scanning = True
    return m


def test_cf_view_shows_scanning_while_none(tmp_path):
    m = _make_cf_model(tmp_path)
    assert 'Scanning' in _strip(m.view())


def test_cf_conv_count_msg_updates_count(tmp_path):
    m = _make_cf_model(tmp_path)
    m, _ = m.update(_ConvCountMsg(count=42))
    assert m.cf_conv_count == 42
    assert m.cf_scanning is False


def test_cf_view_shows_count_after_scan(tmp_path):
    m = _make_cf_model(tmp_path)
    m.cf_conv_count = 42
    m.cf_scanning = False
    assert '42' in _strip(m.view())


def test_cf_enter_advances_to_run(tmp_path):
    m = _make_cf_model(tmp_path)
    m.cf_conv_count = 10
    m.cf_scanning = False
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.RUN


def test_cf_r_also_advances_to_run(tmp_path):
    m = _make_cf_model(tmp_path)
    m.cf_conv_count = 5
    m.cf_scanning = False
    m, _ = m.update(tea.KeyMsg(key='r'))
    assert m.screen == Screen.RUN


def test_cf_enter_blocked_while_scanning(tmp_path):
    m = _make_cf_model(tmp_path)  # cf_scanning=True by default
    m.cf_conv_count = 10
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.CONFIRM  # stays put while scanning


def test_cf_esc_returns_to_provider_select(tmp_path):
    m = _make_cf_model(tmp_path)
    m, _ = m.update(tea.KeyMsg(key='escape'))
    assert m.screen == Screen.PROVIDER_SELECT


def _make_run_model() -> AppModel:
    m = AppModel()
    m.screen = Screen.RUN
    m.width, m.height = 80, 24
    m.run_total   = 10
    m.run_written = 0
    m.run_skipped = 0
    m.run_done    = False
    return m


def test_run_progress_msg_updates_counts():
    m = _make_run_model()
    m, _ = m.update(_ProgressMsg(written=3, skipped=1, total=10))
    assert m.run_written == 3
    assert m.run_skipped == 1


def test_run_done_msg_sets_done():
    m = _make_run_model()
    m, _ = m.update(_DoneMsg(written=8, skipped=2))
    assert m.run_done is True
    assert m.run_written == 8
    assert m.run_skipped == 2


def test_run_view_shows_progress():
    m = _make_run_model()
    m.run_written = 5
    assert '5' in _strip(m.view())


def test_run_view_shows_done_message():
    m = _make_run_model()
    m.run_done = True
    m.run_written = 10
    v = _strip(m.view())
    assert 'Done' in v
    assert 'Written' in v


def test_run_enter_when_done_returns_to_main():
    m = _make_run_model()
    m.run_done = True
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.MAIN


def test_run_enter_while_running_does_nothing():
    m = _make_run_model()
    m.run_done = False
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.RUN


def test_run_error_msg_stored():
    m = _make_run_model()
    m, _ = m.update(_RunErrorMsg(error='something went wrong'))
    assert 'something went wrong' in m.run_error
    assert m.run_done is True


def test_run_view_shows_error():
    m = _make_run_model()
    m.run_error = 'disk full'
    m.run_done = True
    assert 'disk full' in _strip(m.view())


# ── SETTINGS screen ────────────────────────────────────────────────────────────

def _make_st_model() -> AppModel:
    m = AppModel()
    m.screen = Screen.SETTINGS
    m.width, m.height = 80, 24
    m.st_cursor = 0
    m.st_values = {'output_dir': './output', 'user_name': '', 'chatgpt_assistant': '', 'deepseek_assistant': ''}
    m.st_status = ''
    return m


def test_st_view_shows_field_labels():
    m = _make_st_model()
    v = _strip(m.view())
    assert 'Output directory' in v
    assert 'User name' in v
    assert 'ChatGPT assistant name' in v
    assert 'DeepSeek assistant name' in v


def test_st_tab_moves_to_next_field():
    m = _make_st_model()
    m.st_cursor = 0
    m, _ = m.update(tea.KeyMsg(key='tab'))
    assert m.st_cursor == 1


def test_st_shift_tab_moves_to_prev_field():
    m = _make_st_model()
    m.st_cursor = 1
    m, _ = m.update(tea.KeyMsg(key='shift+tab'))
    assert m.st_cursor == 0


def test_st_tab_wraps_to_save_button():
    m = _make_st_model()
    m.st_cursor = 3  # last text field
    m, _ = m.update(tea.KeyMsg(key='tab'))
    assert m.st_cursor == 4  # Save button


def test_st_tab_wraps_from_save_button_to_first_field():
    m = _make_st_model()
    m.st_cursor = 4  # Save button
    m, _ = m.update(tea.KeyMsg(key='tab'))
    assert m.st_cursor == 0


def test_st_shift_tab_wraps_from_first_field_to_save_button():
    m = _make_st_model()
    m.st_cursor = 0
    m, _ = m.update(tea.KeyMsg(key='shift+tab'))
    assert m.st_cursor == 4


def test_st_typing_updates_focused_field():
    m = _make_st_model()
    m.st_cursor = 1  # user_name
    m, _ = m.update(tea.KeyMsg(key='M'))
    m, _ = m.update(tea.KeyMsg(key='a'))
    m, _ = m.update(tea.KeyMsg(key='t'))
    m, _ = m.update(tea.KeyMsg(key='t'))
    assert m.st_values['user_name'] == 'Matt'


def test_st_backspace_deletes_from_focused_field():
    m = _make_st_model()
    m.st_cursor = 0
    m.st_values['output_dir'] = './output'
    m, _ = m.update(tea.KeyMsg(key='backspace'))
    assert m.st_values['output_dir'] == './outpu'


def test_st_save_button_enter_writes_toml(tmp_path, monkeypatch):
    saved = {}
    monkeypatch.setattr('tui._save_settings', lambda v: saved.update(v))
    m = _make_st_model()
    m.st_cursor = 4  # Save button
    m.st_values['user_name'] = 'Matt'
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert saved.get('user_name') == 'Matt'
    assert 'ok' in m.st_status


def test_st_esc_returns_to_main():
    m = _make_st_model()
    m, _ = m.update(tea.KeyMsg(key='escape'))
    assert m.screen == Screen.MAIN


# ── REVIEW screen ──────────────────────────────────────────────────────────────

def test_review_view_shows_placeholder():
    m = AppModel()
    m.screen = Screen.REVIEW
    m.width, m.height = 80, 24
    v = _strip(m.view())
    assert 'Coming soon' in v or 'tagging' in v.lower()


def test_review_esc_returns_to_main():
    m = AppModel()
    m.screen = Screen.REVIEW
    m, _ = m.update(tea.KeyMsg(key='escape'))
    assert m.screen == Screen.MAIN


def test_tui_main_importable():
    """main() exists and is callable without running the program."""
    from tui import main
    assert callable(main)


def test_appmodel_window_size_msg_updates_dimensions():
    m = AppModel()
    m, _ = m.update(tea.WindowSizeMsg(width=120, height=40))
    assert m.width == 120
    assert m.height == 40
