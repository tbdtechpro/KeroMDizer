import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import load_persona, load_branch_config, load_db_path
from parser_factory import build_parser
from renderer import MarkdownRenderer
from file_manager import FileManager
from db import DatabaseManager
from content_parser import parse_content
from inference import infer_tags, infer_syntax, build_full_text


def _to_iso(ts: float | str | None) -> str | None:
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def main():
    arg_parser = argparse.ArgumentParser(
        description='Convert a ChatGPT or DeepSeek export folder to GFM markdown files.'
    )
    arg_parser.add_argument(
        'export_folder',
        type=Path,
        help='Path to the export directory (must contain conversations.json)',
    )
    arg_parser.add_argument(
        '--output',
        type=Path,
        default=Path('./output'),
        help='Output directory for markdown files (default: ./output)',
    )
    arg_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be written without writing any files',
    )
    arg_parser.add_argument(
        '--user-name',
        default=None,
        help='Override user label in output (default: from ~/.keromdizer.toml or "User")',
    )
    arg_parser.add_argument(
        '--assistant-name',
        default=None,
        help='Override assistant label in output (default: from ~/.keromdizer.toml or provider name)',
    )
    arg_parser.add_argument(
        '--source',
        choices=['chatgpt', 'deepseek'],
        default=None,
        help='Export source (default: auto-detected from folder contents)',
    )
    arg_parser.add_argument(
        '--export-jsonl',
        type=Path,
        default=None,
        metavar='PATH',
        help='Also write a JSONL export to PATH after importing',
    )
    args = arg_parser.parse_args()

    if not args.export_folder.is_dir():
        print(f'Error: {args.export_folder} is not a directory', file=sys.stderr)
        sys.exit(1)

    branch_cfg = load_branch_config()
    db_path = load_db_path()
    db = DatabaseManager(db_path)

    conv_parser, provider = build_parser(args.export_folder, source=args.source)
    try:
        conversations = conv_parser.parse()
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    try:
        persona = load_persona(
            provider=provider,
            user_name=args.user_name,
            assistant_name=args.assistant_name,
        )
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    renderer = MarkdownRenderer(persona)
    file_mgr = FileManager(args.output)

    written = 0
    skipped = 0

    try:
        for conv in conversations:
            update_time_iso = _to_iso(conv.update_time)
            if not db.needs_update(conv.id, update_time_iso or ''):
                skipped += 1
                continue

            # Filter branches by import config
            branches_to_import = (
                [b for b in conv.branches if b.branch_index == 1]
                if branch_cfg.import_branches == 'main'
                else conv.branches
            )

            db_branches = []
            for branch in branches_to_import:
                # Resolve image refs in messages (mutates msg.text)
                for msg in branch.messages:
                    resolved = {}
                    for file_id in msg.image_refs:
                        actual_name = file_mgr.copy_asset(args.export_folder, file_id)
                        if actual_name:
                            resolved[file_id] = actual_name
                        else:
                            print(f'Warning: image not found in export: {file_id}', file=sys.stderr)
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
                if args.dry_run:
                    branch_label = (
                        f' (branch {branch.branch_index})' if len(conv.branches) > 1 else ''
                    )
                    print(f'  Would write: {args.output / filename}{branch_label}')
                else:
                    file_mgr.write(filename, content)
                    written += 1

            if not args.dry_run and db_branches:
                db.upsert_conversation(
                    conversation_id=conv.id,
                    provider=provider,
                    title=conv.title,
                    create_time=_to_iso(conv.create_time),
                    update_time=update_time_iso,
                    model_slug=conv.model_slug,
                    branch_count=len(conv.branches),
                    branches=db_branches,
                )

        if not args.dry_run:
            if args.export_jsonl:
                from jsonl_exporter import export_jsonl
                export_jsonl(db, args.export_jsonl, branch_mode=branch_cfg.export_jsonl)
                print(f'JSONL exported to {args.export_jsonl}')
            print(f'Done. Written: {written} file(s), skipped {skipped} up-to-date conversation(s).')
        else:
            total_would_write = sum(
                len([b for b in c.branches
                     if branch_cfg.export_markdown == 'all' or b.branch_index == 1])
                for c in conversations
                if db.needs_update(c.id, _to_iso(c.update_time) or '')
            )
            print(
                f'Dry run complete. Would write ~{total_would_write} file(s),'
                f' skip {skipped} conversation(s).'
            )
    finally:
        db.close()


if __name__ == '__main__':
    main()
