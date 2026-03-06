from datetime import datetime, timezone
from models import Conversation, Branch, PersonaConfig


class MarkdownRenderer:
    def __init__(self, persona: PersonaConfig | None = None):
        self.persona = persona or PersonaConfig()

    def render(self, conversation: Conversation, branch: Branch) -> str:
        lines = []

        # Title
        lines += [f'# {conversation.title}', '']

        # Subheading: date [· model] [· Branch N of M]
        date_str = self._format_date(conversation.create_time)
        parts = [date_str]
        if conversation.model_slug:
            parts.append(conversation.model_slug)
        if len(conversation.branches) > 1:
            parts.append(f'Branch {branch.branch_index} of {len(conversation.branches)}')
        lines += [f'_{"  ·  ".join(parts)}_', '']

        # Messages
        for msg in branch.messages:
            lines.append('---')
            lines.append('')
            if msg.role == 'user':
                header = f'### 👤 {self.persona.user_name}'
            else:
                header = f'### 🤖 {self.persona.assistant_name}'
            lines += [header, '', msg.text, '']

        lines += ['---', '']

        return '\n'.join(lines)

    def _format_date(self, timestamp: float | None) -> str:
        if timestamp is None:
            return 'unknown'
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d')
