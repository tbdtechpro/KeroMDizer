# tui.py
from __future__ import annotations
import enum
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import bubbletea as tea
import lipgloss
from lipgloss import Color
from lipgloss.themes.catppuccin import catppuccin_mocha as M
from db import DatabaseManager

# ── Colours ────────────────────────────────────────────────────────────────────
C_TEXT    = M.text
C_MUTED   = M.subtext0
C_ACCENT  = M.mauve
C_GREEN   = M.green
C_RED     = M.red
C_YELLOW  = M.yellow
C_SURFACE = M.surface0
C_BASE    = M.base
C_CRUST   = M.crust
C_SEL     = M.lavender

# ── Styles ─────────────────────────────────────────────────────────────────────
panel_style   = (lipgloss.Style()
                 .border(lipgloss.rounded_border())
                 .border_foreground(C_ACCENT)
                 .padding(1, 2))
title_style   = (lipgloss.Style()
                 .bold(True)
                 .foreground(C_CRUST)
                 .background(C_ACCENT)
                 .padding(0, 2))
hint_style    = lipgloss.Style().foreground(C_MUTED).italic(True)
error_style   = lipgloss.Style().foreground(C_RED).bold(True)
success_style = lipgloss.Style().foreground(C_GREEN).bold(True)
sel_style     = lipgloss.Style().foreground(C_SEL).bold(True)
muted_style   = lipgloss.Style().foreground(C_MUTED)


class Screen(enum.Enum):
    MAIN            = 'main'
    FOLDER_BROWSER  = 'folder_browser'
    PROVIDER_SELECT = 'provider_select'
    CONFIRM         = 'confirm'
    RUN             = 'run'
    SETTINGS        = 'settings'
    REVIEW          = 'review'


# ── Custom messages ────────────────────────────────────────────────────────────
@dataclass
class _ConvCountMsg(tea.Msg):
    count: int

@dataclass
class _ProgressMsg(tea.Msg):
    written: int
    skipped: int
    total:   int

@dataclass
class _DoneMsg(tea.Msg):
    written: int
    skipped: int

@dataclass
class _ClipboardMsg(tea.Msg):
    text: str

@dataclass
class _RunErrorMsg(tea.Msg):
    error: str


# ── Settings helpers ───────────────────────────────────────────────────────────
def _load_settings() -> dict[str, str]:
    """Load current settings from TOML or return defaults."""
    import tomllib
    toml_path = Path.home() / '.keromdizer.toml'
    data: dict = {}
    if toml_path.exists():
        try:
            with open(toml_path, 'rb') as f:
                data = tomllib.load(f)
        except Exception:
            pass
    providers = data.get('providers', {})
    branches = data.get('branches', {})
    return {
        'output_dir':        data.get('output', {}).get('dir', './output'),
        'user_name':         data.get('user', {}).get('name', ''),
        'chatgpt_assistant': providers.get('chatgpt', {}).get('assistant_name', ''),
        'deepseek_assistant': providers.get('deepseek', {}).get('assistant_name', ''),
        'import_branches':   branches.get('import', 'all'),
        'export_markdown':   branches.get('export_markdown', 'all'),
        'export_jsonl':      branches.get('export_jsonl', 'all'),
    }


def _toml_serialize(data: dict, prefix: str = '') -> list[str]:
    """Minimal recursive TOML serializer for string-valued nested dicts."""
    lines: list[str] = []
    flat = {k: v for k, v in data.items() if not isinstance(v, dict)}
    nested = {k: v for k, v in data.items() if isinstance(v, dict)}
    if flat:
        if prefix:
            lines.append(f'[{prefix}]')
        for k, v in flat.items():
            lines.append(f'{k} = "{v}"')
    for k, v in nested.items():
        sub_prefix = f'{prefix}.{k}' if prefix else k
        lines.extend(_toml_serialize(v, sub_prefix))
    return lines


def _save_settings(values: dict[str, str]) -> None:
    """Persist settings to ~/.keromdizer.toml."""
    import tomllib
    toml_path = Path.home() / '.keromdizer.toml'
    data: dict = {}
    if toml_path.exists():
        try:
            with open(toml_path, 'rb') as f:
                data = tomllib.load(f)
        except Exception:
            pass
    if values.get('user_name'):
        data.setdefault('user', {})['name'] = values['user_name']
    if values.get('chatgpt_assistant'):
        data.setdefault('providers', {}).setdefault('chatgpt', {})['assistant_name'] = values['chatgpt_assistant']
    if values.get('deepseek_assistant'):
        data.setdefault('providers', {}).setdefault('deepseek', {})['assistant_name'] = values['deepseek_assistant']
    branches_data = {}
    if values.get('import_branches'):
        branches_data['import'] = values['import_branches']
    if values.get('export_markdown'):
        branches_data['export_markdown'] = values['export_markdown']
    if values.get('export_jsonl'):
        branches_data['export_jsonl'] = values['export_jsonl']
    if branches_data:
        data['branches'] = branches_data
    toml_path.write_text('\n'.join(_toml_serialize(data)) + '\n', encoding='utf-8')


