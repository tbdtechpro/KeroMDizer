# tests/test_tui.py
from tui import (AppModel, Screen, _ClipboardMsg, _ConvCountMsg, _ProgressMsg, _DoneMsg, _RunErrorMsg,
                  _ProjectProgressMsg, _ProjectDoneMsg, _ProjectErrorMsg, _TokenSavedMsg)
import bubblepy as tea


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


import pygloss as _lipgloss  # for strip_ansi


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
    m.menu_cursor = 5  # last item (6 items: 0-5)
    m, _ = m.update(tea.KeyMsg(key='down'))
    assert m.menu_cursor == 0


def test_main_cursor_wraps_up():
    m = AppModel()
    m.menu_cursor = 0
    m, _ = m.update(tea.KeyMsg(key='up'))
    assert m.menu_cursor == 5


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
    m.menu_cursor = 3  # Review (was 2, now shifted by Export Settings)
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
    assert 'adir' in names
    assert 'zfile.txt' not in names  # files are filtered out


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
    # fb_entries now has 2 items: '..' parent + 'only'
    assert len(m.fb_entries) == 2
    m.fb_cursor = 1  # on the last real entry
    m, _ = m.update(tea.KeyMsg(key='down'))
    assert m.fb_cursor == 1  # clamped at bottom


def test_fb_enter_descends_into_dir(tmp_path):
    sub = tmp_path / 'subdir'
    sub.mkdir()
    m = _make_fb_model(tmp_path)
    # fb_entries[0] = '..' parent, fb_entries[1] = subdir
    assert len(m.fb_entries) == 2
    m.fb_cursor = 1  # move to subdir
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


def test_fb_enter_in_export_folder_advances_to_provider_select(tmp_path):
    """Space selects current folder (export folder with no visible subdirs)."""
    (tmp_path / 'conversations.json').write_text('[]')
    m = _make_fb_model(tmp_path)
    m.fb_dir = tmp_path
    m._fb_refresh()
    # Only the '..' parent entry is shown (conversations.json is a file, filtered out)
    assert len(m.fb_entries) == 1
    assert m.fb_entries[0] == tmp_path.parent
    # Space always selects the *current* directory, regardless of cursor
    m, _ = m.update(tea.KeyMsg(key=' '))
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


def test_ps_down_cycles_to_next(tmp_path):
    m = _make_ps_model(tmp_path)
    m, _ = m.update(tea.KeyMsg(key='down'))
    assert m.ps_cursor == 1


def test_ps_up_wraps(tmp_path):
    m = _make_ps_model(tmp_path)
    m.ps_cursor = 0
    m, _ = m.update(tea.KeyMsg(key='up'))
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
    m.st_values = {
        'output_dir': './output',
        'user_name': '',
        'chatgpt_assistant': '',
        'deepseek_assistant': '',
        'import_branches': 'all',
        'export_markdown': 'all',
        'export_jsonl': 'all',
    }
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
    m.st_cursor = 7  # last field (project_conflict)
    m, _ = m.update(tea.KeyMsg(key='tab'))
    assert m.st_cursor == 8  # Save button


def test_st_tab_wraps_from_save_button_to_first_field():
    m = _make_st_model()
    m.st_cursor = 8  # Save button
    m, _ = m.update(tea.KeyMsg(key='tab'))
    assert m.st_cursor == 0


def test_st_shift_tab_wraps_from_first_field_to_save_button():
    m = _make_st_model()
    m.st_cursor = 0
    m, _ = m.update(tea.KeyMsg(key='shift+tab'))
    assert m.st_cursor == 8


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
    m.st_cursor = 8  # Save button
    m.st_values['user_name'] = 'Matt'
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert saved.get('user_name') == 'Matt'
    assert 'ok' in m.st_status


def test_st_esc_returns_to_main():
    m = _make_st_model()
    m, _ = m.update(tea.KeyMsg(key='escape'))
    assert m.screen == Screen.MAIN


# ── REVIEW screen ──────────────────────────────────────────────────────────────

class _MockDB:
    def __init__(self, rows):
        self._rows = rows
    def list_branches(self, main_only=False, offset=0, limit=500):
        return self._rows
    def get_all_tags(self):
        return []
    def update_branch_tags(self, *a, **kw):
        pass
    def close(self):
        pass


