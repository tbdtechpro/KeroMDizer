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
    return {
        'output_dir':     data.get('output', {}).get('dir', './output'),
        'user_name':      data.get('user', {}).get('name', ''),
        'assistant_name': '',
    }


def _save_settings(values: dict[str, str]) -> None:
    """Persist user_name to ~/.keromdizer.toml."""
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
    lines = []
    if 'user' in data:
        lines.append('[user]')
        lines.append(f'name = "{data["user"].get("name", "")}"')
    for section, contents in data.items():
        if section == 'user':
            continue
        if not isinstance(contents, dict):
            continue
        lines.append(f'\n[{section}]')
        for k, v in contents.items():
            lines.append(f'{k} = "{v}"')
    toml_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


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
        self.fb_scroll: int = 0
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

        # SETTINGS
        st_defaults = _load_settings()
        self.st_fields: list[str] = ['output_dir', 'user_name', 'assistant_name']
        self.st_labels: dict[str, str] = {
            'output_dir':     'Output directory',
            'user_name':      'User name',
            'assistant_name': 'Assistant name',
        }
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
                self._fb_refresh()
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
    def _key_provider_select(self, msg): return self, None
    def _key_confirm(self, msg):         return self, None
    def _key_run(self, msg):             return self, None
    def _key_settings(self, msg):        return self, None
    def _key_review(self, msg):          return self, None

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
        lines.append(muted_style.render(str(self.fb_dir)))
        lines.append('')

        visible = max(4, self.height - 12)
        start = max(0, min(self.fb_cursor - visible // 2,
                           len(self.fb_entries) - visible))
        start = max(0, start)
        shown = self.fb_entries[start:start + visible]

        if not shown:
            lines.append(muted_style.render('  (empty directory)'))
        for i, entry in enumerate(shown):
            idx = start + i
            label = entry.name + ('/' if entry.is_dir() else '')
            if idx == self.fb_cursor:
                lines.append(sel_style.render(f'  ▶  {label}'))
            else:
                row_style = lipgloss.Style().foreground(C_TEXT) if entry.is_dir() else muted_style
                lines.append(row_style.render(f'     {label}'))

        lines += ['', self._footer('↑↓ navigate   enter descend   backspace up   space select   / type path   esc back')]
        return self._panel('\n'.join(lines))
    def _view_provider_select(self): return self._panel('Provider Select')
    def _view_confirm(self):         return self._panel('Confirm')
    def _view_run(self):             return self._panel('Run')
    def _view_settings(self):        return self._panel('Settings')
    def _view_review(self):          return self._panel('Review')

    def _fb_refresh(self) -> None:
        """Populate fb_entries from fb_dir."""
        try:
            entries = sorted(self.fb_dir.iterdir(),
                             key=lambda p: (not p.is_dir(), p.name.lower()))
            self.fb_entries = [e for e in entries if not e.name.startswith('.')]
        except PermissionError:
            self.fb_entries = []
        self.fb_cursor = 0
        self.fb_scroll = 0
        self.fb_status = ''


# ── Entry point ────────────────────────────────────────────────────────────────
def main() -> None:
    model = AppModel()
    p = tea.Program(model, alt_screen=True, mouse_cell_motion=False)
    model._program = p
    try:
        p.run()
    except (tea.ErrInterrupted, tea.ErrProgramKilled):
        pass


if __name__ == '__main__':
    main()
