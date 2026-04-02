# Design: Obsidian Export Format + Contraction Tag Filter Fix

**Date:** 2026-03-31
**Status:** Approved

---

## Overview

Two independent changes:

1. **Contraction tag filter** — fix a defect in YAKE keyword extraction where contraction
   artifacts (`n't`, `r'e`, `'ve`, `'ll`, `'s`, `'d`) appear as inferred tags.
2. **Obsidian export** — add an Obsidian-optimized `.md` export format as a parallel output
   alongside the existing GFM files, enabled via TOML config.

---

## 1. Contraction Tag Filter Fix

### Problem

YAKE tokenizes contractions by splitting on apostrophes, leaving fragments like `n't`
(from "don't", "isn't") and `r'e` (from "they're") as scored keyword candidates.
These appear in `inferred_tags` in the DB and pollute JSONL exports.

### Fix

**File:** `inference.py`, `infer_tags()` — one-line post-filter:

```python
# Before
return [kw for kw, _score in results]

# After
return [kw for kw, _score in results if "'" not in kw]
```

Tokens containing an apostrophe are always contraction artifacts. Short tokens without
apostrophes (`AI`, `UX`, `CI`, `API`) are preserved.

Edge case: possessive forms like `Python's` are also filtered. This is desirable —
`Python` is a better keyword and YAKE typically extracts the root form anyway.

### Tests

Add to `tests/test_inference.py`:
- Assert `n't`, `r'e`, `'ve`, `'ll`, `'s` do not appear in output
- Assert `AI`, `UX`, `CI` (short, no apostrophe) are not filtered

---

## 2. Obsidian Export Format

### Goals

- Produce Obsidian-optimized `.md` files as a parallel output alongside GFM files
- Rich YAML frontmatter using all available metadata from the DB
- Obsidian-native syntax: wikilink image embeds, callout blocks for message turns
- Enabled/disabled independently from other export formats

### Architecture

**New file:** `obsidian_renderer.py`

```python
class ObsidianRenderer:
    def render(self, branch_row: dict) -> str: ...
```

Takes the dict shape returned by `db.list_branches()` / `db.get_branch()`. No dependency
on GFM-rendered markdown or `Conversation`/`Branch` model objects — works directly from
DB data, which carries all needed fields.

### YAML Frontmatter

All fields mapped from DB branch row. Optional fields omitted when null/empty:

```yaml
---
title: "Conversation Title: With Colon"   # quoted when containing : or special chars
aliases:
  - Conversation Title With Colon          # unquoted; used by Obsidian for link suggestions
created: 2026-01-14                        # date part of conv_create_time only
provider: chatgpt                          # always present
model: gpt-4o                              # omitted if null
conversation_id: abc-def-123              # always present
branch: 2                                  # omitted when branch_count == 1
branch_count: 3                            # omitted when == 1
tags:                                      # omitted when empty
  - python
  - api-design
  - my-custom-tag
project: my-project                        # omitted if null
category: work                             # omitted if null
syntax:                                    # omitted when empty
  - python
  - bash
---
```

**Tag sources:** `inferred_tags` first, then user-applied `tags` — merged, deduplicated,
preserving order of first appearance.

