# Finding Your ChatGPT Project Gizmo IDs

KeroMDizer can automatically associate your imported conversations with their
ChatGPT project names. To enable this, you need to find the **gizmo ID** for
each of your projects.

---

## What is a Gizmo ID?

Every ChatGPT project has a unique gizmo ID embedded in its URL. It looks like:

```
g-p-69b19d003d948191836ab8081b8fddfc
```

---

## How to Find Your Project URLs

1. Go to [chatgpt.com](https://chatgpt.com) and log in.
2. Open a project from the left sidebar.
3. Look at the browser address bar. The URL will be one of:

   - Project page: `https://chatgpt.com/g/{gizmo_id}-{slug}/project`
   - A chat inside the project: `https://chatgpt.com/g/{gizmo_id}-{slug}/c/{conversation_id}`

4. Copy the `g-p-...` portion — that is your gizmo ID.

---

## Add Your Projects to ~/.keromdizer.toml

Open `~/.keromdizer.toml` (create it if it doesn't exist) and add a
`[chatgpt.projects]` section:

```toml
[chatgpt.projects]
"g-p-69b19d003d948191836ab8081b8fddfc" = "My Work Project"
"g-p-69758729f94481919287e4329d3cfd3a" = "Personal Notes"
```

The key is the gizmo ID; the value is the project name that will appear in your
exported files and the REVIEW screen.

---

## Retrieving Your Bearer Token

The sync requires a short-lived Bearer token from your ChatGPT session.

### Option 1 — Auto-extract from browser (easiest)

```bash
python retrieve_token.py
```

This uses your browser's local session cookies. Works best with Firefox.
You must be logged in to chatgpt.com.

### Option 2 — Paste from browser console

1. Open [chatgpt.com](https://chatgpt.com) in your browser.
2. Open DevTools (F12) → **Console** tab.
3. Paste and run:

   ```js
   (async () => {
     const s = await fetch('/api/auth/session').then(r => r.json());
     console.log(s.accessToken);
   })();
   ```

4. Copy the printed token (starts with `eyJ`).
5. Run:

   ```bash
   python retrieve_token.py --paste "eyJ..."
   ```

   Or use `[V] Paste token` in the TUI PROJECTS screen.

---

## Running the Sync

### Via TUI

1. Launch the TUI: `python tui.py`
2. Select **Projects** from the main menu.
3. Use **[B]** to auto-extract the token from your browser, or **[V]** to paste.
4. Press **Enter** to run the sync.

### Notes

- Tokens expire in ~20 minutes. Re-run `retrieve_token.py` if the sync fails with
  an auth error.
- The sync conflict behaviour can be changed in **Settings → Project conflict**:
  - `preserve` (default) — only fills empty project fields
  - `overwrite` — always replaces with the fetched project name
  - `flag` — same as overwrite, but shows a warning count in the UI
