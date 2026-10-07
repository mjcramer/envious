"""Shared helpers for the unittest modules in tests/.

Everything here runs against the chezmoi *source* tree (the `dot_claude/...`
files with their `executable_` prefixes), never against the deployed ~/.claude,
so the suite can run before `chezmoi apply` and does not depend on what is
currently installed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO = Path(__file__).resolve().parent.parent
GUARD = REPO / "dot_claude" / "hooks" / "executable_guard-infra.py"

Decision = Literal["deny", "ask", "allow"]


@dataclass(frozen=True)
class GuardResult:
    """What Claude Code would see after running the guard on one payload."""

    decision: Decision
    reason: str          # permissionDecisionReason, or "" when the guard allowed
    exit_code: int
    stdout: str
    stderr: str


def bash_payload(command: str) -> bytes:
    """The PreToolUse payload Claude Code sends for a Bash tool call."""
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}).encode()


def run_guard(stdin: bytes, *, script: Path = GUARD) -> GuardResult:
    """Run the guard as Claude Code does -- `python3 <hook>` with the payload on
    stdin -- and parse its verdict.

    The guard's contract is: exit 0 always; print nothing to allow; otherwise
    print one JSON object with hookSpecificOutput.permissionDecision. Anything
    outside that contract (non-zero exit, unparsable stdout, a decision other
    than deny/ask) raises here, because a test that quietly read it as "allow"
    would hide exactly the failure the suite exists to catch.
    """
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=stdin, capture_output=True, env=env, timeout=30,
    )
    stdout = proc.stdout.decode(errors="replace")
    stderr = proc.stderr.decode(errors="replace")
    if proc.returncode != 0:
        raise AssertionError(
            f"guard exited {proc.returncode} (the hook must always exit 0)\n{stderr}")
    if not stdout.strip():
        return GuardResult("allow", "", proc.returncode, stdout, stderr)
    out = json.loads(stdout)["hookSpecificOutput"]
    decision = out["permissionDecision"]
    if decision not in ("deny", "ask"):
        raise AssertionError(f"unexpected permissionDecision {decision!r} in {stdout!r}")
    return GuardResult(decision, out.get("permissionDecisionReason", ""),
                       proc.returncode, stdout, stderr)


def guard(command: str) -> GuardResult:
    """Shorthand: run the guard on a Bash command string."""
    return run_guard(bash_payload(command))
