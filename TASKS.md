# KeroMDizer — Task Backlog

> Start any feature task with `/brainstorming` before touching code.

---

## Completed

| Task | Description |
|---|---|
| Project bootstrap | requirements-dev.txt, test fixture, git init, .gitignore |
| Data models | `Message`, `Branch`, `Conversation` dataclasses |
| ConversationParser | Tree traversal, branch reconstruction, message extraction |
| MarkdownRenderer | GFM markdown generation with metadata table |
| FileManager | Filename sanitization, deduplication via manifest.json, asset copying |
| CLI entrypoint | `keromdizer.py` with argparse — export folder, --output, --dry-run |
| Integration | Verified against real export: 459 files, 391 conversations, deduplication confirmed |
| bootstrap.sh | Ubuntu 24.04 setup script — checks deps, creates venv, runs tests |
| CLAUDE.md | Project context for Claude Code sessions |
| .gitignore | Hardened to prevent personal data from being committed |

---

## Pending

### #17 — UAT (User Acceptance Testing)

Run structured user acceptance testing against real ChatGPT exports to validate output quality, edge cases, and usability.

**Test scenarios:**

- [ ] Large export (400+ conversations) — performance, no crashes
- [ ] Conversations with branches — verify `_branch-N.md` files are correct and complete
- [ ] Conversations with user-uploaded images — verify `assets/` copies and links resolve
- [ ] Conversations with DALL-E images — verify `file-service://` warnings appear but don't abort
- [ ] Conversations with null/empty titles — verify `Untitled` fallback
- [ ] Conversations with special characters in titles (`·`, `•`, curly quotes, emoji) — verify filename sanitization
- [ ] Multi-run deduplication — second run skips all; third run after export update re-exports changed conversations
- [ ] `--dry-run` accuracy — verify would-write count matches actual write count
- [ ] Markdown rendering quality — spot-check code blocks, tables, lists in Obsidian or VS Code
- [ ] Output portability — verify moving the `output/` folder doesn't break image links (they're relative)

**Acceptance criteria:** No data loss, no crashes, no PII in filenames, images resolve correctly, deduplication works across runs.

---

### #18 — Add DeepSeek Export Support

Extend KeroMDizer to parse and convert DeepSeek data exports alongside ChatGPT exports.

**Known export location:**
```
~/OneDrive/ChatGPT & DeepSeek Data Exports/deepseek_data-2025-11-24/conversations.json
```

**Pre-implementation research:**
- [ ] Inspect DeepSeek `conversations.json` schema vs ChatGPT schema (roles, content types, mapping structure, timestamps)
- [ ] Determine if DeepSeek uses the same tree/mapping structure or a flat list
- [ ] Identify DeepSeek-specific content types (reasoning/thinking blocks are common in DeepSeek R1)
- [ ] Check whether DeepSeek includes image/file assets in the export

**Architecture options:**
- Subclass `ConversationParser`, override `_parse_conversation` — schema likely similar but not identical
- Or: auto-detect export type in `ConversationParser.parse()` based on schema fingerprinting
- Keep `Conversation`/`Branch`/`Message` model unchanged — only the parser changes

**CLI consideration:** May need `--format` flag (`chatgpt|deepseek|auto`) or silent auto-detection based on export contents.

> Run `/brainstorming` before implementation.

---

### #19 — Add TUI Interface

Build an interactive terminal UI using the tbdtechpro Python TUI ecosystem.

**Python TUI repos (clone before implementation):**

```bash
git clone https://github.com/tbdtechpro/bubbletea  # Python port of BubbleTea framework
git clone https://github.com/tbdtechpro/lipgloss   # Python port of lipgloss (terminal styling)
git clone https://github.com/tbdtechpro/Pyubbles   # Python port of Bubbles (TUI components)
git clone https://github.com/tbdtechpro/Pyglow     # Python port of Glow (markdown renderer)
```

**Pre-implementation research:**
- [ ] Inspect each repo's API — assess maturity and available components
- [ ] Determine if `bubbletea` Python port implements the Model/Update/View pattern from the Go original
- [ ] Check if `Pyubbles` has a progress bar or file picker component
- [ ] Check if `Pyglow` can render markdown strings (for a conversation preview pane)

**Planned TUI features (confirm during brainstorming):**
- Export folder path input
- Output directory selection
- Live progress display during conversion (per-conversation)
- Summary screen: written / skipped / warning counts
- Option toggles: `--dry-run`, etc.
- Stretch: conversation browser with `Pyglow` markdown preview pane

**Architecture note:** `ConversationParser`, `MarkdownRenderer`, `FileManager` are pure classes not coupled to argparse — they can be instantiated directly from TUI code. However `msg.text` is mutated in-place during image resolution in `keromdizer.py`; TUI re-renders will require re-parsing (see `CLAUDE.md`).

> Run `/brainstorming` before implementation.

---

### #20 — Add JSONL Export for Machine/AI Interpretation

Generate a JSONL (JSON Lines) file to enable ML/AI consumption of converted conversations.

**Output format — each line is one conversation branch:**
```json
{
  "conversation_id": "abc-123",
  "title": "My Chat",
  "date": "2026-01-14",
  "model": "gpt-4o",
  "branch_index": 1,
  "total_branches": 2,
  "source_file": "2026-01-14_My_Chat.md",
  "messages": [
    {"role": "user", "text": "...", "image_refs": []},
    {"role": "assistant", "text": "...", "image_refs": []}
  ]
}
```

**Open design questions (resolve during brainstorming):**
- [ ] One JSONL per output run (all conversations) vs one JSONL per markdown file vs one per conversation?
- [ ] Full message text or truncated preview?
- [ ] `image_refs` as resolved asset paths or original file IDs?
- [ ] Include `system_prompt` field if present in the export?
- [ ] Opt-in via `--jsonl` flag or always generated alongside markdown?
- [ ] Include per-message token count estimate?

**Architecture:** New `JsonlExporter` class alongside `MarkdownRenderer` — same `(Conversation, Branch)` input, JSONL output. `FileManager` handles writing. Compatible with standard ML tooling (HuggingFace `datasets`, LangChain, etc.).

> Run `/brainstorming` before implementation.
