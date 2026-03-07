import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from models import Conversation, Branch


class FileManager:
    def __init__(self, output_dir: Path, used_filenames: set[str] | None = None):
        self.output_dir = Path(output_dir)
        self.assets_dir = self.output_dir / 'assets'
        self._used_filenames: set[str] = set(used_filenames) if used_filenames else set()

    def sanitize_filename(self, title: str) -> str:
        title = (title or '').strip() or 'Untitled'
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f·•\u2019\u2018]', '_', title)
        safe = re.sub(r'[\s_]+', '_', safe)
        safe = safe.strip('_')
        return safe[:80]

    def make_filename(self, conversation: Conversation, branch: Branch) -> str:
        date_str = self._format_date(conversation.create_time)
        safe_title = self.sanitize_filename(conversation.title)
        total = len(conversation.branches)

        if total > 1 and branch.branch_index > 1:
            base = f'{date_str}_{safe_title}_branch-{branch.branch_index}'
        else:
            base = f'{date_str}_{safe_title}'

        filename = f'{base}.md'

        if filename in self._used_filenames:
            short_id = conversation.id[:8]
            filename = f'{base}_{short_id}.md'

        self._used_filenames.add(filename)
        return filename

    def write(self, filename: str, content: str) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding='utf-8')

    def copy_asset(self, export_folder: Path, file_id: str) -> str | None:
        """Find file by prefix in export_folder or dalle-generations/, copy to assets/, return filename."""
        search_dirs = [
            Path(export_folder),
            Path(export_folder) / 'dalle-generations',
        ]
        for search_dir in search_dirs:
            matches = list(search_dir.glob(f'{file_id}*'))
            if matches:
                src = matches[0]
                self.assets_dir.mkdir(parents=True, exist_ok=True)
                dst = self.assets_dir / src.name
                if not dst.exists():
                    shutil.copy2(src, dst)
                return src.name
        return None

    def _format_date(self, timestamp: float | None) -> str:
        if timestamp is None:
            return 'unknown'
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d')
