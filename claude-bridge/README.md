# cramer-bridge

A local message bus between Claude Desktop and terminal Claude Code. Nothing
leaves the machine: a stdio MCP server plus an append-only log in
`~/.local/state/cramer-bridge/`.

---

## For Claude Code: installation task

You have been handed this bundle to install. Work through the steps in order.
Stop and report if a verification step fails rather than continuing.

**Assumptions to check first.** This targets macOS with chezmoi managing
dotfiles. Confirm `chezmoi` and `python3` are on PATH and that
`chezmoi source-path` resolves. If chezmoi is not in use, skip to "Manual
install" below instead.

### Step 1 — copy files into the chezmoi source tree

```bash
SRC="$(chezmoi source-path)"
mkdir -p "${SRC}/dot_local/lib/cramer-bridge"
cp chezmoi/dot_local/lib/cramer-bridge/server.py        "${SRC}/dot_local/lib/cramer-bridge/"
cp chezmoi/dot_local/lib/cramer-bridge/requirements.txt "${SRC}/dot_local/lib/cramer-bridge/"
cp chezmoi/run_onchange_after_20-install-cramer-bridge.sh.tmpl "${SRC}/"
```

Do not rename the `run_onchange_after_` file. The prefix is what makes chezmoi
re-run it when `server.py` changes, and `_after_` makes it run once the files
it references are in place.

### Step 2 — dry run, then apply

```bash
chezmoi diff
chezmoi apply -v
```

Read the diff before applying. The script builds a venv, installs `mcp` into
it, merges one key into the Claude Desktop config, and registers the server
with Claude Code at user scope.

### Step 3 — verify the venv

```bash
~/.local/lib/cramer-bridge/.venv/bin/python -c "import mcp.server.fastmcp; print('ok')"
```

If this fails, the install script should already have refused to register
anything. Report the pip error and stop.

### Step 4 — verify the server starts and the store works

```bash
~/.local/lib/cramer-bridge/.venv/bin/python ~/.local/lib/cramer-bridge/server.py --dump
```

Empty output on a fresh install is correct. A traceback is not.

### Step 5 — verify registration on both sides

```bash
claude mcp get cramer-bridge
python3 -c "import json,pathlib; p=pathlib.Path.home()/'Library/Application Support/Claude/claude_desktop_config.json'; print(json.loads(p.read_text())['mcpServers'].get('cramer-bridge'))"
```

Both should show the venv interpreter and the path to `server.py`.

### Step 6 — end-to-end smoke test

Restart Claude Desktop first; it only reads its config at launch. Then from a
Claude Code session, call the bridge:

- `post_message` with sender `code:setup`, recipient `desktop`, subject
  `Bridge installed`, body describing what you did and anything you had to fix.

Then tell the user to ask Claude Desktop to read messages for `desktop`. If the
message appears there, the bridge works in both directions.

### Known rough edges

The `mcp` package was never actually installed when this was written (no
network in the authoring sandbox), so the FastMCP API surface —
`FastMCP(...)`, `@mcp.tool()`, `Annotated[str, Field(description=...)]`,
`mcp.run()` — is written against the documented API rather than a verified
install. If the import or decorator signature differs in the installed version,
fix `server.py` to match and note the change in your `post_message` body so the
user knows what moved. The store logic below it was tested and should not need
changes.

### Manual install (no chezmoi)

```bash
mkdir -p ~/.local/lib/cramer-bridge
cp chezmoi/dot_local/lib/cramer-bridge/* ~/.local/lib/cramer-bridge/
cd ~/.local/lib/cramer-bridge
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
claude mcp add --scope user --transport stdio cramer-bridge -- \
  ~/.local/lib/cramer-bridge/.venv/bin/python ~/.local/lib/cramer-bridge/server.py
```

Then add the same command and args under `mcpServers` in
`~/Library/Application Support/Claude/claude_desktop_config.json`. Merge the
key, back the file up first, and do not overwrite it.

---

## Reference

### Bundle contents

```
README.md
chezmoi/
  dot_local/lib/cramer-bridge/server.py           # the MCP server
  dot_local/lib/cramer-bridge/requirements.txt
  run_onchange_after_20-install-cramer-bridge.sh.tmpl
```

### Naming participants

Addresses are free strings. The convention the tool descriptions teach the
model:

- `desktop` — the Claude Desktop app
- `code:<agent>` — a Claude Code session or subagent, e.g. `code:security-reviewer`
- `all` — broadcast

A recipient of `code` prefix-matches, so it reaches every `code:*` participant.

`from` is a Python keyword, so the message fields are `sender` and `recipient`
rather than `from` and `to`.

### Tools

| Tool | Purpose |
| --- | --- |
| `post_message` | Write a note, task, or result |
| `read_messages` | Fetch by recipient, thread, unread state, or timestamp |
| `mark_read` | Record that a participant saw something |
| `list_threads` | Thread-level overview, optionally only ones with open tasks |
| `claim_task` | Take the oldest unclaimed task addressed to you |
| `close_task` | Mark done or cancelled, optionally posting a result |

### Closing the polling gap

Neither side is pushed to. To make agents check without being asked, add a
`SessionStart` hook in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Call cramer-bridge read_messages for code:<your agent name> before starting.'"
          }
        ]
      }
    ]
  }
}
```

That injects a nudge rather than doing the read itself, which keeps the hook
from failing when the store is empty.

### Storage notes

The log is append-only JSONL, and state (read, claimed, done) is reconstructed
by replaying it. That is deliberate: every client spawns its own copy of the
server, so two processes write concurrently, and appending avoids rewriting
lines another process may be mid-read on. Verified with three concurrent
writers at 180 records: no torn or unparseable lines. The state directory is
created `0700` and the log `0600`.

Tasks are single-claim. A second `claim_task` on the same message is refused
rather than overriding the first, so two agents cannot pick up the same work.

Bodies are capped at 64 KB. For anything larger, write a file and send the path.

### What was tested

Every tool function was exercised end to end against a stubbed FastMCP, along
with the concurrency, permissions, oversize-body, unknown-id, double-claim, and
malformed-config paths. The real SDK binding is the one unverified piece, as
noted under "Known rough edges".

### Limits worth knowing

- This only works from the Claude Desktop app. Local stdio MCP servers are not
  available on claude.ai in a browser, and not in Cowork. Custom connectors are
  the reverse mechanism: they connect from Anthropic's cloud and cannot reach
  localhost.
- It is a mailbox, not a socket. Neither side sees a message until it calls
  `read_messages`. Nothing interrupts a session in flight.
- No authentication. Anything running as your user can read and write the log.
  Treat the store as sensitive and keep it out of any synced or backed-up
  directory you would not put credentials in.
