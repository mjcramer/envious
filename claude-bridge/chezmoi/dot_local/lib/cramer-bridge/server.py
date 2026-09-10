#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2.0"]
# ///
"""
cramer-bridge — a local message bus between Claude Desktop and Claude Code.

Transport: stdio MCP. Each client (Desktop, each Claude Code session) spawns
its own copy of this process, so all shared state lives on disk.

Store: a single append-only JSONL event log. Appends under PIPE_BUF are atomic
on POSIX, so concurrent writers do not need a lock. Current state (read /
claimed / done) is reconstructed by replaying the log, which avoids rewriting
lines that another process may be reading.

Everything this process prints to stdout is JSON-RPC. Diagnostics go to stderr.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

STATE_DIR = Path(
    os.environ.get("CRAMER_BRIDGE_DIR")
    or Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "cramer-bridge"
)
LOG_PATH = STATE_DIR / "messages.jsonl"

# Cap on how much body text a single message may carry.
MAX_BODY = 64 * 1024


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ensure_store() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not LOG_PATH.exists():
        LOG_PATH.touch(mode=0o600)


def append(event: dict[str, Any]) -> dict[str, Any]:
    ensure_store()
    line = json.dumps(event, separators=(",", ":")) + "\n"
    # Open per append in append mode so the write is a single atomic syscall
    # even with another process writing concurrently.
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return event


def read_events() -> list[dict[str, Any]]:
    ensure_store()
    events: list[dict[str, Any]] = []
    with LOG_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # A torn write (process killed mid-append) would land here.
                # Skip it rather than failing the whole read.
                print("cramer-bridge: skipping unparseable log line", file=sys.stderr)
    return events


def materialize() -> dict[str, dict[str, Any]]:
    """Replay the log into current message state, in chronological order."""
    messages: dict[str, dict[str, Any]] = {}
    for ev in read_events():
        if ev.get("type") == "message":
            messages[ev["id"]] = {
                "id": ev["id"],
                "ts": ev["ts"],
                "sender": ev["sender"],
                "recipient": ev["recipient"],
                "kind": ev["kind"],
                "subject": ev["subject"],
                "body": ev["body"],
                "thread": ev.get("thread") or ev["id"],
                "read_by": [],
                "claimed_by": None,
                "status": "open" if ev["kind"] == "task" else "n/a",
            }
        elif ev.get("type") == "status":
            msg = messages.get(ev["message_id"])
            if msg is None:
                continue
            if ev["status"] == "read":
                if ev["by"] not in msg["read_by"]:
                    msg["read_by"].append(ev["by"])
            elif ev["status"] == "claimed":
                # First claim wins. A second claimant is a race, not an override.
                if msg["claimed_by"] is None:
                    msg["claimed_by"] = ev["by"]
                    msg["status"] = "claimed"
            elif ev["status"] in ("done", "cancelled"):
                msg["status"] = ev["status"]
    return messages


def addressed_to(msg: dict[str, Any], who: str | None) -> bool:
    """Address matching. 'all' is a broadcast every participant receives."""
    if not who:
        return True
    recipient = msg["recipient"]
    if recipient in ("all", who):
        return True
    # Prefix match so recipient "code" reaches "code:security-reviewer".
    return recipient.startswith(who + ":")


def summarize(msg: dict[str, Any], include_body: bool = True) -> dict[str, Any]:
    out = {
        "id": msg["id"],
        "ts": msg["ts"],
        "sender": msg["sender"],
        "recipient": msg["recipient"],
        "kind": msg["kind"],
        "subject": msg["subject"],
        "thread": msg["thread"],
    }
    if msg["kind"] == "task":
        out["status"] = msg["status"]
        out["claimed_by"] = msg["claimed_by"]
    if include_body:
        out["body"] = msg["body"]
    return out


def reply(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP("cramer-bridge")

PARTICIPANT_HINT = (
    'Participant name. Convention: "desktop" for the Claude Desktop app, '
    '"code:<agent>" for a Claude Code session or subagent '
    '(e.g. "code:security-reviewer"), "all" to broadcast.'
)

Participant = Annotated[str, Field(description=PARTICIPANT_HINT)]


@mcp.tool()
def post_message(
    sender: Participant,
    recipient: Participant,
    subject: Annotated[str, Field(description="One-line summary.")],
    body: Annotated[str, Field(description="Full message text. Markdown is fine.")],
    kind: Annotated[
        Literal["note", "task", "result"],
        Field(description="note = FYI, task = work request, result = response to a task."),
    ] = "note",
    thread: Annotated[
        str | None,
        Field(description="Message id to attach this to. Omit to start a new thread."),
    ] = None,
) -> str:
    """Post a message to the shared local bridge.

    The other side (Claude Desktop or a Claude Code session) picks it up on its
    next read. Use kind='task' when you want the other side to do something and
    report back.
    """
    if len(body) > MAX_BODY:
        return reply({"error": f"body exceeds {MAX_BODY} bytes; write to a file and send the path"})

    event = append(
        {
            "type": "message",
            "id": str(uuid.uuid4()),
            "ts": now(),
            "sender": sender,
            "recipient": recipient,
            "kind": kind,
            "subject": subject,
            "body": body,
            "thread": thread,
        }
    )
    return reply({"posted": event["id"], "thread": event["thread"] or event["id"]})


@mcp.tool()
def read_messages(
    recipient: Annotated[
        str | None, Field(description=PARTICIPANT_HINT + " Omit to read everything.")
    ] = None,
    unread_by: Annotated[
        str | None,
        Field(description="Only return messages this participant has not marked read."),
    ] = None,
    thread: Annotated[str | None, Field(description="Restrict to one thread id.")] = None,
    since: Annotated[
        str | None, Field(description="ISO-8601 timestamp; only messages after it.")
    ] = None,
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
) -> str:
    """Fetch messages addressed to a participant, newest last.

    Call this at the start of a session to see what the other side left.
    """
    msgs = list(materialize().values())
    if recipient:
        msgs = [m for m in msgs if addressed_to(m, recipient)]
    if thread:
        msgs = [m for m in msgs if m["thread"] == thread]
    if since:
        msgs = [m for m in msgs if m["ts"] > since]
    if unread_by:
        msgs = [m for m in msgs if unread_by not in m["read_by"]]

    total = len(msgs)
    msgs = msgs[-limit:]
    return reply(
        {"total": total, "returned": len(msgs), "messages": [summarize(m) for m in msgs]}
    )


@mcp.tool()
def mark_read(by: Participant, message_ids: list[str]) -> str:
    """Record that a participant has seen these messages."""
    known = materialize()
    marked: list[str] = []
    unknown: list[str] = []
    for message_id in message_ids:
        if message_id not in known:
            unknown.append(message_id)
            continue
        append(
            {
                "type": "status",
                "id": str(uuid.uuid4()),
                "ts": now(),
                "message_id": message_id,
                "status": "read",
                "by": by,
            }
        )
        marked.append(message_id)
    return reply({"marked": marked, "unknown": unknown})


@mcp.tool()
def list_threads(
    recipient: Annotated[
        str | None, Field(description="Only threads involving this participant.")
    ] = None,
    open_tasks_only: Annotated[
        bool, Field(description="Only threads with an unfinished task.")
    ] = False,
) -> str:
    """One entry per thread: participants, subject, message count, latest activity."""
    threads: dict[str, dict[str, Any]] = {}
    for m in materialize().values():
        t = threads.setdefault(
            m["thread"],
            {
                "thread": m["thread"],
                "subject": m["subject"],
                "participants": set(),
                "count": 0,
                "last_ts": m["ts"],
                "open_task": False,
            },
        )
        t["participants"].update({m["sender"], m["recipient"]})
        t["count"] += 1
        t["last_ts"] = max(t["last_ts"], m["ts"])
        if m["kind"] == "task" and m["status"] in ("open", "claimed"):
            t["open_task"] = True

    out = list(threads.values())
    if recipient:
        out = [
            t
            for t in out
            if any(p == "all" or p == recipient or p.startswith(recipient + ":") for p in t["participants"])
        ]
    if open_tasks_only:
        out = [t for t in out if t["open_task"]]
    out.sort(key=lambda t: t["last_ts"])

    return reply({"threads": [{**t, "participants": sorted(t["participants"])} for t in out]})


@mcp.tool()
def claim_task(
    by: Participant,
    task_id: Annotated[
        str | None, Field(description="Claim a specific task instead of the oldest.")
    ] = None,
) -> str:
    """Take the oldest unclaimed task addressed to you.

    Prevents two agents picking up the same work. Returns null if nothing is open.
    """
    tasks = [m for m in materialize().values() if m["kind"] == "task"]

    if task_id:
        candidate = next((m for m in tasks if m["id"] == task_id), None)
        if candidate is None:
            return reply({"claimed": None, "reason": "no such task"})
    else:
        candidate = next(
            (m for m in tasks if m["status"] == "open" and addressed_to(m, by)), None
        )
        if candidate is None:
            return reply({"claimed": None, "reason": "no open tasks"})

    if candidate["claimed_by"]:
        return reply({"claimed": None, "reason": f"already claimed by {candidate['claimed_by']}"})

    append(
        {
            "type": "status",
            "id": str(uuid.uuid4()),
            "ts": now(),
            "message_id": candidate["id"],
            "status": "claimed",
            "by": by,
        }
    )
    return reply({"claimed": summarize(candidate)})


@mcp.tool()
def close_task(
    by: Participant,
    task_id: str,
    status: Literal["done", "cancelled"] = "done",
    result: Annotated[
        str | None, Field(description="Optional summary posted as a result message.")
    ] = None,
) -> str:
    """Mark a task done or cancelled, optionally posting a result in its thread."""
    task = materialize().get(task_id)
    if task is None:
        return reply({"error": "no such task"})

    append(
        {
            "type": "status",
            "id": str(uuid.uuid4()),
            "ts": now(),
            "message_id": task_id,
            "status": status,
            "by": by,
        }
    )

    result_id = None
    if result:
        event = append(
            {
                "type": "message",
                "id": str(uuid.uuid4()),
                "ts": now(),
                "sender": by,
                "recipient": task["sender"],
                "kind": "result",
                "subject": f"Re: {task['subject']}",
                "body": result,
                "thread": task["thread"],
            }
        )
        result_id = event["id"]

    return reply({"task": task_id, "status": status, "result_message": result_id})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def dump() -> None:
    """Print the log for eyeballing from a terminal, bypassing both clients."""
    for m in materialize().values():
        status = f"/{m['status']}" if m["kind"] == "task" else ""
        print(
            f"{m['ts']}  {m['sender']} -> {m['recipient']}  "
            f"[{m['kind']}{status}]  {m['subject']}  ({m['id']})"
        )


if __name__ == "__main__":
    if "--dump" in sys.argv:
        dump()
        sys.exit(0)
    print(f"cramer-bridge: ready, store at {LOG_PATH}", file=sys.stderr)
    mcp.run()
