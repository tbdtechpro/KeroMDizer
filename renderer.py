from datetime import datetime, timezone
from models import Conversation, Branch


class MarkdownRenderer:
    def render(self, conversation: Conversation, branch: Branch) -> str:
        lines = []

        # Metadata table
        date_str = self._format_date(conversation.create_time)
        total_branches = len(conversation.branches)
        lines += [
            '| Field | Value |',
            '|---|---|',
            f'| Date | {date_str} |',
            f'| Model | {conversation.model_slug or "unknown"} |',
            f'| Conversation ID | {conversation.id} |',
        ]
        if total_branches > 1:
            lines.append(f'| Branch | {branch.branch_index} of {total_branches} |')
        if conversation.is_shared:
            lines.append('| Shared | Yes |')
        if conversation.audio_count > 0:
            lines.append(f'| Audio | {conversation.audio_count} recordings |')
        lines.append('')

        # Title
        lines += [f'# {conversation.title}', '']

        # Messages
        for msg in branch.messages:
            lines.append('---')
            lines.append('')
            header = '### 👤 User' if msg.role == 'user' else '### 🤖 Assistant'
            lines += [header, '', msg.text, '']

        lines += ['---', '']

        return '\n'.join(lines)

    def _format_date(self, timestamp: float | None) -> str:
        if timestamp is None:
            return 'unknown'
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d')
