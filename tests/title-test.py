#!/usr/bin/env python3
"""Behaviour tests for the Claude Code session-title hook.

  dot_claude/hooks/executable_title.py.tmpl   deploys to ~/.claude/hooks/title.py
  .chezmoitemplates/python-shebang            the interpreter line it is rendered with

The source file is valid Python as it stands (its only template syntax is the
shebang, a comment to Python), so the suite runs it by path under this
interpreter with the deployed flags, -ISB, and feeds it the JSON Claude Code
sends on stdin. HOME points at a throwaway directory holding a synthetic
settings.json, so the real ~/.claude is never read; the git repos are made
fresh under a tempdir with no global config.

The contract, as properties:

  names      SessionStart (startup, resume, fork) and UserPromptSubmit emit
             hookSpecificOutput.sessionTitle = "<repo> <agent>" under the
             hookEventName of the event that ran, while the session has no
             custom title (session_title absent or empty)
  keeps      a custom title is never overwritten, and SessionStart after
             /clear or a compaction gets no sessionTitle at all
  tracks     every event carries terminalSequence (OSC 0, the same title) and
             Stop and CwdChanged carry nothing else
  resolves   <repo> is the main checkout's directory name from the checkout,
             a subdirectory, a linked worktree and a subdirectory of one;
             outside git it is the cwd's own name
  falls back <agent> is agent_type, else settings.json's "agent", else default
  fails open malformed stdin, no git on PATH, a missing cwd, a missing or
             broken settings.json: exit 0, nothing on stderr, and either one
             well-formed object or nothing on stdout
  sanitises  control characters in a directory or agent name never reach the
             OSC sequence or the session title, and the title is bounded
  renders    with chezmoi on PATH, the partial gives this OS/arch's interpreter
             and the rendered file runs as deployed, by its own shebang
  wired      settings.json calls ~/.claude/hooks/title.py directly on all four
             events and nothing still names title.sh

Run:  tests/title-test.py
"""

import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "dot_claude", "hooks", "executable_title.py.tmpl")
PARTIAL = os.path.join(REPO, ".chezmoitemplates", "python-shebang")
SETTINGS = os.path.join(REPO, "dot_claude", "settings.json")
EVENTS = ("SessionStart", "UserPromptSubmit", "Stop", "CwdChanged")

failures = 0


def ok(msg):
    print("  ok    %s" % msg)


def bad(msg):
    global failures
    failures += 1
    print("  FAIL  %s" % msg)


def osc(title):
    return "\x1b]0;%s\x07" % title


# ------------------------------------------------------------------ fixtures

TMP = tempfile.mkdtemp(prefix="title-test-")
HOME = os.path.join(TMP, "home")
os.makedirs(os.path.join(HOME, ".claude"))
with open(os.path.join(HOME, ".claude", "settings.json"), "w") as fh:
    json.dump({"agent": "orchestrator"}, fh)

GIT_ENV = dict(os.environ, HOME=HOME,
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="test@localhost",
               GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="test@localhost")


def git(*args):
    subprocess.run(["git", *args], env=GIT_ENV, check=True, capture_output=True)


MAIN = os.path.join(TMP, "widget")
SUBDIR = os.path.join(MAIN, "src", "deep")
WORKTREE = os.path.join(TMP, "widget.craft-engineer.fix-the-thing")
WT_SUBDIR = os.path.join(WORKTREE, "src")
PLAIN = os.path.join(TMP, "plain-dir")
os.makedirs(SUBDIR)
os.makedirs(PLAIN)
git("init", "-q", "-b", "main", MAIN)
git("-C", MAIN, "commit", "-q", "--allow-empty", "-m", "init")
git("-C", MAIN, "worktree", "add", "-q", "-b", "agent/craft-engineer/fix-the-thing", WORKTREE)
os.makedirs(WT_SUBDIR)


def run(payload, home=HOME, path=None, cwd=TMP, script=None):
    """The hook as deployed: by path under -ISB, payload on stdin, HOME at a scratch dir.

    `payload` is sent as given when it is a string, else JSON-encoded. `script`
    names an already rendered, executable copy to run by its own shebang.
    """
    env = dict(os.environ, HOME=home)
    if path is not None:
        env["PATH"] = path
    text = payload if isinstance(payload, str) else json.dumps(payload)
    cmd = [script] if script else [sys.executable, "-ISB", SCRIPT]
    return subprocess.run(cmd, check=False, input=text, capture_output=True, text=True,
                          env=env, cwd=cwd)