def _cmd_clipboard(program: Optional['tea.Program']) -> None:
    """Spawn daemon thread to read clipboard and send _ClipboardMsg."""
    def _run():
        import subprocess
        for cmd in (['wl-paste'], ['xclip', '-selection', 'clipboard', '-o'], ['xsel', '--clipboard', '--output']):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    if program:
                        program.send(_ClipboardMsg(text=result.stdout))
                    return
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        if program:
            program.send(_ClipboardMsg(text=''))
    threading.Thread(target=_run, daemon=True).start()


class AppModel(tea.Model):
    def __init__(self):
        self.screen: Screen = Screen.MAIN
        self.width:  int = 80
        self.height: int = 24
        self._program: Optional[tea.Program] = None

        # MAIN
        self.menu_cursor: int = 0
        self.menu_items: list[str] = ['Import', 'Settings', 'Review']

        # FOLDER_BROWSER
        self.fb_dir: Path = Path.home()
        self.fb_entries: list[Path] = []
        self.fb_cursor: int = 0
        self.fb_text_mode: bool = False
        self.fb_text_input: str = ''
        self.fb_status: str = ''

        # PROVIDER_SELECT
        self.ps_options: list[str] = ['auto', 'chatgpt', 'deepseek']
        self.ps_cursor: int = 0
        self.ps_detected: str = ''

        # CONFIRM
        self.cf_folder: Path = Path('.')
        self.cf_provider: str = 'chatgpt'
        self.cf_conv_count: Optional[int] = None
        self.cf_scanning: bool = False

        # RUN
        self.run_total:   int = 0
        self.run_written: int = 0
        self.run_skipped: int = 0
        self.run_done:    bool = False
        self.run_error:   str = ''

        # DB
        from config import load_db_path
        self._db: DatabaseManager = DatabaseManager(load_db_path())

        # REVIEW
        self.rv_rows: list[dict] = []
        self.rv_cursor: int = 0
        self.rv_editing: bool = False
        self.rv_edit_field: int = 0    # 0=tags_draft, 1=project, 2=category, 3=syntax_draft
        self.rv_edit_values: dict[str, str] = {}
        self.rv_autocomplete: list[str] = []
        self.rv_all_tags: list[str] = []
        self.rv_status: str = ''

        # SETTINGS
        st_defaults = _load_settings()
        self.st_fields: list[str] = [
            'output_dir', 'user_name', 'chatgpt_assistant', 'deepseek_assistant',
            'import_branches', 'export_markdown', 'export_jsonl',
        ]
        self.st_labels: dict[str, str] = {
            'output_dir':         'Output directory',
            'user_name':          'User name',
            'chatgpt_assistant':  'ChatGPT assistant name',
            'deepseek_assistant': 'DeepSeek assistant name',
            'import_branches':    'Import branches',
            'export_markdown':    'Markdown export branches',
            'export_jsonl':       'JSONL export branches',
        }
        self.st_toggle_fields: set[str] = {'import_branches', 'export_markdown', 'export_jsonl'}
        self.st_values: dict[str, str] = st_defaults
        self.st_cursor: int = 0
        self.st_status: str = ''

    def init(self) -> Optional[tea.Cmd]:
        return tea.window_size()

    def update(self, msg: tea.Msg) -> tuple[AppModel, Optional[tea.Cmd]]:
        if isinstance(msg, tea.WindowSizeMsg):
            self.width, self.height = msg.width, msg.height
            return self, None
        if isinstance(msg, tea.KeyMsg) and msg.key == 'ctrl+c':
            return self, tea.quit_cmd
        dispatch = {
            Screen.MAIN:            self._key_main,
            Screen.FOLDER_BROWSER:  self._key_folder_browser,
            Screen.PROVIDER_SELECT: self._key_provider_select,
            Screen.CONFIRM:         self._key_confirm,
            Screen.RUN:             self._key_run,
            Screen.SETTINGS:        self._key_settings,
            Screen.REVIEW:          self._key_review,
        }
        handler = dispatch.get(self.screen)
        if handler:
            return handler(msg)
        return self, None

    def view(self) -> str:
        views = {
            Screen.MAIN:            self._view_main,
            Screen.FOLDER_BROWSER:  self._view_folder_browser,
            Screen.PROVIDER_SELECT: self._view_provider_select,
            Screen.CONFIRM:         self._view_confirm,
            Screen.RUN:             self._view_run,
            Screen.SETTINGS:        self._view_settings,
            Screen.REVIEW:          self._view_review,
        }
        return views[self.screen]() + '\n'

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _header(self, subtitle: str = '') -> str:
        title = 'KeroMDizer'
        if subtitle:
            title += f'  /  {subtitle}'
        return title_style.render(title)

    def _footer(self, hints: str) -> str:
        return hint_style.render(hints)

    def _panel(self, content: str) -> str:
        w = min(self.width - 4, 72)
        return panel_style.width(w).render(content)

    # ── Screen stubs (implemented in later tasks) ──────────────────────────────
    def _key_main(self, msg):
        if not isinstance(msg, tea.KeyMsg):
            return self, None
        n = len(self.menu_items)
        if msg.key in ('down', 'j'):
            self.menu_cursor = (self.menu_cursor + 1) % n
        elif msg.key in ('up', 'k'):
            self.menu_cursor = (self.menu_cursor - 1) % n
        elif msg.key == 'q':
            return self, tea.quit_cmd
        elif msg.key == 'enter':
            dest = [Screen.FOLDER_BROWSER, Screen.SETTINGS, Screen.REVIEW]
            self.screen = dest[self.menu_cursor]
            if self.screen == Screen.FOLDER_BROWSER:
                self._start_new_import()
            elif self.screen == Screen.REVIEW:
                self._load_review_data()
        return self, None

    def _key_folder_browser(self, msg):
        if isinstance(msg, _ClipboardMsg):
            if self.fb_text_mode:
                self.fb_text_input += msg.text.strip()
            return self, None

        if not isinstance(msg, tea.KeyMsg):
            return self, None

        key = msg.key

        # ── Text mode ──────────────────────────────────────────────────────────
        if self.fb_text_mode:
            if key == 'escape':
                self.fb_text_mode = False
                self.fb_text_input = ''
                self.fb_status = ''
            elif key == 'enter':
                p = Path(self.fb_text_input.strip()).expanduser()
                if p.is_dir():
                    self._select_folder(p)
                else:
                    self.fb_status = f'error:Not a directory: {p}'
            elif key == 'backspace':
                self.fb_text_input = self.fb_text_input[:-1]
            elif key == 'ctrl+u':
                self.fb_text_input = ''
            elif key == 'ctrl+v':
                _cmd_clipboard(self._program)
            elif len(key) == 1:
                self.fb_text_input += key
            return self, None

        # ── Browse mode ────────────────────────────────────────────────────────
        if key == 'escape':
            self.screen = Screen.MAIN
        elif key in ('down', 'j'):
            self.fb_cursor = min(self.fb_cursor + 1, len(self.fb_entries) - 1)
        elif key in ('up', 'k'):
            self.fb_cursor = max(self.fb_cursor - 1, 0)
        elif key == 'backspace':
            parent = self.fb_dir.parent
            if parent != self.fb_dir:
                self.fb_dir = parent
                self._fb_refresh()
        elif key == 'enter':
            if self.fb_entries and self.fb_entries[self.fb_cursor].is_dir():
                self.fb_dir = self.fb_entries[self.fb_cursor]
                self._fb_refresh()
            else:
                self._select_folder(self.fb_dir)
        elif key == ' ':
            self._select_folder(self.fb_dir)
        elif key == '/':
            self.fb_text_mode = True
            self.fb_text_input = ''
            self.fb_status = ''
        return self, None

    def _select_folder(self, path: Path) -> None:
        """Advance to PROVIDER_SELECT with the chosen folder."""
        self.cf_folder = path
        self.ps_cursor = 0
        self.ps_detected = ''
        self.screen = Screen.PROVIDER_SELECT

    def _key_provider_select(self, msg):
        if not isinstance(msg, tea.KeyMsg):
            return self, None
        n = len(self.ps_options)
        key = msg.key
        if key == 'escape':
            self.screen = Screen.FOLDER_BROWSER
            self.fb_dir = self.cf_folder
            self._fb_refresh()
        elif key in ('down', 'j'):
            self.ps_cursor = (self.ps_cursor + 1) % n
        elif key in ('up', 'k'):
            self.ps_cursor = (self.ps_cursor - 1) % n
        elif key == 'enter':
            chosen = self.ps_options[self.ps_cursor]
            if chosen == 'auto':
                from parser_factory import detect_source
                chosen = detect_source(self.cf_folder)
            self.cf_provider = chosen
            self.cf_conv_count = None
            self.cf_scanning = True
            self.screen = Screen.CONFIRM
            _cmd_scan(self.cf_folder, self.cf_provider, self._program)
        return self, None
    def _key_confirm(self, msg):
        if isinstance(msg, _ConvCountMsg):
            self.cf_conv_count = msg.count
            self.cf_scanning = False
            return self, None
        if not isinstance(msg, tea.KeyMsg):
            return self, None
        key = msg.key
        if key == 'escape':
            self.screen = Screen.PROVIDER_SELECT
        elif key in ('enter', 'r') and not self.cf_scanning:
            self.run_total   = self.cf_conv_count or 0
            self.run_written = 0
            self.run_skipped = 0
            self.run_done    = False
            self.run_error   = ''
            self.screen = Screen.RUN
            _cmd_run(self.cf_folder, self.cf_provider, self.st_values, self._program)
        return self, None
    def _key_run(self, msg):
        if isinstance(msg, _ProgressMsg):
            self.run_written = msg.written
            self.run_skipped = msg.skipped
            self.run_total   = msg.total
            return self, None
        if isinstance(msg, _DoneMsg):
            self.run_written = msg.written
            self.run_skipped = msg.skipped
            self.run_done    = True
            return self, None
        if isinstance(msg, _RunErrorMsg):
            self.run_error = msg.error
            self.run_done  = True
            return self, None
        if isinstance(msg, tea.KeyMsg):
            if self.run_done:
                if msg.key in ('enter', 'q'):
                    self.screen = Screen.MAIN
                elif msg.key == 'n':
                    self._start_new_import()
        return self, None
    def _key_settings(self, msg):
        if not isinstance(msg, tea.KeyMsg):
            return self, None
        key = msg.key
        n_fields = len(self.st_fields)  # 3 text fields

        if key == 'escape':
            self.screen = Screen.MAIN
        elif key == 'tab':
            self.st_cursor = (self.st_cursor + 1) % (n_fields + 1)
        elif key == 'shift+tab':
            self.st_cursor = (self.st_cursor - 1) % (n_fields + 1)
        elif key == 'enter' and self.st_cursor == n_fields:
            # Save button
            try:
                _save_settings(self.st_values)
                self.st_status = 'ok:Settings saved'
            except Exception as e:
                self.st_status = f'error:{e}'
        elif self.st_cursor < n_fields:
            field_key = self.st_fields[self.st_cursor]
            if field_key in self.st_toggle_fields:
                if key in ('enter', ' '):
                    current = self.st_values.get(field_key, 'all')
                    self.st_values[field_key] = 'main' if current == 'all' else 'all'
            else:
                current = self.st_values.get(field_key, '')
                if key == 'backspace':
                    self.st_values[field_key] = current[:-1]
                elif key == 'ctrl+u':
                    self.st_values[field_key] = ''
                elif len(key) == 1:
                    self.st_values[field_key] = current + key
            self.st_status = ''
        return self, None
    def _key_review(self, msg):
        if not isinstance(msg, tea.KeyMsg):
            return self, None
        key = msg.key

        if self.rv_editing:
            edit_fields = ['tags_draft', 'project', 'category', 'syntax_draft']
            n = len(edit_fields)
            if key == 'escape':
                self.rv_editing = False
                self.rv_status = ''
            elif key == 'ctrl+s':
                self._save_edit()
            elif key == 'tab':
                self.rv_edit_field = (self.rv_edit_field + 1) % (n + 1)
                self.rv_autocomplete = []
            elif key == 'shift+tab':
                self.rv_edit_field = (self.rv_edit_field - 1) % (n + 1)
                self.rv_autocomplete = []
            elif key == 'enter' and self.rv_edit_field == n:
                self._save_edit()
            elif self.rv_edit_field < n:
                fk = edit_fields[self.rv_edit_field]
                current = self.rv_edit_values.get(fk, '')
                if key == 'backspace':
                    self.rv_edit_values[fk] = current[:-1]
                elif key == 'ctrl+u':
                    self.rv_edit_values[fk] = ''
                elif len(key) == 1:
                    self.rv_edit_values[fk] = current + key
                # Update autocomplete for tags field
                if fk == 'tags_draft':
                    partial = self.rv_edit_values[fk].rsplit(',', 1)[-1].strip()
                    if partial:
                        self.rv_autocomplete = [
                            t for t in self.rv_all_tags
                            if t.lower().startswith(partial.lower())
                        ][:5]
                    else:
                        self.rv_autocomplete = []
            return self, None

        if key == 'escape':
            self.screen = Screen.MAIN
        elif key in ('down', 'j') and self.rv_rows:
            self.rv_cursor = min(self.rv_cursor + 1, len(self.rv_rows) - 1)
        elif key in ('up', 'k') and self.rv_rows:
            self.rv_cursor = max(self.rv_cursor - 1, 0)
        elif key == 'enter' and self.rv_rows:
            self._open_editor()
        return self, None

    def _view_main(self) -> str:
        lines = [self._header(), '']
        for i, item in enumerate(self.menu_items):
            if i == self.menu_cursor:
                lines.append(sel_style.render(f'  ▶  {item}'))
            else:
                lines.append(muted_style.render(f'     {item}'))
        lines += ['', self._footer('↑↓ move   enter select   q quit')]
        return self._panel('\n'.join(lines))
    def _view_folder_browser(self) -> str:
        lines = [self._header('Select Folder'), '']

        if self.fb_text_mode:
            lines.append(muted_style.render('Type or paste a path:'))
            lines.append(f'  {self.fb_text_input}█')
            if self.fb_status:
                prefix, _, rest = self.fb_status.partition(':')
                s = error_style.render(rest) if prefix == 'error' else success_style.render(rest)
                lines.append(s)
            lines += ['', self._footer('enter confirm   esc browse mode   ctrl+v paste')]
            return self._panel('\n'.join(lines))

        # Current path
        w = min(self.width - 4, 72)
        path_str = str(self.fb_dir)
        path_max = w - 8
        if len(path_str) > path_max:
            path_str = '…' + path_str[-(path_max - 1):]
        lines.append(muted_style.render(path_str))
        lines.append('')

        if (self.fb_dir / 'conversations.json').exists():
            lines.append(success_style.render('  ✓ Export folder detected — press enter or space to import'))
            lines.append('')

        visible = max(4, self.height - 12)
        start = max(0, min(self.fb_cursor - visible // 2,
                           len(self.fb_entries) - visible))
        start = max(0, start)
        shown = self.fb_entries[start:start + visible]

        w = min(self.width - 4, 72)
        inner_w = w - 6   # panel border (2) + padding (2*2)
        max_label = max(10, inner_w - 5)  # 5 = len('  ▶  ')

        if not shown and not (self.fb_dir / 'conversations.json').exists():
            lines.append(muted_style.render('  (empty directory)'))
        for i, entry in enumerate(shown):
            idx = start + i
            label = entry.name + ('/' if entry.is_dir() else '')
            if len(label) > max_label:
                label = label[:max_label - 1] + '…'
            if idx == self.fb_cursor:
                lines.append(sel_style.render(f'  ▶  {label}'))
            else:
                row_style = lipgloss.Style().foreground(C_TEXT) if entry.is_dir() else muted_style
                lines.append(row_style.render(f'     {label}'))

        lines += ['', self._footer('↑↓ navigate   enter open / select   backspace up   / type path   esc back')]
        return self._panel('\n'.join(lines))
    def _view_provider_select(self) -> str:
        lines = [self._header('Select Provider'), '']
        lines.append(muted_style.render(f'Folder:  {self.cf_folder}'))
        lines.append('')
        for i, opt in enumerate(self.ps_options):
            if i == self.ps_cursor:
                lines.append(sel_style.render(f'  ▶  {opt}'))
            else:
                lines.append(muted_style.render(f'     {opt}'))
        lines += ['', self._footer('↑↓ move   enter confirm   esc back')]
        return self._panel('\n'.join(lines))
    def _view_confirm(self) -> str:
        lines = [self._header('Confirm'), '']
        lines.append(f'  Folder:    {self.cf_folder}')
        lines.append(f'  Provider:  {self.cf_provider}')
        lines.append(f'  Output:    {self.st_values.get("output_dir", "./output")}')
        lines.append('')
        if self.cf_scanning:
            lines.append(muted_style.render('  Scanning conversations...'))
        else:
            count = self.cf_conv_count or 0
            lines.append(success_style.render(f'  {count} conversation(s) found'))
        lines += ['', self._footer('enter / r  run   esc back')]
        return self._panel('\n'.join(lines))
    def _view_run(self) -> str:
        lines = [self._header('Running'), '']
        if self.run_error:
            lines.append(error_style.render(f'Error: {self.run_error}'))
            lines += ['', self._footer('enter / q  return to main')]
        elif self.run_done:
            lines.append(success_style.render(
                f'Done!  Written: {self.run_written}  Skipped: {self.run_skipped}'
            ))
            lines += ['', self._footer('enter / q  return to main   n new import')]
        else:
            total_str = f'/{self.run_total}' if self.run_total else ''
            lines.append(f'  Written:  {self.run_written}{total_str}')
            lines.append(f'  Skipped:  {self.run_skipped}')
            lines.append('')
            lines.append(muted_style.render('  Converting…'))
        return self._panel('\n'.join(lines))
    def _view_settings(self) -> str:
        lines = [self._header('Settings'), '']
        n_fields = len(self.st_fields)

        for i, fk in enumerate(self.st_fields):
            label = self.st_labels[fk]
            value = self.st_values.get(fk, '')
            focused = (i == self.st_cursor)
            label_s = sel_style.render(label) if focused else muted_style.render(label)
            if fk in self.st_toggle_fields:
                val_display = sel_style.render(f'[ {value} ]') if focused else muted_style.render(f'  {value}  ')
            else:
                val_display = f'{value}\u2588' if focused else value or muted_style.render('(default)')
            lines.append(f'  {label_s}')
            lines.append(f'  {val_display}')
            lines.append('')

        # Save button
        btn_focused = (self.st_cursor == n_fields)
        btn = sel_style.render('[ Save to ~/.keromdizer.toml ]') if btn_focused else muted_style.render('[ Save to ~/.keromdizer.toml ]')
        lines.append(f'  {btn}')

        if self.st_status:
            prefix, _, rest = self.st_status.partition(':')
            s = success_style.render(rest) if prefix == 'ok' else error_style.render(rest)
            lines += ['', f'  {s}']

        lines += ['', self._footer('tab next field   shift+tab prev   esc back')]
        return self._panel('\n'.join(lines))
    def _view_review_editor(self) -> str:
        row = self.rv_rows[self.rv_cursor]
        title = (row.get('title') or 'Untitled')[:40]
        lines = [self._header(f'Edit: {title}'), '']
        edit_fields = ['tags_draft', 'project', 'category', 'syntax_draft']
        labels = {
            'tags_draft':   'Tags (comma-separated)',
            'project':      'Project',
            'category':     'Category',
            'syntax_draft': 'Syntax (comma-separated)',
        }
        for i, fk in enumerate(edit_fields):
            focused = (i == self.rv_edit_field)
            label = labels[fk]
            value = self.rv_edit_values.get(fk, '')
            label_s = sel_style.render(label) if focused else muted_style.render(label)
            val_display = f'{value}\u2588' if focused else value or muted_style.render('(empty)')
            lines.append(f'  {label_s}')
            lines.append(f'  {val_display}')
            if focused and fk == 'tags_draft' and self.rv_autocomplete:
                lines.append(muted_style.render('  Suggestions: ' + '  '.join(self.rv_autocomplete)))
            lines.append('')

        # Read-only inferred fields
        lines.append(muted_style.render('  Inferred tags:   ' + ', '.join(row.get('inferred_tags') or [])))
        lines.append(muted_style.render('  Inferred syntax: ' + ', '.join(row.get('inferred_syntax') or [])))
        lines.append('')

        # Save button
        save_focused = (self.rv_edit_field == len(edit_fields))
        btn = sel_style.render('[ Save ]') if save_focused else muted_style.render('[ Save ]')
        lines.append(f'  {btn}')

        if self.rv_status:
            prefix, _, rest = self.rv_status.partition(':')
            s = success_style.render(rest) if prefix == 'ok' else error_style.render(rest)
            lines += ['', f'  {s}']

        lines += ['', self._footer('tab next field   ctrl+s save   esc back')]
        return self._panel('\n'.join(lines))

    def _view_review(self) -> str:
        if self.rv_editing and self.rv_rows:
            return self._view_review_editor()

        lines = [self._header('Review & Tag'), '']

        if not self.rv_rows:
            lines.append(muted_style.render('  No conversations in database.'))
            lines.append(muted_style.render('  Run an import first.'))
            lines += ['', self._footer('esc back')]
            return self._panel('\n'.join(lines))

        w = min(self.width - 4, 80)
        meta_w = 14
        title_w = max(20, w - 26 - meta_w)  # 26 = indent(2)+date(12)+provider(10)+spacing(2)

        # Column headers
        header = f'  {"Date":<12}{"Provider":<10}{"Title":<{title_w}}  {"Tags":<{meta_w}}'
        lines.append(muted_style.render(header))
        lines.append(muted_style.render('  ' + '─' * (w - 4)))

        visible = max(4, self.height - 10)
        start = max(0, min(self.rv_cursor - visible // 2, len(self.rv_rows) - visible))
        start = max(0, start)
        shown = self.rv_rows[start:start + visible]

        reviewed_style = lipgloss.Style().foreground(C_GREEN)
        for i, row in enumerate(shown):
            idx = start + i
            date_str = (row.get('conv_create_time') or '')[:10]
            provider = (row.get('provider') or '')[:8]
            title = (row.get('title') or 'Untitled')
            if len(title) > title_w - 1:
                title = title[:title_w - 2] + '…'
            tags = row.get('tags') or []
            project = row.get('project') or ''
            category = row.get('category') or ''
            is_reviewed = bool(tags or project or category)
            if tags:
                tag_summary = ', '.join(tags)
            elif project:
                tag_summary = f'[{project}]'
            else:
                tag_summary = ''
            if len(tag_summary) > meta_w:
                tag_summary = tag_summary[:meta_w - 1] + '…'
            cell = f'  {date_str:<12}{provider:<10}{title:<{title_w}}  {tag_summary:<{meta_w}}'
            if idx == self.rv_cursor:
                lines.append(sel_style.render(cell))
            elif is_reviewed:
                lines.append(reviewed_style.render(cell))
            else:
                lines.append(lipgloss.Style().foreground(C_TEXT).render(cell))

        lines += ['', self._footer('↑↓ navigate   enter edit tags   esc back')]
        return self._panel('\n'.join(lines))

    def _start_new_import(self) -> None:
        """Navigate to FOLDER_BROWSER, landing at the parent of the last selected
        folder so the user can easily pick a different export directory."""
        if self.cf_folder != Path('.'):
            self.fb_dir = self.cf_folder.parent
        self.screen = Screen.FOLDER_BROWSER
        self._fb_refresh()

    def _fb_refresh(self) -> None:
        """Populate fb_entries from fb_dir — directories only.

        Files are never shown; the app handles JSON selection internally.
        """
        try:
            entries = sorted(self.fb_dir.iterdir(), key=lambda p: p.name.lower())
            self.fb_entries = [e for e in entries if e.is_dir() and not e.name.startswith('.')]
        except PermissionError:
            self.fb_entries = []
        self.fb_cursor = 0
        self.fb_status = ''

    def _open_editor(self) -> None:
        if not self.rv_rows:
            return
        row = self.rv_rows[self.rv_cursor]
        self.rv_edit_field = 0
        self.rv_edit_values = {
            'tags_draft':   ', '.join(row.get('tags') or []),
            'project':      row.get('project') or '',
            'category':     row.get('category') or '',
            'syntax_draft': ', '.join(row.get('syntax') or []),
        }
        self.rv_all_tags = self._db.get_all_tags()
        self.rv_autocomplete = []
        self.rv_editing = True
        self.rv_status = ''

    def _save_edit(self) -> None:
        if not self.rv_rows:
            return
        row = self.rv_rows[self.rv_cursor]
        tags = [t.strip() for t in self.rv_edit_values.get('tags_draft', '').split(',') if t.strip()]
        project = self.rv_edit_values.get('project', '').strip() or None
        category = self.rv_edit_values.get('category', '').strip() or None
        syntax = [s.strip() for s in self.rv_edit_values.get('syntax_draft', '').split(',') if s.strip()]
        self._db.update_branch_tags(row['branch_id'], tags, project, category, syntax)
        # Update in-memory row immediately
        row['tags'] = tags
        row['project'] = project
        row['category'] = category
        row['syntax'] = syntax
        self.rv_all_tags = self._db.get_all_tags()
        self.rv_status = 'ok:Saved'

    def _load_review_data(self) -> None:
        """Load/refresh branches from DB into REVIEW state."""
        self.rv_rows = self._db.list_branches()
        self.rv_cursor = max(0, min(self.rv_cursor, len(self.rv_rows) - 1)) if self.rv_rows else 0


# ── Background commands ────────────────────────────────────────────────────────
def _cmd_scan(folder: Path, provider: str, program: Optional['tea.Program']) -> None:
    """Start background thread to parse conversations and send _ConvCountMsg.

    Uses daemon thread + program.send() pattern for background work.
    Not a tea.Cmd — spawns thread directly as a side effect.
    """
    def _run():
        try:
            from parser_factory import build_parser
            parser, _ = build_parser(folder, source=provider)
            convs = parser.parse()
            if program:
                program.send(_ConvCountMsg(count=len(convs)))
        except Exception:
            if program:
                program.send(_ConvCountMsg(count=0))
    threading.Thread(target=_run, daemon=True).start()


def _to_iso(ts):
    from datetime import datetime, timezone
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _cmd_run(folder: Path, provider: str, st_values: dict, program: Optional['tea.Program']) -> None:
    """Run conversion pipeline in background daemon thread.

    Uses daemon thread + program.send() pattern (same as _cmd_scan).
    Not a tea.Cmd — spawns thread directly as a side effect.
    """
    def _worker():
        from config import load_db_path
        from db import DatabaseManager
        db = DatabaseManager(load_db_path())
        try:
            from parser_factory import build_parser
            from renderer import MarkdownRenderer
            from file_manager import FileManager
            from config import load_persona, load_branch_config
            from content_parser import parse_content
            from inference import infer_tags, infer_syntax, build_full_text

            output_dir = Path(st_values.get('output_dir', './output'))
            parser, prov = build_parser(folder, source=provider)
            conversations = parser.parse()
            total = len(conversations)

            branch_cfg = load_branch_config()
            persona = load_persona(
                provider=prov,
                user_name=st_values.get('user_name') or None,
                assistant_name=st_values.get(f'{prov}_assistant') or None,
            )
            renderer = MarkdownRenderer(persona)
            file_mgr = FileManager(output_dir)

            written = 0
            skipped = 0

            for conv in conversations:
                update_time_iso = _to_iso(conv.update_time)
                if not db.needs_update(conv.id, update_time_iso or ''):
                    skipped += 1
                    if program:
                        program.send(_ProgressMsg(written=written, skipped=skipped, total=total))
                    continue

                # Filter branches by import config
                branches_to_import = (
                    [b for b in conv.branches if b.branch_index == 1]
                    if branch_cfg.import_branches == 'main'
                    else conv.branches
                )

                db_branches = []
                for branch in branches_to_import:
                    # Resolve image refs (ChatGPT only; DeepSeek has none)
                    for msg in branch.messages:
                        resolved = {}
                        for file_id in msg.image_refs:
                            actual = file_mgr.copy_asset(folder, file_id)
                            if actual:
                                resolved[file_id] = actual
                        for old_id, new_name in resolved.items():
                            msg.text = msg.text.replace(
                                f'assets/{old_id})', f'assets/{new_name})'
                            )

                    # Parse structured content and run inference
                    all_segments = []
                    msg_records = []
                    for msg in branch.messages:
                        segments = parse_content(msg.text)
                        all_segments.extend(segments)
                        msg_records.append({
                            'role': msg.role,
                            'timestamp': _to_iso(msg.create_time),
                            'content': [
                                {
                                    'type': s.type,
                                    'text': s.text,
                                    **(({'language': s.language}) if s.language else {}),
                                }
                                for s in segments
                            ],
                        })

                    full_text = build_full_text(all_segments)
                    i_tags = infer_tags(full_text)
                    i_syntax = infer_syntax(all_segments)

                    db_branches.append({
                        'branch_id': f'{conv.id}__branch_{branch.branch_index}',
                        'branch_index': branch.branch_index,
                        'is_main_branch': branch.branch_index == 1,
                        'messages': msg_records,
                        'inferred_tags': i_tags,
                        'inferred_syntax': i_syntax,
                    })

                    # Write markdown (filtered by export_markdown config)
                    if branch_cfg.export_markdown == 'main' and branch.branch_index != 1:
                        continue
                    content = renderer.render(conv, branch)
                    filename = file_mgr.make_filename(conv, branch)
                    file_mgr.write(filename, content)
                    written += 1

                if db_branches:
                    db.upsert_conversation(
                        conversation_id=conv.id,
                        provider=prov,
                        title=conv.title,
                        create_time=_to_iso(conv.create_time),
                        update_time=update_time_iso,
                        model_slug=conv.model_slug,
                        branch_count=len(conv.branches),
                        branches=db_branches,
                    )

                if program:
                    program.send(_ProgressMsg(written=written, skipped=skipped, total=total))

            if program:
                program.send(_DoneMsg(written=written, skipped=skipped))

        except Exception as e:
            if program:
                program.send(_RunErrorMsg(error=str(e)))
        finally:
            db.close()

    threading.Thread(target=_worker, daemon=True).start()


# ── Entry point ────────────────────────────────────────────────────────────────
def main() -> None:
    model = AppModel()
    p = tea.Program(model, alt_screen=True, mouse_cell_motion=False)
    model._program = p
    try:
        p.run()
    except (tea.ErrInterrupted, tea.ErrProgramKilled):
        pass
    finally:
        model._db.close()


if __name__ == '__main__':
    main()
