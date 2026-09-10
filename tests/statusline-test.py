#!/usr/bin/env python3
"""Width and degradation tests for both Claude Code status lines.

  dot_claude/executable_statusline.sh           the two-line status bar
  dot_claude/executable_subagent-statusline.sh  one row per subagent

Both are laid out by arithmetic the scripts do on their own strings, so this
harness deliberately does not reuse any of it: widths here are measured with
unicodedata, the way a terminal measures them, and the fixtures are fed in as
real JSON on stdin at real widths.

The invariant under test is the one the user asked for -- nothing gets cut off
unless there genuinely is not room -- expressed as three properties:

  fits    no rendered line reaches the last column, so nothing ever wraps
  keeps   with room to spare, the agent name and the worktree directory are
          present in full (they are what say *which* agent and *which* checkout)
  fills   with room to spare, the line spans the window instead of stopping at
          some fixed column

"fills" only means anything if the width was found, so width_source_suite()
pins down which source usable_cols() believes and in what order, by measurement
rather than by inspection. `ps` is shimmed throughout so the process tree the
scripts see is an input to the test rather than a property of the window the
suite happens to be running in.

Run:  tests/statusline-test.py [path/to/statusline.sh]
"""

import contextlib
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
SUBSCRIPT = os.path.join(REPO, "dot_claude", "executable_subagent-statusline.sh")

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


# ------------------------------------------------------------- process tree

# usable_cols() asks `ps` for its ancestors' terminals, so the real process tree
# would leak into every test: run the suite from a 240-column window and the
# "width unknown" cases would find 240 instead of falling back. This stand-in
# makes the tree an input. It answers only the one query the library makes.
PS_SHIM = r"""#!/bin/sh
# Test stand-in for ps(1): answers `ps -o ppid=,tty= -p <pid>` from
# PS_FAKE_TABLE, which holds "pid:ppid:tty" rows separated by ";". An unknown
# pid exits 1, the way ps does for a process that has gone; an empty table
# therefore means no ancestor has a terminal.
pid=
prev=
for arg in "$@"; do
  if [ "$prev" = "-p" ]; then pid=$arg; fi
  prev=$arg
done
[ -n "$pid" ] || exit 1
saved=$IFS
set -f                      # splitting on ";" is the point; globbing is not
IFS=';'
# shellcheck disable=SC2086
set -- ${PS_FAKE_TABLE:-}
IFS=$saved
set +f
for row in "$@"; do
  case $row in
    "$pid":*) rest=${row#*:}; printf ' %s %s\n' "${rest%%:*}" "${rest#*:}"; exit 0 ;;
  esac
done
exit 1
"""

_shim_dir = tempfile.mkdtemp(prefix="statusline-shim-")
with open(os.path.join(_shim_dir, "ps"), "w") as _fh:
    _fh.write(PS_SHIM)
os.chmod(os.path.join(_shim_dir, "ps"), 0o755)


def script_env(cols, ps_table=None, **over):
    """Environment for a script run: nothing about this machine leaks in.

    `ps` is shimmed, and both width overrides are cleared unless a test sets
    them -- a CLAUDE_STATUSLINE_COLS exported in the shell running the tests
    would otherwise silently decide every case.
    """
    env = dict(os.environ)
    env["HOME"] = HOME
    env["TERM"] = "xterm-ghostty"
    env["PATH"] = _shim_dir + os.pathsep + env.get("PATH", "")
    env["PS_FAKE_TABLE"] = ps_table or ""
    env.pop("CLAUDE_STATUSLINE_COLS", None)
    env.pop("COLUMNS", None)
    env.pop("LINES", None)
    if cols is not None:
        env["COLUMNS"] = str(cols)
    for k, v in over.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = str(v)
    return env