def output(p, what):
    """The one JSON object the hook printed, or None after a bad()."""
    if p.returncode != 0 or p.stderr:
        bad("%s: exit %d, stderr %r" % (what, p.returncode, p.stderr[:120]))
        return None
    lines = p.stdout.split("\n")
    if len(lines) != 2 or lines[1] != "" or not lines[0].startswith("{"):
        bad("%s: want exactly one JSON line on stdout, got %r" % (what, p.stdout[:120]))
        return None
    try:
        out = json.loads(lines[0])
    except ValueError as e:
        bad("%s: stdout is not JSON (%s): %r" % (what, e, lines[0][:120]))
        return None
    if not isinstance(out, dict):
        bad("%s: want a JSON object, got %r" % (what, lines[0][:120]))
        return None
    return out


def event(name, cwd=MAIN, **fields):
    return dict(hook_event_name=name, cwd=cwd, session_id="synthetic", **fields)


# -------------------------------------------------------------------- suites

def names_suite():
    want = "widget orchestrator"
    for ev, extra in (("SessionStart", {"source": "startup"}),
                      ("SessionStart", {"source": "resume"}),
                      ("SessionStart", {"source": "fork"}),
                      ("UserPromptSubmit", {"prompt": "hello"})):
        label = "%s %s" % (ev, extra.get("source", ""))
        out = output(run(event(ev, **extra)), label)
        if out is None:
            continue
        hso = {"hookEventName": ev, "sessionTitle": want}
        if (set(out) == {"terminalSequence", "hookSpecificOutput"}
                and out["hookSpecificOutput"] == hso
                and out["terminalSequence"] == osc(want)):
            ok("%-26s names the session %r and sets the tab title" % (label, want))
        else:
            bad("%s gave %r, want hookSpecificOutput %r" % (label, out, hso))

    # An empty custom title is no custom title.
    out = output(run(event("UserPromptSubmit", session_title="")), "empty session_title")
    if out is not None:
        if out.get("hookSpecificOutput", {}).get("sessionTitle") == want:
            ok("an empty session_title counts as unset")
        else:
            bad("empty session_title suppressed the name: %r" % out)


def keeps_suite():
    for ev, extra in (("SessionStart", {"source": "startup"}),
                      ("UserPromptSubmit", {})):
        out = output(run(event(ev, session_title="my own name", **extra)), ev + " custom")
        if out is None:
            continue
        if "hookSpecificOutput" not in out and out.get("terminalSequence") == osc("widget orchestrator"):
            ok("%-18s keeps a custom title, still sets the tab" % ev)
        else:
            bad("%s with a custom title gave %r" % (ev, out))

    for source in ("clear", "compact", None):
        extra = {} if source is None else {"source": source}
        out = output(run(event("SessionStart", **extra)), "SessionStart %s" % source)
        if out is None:
            continue
        if "hookSpecificOutput" not in out and "terminalSequence" in out:
            ok("SessionStart source=%-8s no sessionTitle, tab title only" % source)
        else:
            bad("SessionStart source=%s gave %r" % (source, out))


def tracks_suite():
    for ev in ("Stop", "CwdChanged", "Notification"):
        out = output(run(event(ev)), ev)
        if out is None:
            continue
        if out == {"terminalSequence": osc("widget orchestrator")}:
            ok("%-18s terminalSequence only" % ev)
        else:
            bad("%s gave %r, want terminalSequence alone" % (ev, out))


def resolves_suite():
    cases = ((MAIN, "widget", "the main checkout"),
             (SUBDIR, "widget", "a subdirectory of the checkout"),
             (WORKTREE, "widget", "a linked worktree"),
             (WT_SUBDIR, "widget", "a subdirectory of a linked worktree"),
             (PLAIN, "plain-dir", "a directory outside git"),
             (PLAIN + "/", "plain-dir", "a cwd with a trailing slash"))
    for cwd, repo, what in cases:
        out = output(run(event("Stop", cwd=cwd)), what)
        if out is None:
            continue
        if out.get("terminalSequence") == osc(repo + " orchestrator"):
            ok("%-38s -> %s" % (what, repo))
        else:
            bad("%s gave %r, want repo %r" % (what, out, repo))

    # No cwd in the payload: the process's own directory stands in.
    out = output(run({"hook_event_name": "Stop"}, cwd=WORKTREE), "no cwd field")
    if out is not None:
        if out.get("terminalSequence") == osc("widget orchestrator"):
            ok("a payload without cwd falls back to the process cwd")
        else:
            bad("no cwd field gave %r" % out)


