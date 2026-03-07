from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    role: str  # 'user' or 'assistant'
    text: str
    create_time: Optional[float] = None
    image_refs: list[str] = field(default_factory=list)


@dataclass
class Branch:
    messages: list[Message]
    branch_index: int  # 1 = main thread (current_node path), 2+ = alternates


@dataclass
class Conversation:
    id: str
    title: str
    create_time: Optional[float]
    update_time: Optional[float]
    model_slug: Optional[str]
    branches: list[Branch]
    is_shared: bool = False
    audio_count: int = 0


@dataclass
class PersonaConfig:
    user_name: str = 'User'
    assistant_name: str = 'Assistant'


@dataclass
class BranchConfig:
    import_branches: str = 'all'   # 'main' | 'all'
    export_markdown: str = 'all'   # 'main' | 'all'
    export_jsonl: str = 'all'      # 'main' | 'all'
