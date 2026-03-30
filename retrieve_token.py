#!/usr/bin/env python3
"""
retrieve_token.py — save ChatGPT Bearer token to ~/.keromdizer_token.json.

Three modes:

  1. Auto-extract from browser (default — requires browser_cookie3):
       python retrieve_token.py

  2. Paste token directly:
       python retrieve_token.py --paste "eyJ..."

  3. Read from stdin (pipe-friendly):
       xclip -o | python retrieve_token.py --stdin

How to get the token string (modes 2 / 3):
  - Open Chrome/Firefox DevTools (F12) → Console tab
  - Make sure you are logged in at chatgpt.com
  - Paste and run:
      (async () => {
        const s = await fetch('/api/auth/session').then(r => r.json());
        console.log(s.accessToken);
      })();
  - Copy the printed token and pass it to --paste or pipe to --stdin
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from project_fetcher import TOKEN_FILE


def parse_token_string(raw: str) -> str:
    """Extract a Bearer token from various input formats.

    Accepts:
      - Raw JWT string (eyJ...)
      - 'Bearer eyJ...' prefixed string
      - JSON object with 'accessToken' or 'access_token' key

    Raises ValueError on empty input or unrecognised JSON.
    """
    raw = raw.strip()
    if not raw:
        raise ValueError('Input is empty — no token found')

    # Strip Bearer prefix
    if raw.lower().startswith('bearer '):
        raw = raw[7:].strip()

    # Try JSON parse
    if raw.startswith('{'):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f'Invalid JSON: {e}') from e
        token = data.get('accessToken') or data.get('access_token')
        if not token:
            raise ValueError(
                'JSON parsed but no accessToken or access_token field found'
            )
        return token

    return raw


def save_token(token: str, token_file: Path = TOKEN_FILE) -> None:
    """Write token to JSON file with a fetched_at timestamp.

    The file is created with mode 0o600 (owner read/write only)
    to protect the Bearer token from other users on the system.
    """
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(
        json.dumps({
            'access_token': token,
            'fetched_at': datetime.now(tz=timezone.utc).isoformat(),
        }),
        encoding='utf-8',
    )
    os.chmod(token_file, 0o600)


def get_chatgpt_token_from_browser() -> str | None:
    """Try to extract ChatGPT Bearer token from the local browser profile.

    Uses browser_cookie3 to read the __Secure-next-auth.session-token cookie,
    then exchanges it for a Bearer token via /api/auth/session.
    Tries Firefox first (most reliable on Linux), then Chrome/Chromium.
    Returns the access token string, or None on failure.
    """
    try:
        import browser_cookie3
    except ImportError:
        print(
            '[!] browser_cookie3 is not installed.\n'
            '    Install it with: pip install browser_cookie3\n'
            '    Or use --paste / --stdin instead.',
            file=sys.stderr,
        )
        return None

    try:
        import requests
    except ImportError:
        print('[!] requests is not installed: pip install requests', file=sys.stderr)
        return None

    browsers = [
        ('Firefox',  getattr(browser_cookie3, 'firefox',  None)),
        ('Chrome',   getattr(browser_cookie3, 'chrome',   None)),
        ('Chromium', getattr(browser_cookie3, 'chromium', None)),
    ]

    session_cookie: str | None = None
    for browser_name, browser_fn in browsers:
        if browser_fn is None:
            continue
        try:
            cj = browser_fn(domain_name='.chatgpt.com')
            for c in cj:
                if c.name == '__Secure-next-auth.session-token' and c.value:
                    session_cookie = c.value
                    print(f'[*] Found session cookie in {browser_name}')
                    break
        except Exception as exc:
            print(f'[!] {browser_name}: {exc}', file=sys.stderr)
        if session_cookie:
            break

    if not session_cookie:
        print(
            '[!] No ChatGPT session cookie found in any browser.\n'
            '    Make sure you are logged in at chatgpt.com,\n'
            '    or use --paste / --stdin.',
            file=sys.stderr,
        )
        return None

    try:
        resp = requests.get(
            'https://chatgpt.com/api/auth/session',
            cookies={'__Secure-next-auth.session-token': session_cookie},
            timeout=30,
        )
        resp.raise_for_status()
        token = resp.json().get('accessToken')
        if not token:
            print('[!] Session exchange succeeded but no accessToken in response.', file=sys.stderr)
            return None
        return token
    except Exception as exc:
        print(f'[!] Failed to exchange session cookie for token: {exc}', file=sys.stderr)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Save ChatGPT Bearer token to ~/.keromdizer_token.json.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Examples:\n'
            '  # Auto-extract from browser (recommended):\n'
            '  python retrieve_token.py\n\n'
            '  # Paste token from browser console JS snippet:\n'
            '  python retrieve_token.py --paste "eyJ..."\n\n'
            '  # Pipe from clipboard (Linux):\n'
            '  xclip -o | python retrieve_token.py --stdin\n'
        ),
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--paste',
        metavar='TOKEN',
        help='Paste the Bearer token directly (or JSON from the console snippet).',
    )
    group.add_argument(
        '--stdin',
        action='store_true',
        help='Read token from stdin (pipe-friendly).',
    )
    args = parser.parse_args()

    if args.paste:
        try:
            token = parse_token_string(args.paste)
        except ValueError as e:
            print(f'[!] {e}', file=sys.stderr)
            sys.exit(1)
    elif args.stdin:
        raw = sys.stdin.read()
        try:
            token = parse_token_string(raw)
        except ValueError as e:
            print(f'[!] {e}', file=sys.stderr)
            sys.exit(1)
    else:
        print('[*] Attempting to extract token from your browser...')
        token = get_chatgpt_token_from_browser()
        if not token:
            sys.exit(1)

    save_token(token)
    print(f'[+] Token saved to {TOKEN_FILE}')
    print('    Note: ChatGPT tokens expire after ~20 minutes. Run the sync soon.')


if __name__ == '__main__':
    main()
