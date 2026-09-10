#!/usr/bin/env python3
"""Width and degradation tests for dot_claude/executable_statusline.sh.

The status line is laid out by arithmetic the script does on its own strings, so
this harness deliberately does not reuse any of it: widths here are measured
with unicodedata, the way a terminal measures them, and the fixtures are fed in
as real JSON on stdin at real terminal widths.

The invariant under test is the one the user asked for -- the line never gets
cut off unless there genuinely is not room -- expressed as three properties:

  fits    no rendered line reaches the last column, so nothing ever wraps
  keeps   with room to spare, the agent name and the worktree directory are
          present in full (they are what say *which* agent and *which* checkout)
  fills   with room to spare, the line spans the window instead of stopping at
          some fixed column

Run:  tests/statusline-test.py [path/to/statusline.sh]
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    REPO, "dot_claude", "executable_statusline.sh")

# The script keeps a couple of columns for Claude Code's own spacing. Tests
# allow anything up to the last column, so this only has to be a lower bound on
# how close to the edge "fills the window" means.
EDGE_SLACK = 4

ANSI = re.compile(r"\x1b\[[0-9;]*m")

failures = 0


def ok(msg):
    print("  ok    %s" % msg)


def bad(msg):
    global failures
    failures += 1
    print("  FAIL  %s" % msg)


def viswidth(s):
    """Columns a terminal spends on s, ignoring SGR colour sequences."""
    total = 0
    for ch in ANSI.sub("", s):
        if unicodedata.combining(ch):
            continue
        # Wide and Fullwidth take two cells; Ambiguous (the box-drawing and
        # ellipsis glyphs) takes one in every terminal this repo targets.
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


def plain(s):
    return ANSI.sub("", s)


# ------------------------------------------------------------------ fixtures

def payload(**over):
    """A full payload, so that omitting a field in a fixture is deliberate."""
    p = {
        "model": {"display_name": "Opus 5"},
        "effort": {"level": "high"},
        "fast_mode": True,
        "thinking": {"enabled": False},
        "output_style": {"name": "default"},
        "context_window": {
            "used_percentage": 63,
            "total_input_tokens": 126000,
            "context_window_size": 200000,
        },
        "cost": {"total_cost_usd": 4.2137, "total_lines_added": 812,
                 "total_lines_removed": 340},
        "rate_limits": {
            "five_hour": {"used_percentage": 47, "resets_at": 4102444800},
            "seven_day": {"used_percentage": 81, "resets_at": 4102444800},
        },
        "workspace": {"current_dir": "/Users/synthetic/projects/mjcramer/envious"},
        "version": "2.1.0",
    }
    for k, v in over.items():
        if v is None:
            p.pop(k, None)
        else:
            p[k] = v
    return p


AGENTS = ["orchestrator", "hardware-engineer", "incident-responder",
          "security-reviewer", "system-designer", "craft-engineer",
          "spike-engineer", "infra-engineer"]

WIDTHS = [40, 60, 80, 100, 120, 160, 200]

HOME = "/Users/synthetic"


def wdir(path):
    return {"workspace": {"current_dir": path}}


cases = []  # (name, payload, expects_two_lines)

# One case per agent, in the worktree its name produces. This is the shape the
# user actually runs in, not an edge case.
for a in AGENTS:
    cases.append((
        "agent %s" % a,
        payload(agent={"name": a},
                **wdir("%s/projects/mjcramer/envious.%s" % (HOME, a))),
        True,
    ))

cases += [
    ("deep nested path",
     payload(agent={"name": "system-designer"},
             **wdir("%s/projects/mjcramer/envious/dot_local/private_share/"
                    "templates/scala-pekko/src/main/scala" % HOME)),
     True),

    ("every flag lit",
     payload(agent={"name": "hardware-engineer"},
             vim={"mode": "NORMAL"},
             pr={"number": 148},
             output_style={"name": "Explanatory"},
             fast_mode=True,
             thinking={"enabled": False},
             **wdir("%s/projects/mjcramer/envious.hardware-engineer" % HOME)),
     True),

    ("no agent, plain checkout",
     payload(**wdir("%s/projects/mjcramer/envious" % HOME)),
     True),

    ("nulls everywhere",
     {"workspace": {"current_dir": "%s/projects/mjcramer/envious" % HOME},
      "model": {"display_name": None}, "effort": None, "agent": None,
      "cost": {"total_cost_usd": None}, "rate_limits": None},
     True),

    ("bare cwd only",
     {"cwd": "%s/projects/mjcramer/envious" % HOME},
     True),

    ("empty object", {}, False),
]


def dedupe(paths):
    """Existing, distinct interpreters, in the order given."""
    out = []
    for p in paths:
        if p and os.path.exists(p) and os.path.realpath(p) not in \
                [os.path.realpath(q) for q in out]:
            out.append(p)
    return out


def bash_version(bash):
    v = subprocess.run([bash, "-c", 'echo "$BASH_VERSION"'],
                       capture_output=True, text=True).stdout.strip()
    return "bash %s" % (v or "?")


def run(payload_text, cols, cwd=REPO):
    env = dict(os.environ)
    env["HOME"] = HOME
    env["TERM"] = "xterm-ghostty"
    if cols is None:
        env.pop("COLUMNS", None)
    else:
        env["COLUMNS"] = str(cols)
    p = subprocess.run(
        [BASH, SCRIPT], input=payload_text, capture_output=True, text=True,
        env=env, cwd=cwd,
        # Detach from the controlling terminal so /dev/tty and tput answer the
        # way they do under Claude Code, whichever way this harness was started.
        start_new_session=True,
    )
    return p


def has_right_group(obj):
    """True when line 2 has something to push to the right edge at all."""
    cost = obj.get("cost") or {}
    if cost.get("total_cost_usd") or cost.get("total_lines_added") \
            or cost.get("total_lines_removed"):
        return True
    return bool(obj.get("rate_limits"))


def check(name, payload_text, cols, expect_two, want_agent=None, want_tail=None,
          want_fill=True):
    target = cols if cols is not None else 80  # unknown width assumes 80
    p = run(payload_text, cols)
    label = "%s @ %s" % (name, cols if cols is not None else "unknown")

    if p.returncode != 0:
        bad("%s: exit %d (%s)" % (label, p.returncode, p.stderr.strip()[:120]))
        return
    if p.stderr.strip():
        bad("%s: wrote to stderr: %s" % (label, p.stderr.strip()[:120]))
        return
    if p.stdout.endswith("\n"):
        bad("%s: trailing newline would render as a blank status line" % label)
        return

    lines = p.stdout.split("\n")
    if expect_two and len(lines) != 2:
        bad("%s: %d line(s), want 2" % (label, len(lines)))
        return

    for i, line in enumerate(lines, 1):
        w = viswidth(line)
        # Reaching the final column is enough to wrap on a terminal without
        # deferred wrap, so the last column is out of bounds too.
        if w > target - 1:
            bad("%s: line %d is %d columns wide, target %d\n        |%s|"
                % (label, i, w, target, plain(line)))
            return

    if want_agent and target >= 100:
        if ("@" + want_agent) not in plain(lines[0]):
            bad("%s: dropped the agent name with %d columns to spare\n        |%s|"
                % (label, target, plain(lines[0])))
            return
    if want_tail and target >= 100:
        if want_tail not in plain(lines[0]):
            bad("%s: dropped the worktree name with %d columns to spare\n        |%s|"
                % (label, target, plain(lines[0])))
            return

    if target >= 100 and expect_two and want_fill:
        w = viswidth(lines[1])
        if w < target - EDGE_SLACK:
            bad("%s: line 2 stops at column %d of %d instead of spanning the window"
                % (label, w, target))
            return

    ok(label)


def suite():
    # 1. Every fixture at every width, plus the unknown-width path.
    for name, obj, expect_two in cases:
        text = json.dumps(obj)
        agent = (obj.get("agent") or {}).get("name") \
            if isinstance(obj.get("agent"), dict) else None
        cur = (obj.get("workspace") or {}).get("current_dir") or obj.get("cwd") or ""
        tail = cur.rsplit("/", 1)[-1] if cur else None
        fill = has_right_group(obj)
        for cols in WIDTHS + [None]:
            check(name, text, cols, expect_two, want_agent=agent, want_tail=tail,
                  want_fill=fill)

    # 2. A payload jq cannot parse must still leave a usable status line.
    for junk in ["", "not json", '{"workspace": ', "[1,2,3]"]:
        p = run(junk, 120)
        if p.returncode == 0 and p.stdout.strip() and not p.stdout.endswith("\n"):
            ok("malformed payload %-16r degrades to %s" % (junk, p.stdout.strip()[:40]))
        else:
            bad("malformed payload %r gave exit %d, stdout %r"
                % (junk, p.returncode, p.stdout[:60]))

    # 3. Real git state: a long agent branch in a dirty worktree is the worst
    #    case for line 1, and it must still fit and still keep the agent name.
    tmp = tempfile.mkdtemp(prefix="statusline-test-")
    try:
        repo = os.path.join(tmp, "envious.hardware-engineer")
        os.makedirs(repo)
        env = dict(os.environ, GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="test@localhost",
                   GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="test@localhost")
        subprocess.run(["git", "init", "-q", "-b",
                        "agent/hardware-engineer/thermal-sensor-recalibration", repo],
                       env=env, check=True, capture_output=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "--allow-empty", "-m", "init"],
                       env=env, check=True, capture_output=True)
        with open(os.path.join(repo, "dirty.txt"), "w") as fh:
            fh.write("scratch\n")

        text = json.dumps(payload(agent={"name": "hardware-engineer"},
                                  vim={"mode": "NORMAL"}, pr={"number": 148},
                                  **wdir(repo)))
        for cols in WIDTHS + [None]:
            target = cols if cols is not None else 80
            p = run(text, cols, cwd=repo)
            lines = p.stdout.split("\n")
            widths = [viswidth(l) for l in lines]
            if max(widths) > target - 1:
                bad("dirty agent worktree @ %s: %d columns wide, target %d\n        |%s|"
                    % (cols, max(widths), target, plain(lines[0])))
            elif target >= 120 and "@hardware-engineer" not in plain(lines[0]):
                bad("dirty agent worktree @ %s: lost the agent name\n        |%s|"
                    % (cols, plain(lines[0])))
            else:
                ok("dirty agent worktree @ %s (widths %s)"
                   % (cols if cols is not None else "unknown", widths))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# Every bash on the box, because macOS ships 3.2 at /bin/bash and that is what
# the script has to keep working under even when a newer bash is first on PATH.
for BASH in dedupe([shutil.which("bash"), "/bin/bash", "/usr/local/bin/bash",
                    "/opt/homebrew/bin/bash"]):
    print("statusline layout tests (%s, %s)"
          % (os.path.relpath(SCRIPT, REPO), bash_version(BASH)))
    suite()

print("statusline layout tests: %s"
      % ("FAILED (%d)" % failures if failures else "all good"))
sys.exit(1 if failures else 0)
