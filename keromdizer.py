import argparse
import sys
from pathlib import Path

from conversation_parser import ConversationParser
from renderer import MarkdownRenderer
from file_manager import FileManager


def main():
    arg_parser = argparse.ArgumentParser(
        description='Convert a ChatGPT data export folder to GFM markdown files.'
    )
    arg_parser.add_argument(
        'export_folder',
        type=Path,
        help='Path to the ChatGPT export directory (must contain conversations.json)',
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
    args = arg_parser.parse_args()

    if not args.export_folder.is_dir():
        print(f'Error: {args.export_folder} is not a directory', file=sys.stderr)
        sys.exit(1)

    conv_parser = ConversationParser(args.export_folder)
    try:
        conversations = conv_parser.parse()
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    renderer = MarkdownRenderer()
    file_mgr = FileManager(args.output)

    written = 0
    skipped = 0

    for conv in conversations:
        if not file_mgr.needs_update(conv):
            skipped += 1
            continue

        for branch in conv.branches:
            # Resolve image references to actual filenames
            for msg in branch.messages:
                resolved = {}
                for file_id in msg.image_refs:
                    actual_name = file_mgr.copy_asset(args.export_folder, file_id)
                    if actual_name:
                        resolved[file_id] = actual_name
                    else:
                        print(f'Warning: image not found in export: {file_id}')
                for old_id, new_name in resolved.items():
                    msg.text = msg.text.replace(
                        f'assets/{old_id})', f'assets/{new_name})'
                    )

            content = renderer.render(conv, branch)
            filename = file_mgr.make_filename(conv, branch)

            if args.dry_run:
                branch_label = f' (branch {branch.branch_index})' if len(conv.branches) > 1 else ''
                print(f'  Would write: {args.output / filename}{branch_label}')
            else:
                file_mgr.write(filename, content, conv)
                written += 1

    if not args.dry_run:
        file_mgr.save_manifest()
        print(f'Done. Written: {written} file(s), skipped {skipped} up-to-date conversation(s).')
    else:
        total_would_write = sum(len(c.branches) for c in conversations if file_mgr.needs_update(c))
        print(f'Dry run complete. Would write ~{total_would_write} file(s), skip {skipped} conversation(s).')


if __name__ == '__main__':
    main()