def agent_suite():
    def check(what, want, **kw):
        out = output(run(event("Stop", **kw.pop("fields", {})), **kw), what)
        if out is None:
            return
        if out.get("terminalSequence") == osc("widget " + want):
            ok("%-42s -> %s" % (what, want))
        else:
            bad("%s gave %r, want agent %r" % (what, out, want))

    check("agent_type in the payload", "craft-engineer", fields={"agent_type": "craft-engineer"})
    check("no agent_type, settings.json agent", "orchestrator")
    check("empty agent_type, settings.json agent", "orchestrator", fields={"agent_type": ""})
    check("agent_type beats settings.json", "security-reviewer",
          fields={"agent_type": "security-reviewer"})

    for what, body in (("settings.json without an agent key", '{"model": "opus"}'),
                       ("settings.json with a non-string agent", '{"agent": 7}'),
                       ("malformed settings.json", '{"agent": ')):
        home = tempfile.mkdtemp(prefix="home-", dir=TMP)
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "settings.json"), "w") as fh:
            fh.write(body)
        check(what, "default", home=home)
    home = tempfile.mkdtemp(prefix="home-", dir=TMP)
    check("no ~/.claude at all", "default", home=home)


def fails_open_suite():
    for what, text in (("not JSON", "nope"), ("empty stdin", ""), ("truncated JSON", '{"cwd": '),
                       ("a JSON array", "[1, 2]"), ("JSON null", "null")):
        p = run(text)
        if p.returncode == 0 and p.stdout == "" and p.stderr == "":
            ok("%-18s exit 0, silent" % what)
        else:
            bad("%s gave exit %d, stdout %r, stderr %r"
                % (what, p.returncode, p.stdout[:60], p.stderr[:60]))

    empty = tempfile.mkdtemp(prefix="nopath-", dir=TMP)
    out = output(run(event("Stop", cwd=WORKTREE), path=empty), "no git on PATH")
    if out is not None:
        if out.get("terminalSequence") == osc("widget.craft-engineer.fix-the-thing orchestrator"):
            ok("no git on PATH falls back to the directory name")
        else:
            bad("no git on PATH gave %r" % out)

    missing = os.path.join(TMP, "gone", "away")
    out = output(run(event("Stop", cwd=missing)), "missing cwd")
    if out is not None:
        if out.get("terminalSequence") == osc("away orchestrator"):
            ok("a cwd that does not exist still gives its name")
        else:
            bad("missing cwd gave %r" % out)

    out = output(run(event("Stop", cwd=5)), "non-string cwd")
    if out is not None and "terminalSequence" in out:
        ok("a non-string cwd is ignored, not fatal")
    elif out is not None:
        bad("non-string cwd gave %r" % out)

    pycache = os.path.join(os.path.dirname(SCRIPT), "__pycache__")
    if os.path.exists(pycache):
        bad("running the source left %s behind (-B is not in effect)" % pycache)
    else:
        ok("no __pycache__ beside the source after every run")


def sanitises_suite():
    # A directory name carrying ESC, BEL, a newline, DEL and a C1 control: each
    # could end or forge a terminal sequence, or land in the persisted session name.
    crafted = os.path.join(TMP, "evil\x1b]52;c;x\x07\nline2\x7f\x9b[31mred")
    os.makedirs(crafted)
    bare = "evil]52;c;xline2[31mred orchestrator"
    out = output(run(event("SessionStart", source="startup", cwd=crafted)), "crafted cwd")
    if out is not None:
        seq, title = out.get("terminalSequence", ""), out.get("hookSpecificOutput", {}).get("sessionTitle")
        if seq == osc(bare) and title == bare:
            ok("control characters in a directory name are stripped from both outputs")
        else:
            bad("crafted cwd gave %r" % out)
        body = seq[len("\x1b]0;"):-1] if seq.startswith("\x1b]0;") and seq.endswith("\x07") else None
        if body is not None and not re.search(r"[\x00-\x1f\x7f-\x9f]", body):
            ok("terminalSequence is still one OSC 0 ... BEL with a clean body")
        else:
            bad("terminalSequence is not a single clean OSC 0: %r" % seq)

    out = output(run(event("Stop", agent_type="a\x07\x1b[1mb")), "crafted agent_type")
    if out is not None:
        if out.get("terminalSequence") == osc("widget a[1mb"):
            ok("control characters in agent_type are stripped too")
        else:
            bad("crafted agent_type gave %r" % out)

    out = output(run(event("Stop", agent_type="x" * 500)), "long agent_type")
    if out is not None:
        body = out.get("terminalSequence", "")[len("\x1b]0;"):-1]
        if len(body) == 120 and body.startswith("widget x"):
            ok("the title is capped at 120 characters")
        else:
            bad("long title gave %d characters: %r" % (len(body), body[:40]))


