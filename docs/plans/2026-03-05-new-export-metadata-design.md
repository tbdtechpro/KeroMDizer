# Design: New Export Metadata Support

Date: 2026-03-05
Status: Approved

## Summary

Three improvements based on analysis of the March 2026 ChatGPT export format:
1. Resolve DALL-E images from `dalle-generations/` (fixes 156 previously-broken image refs)
2. Add `Shared: Yes` metadata row for publicly-shared conversations
3. Add `Audio: N recordings` metadata row for voice conversations

## 1. DALL-E Image Resolution

**Problem:** DALL-E image asset pointers use `file-service://file-XXX` URIs. The parser strips `sediment://` but not `file-service://`, so these images are never found. The March 2026 export now includes these files in `dalle-generations/`.

**Changes:**
- `conversation_parser.py` — `_parts_to_text` and `_extract_image_refs`: strip `file-service://` in addition to `sediment://`
- `file_manager.py` — `copy_asset`: if not found in export root, also glob in `export_folder/dalle-generations/`

**Result:** DALL-E images resolve and are copied to `assets/`, embedded as `![image](assets/file-XXX-uuid.webp)`.

## 2. Shared Conversation Flag

**Problem:** `shared_conversations.json` identifies conversations shared publicly, but this isn't surfaced in markdown output.

**Changes:**
- `models.py` — add `is_shared: bool = False` to `Conversation`
- `conversation_parser.py` — `parse()` loads `shared_conversations.json` if present (graceful skip if absent), builds a `set[str]` of shared conversation IDs, sets `conv.is_shared` after parsing each conversation
- `renderer.py` — appends `| Shared | Yes |` metadata row when `conversation.is_shared`

## 3. Voice Audio Note

**Problem:** Some conversations have `.wav` recordings in `<export_folder>/<conversation_id>/audio/` but nothing in the markdown acknowledges them.

**Changes:**
- `models.py` — add `audio_count: int = 0` to `Conversation`
- `conversation_parser.py` — `_parse_conversation` checks if `self.export_folder / conv_id / 'audio'` exists, counts `.wav` files, sets `audio_count`
- `renderer.py` — appends `| Audio | N recordings |` metadata row when `audio_count > 0`

## Architecture Notes

- No new classes or files needed
- `Conversation` datamodel grows by 2 optional fields (`is_shared`, `audio_count`)
- All three features degrade gracefully when the relevant data is absent (old export format)
- Tests need fixtures updated + new test cases for each feature

## Out of Scope

- `message_feedback.json` — rating is per-conversation not per-message, only 7 entries, low value
- `atlas_mode_enabled` — always false
- `gizmo_id` — opaque ID, no human-readable name available in export