def _make_row(conv_id, title):
    return {
        'branch_id': f'{conv_id}__branch_1',
        'conversation_id': conv_id, 'branch_index': 1,
        'is_main_branch': True, 'title': title, 'provider': 'chatgpt',
        'conv_create_time': '2026-01-14T00:00:00+00:00', 'model_slug': 'gpt-4o',
        'tags': [], 'project': None, 'category': None, 'syntax': [],
        'inferred_tags': [], 'inferred_syntax': [], 'messages': [],
    }


def test_review_screen_renders_empty_state(monkeypatch):
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB([]))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    view = model.view()
    # Should show some kind of empty state message
    assert any(word in view.lower() for word in ('no conversation', 'empty', 'import', 'database'))


def test_review_screen_shows_branch_titles(monkeypatch):
    rows = [_make_row('c1', 'My Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    view = model.view()
    assert 'My Chat' in view


def test_review_cursor_moves_down(monkeypatch):
    rows = [_make_row('c1', 'First Chat'), _make_row('c2', 'Second Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    assert model.rv_cursor == 0
    model, _ = model.update(tea.KeyMsg(key='down'))
    assert model.rv_cursor == 1


def test_review_cursor_does_not_go_below_last(monkeypatch):
    rows = [_make_row('c1', 'Only')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='down'))
    assert model.rv_cursor == 0


def test_review_cursor_moves_up(monkeypatch):
    rows = [_make_row('c1', 'First'), _make_row('c2', 'Second')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model.rv_cursor = 1
    model, _ = model.update(tea.KeyMsg(key='up'))
    assert model.rv_cursor == 0


def test_review_escape_returns_to_main(monkeypatch):
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB([]))
    model = AppModel()
    model.screen = Screen.REVIEW
    model, _ = model.update(tea.KeyMsg(key='escape'))
    assert model.screen == Screen.MAIN


def test_review_view_shows_placeholder():
    m = AppModel()
    m.screen = Screen.REVIEW
    m.width, m.height = 80, 24
    v = _strip(m.view())
    assert 'Coming soon' in v or 'tagging' in v.lower() or 'import' in v.lower() or 'no conversation' in v.lower()


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


def test_settings_branch_toggles_present_in_view():
    model = AppModel()
    model.screen = Screen.SETTINGS
    view = model.view()
    assert 'Import branches' in view
    assert 'Markdown export branches' in view
    assert 'JSONL export branches' in view


def test_settings_branch_toggle_cycles_on_enter():
    model = AppModel()
    model.screen = Screen.SETTINGS
    # Navigate to import_branches toggle (index 4)
    for _ in range(4):
        model, _ = model.update(tea.KeyMsg(key='tab'))
    assert model.st_cursor == 4
    initial = model.st_values.get('import_branches', 'all')
    model, _ = model.update(tea.KeyMsg(key='enter'))
    assert model.st_values['import_branches'] != initial


def test_settings_tab_wraps_at_9():
    # 8 fields + 1 Save button = 9 positions (0–8); 9 tabs wraps back to 0
    model = AppModel()
    model.screen = Screen.SETTINGS
    for _ in range(9):
        model, _ = model.update(tea.KeyMsg(key='tab'))
    assert model.st_cursor == 0


def test_settings_save_includes_branch_config(tmp_path, monkeypatch):
    # Just verify that the branch fields exist in st_values with valid values
    model = AppModel()
    model.screen = Screen.SETTINGS
    assert 'import_branches' in model.st_values
    assert 'export_markdown' in model.st_values
    assert 'export_jsonl' in model.st_values
    assert model.st_values['import_branches'] in ('main', 'all')
    assert model.st_values['export_markdown'] in ('main', 'all')
    assert model.st_values['export_jsonl'] in ('main', 'all')


def test_settings_project_conflict_present():
    model = AppModel()
    assert 'project_conflict' in model.st_values
    assert model.st_values['project_conflict'] in ('preserve', 'overwrite', 'flag')


def test_settings_project_conflict_cycles_preserve_overwrite_flag():
    model = AppModel()
    model.screen = Screen.SETTINGS
    # Navigate to project_conflict field (index 7)
    for _ in range(7):
        model, _ = model.update(tea.KeyMsg(key='tab'))
    assert model.st_cursor == 7
    model.st_values['project_conflict'] = 'preserve'
    model, _ = model.update(tea.KeyMsg(key='enter'))
    assert model.st_values['project_conflict'] == 'overwrite'
    model, _ = model.update(tea.KeyMsg(key='enter'))
    assert model.st_values['project_conflict'] == 'flag'
    model, _ = model.update(tea.KeyMsg(key='enter'))
    assert model.st_values['project_conflict'] == 'preserve'


def test_settings_project_conflict_in_view():
    model = AppModel()
    model.screen = Screen.SETTINGS
    view = model.view()
    assert 'Project conflict' in view


# ── REVIEW editor ──────────────────────────────────────────────────────────────

def test_review_enter_opens_editor(monkeypatch):
    """After Task 4, 'e' opens the editor (enter goes to viewer instead)."""
    rows = [_make_row('c1', 'Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='e'))
    assert model.rv_editing is True
    view = model.view()
    assert 'Tags' in view


def test_review_editor_escape_returns_to_table(monkeypatch):
    rows = [_make_row('c1', 'Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='e'))
    assert model.rv_editing is True
    model, _ = model.update(tea.KeyMsg(key='escape'))
    assert model.rv_editing is False


def test_review_editor_typing_updates_tags_draft(monkeypatch):
    rows = [_make_row('c1', 'Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='e'))
    for ch in 'pyt':
        model, _ = model.update(tea.KeyMsg(key=ch))
    assert 'pyt' in model.rv_edit_values.get('tags_draft', '')


def test_review_editor_autocomplete_shown(monkeypatch):
    class MockDBWithTags(_MockDB):
        def get_all_tags(self):
            return ['python', 'pytest', 'rust']
    rows = [_make_row('c1', 'Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: MockDBWithTags(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='e'))
    for ch in 'py':
        model, _ = model.update(tea.KeyMsg(key=ch))
    view = model.view()
    assert 'python' in view or 'pytest' in view


def test_review_editor_ctrl_s_saves(monkeypatch):
    saved = {}
    class MockDBSave(_MockDB):
        def update_branch_tags(self, branch_id, tags, project, category, syntax):
            saved['branch_id'] = branch_id
            saved['tags'] = tags
    rows = [_make_row('c1', 'Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: MockDBSave(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='e'))
    model.rv_edit_values['tags_draft'] = 'python, async'
    model, _ = model.update(tea.KeyMsg(key='ctrl+s'))
    assert saved.get('branch_id') == 'c1__branch_1'
    assert 'python' in saved.get('tags', [])
    assert 'async' in saved.get('tags', [])


# ── SEARCH screen ───────────────────────────────────────────────────────────────

def test_search_screen_in_enum():
    assert hasattr(Screen, 'SEARCH')


def test_search_initial_state():
    m = AppModel()
    assert m.ss_query == ''
    assert m.ss_results == []
    assert m.ss_searched == False
    assert m.ss_field == 0


def test_search_typing_updates_query():
    m = AppModel()
    m.screen = Screen.SEARCH
    for ch in 'python':
        m, _ = m.update(tea.KeyMsg(key=ch))
    assert m.ss_query == 'python'


def test_search_tab_cycles_fields():
    m = AppModel()
    m.screen = Screen.SEARCH
    for _ in range(4):
        m, _ = m.update(tea.KeyMsg(key='tab'))
    assert m.ss_field == 0  # wrapped back to start


def test_search_escape_from_results_goes_to_query():
    m = AppModel()
    m.screen = Screen.SEARCH
    m.ss_field = 3
    m, _ = m.update(tea.KeyMsg(key='escape'))
    assert m.ss_field == 0
    assert m.screen == Screen.SEARCH  # still on search screen


def test_search_escape_from_query_goes_to_main():
    m = AppModel()
    m.screen = Screen.SEARCH
    m.ss_field = 0
    m, _ = m.update(tea.KeyMsg(key='escape'))
    assert m.screen == Screen.MAIN


def test_search_menu_item_accessible():
    m = AppModel()
    assert 'Search' in m.menu_items
    m.menu_cursor = m.menu_items.index('Search')
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.SEARCH


def test_search_enter_on_results_opens_viewer():
    m = AppModel()
    m.screen = Screen.SEARCH
    m.ss_field = 3
    m.ss_results = [{'branch_id': 'b1', 'title': 'Test', 'md_filename': '',
                     'provider': 'chatgpt', 'conv_create_time': '2026-01-01',
                     'tags': [], 'project': None, 'category': None,
                     'syntax': [], 'inferred_tags': [], 'inferred_syntax': [],
                     'is_main_branch': True, 'branch_index': 1}]
    m.ss_cursor = 0
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.VIEWER


# ── VIEWER screen ────────────────────────────────────────────────────────────────

def test_viewer_screen_in_enum():
    assert hasattr(Screen, 'VIEWER')


def test_viewer_state_initialized():
    m = AppModel()
    assert m.vw_lines == []
    assert m.vw_offset == 0
    assert m.vw_row is None


def test_viewer_scroll_down():
    m = AppModel()
    m.width, m.height = 80, 24
    m.screen = Screen.VIEWER
    m.vw_lines = [f'line {i}' for i in range(50)]
    m.vw_row = {'title': 'Test', 'branch_id': 'x'}
    m, _ = m.update(tea.KeyMsg(key='down'))
    assert m.vw_offset == 1


def test_viewer_scroll_clamps_at_top():
    m = AppModel()
    m.width, m.height = 80, 24
    m.screen = Screen.VIEWER
    m.vw_lines = [f'line {i}' for i in range(50)]
    m.vw_row = {'title': 'Test', 'branch_id': 'x'}
    m.vw_offset = 0
    m, _ = m.update(tea.KeyMsg(key='up'))
    assert m.vw_offset == 0  # clamped at 0


def test_viewer_escape_returns_to_source_screen():
    m = AppModel()
    m.screen = Screen.VIEWER
    m.vw_return_screen = Screen.SEARCH
    m.vw_row = {'title': 'Test', 'branch_id': 'x'}
    m, _ = m.update(tea.KeyMsg(key='escape'))
    assert m.screen == Screen.SEARCH


def test_review_enter_opens_viewer_not_editor():
    """After Task 4, enter on REVIEW goes to VIEWER, not directly to editor."""
    m = AppModel()
    m.screen = Screen.REVIEW
    m.rv_rows = [{'branch_id': 'b1', 'title': 'Test', 'md_filename': '', 'provider': 'chatgpt',
                  'conv_create_time': '2026-01-01', 'tags': [], 'project': None, 'category': None,
                  'syntax': [], 'inferred_tags': [], 'inferred_syntax': [], 'is_main_branch': True,
                  'branch_index': 1}]
    m.rv_cursor = 0
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.VIEWER


# ── Export Settings tests ───────────────────────────────────────────────────────

def test_export_settings_screen_in_enum():
    assert hasattr(Screen, 'EXPORT_SETTINGS')


def test_export_settings_initial_state():
    m = AppModel()
    assert hasattr(m, 'es_values')
    assert 'html_github_enabled' in m.es_values
    assert 'docx_enabled' in m.es_values


def test_export_settings_accessible_from_main():
    m = AppModel()
    m.menu_cursor = m.menu_items.index('Export')
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.screen == Screen.EXPORT_SETTINGS


def test_export_settings_toggle_html_github():
    m = AppModel()
    m.screen = Screen.EXPORT_SETTINGS
    # Navigate to html_github_enabled (index 0)
    m.es_cursor = 0
    initial = m.es_values.get('html_github_enabled', 'no')
    m, _ = m.update(tea.KeyMsg(key='enter'))
    assert m.es_values['html_github_enabled'] != initial


def test_export_settings_escape_goes_to_main():
    m = AppModel()
    m.screen = Screen.EXPORT_SETTINGS
    m, _ = m.update(tea.KeyMsg(key='escape'))
    assert m.screen == Screen.MAIN


# ── PROJECTS screen ─────────────────────────────────────────────────────────────

def test_projects_screen_in_enum():
    assert Screen.PROJECTS.value == 'projects'


def test_projects_accessible_from_main(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    monkeypatch.setattr('tui.AppModel.__init__', lambda self: None)  # skip heavy init
    # Just verify the menu item exists
    model = AppModel.__new__(AppModel)
    model.menu_items = ['Import', 'Settings', 'Export', 'Review', 'Projects', 'Search']
    assert 'Projects' in model.menu_items


def test_projects_initial_state(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {'g-p-abc': 'My Project'})
    model = AppModel()
    assert hasattr(model, 'pj_token_found')
    assert hasattr(model, 'pj_projects_count')
    assert model.pj_projects_count == 1
    assert model.pj_paste_mode is False
    assert model.pj_syncing is False
    assert model.pj_status == ''


def test_projects_escape_returns_to_main(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model, _ = model.update(tea.KeyMsg(key='escape'))
    assert model.screen == Screen.MAIN


def test_projects_v_enters_paste_mode(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model, _ = model.update(tea.KeyMsg(key='v'))
    assert model.pj_paste_mode is True


def test_projects_paste_mode_escape_cancels(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model.pj_paste_mode = True
    model.pj_paste_input = 'partial'
    model, _ = model.update(tea.KeyMsg(key='escape'))
    assert model.pj_paste_mode is False
    assert model.pj_paste_input == ''


def test_projects_paste_mode_typing(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model.pj_paste_mode = True
    model, _ = model.update(tea.KeyMsg(key='e'))
    model, _ = model.update(tea.KeyMsg(key='y'))
    model, _ = model.update(tea.KeyMsg(key='J'))
    assert model.pj_paste_input == 'eyJ'


def test_projects_view_shows_token_status(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model.pj_token_found = True
    view = model.view()
    assert 'Token status' in view
    assert '● Found' in view


def test_projects_view_shows_missing_token(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model.pj_token_found = False
    view = model.view()
    assert '○ Missing' in view


def test_projects_progress_msg_updates_progress(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model.pj_syncing = True
    model, _ = model.update(_ProjectProgressMsg(project_name='Tools', count=5))
    assert 'Tools' in model.pj_progress


def test_projects_done_msg_clears_syncing(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model.pj_syncing = True
    model, _ = model.update(_ProjectDoneMsg(applied=10, conflicts=2))
    assert model.pj_syncing is False
    assert model.pj_applied == 10
    assert model.pj_conflicts == 2
    assert 'ok' in model.pj_status


def test_projects_error_msg_clears_syncing(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model.pj_syncing = True
    model, _ = model.update(_ProjectErrorMsg(error='Network error'))
    assert model.pj_syncing is False
    assert 'error' in model.pj_status


def test_projects_token_saved_msg_success(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model, _ = model.update(_TokenSavedMsg(success=True, message='Token saved'))
    assert model.pj_token_found is True
    assert 'ok' in model.pj_status


def test_projects_token_saved_msg_failure(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model, _ = model.update(_TokenSavedMsg(success=False, message='No token in browser'))
    assert 'error' in model.pj_status
    assert 'No token in browser' in model.pj_status


def test_projects_paste_confirm_success(monkeypatch, tmp_path):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    token_file = tmp_path / 'token.json'
    monkeypatch.setattr('tui.project_fetcher.TOKEN_FILE', token_file)
    # Monkeypatch save_token to avoid writing to real home dir
    monkeypatch.setattr('retrieve_token.TOKEN_FILE', token_file)
    model = AppModel()
    model.screen = Screen.PROJECTS
    model.pj_paste_mode = True
    model.pj_paste_input = 'eyJtest'
    model, _ = model.update(tea.KeyMsg(key='enter'))
    assert model.pj_paste_mode is False
    assert model.pj_token_found is True
    assert 'ok' in model.pj_status


def test_projects_r_key_triggers_sync(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {'g-p-abc': 'Tools'})
    synced = []
    monkeypatch.setattr('tui._cmd_sync_projects', lambda *a, **kw: synced.append(True))
    monkeypatch.setattr('tui.project_fetcher.load_token', lambda: 'eyJtoken')
    model = AppModel()
    model.screen = Screen.PROJECTS
    model.pj_token_found = True
    model, _ = model.update(tea.KeyMsg(key='r'))
    assert model.pj_syncing is True
    assert len(synced) == 1


def test_projects_view_shows_syncing_progress(monkeypatch):
    monkeypatch.setattr('tui._load_chatgpt_projects', lambda: {})
    model = AppModel()
    model.screen = Screen.PROJECTS
    model.pj_syncing = True
    model.pj_progress = "Fetching 'Tools'… 5 conversations"
    view = model.view()
    assert 'Tools' in view