def expected_shebang():
    system, machine = platform.system(), platform.machine()
    if system == "Darwin":
        return "#!%s -ISB" % ("/usr/local/bin/python3" if machine == "x86_64"
                               else "/opt/homebrew/bin/python3")
    if system == "Linux":
        return "#!/usr/bin/python3 -ISB"
    return None


def renders_suite():
    with open(SCRIPT) as fh:
        first = fh.readline().rstrip("\n")
        rest = fh.read()
    if first == '#!{{ template "python-shebang" . }}':
        ok("line 1 is the shared shebang partial")
    else:
        bad("line 1 is %r, want the python-shebang partial" % first)
    if "{{" in rest or "}}" in rest:
        bad("template syntax after line 1 would break the render")
    else:
        ok("no template syntax after line 1")
    if not os.path.exists(PARTIAL):
        bad("%s is missing" % os.path.relpath(PARTIAL, REPO))
        return

    if not shutil.which("chezmoi"):
        print("  skip  chezmoi not on PATH: shebang render and deployed run not checked")
        return
    want = expected_shebang()
    p = subprocess.run(["chezmoi", "execute-template", "--source", REPO, first],
                       check=False, capture_output=True, text=True)
    if p.returncode != 0:
        bad("chezmoi did not render the shebang: %s" % p.stderr.strip())
        return
    got = p.stdout.strip()
    if want is None:
        print("  skip  no expected shebang for %s/%s; rendered %r"
              % (platform.system(), platform.machine(), got))
    elif got == want:
        ok("partial renders %s on %s/%s" % (got, platform.system(), platform.machine()))
    else:
        bad("partial rendered %r, want %r" % (got, want))

    interpreter = got[2:].split()[0]
    if not os.access(interpreter, os.X_OK):
        print("  skip  %s is not installed here; deployed run not checked" % interpreter)
        return
    rendered = os.path.join(TMP, "title.py")
    with open(SCRIPT) as src, open(rendered, "w") as dst:
        subprocess.run(["chezmoi", "execute-template", "--source", REPO],
                       stdin=src, stdout=dst, check=True)
    os.chmod(rendered, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    payload = event("SessionStart", source="startup", cwd=WORKTREE)
    deployed = output(run(payload, script=rendered), "deployed run")
    reference = output(run(payload), "reference run")
    if deployed is not None and reference is not None:
        if deployed == reference and deployed.get("hookSpecificOutput", {}).get("sessionTitle") == "widget orchestrator":
            ok("rendered title.py runs by its own shebang and agrees with the source run")
        else:
            bad("deployed run %r differs from the source run %r" % (deployed, reference))


def wired_suite():
    with open(SETTINGS) as fh:
        text = fh.read()
    hooks = json.loads(text).get("hooks", {})
    for ev in EVENTS:
        commands = [h.get("command") for m in hooks.get(ev, []) for h in m.get("hooks", [])]
        if "~/.claude/hooks/title.py" in commands:
            ok("settings.json %-16s calls ~/.claude/hooks/title.py directly" % ev)
        else:
            bad("settings.json %s does not call ~/.claude/hooks/title.py: %r" % (ev, commands))
    if "title.sh" in text:
        bad("settings.json still names title.sh")
    else:
        ok("nothing in settings.json names title.sh")


print("session-title hook tests (%s, python %s)"
      % (os.path.relpath(SCRIPT, REPO), platform.python_version()))
try:
    names_suite()
    keeps_suite()
    tracks_suite()
    resolves_suite()
    agent_suite()
    fails_open_suite()
    sanitises_suite()
    renders_suite()
    wired_suite()
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("session-title hook tests: %s"
      % ("FAILED (%d)" % failures if failures else "all good"))
sys.exit(1 if failures else 0)
