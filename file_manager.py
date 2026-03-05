import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from models import Conversation, Branch


class FileManager:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.assets_dir = self.output_dir / 'assets'
        self.manifest_path = self.output_dir / 'manifest.json'
        self._manifest: dict = self._load_manifest()
        self._used_filenames: set[str] = {
            f for entry in self._manifest.values() for f in entry.get('files', [])
        }

    def _load_manifest(self) -> dict:
        if self.manifest_path.exists():
            with open(self.manifest_path, encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_manifest(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            json.dump(self._manifest, f, indent=2)

    def needs_update(self, conversation: Conversation) -> bool:
        entry = self._manifest.get(conversation.id)
        if not entry:
            return True
        return (conversation.update_time or 0) > entry.get('update_time', 0)

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

    def write(self, filename: str, content: str, conversation: Conversation):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding='utf-8')

        entry = self._manifest.setdefault(conversation.id, {'update_time': 0, 'files': []})
        entry['update_time'] = conversation.update_time or 0
        if filename not in entry['files']:
            entry['files'].append(filename)

    def copy_asset(self, export_folder: Path, file_id: str) -> str | None:
        """Find file by prefix in export_folder, copy to assets/, return actual filename."""
        matches = list(Path(export_folder).glob(f'{file_id}*'))
        if not matches:
            return None
        src = matches[0]
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        dst = self.assets_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        return src.name

    def _format_date(self, timestamp: float | None) -> str:
        if timestamp is None:
            return 'unknown'
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d')
