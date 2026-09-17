#!/usr/bin/env python3
"""Tests for SSH commit signing, across the two source files that set it up.

  private_dot_config/git/readonly_config.tmpl            declares the signing
  private_dot_ssh/run_onchange_after_setup-ssh-identity.sh.tmpl  makes the key

Both are chezmoi templates, so the suite renders them with `chezmoi
execute-template` and tests the rendered output -- it never applies anything
and never touches the real ~. The script runs against a throwaway HOME with a
throwaway key; no real key material is read or written.

The properties worth holding onto:

  declares   the rendered git config actually parses, and git reads back
             gpg.format=ssh, commit.gpgsign=true, and a signingkey
  absolute   both paths are absolute, not "~/..." -- git 2.55 expands the tilde
             in user.signingkey but older gits on the Linux target do not, and
             that failure surfaces as a confusing signing error
  generates  a fresh HOME comes out with a key and an allowed_signers naming
             the configured email as principal
  idempotent a second run changes nothing, a stale allowed_signers is rewritten
  degrades   a missing pubkey warns and still exits 0, because the private key
             is still usable and only local verification is affected
  signs      end to end: with that config and that key, a commit is signed and
             verifies as a good signature for the configured email

Run:  tests/ssh-signing-test.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_TMPL = os.path.join(REPO, "private_dot_config", "git", "readonly_config.tmpl")
SCRIPT_TMPL = os.path.join(
    REPO, "private_dot_ssh", "run_onchange_after_setup-ssh-identity.sh.tmpl")

failures = 0


def ok(msg):
    print("  ok    %s" % msg)


def bad(msg):
    global failures
    failures += 1
    print("  FAIL  %s" % msg)


def render(path):
    """The template as chezmoi would write it, using this repo as the source."""
    with open(path) as f:
        p = subprocess.run(["chezmoi", "execute-template", "--source", REPO],
                           stdin=f, capture_output=True, text=True)
    if p.returncode != 0:
        bad("%s did not render: %s" % (os.path.basename(path), p.stderr.strip()))
        return None
    return p.stdout


def git(args, home=None, cwd=None, config=None):
    env = dict(os.environ)
    if home:
        env["HOME"] = home
    if config:
        env["GIT_CONFIG_GLOBAL"] = config
    # A stray system config would mask what the rendered file says.
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return subprocess.run(["git"] + args, cwd=cwd, env=env,
                          capture_output=True, text=True)


def config_suite(tmp, rendered):
    path = os.path.join(tmp, "gitconfig")
    with open(path, "w") as f:
        f.write(rendered)

    want = {
        "gpg.format": "ssh",
        "commit.gpgsign": "true",
        "user.signingkey": None,
        "gpg.ssh.allowedsignersfile": None,
    }
    p = git(["config", "-f", path, "--list"])
    if p.returncode != 0:
        bad("rendered git config does not parse: %s" % p.stderr.strip())
        return
    got = dict(line.split("=", 1) for line in p.stdout.splitlines() if "=" in line)

    for key, value in want.items():
        if key not in got:
            bad("git config is missing %s" % key)
        elif value is not None and got[key] != value:
            bad("git config has %s=%s, want %s" % (key, got[key], value))
        else:
            ok("git config sets %s" % key)

    for key in ("user.signingkey", "gpg.ssh.allowedsignersfile"):
        value = got.get(key, "")
        if value.startswith("~"):
            bad("%s is tilde-relative (%s); older git will not expand it" % (key, value))
        elif not value.startswith("/"):
            bad("%s is not an absolute path (%s)" % (key, value))
        else:
            ok("%s is absolute" % key)


def script_suite(tmp, rendered, email):
    path = os.path.join(tmp, "setup-ssh-identity.sh")
    with open(path, "w") as f:
        f.write(rendered)
    os.chmod(path, 0o755)

    home = os.path.join(tmp, "home")
    os.makedirs(os.path.join(home, ".ssh"), mode=0o700)
    key = os.path.join(home, ".ssh", "id_ed25519")
    pub = key + ".pub"
    signers = os.path.join(home, ".ssh", "allowed_signers")

    def run(label):
        env = dict(os.environ, HOME=home)
        p = subprocess.run(["bash", path], env=env, capture_output=True, text=True)
        if p.returncode != 0:
            bad("%s: script exited %d: %s" % (label, p.returncode, p.stderr.strip()))
        return p.stdout

    out = run("fresh HOME")
    if not os.path.exists(key) or not os.path.exists(pub):
        bad("fresh HOME: no key generated")
        return None, None
    ok("fresh HOME generates a key")

    if not os.path.exists(signers):
        bad("fresh HOME: no allowed_signers written")
        return None, None
    with open(signers) as f:
        first = f.read()
    if not first.startswith(email + " ssh-ed25519 "):
        bad("allowed_signers does not name %s as an ed25519 principal: %r" % (email, first))
    else:
        ok("allowed_signers names %s" % email)

    run("second run")
    with open(signers) as f:
        if f.read() != first:
            bad("second run rewrote allowed_signers")
        else:
            ok("second run is idempotent")

    with open(signers, "w") as f:
        f.write("stale@example.com ssh-ed25519 AAAA\n")
    run("stale allowed_signers")
    with open(signers) as f:
        if f.read() != first:
            bad("a stale allowed_signers was not repaired")
        else:
            ok("a stale allowed_signers is repaired")

    # The private key alone is still good for auth and for signing, so this is a
    # warning and a zero exit, not an aborted apply.
    os.rename(pub, pub + ".away")
    out = run("missing pubkey")
    if "WARNING" not in out:
        bad("a missing pubkey passed without a warning")
    else:
        ok("a missing pubkey warns and does not abort")
    os.rename(pub + ".away", pub)

    return home, key


def signing_suite(tmp, rendered, home, email):
    """The whole point: does a commit under this config come out verifiable."""
    # The rendered config names the real home; point it at the throwaway one so
    # the key this suite generated is the one git is told to sign with.
    config = os.path.join(tmp, "gitconfig-fakehome")
    with open(config, "w") as f:
        f.write(rendered.replace(os.path.expanduser("~") + "/", home + "/"))

    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    git(["init", "-q", "."], cwd=repo)
    open(os.path.join(repo, "a.txt"), "w").write("synthetic\n")
    git(["add", "a.txt"], cwd=repo, config=config)
    p = git(["commit", "-m", "signed"], cwd=repo, home=home, config=config)
    if p.returncode != 0:
        bad("commit did not sign: %s" % (p.stderr.strip() or p.stdout.strip()))
        return
    ok("a commit is signed with no further configuration")

    p = git(["log", "--show-signature", "-1"], cwd=repo, home=home, config=config)
    if not re.search(r'Good "git" signature for %s' % re.escape(email), p.stdout):
        bad("signature does not verify locally: %s"
            % " ".join(p.stdout.split("\n")[1:3]))
    else:
        ok("the signature verifies against allowed_signers")


print("ssh commit signing tests")

if not shutil.which("chezmoi"):
    print("ssh commit signing tests: SKIPPED (chezmoi not on PATH)")
    sys.exit(0)

tmp = tempfile.mkdtemp(prefix="ssh-signing-test.")
try:
    config_rendered = render(CONFIG_TMPL)
    script_rendered = render(SCRIPT_TMPL)
    if config_rendered is None or script_rendered is None:
        sys.exit(1)

    # The email is data, not a constant: .chezmoi.toml.tmpl picks it by hostname.
    m = re.search(r"^\s*email = \"(.+)\"", config_rendered, re.M)
    if not m:
        bad("no user.email in the rendered git config")
        sys.exit(1)
    email = m.group(1)

    config_suite(tmp, config_rendered)
    home, _ = script_suite(tmp, script_rendered, email)
    if home:
        signing_suite(tmp, config_rendered, home, email)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("ssh commit signing tests: %s"
      % ("FAILED (%d)" % failures if failures else "all good"))
sys.exit(1 if failures else 0)