def run(payload_text, cols, cwd=REPO, env=None):
    p = subprocess.run(
        [BASH, SCRIPT], input=payload_text, capture_output=True, text=True,
        env=env if env is not None else script_env(cols), cwd=cwd,
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
    # Too narrow to keep the whole path: what has to survive is its *end*.
    # "…hardware-engineer" says which worktree this is, "envious.…" does not,
    # and this is the only thing asserting the direction of that last-resort
    # clip -- every other check runs at a width where nothing gets clipped.
    if want_tail and target < 60 and len(want_tail) >= 8:
        if want_tail[-8:] not in plain(lines[0]):
            bad("%s: clipped the directory from the wrong end\n        |%s|"
                % (label, plain(lines[0])))
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


def in_pty(cols, rows, script, stdin_text):
    """Run a script attached to a real pty of a chosen size.

    This is the only thing here that exercises the `stty size </dev/tty` branch
    of usable_cols() -- the environment-variable tests never reach it. It is
    also exactly what a user gets running the script by hand from a terminal.
    """
    import fcntl, pty, struct, termios

    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:                                    # child
        os.setsid()
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)    # adopt the pty as our tty
        os.dup2(r, 0); os.dup2(slave, 1); os.dup2(slave, 2)
        for fd in (master, slave, r, w):
            if fd > 2:
                os.close(fd)
        # A real shell exports no COLUMNS, and the pty we just adopted is the
        # only width source that should answer here -- script_env clears the
        # override and shims `ps` so nothing else can.
        env = script_env(None, TERM="xterm-256color")
        os.execve(BASH, [BASH, script], env)
    os.close(slave); os.close(r)
    os.write(w, stdin_text.encode()); os.close(w)
    out = b""
    while True:
        try:
            chunk = os.read(master, 65536)
        except OSError:                             # slave end closed
            break
        if not chunk:
            break
        out += chunk
    os.close(master); os.waitpid(pid, 0)
    return out.decode(errors="replace").replace("\r\n", "\n")