**Tag sanitization** (to meet Obsidian's valid-character constraint):
1. Lowercase
2. Replace spaces with `-`
3. Strip any char that is not alphanumeric, `-`, `_`, or `/`
4. Drop empty results after stripping
5. Deduplicate

### Body Format

`# Title` heading, followed by each message as an Obsidian callout. No `---` horizontal
rules between turns — callout blocks are visually self-contained.

**Callout types:**
- User turn: `> [!question]` — yellow, question-mark icon
- Assistant turn: `> [!abstract]` — green, clipboard icon

**Persona labels** come from `user_alias` / `assistant_alias` stored in the DB
(captured at import time from the active persona config).

**Example:**

```markdown
# Conversation Title

> [!question] 👤 Matt
>
> User message line 1
>
> ```python
> def foo():
>     pass
> ```

> [!abstract] 🤖 ChatGPT
>
> Response text here...
```

### Callout Body Building

Message content is reconstructed from the structured `content` segments stored in the
DB (type `prose` or `code`). For each message:

1. Reconstruct full text from segments (code segments preserve their fences)
2. Apply image conversion: `![anything](assets/filename.ext)` → `![[filename.ext]]`
3. Prefix every non-empty line with `> `; every blank/empty line with `>` (no trailing space)
4. Prepend callout header line and a blank `>` separator line

Code blocks render correctly inside Obsidian callouts — the `>` prefix on fence lines
(` ``` `) is fully supported by Obsidian's renderer.

### Image Conversion

Regex applied to message text before callout wrapping:

```
![anything](assets/filename.ext)  →  ![[filename.ext]]
```

Pattern: `r'!\[.*?\]\(assets/([^)]+)\)'` → `![[\\1]]`

Only the filename is used in the wikilink — Obsidian resolves `![[filename.ext]]` by
filename anywhere in the vault, so no path prefix is needed.

### Config & Wiring

**`models.py`** — add to `ExportConfig`:
```python
obsidian_enabled: bool = False
obsidian_dir: str = ''
```

**`config.py`** — `load_export_config()` reads:
```python
obsidian_enabled=e.get('obsidian', 'no') == 'yes',
obsidian_dir=e.get('obsidian_dir', ''),
```

**TOML (`~/.keromdizer.toml`):**
```toml
[exports]
obsidian = "yes"
obsidian_dir = "~/vault/ChatGPT"   # optional; defaults to <output>/obsidian
```

**`keromdizer.py` post-sweep** — added alongside html/docx sweep block. Iterates
`db.list_branches()`, renders from DB data (not from the GFM `.md` file). Uses
`md_filename` to derive the output filename; branches without `md_filename` are skipped:

```python
if exp_cfg.obsidian_enabled:
    from obsidian_renderer import ObsidianRenderer
    obsidian_renderer = ObsidianRenderer()
    obsidian_dir = (
        Path(exp_cfg.obsidian_dir).expanduser()
        if exp_cfg.obsidian_dir
        else args.output / 'obsidian'
    )
    for row in db.list_branches():
        md_filename = row.get('md_filename') or ''
        if not md_filename:
            continue
        out = obsidian_dir / md_filename
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(obsidian_renderer.render(row), encoding='utf-8')
```

**`tui.py` SETTINGS screen** — add `obsidian` toggle (cycles `no` ↔ `yes`) and
`obsidian_dir` text field, following the same pattern as the existing `html_github`,
`html_retro`, and `docx` fields.

### Tests

**`tests/test_obsidian_renderer.py`** — new file:
- Frontmatter: title quoting (with/without special chars), `aliases`, `created` date
  formatting, `model`/`branch`/`branch_count` omitted when null/single-branch
- Tags: inferred + user-applied merged, sanitized, deduplicated; omitted when empty
- `project`/`category`/`syntax` present when set, absent when null/empty
- Callout wrapping: user → `[!question]`, assistant → `[!abstract]`; persona labels
  from `user_alias`/`assistant_alias`
- Blank lines: empty lines in body become `>` not `> `
- Code blocks inside callouts: fence lines correctly prefixed with `> `
- Image conversion: `![](assets/file_abc.jpg)` → `![[file_abc.jpg]]`
- Graceful handling of missing optional fields (null model, no tags, single branch)

---

## Files Changed

| File | Change |
|---|---|
| `inference.py` | Filter apostrophe-containing tokens in `infer_tags()` |
| `obsidian_renderer.py` | New — `ObsidianRenderer` class |
| `models.py` | Add `obsidian_enabled`, `obsidian_dir` to `ExportConfig` |
| `config.py` | Read obsidian fields in `load_export_config()` |
| `keromdizer.py` | Add obsidian post-sweep block |
| `tui.py` | Add obsidian toggle + dir field to SETTINGS screen |
| `tests/test_inference.py` | Add apostrophe filter test cases |
| `tests/test_obsidian_renderer.py` | New — full renderer test suite |