def pty_suite():
    """A real terminal, including a genuine 80-column one.

    80 matters specifically: terminfo's default width is also 80, so a real
    80-column terminal and a terminal that could not be measured used to be
    indistinguishable. `stty` tells them apart. `tput` does not -- it is
    measured here answering 80 at every size, which is why usable_cols() does
    not consult it.
    """
    tmp = tempfile.mkdtemp(prefix="statusline-pty-")
    probe = os.path.join(tmp, "probe.sh")
    with open(probe, "w") as fh:
        fh.write('echo "[$({ stty size </dev/tty; } 2>/dev/null | cut -d\' \' -f2)]'
                 '[$(tput cols 2>/dev/null)]"\n')
    text = json.dumps(payload(
        agent={"name": "hardware-engineer"}, pr={"number": 148},
        **wdir("%s/projects/mjcramer/envious.hardware-engineer" % HOME)))
    try:
        for cols in (80, 132, 200):
            got = in_pty(cols, 24, probe, "").strip()
            want = "[%d]" % cols
            if not got.startswith(want):
                bad("pty %d: stty reported %r, want it to start %s" % (cols, got, want))
                continue
            ok("pty %3d: stty reports %d, tput reports %s"
               % (cols, cols, got[len(want):].strip("[]")))

            out = in_pty(cols, 24, SCRIPT, text)
            lines = [l for l in out.split("\n") if l]
            if len(lines) != 2:
                bad("pty %d: %d line(s) of output, want 2" % (cols, len(lines)))
            elif max(viswidth(l) for l in lines) > cols - 1:
                bad("pty %d: rendered %d columns\n        |%s|"
                    % (cols, max(viswidth(l) for l in lines), plain(lines[0])))
            elif min(viswidth(l) for l in lines) < cols - EDGE_SLACK:
                bad("pty %d: rendered only %d columns, does not span the terminal"
                    % (cols, min(viswidth(l) for l in lines)))
            else:
                ok("pty %3d: both lines span the terminal (%s)"
                   % (cols, [viswidth(l) for l in lines]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------- width sources

# statusline-lib.sh: RESERVED_COLS, the margin taken off any *terminal* width,
# and ASSUMED_COLS, what a line is laid out against when nothing answered. Both
# are asserted against exactly, so a change to either belongs here too.
RESERVED = 2
ASSUMED = 80 - RESERVED


@contextlib.contextmanager
def live_pty(cols, rows=24):
    """A pty of a chosen size, yielding its slave device's basename.

    Both ends stay open for the life of the block so the device keeps existing
    and keeps answering with the size set here. Nothing adopts it as a
    controlling terminal -- the point is a terminal the script does *not* own,
    reachable only through /dev, which is the shape of the Claude Code case.
    """
    import fcntl, pty, struct, termios

    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    try:
        yield os.path.basename(os.ttyname(slave))
    finally:
        os.close(slave)
        os.close(master)


def tree(*rows):
    """A PS_FAKE_TABLE for a chain rooted at this process's child.

    Each row is a terminal name (or "??" for a process without one); the walk
    starts at the script's parent, which is this harness, so the first row is
    what $PPID reports.
    """
    pids = [os.getpid()] + [900 + i for i in range(1, len(rows) + 1)]
    return ";".join("%d:%d:%s" % (pids[i], pids[i + 1], t)
                    for i, t in enumerate(rows))


def width_source_suite():
    """Which source usable_cols() believes, and in what order.

    Every case pins the width by measurement rather than by inspecting the
    script: a source was believed if and only if the line spans that width.
    """
    text = json.dumps(payload(
        agent={"name": "hardware-engineer"}, pr={"number": 148},
        **wdir("%s/projects/mjcramer/envious.hardware-engineer" % HOME)))

    def widths(label, cols=None, ps_table=None, **over):
        p = run(text, None, env=script_env(cols, ps_table, **over))
        if p.returncode != 0 or p.stderr.strip():
            bad("%s: exit %d, stderr %s" % (label, p.returncode, p.stderr.strip()[:120]))
            return None
        return [viswidth(l) for l in p.stdout.split("\n")]

    def spans(label, term, **kw):
        """The layout used `term` as the terminal width, exactly."""
        ws = widths(label, **kw)
        if ws is None:
            return
        want = term - RESERVED
        if ws == [want, want]:
            ok("%s -> %d columns" % (label, want))
        else:
            bad("%s: lines are %s columns, want both at %d (terminal %d)"
                % (label, ws, want, term))

    def unknown(label, **kw):
        """Nothing answered: the layout stayed inside the assumed width."""
        ws = widths(label, **kw)
        if ws is None:
            return
        if max(ws) <= ASSUMED:
            ok("%s -> falls back inside %d columns %s" % (label, ASSUMED, ws))
        else:
            bad("%s: lines are %s columns, want none wider than the assumed %d"
                % (label, ws, ASSUMED))

    # 1. The override is the highest-precedence source, and the only one that
    #    works when every form of detection has failed. This is the escape
    #    hatch: whatever else is broken, this must put the line where asked.
    spans("override alone", 150, CLAUDE_STATUSLINE_COLS=150)

    # 2. ...and it beats both of the sources that could disagree with it.
    spans("override beats COLUMNS", 150, cols=90, CLAUDE_STATUSLINE_COLS=150)
    with live_pty(240) as dev:
        spans("override beats the parent's terminal", 150,
              ps_table=tree(dev), CLAUDE_STATUSLINE_COLS=150)

    # 3. A non-width override is ignored rather than obeyed or fatal, so a typo
    #    in a shell profile degrades to normal detection.
    for junk in ("0", "abc", "-5", "", "1e3", "12.5", " 120"):
        spans("override %-6r ignored, COLUMNS used" % junk, 100,
              cols=100, CLAUDE_STATUSLINE_COLS=junk)

    # 4. COLUMNS=0. This is the case that was indistinguishable from unset and
    #    is what actually arrives: bash sets COLUMNS=0 when it has no terminal,
    #    and 0 is not a width.
    unknown("COLUMNS=0 with no terminal anywhere", cols=0)
    with live_pty(240) as dev:
        spans("COLUMNS=0 defers to the parent's terminal", 240,
              cols=0, ps_table=tree(dev))

    # 5. The parent's terminal -- the route that makes this work under Claude
    #    Code, where the status line has no terminal of its own but the process
    #    that spawned it does.
    for term in (100, 132, 240):
        with live_pty(term) as dev:
            spans("parent's terminal, %d columns" % term, term, ps_table=tree(dev))

    # 6. The walk climbs past processes without a terminal (Claude Code may
    #    spawn us through a shell) but is bounded, so a strange process tree
    #    cannot cost a fork per ancestor all the way up to init.
    with live_pty(180) as dev:
        spans("terminal 4 ancestors up", 180, ps_table=tree("??", "??", "??", dev))
        unknown("terminal 5 ancestors up is past the bound",
                ps_table=tree("??", "??", "??", "??", dev))

    # 7. Things `ps` can say that are not a usable terminal.
    unknown("parent has no terminal (macOS '??')", ps_table=tree("??"))
    unknown("parent has no terminal (Linux '?')", ps_table=tree("?"))
    unknown("terminal device does not exist", ps_table=tree("ttys999"))
    unknown("terminal name is an absolute path", ps_table=tree("/dev/tty"))
    unknown("ps knows nothing about our parent", ps_table="")

    # 8. COLUMNS still wins over the terminal when Claude Code does set it: a
    #    version that reports a width knows better than we do how much of the
    #    window the status line gets.
    with live_pty(240) as dev:
        spans("COLUMNS beats the parent's terminal", 120, cols=120, ps_table=tree(dev))


SPECIALISTS = ["hardware-engineer", "incident-responder", "security-reviewer",
               "system-designer", "craft-engineer", "spike-engineer",
               "infra-engineer", "orchestrator"]


def task(**over):
    t = {
        "id": "task-1", "name": "craft-engineer", "type": "craft-engineer",
        "status": "running", "description": "extracting the shared width helpers",
        "label": "craft", "startTime": 1757500000,
        "model": "claude-opus-5", "effort": "high",
        "contextWindowSize": 200000, "tokenCount": 63400,
        "cwd": "%s/projects/mjcramer/envious.craft-engineer" % HOME,
    }
    t.update(over)
    return t


def run_sub(payload_text, cols):
    return subprocess.run([BASH, SUBSCRIPT], input=payload_text, capture_output=True,
                          text=True, env=script_env(cols), cwd=REPO,
                          start_new_session=True)


def check_sub(name, tasks, cols, want_intact=True):
    """cols is the payload's `columns`; None means the field is absent."""
    payload = {"tasks": tasks}
    if cols is not None:
        payload["columns"] = cols
    # With no `columns` and no COLUMNS in the environment the script falls back
    # to its assumed 80 less the reserve; that is the width it must respect.
    target = cols if cols is not None else 78
    label = "%s @ %s" % (name, cols if cols is not None else "no columns field")

    p = run_sub(json.dumps(payload), None)
    if p.returncode != 0 or p.stderr.strip():
        bad("%s: exit %d, stderr %s" % (label, p.returncode, p.stderr.strip()[:120]))
        return

    emitted = {}
    for line in p.stdout.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            bad("%s: emitted a line that is not JSON: %r" % (label, line[:100]))
            return
        if set(obj) != {"id", "content"}:
            bad("%s: row object has keys %s, want id+content" % (label, sorted(obj)))
            return
        if obj["id"] in emitted:
            bad("%s: emitted id %r twice" % (label, obj["id"]))
            return
        emitted[obj["id"]] = obj["content"]

    for t in tasks:
        tid = t.get("id")
        if not tid:
            # No id means the row cannot be addressed; it must keep the default.
            continue
        if tid not in emitted:
            bad("%s: task %r got no row" % (label, tid))
            return
        c = emitted[tid]
        if not c:
            bad("%s: task %r got empty content, which hides the row" % (label, tid))
            return
        # A row body is a single line by contract.
        if any(ch in c for ch in "\n\r\t"):
            bad("%s: task %r content carries a raw control character" % (label, tid))
            return
        w = viswidth(c)
        # `columns` is documented as the *usable* row width, so filling it
        # exactly is allowed here -- unlike the main line, which is measured
        # against a whole-terminal width.
        if w > target:
            bad("%s: task %r row is %d columns, target %d\n        |%s|"
                % (label, tid, w, target, plain(c)))
            return
        if want_intact and target >= 100:
            if t.get("name") and t["name"] not in plain(c):
                bad("%s: task %r lost its name with room to spare\n        |%s|"
                    % (label, tid, plain(c)))
                return
            tail = (t.get("cwd") or "").rsplit("/", 1)[-1]
            if tail and tail not in plain(c):
                bad("%s: task %r lost its worktree name with room to spare\n        |%s|"
                    % (label, tid, plain(c)))
                return
        # Same as the main line: when the path has to be clipped, the end of it
        # is what identifies the worktree, so that is the end that must survive.
        if target < 60:
            tail = (t.get("cwd") or "").rsplit("/", 1)[-1]
            if len(tail) >= 8 and tail[-8:] not in plain(c):
                bad("%s: task %r clipped the directory from the wrong end\n        |%s|"
                    % (label, tid, plain(c)))
                return

    ok("%s (%d row(s))" % (label, len(emitted)))


def subagent_suite():
    # One row per specialist, each in its own worktree -- the case that matters.
    rows = [task(id="t%d" % i, name=a, type=a,
                 cwd="%s/projects/mjcramer/envious.%s" % (HOME, a))
            for i, a in enumerate(SPECIALISTS)]
    for cols in WIDTHS:
        check_sub("all specialists", rows, cols)
    check_sub("all specialists", rows, None)

    # A deep path, and one whose tail is not an agent worktree.
    deep = [task(id="d1", name="system-designer", type="system-designer",
                 cwd="%s/projects/mjcramer/envious/dot_local/private_share/"
                     "templates/scala-pekko/src/main/scala" % HOME)]
    for cols in WIDTHS:
        check_sub("deep path", deep, cols)

    # Fields absent or null, one at a time and all at once.
    sparse = [
        task(id="n1", description=None, model=None, effort=None,
             contextWindowSize=None, tokenCount=None),
        task(id="n2", status=None, type=None, label=None),
        {"id": "n3", "name": "infra-engineer",
         "cwd": "%s/projects/mjcramer/envious.infra-engineer" % HOME},
        {"id": "n4"},
    ]
    for cols in WIDTHS:
        check_sub("sparse tasks", sparse, cols, want_intact=False)

    # A description carrying the characters that would break the JSON-lines
    # contract if they reached the output.
    nasty = [task(id="x1", description="line one\tand\nline two\r\ndone")]
    check_sub("control chars in description", nasty, 200)
    check_sub("control chars in description", nasty, 60)

    # A task with no id keeps the default rendering and must not be emitted.
    p = run_sub(json.dumps({"columns": 120, "tasks": [task(id=""), task(id="keep")]}), None)
    ids = [json.loads(l)["id"] for l in p.stdout.splitlines()]
    if ids == ["keep"]:
        ok("task with no id is left to the default rendering")
    else:
        bad("task with no id: emitted %r, want ['keep']" % (ids,))

    # Nothing to say means say nothing: every one of these must leave all rows
    # at their default rendering rather than emit anything.
    for name, text in [("malformed", "not json"), ("truncated", '{"tasks": ['),
                       ("no tasks key", '{"columns": 120}'),
                       ("empty tasks", '{"columns": 120, "tasks": []}'),
                       ("empty payload", ""), ("array payload", "[1,2,3]")]:
        p = run_sub(text, None)
        if p.returncode == 0 and not p.stdout.strip() and not p.stderr.strip():
            ok("%-14s payload emits nothing, exit 0" % name)
        else:
            bad("%s payload gave exit %d, stdout %r, stderr %r"
                % (name, p.returncode, p.stdout[:60], p.stderr[:60]))


# Every bash on the box, because macOS ships 3.2 at /bin/bash and that is what
# the script has to keep working under even when a newer bash is first on PATH.
for BASH in dedupe([shutil.which("bash"), "/bin/bash", "/usr/local/bin/bash",
                    "/opt/homebrew/bin/bash"]):
    print("statusline layout tests (%s, %s)"
          % (os.path.relpath(SCRIPT, REPO), bash_version(BASH)))
    suite()
    pty_suite()
    width_source_suite()
    # Skipped when an alternate main script was named on the command line, since
    # the two are versioned together.
    if len(sys.argv) <= 1 and os.path.exists(SUBSCRIPT):
        print("subagent row tests (%s, %s)"
              % (os.path.relpath(SUBSCRIPT, REPO), bash_version(BASH)))
        subagent_suite()

shutil.rmtree(_shim_dir, ignore_errors=True)

print("statusline layout tests: %s"
      % ("FAILED (%d)" % failures if failures else "all good"))
sys.exit(1 if failures else 0)
