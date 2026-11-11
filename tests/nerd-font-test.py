#!/usr/bin/env python3
"""Behaviour tests for the Linux Nerd Font install script.

  .chezmoiscripts/run_onchange_after_install-nerd-font.sh.tmpl
  .chezmoidata/packages.yaml                  packages.nerd_font, the pin

The template is rendered with chezmoi as if on Linux (--override-data sets
.chezmoi.os and, per case, the pin) and the result is run with bash against a
throwaway HOME. PATH holds only a directory of symlinks to the handful of
tools the script needs plus two stubs: `curl` copies a tiny synthetic archive
built here instead of touching the network, and `fc-cache` records its
arguments. Nothing is downloaded and the real font directories and font cache
are never touched.

The contract, as properties:

  renders    nothing at all on macOS; on Linux a bash script carrying the pin
             from packages.yaml, clean under shellcheck when it is on PATH
  pins       packages.nerd_font names a release tag, a .tar.xz asset and a
             sha256, and apt provides the tools the script cannot assume
  installs   every .ttf of the archive, and only those, lands in
             <data home>/fonts/<name>/, fetched from that release's URL; the
             font cache is refreshed for that directory
  repeats    a second run downloads nothing and changes nothing
  upgrades   a new pin replaces the directory, leaving no file of the old one
  refuses    a checksum mismatch, a failed download or an archive without
             fonts exits non-zero and leaves an existing install as it was
  degrades   without fc-cache the fonts are still installed; without a tool
             it needs, it says which and installs nothing

Run:  tests/nerd-font-test.py
"""

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, ".chezmoiscripts", "run_onchange_after_install-nerd-font.sh.tmpl")
PACKAGES = os.path.join(REPO, ".chezmoidata", "packages.yaml")

# Everything the rendered script runs besides bash builtins, curl and fc-cache.
TOOLS = ("basename", "cat", "chmod", "cut", "mkdir", "mktemp", "mv", "rm",
         "sha256sum", "tar", "xz")
# The stubs' own needs.
STUB_TOOLS = ("cp",)

CURL_STUB = """#!/bin/sh
# Stands in for: curl -fsSL --retry 3 -o <dest> <url>
while [ $# -gt 1 ]; do
    [ "$1" = "-o" ] && dest=$2
    shift
done
echo "$1" >> "$STUB_LOG.curl"
[ -n "${STUB_CURL_FAIL:-}" ] && exit 22
cp "$STUB_ARCHIVE" "$dest"
"""

FC_CACHE_STUB = """#!/bin/sh
echo "$*" >> "$STUB_LOG.fc-cache"
"""

failures = 0


def ok(msg):
    print("  ok    %s" % msg)


def bad(msg):
    global failures
    failures += 1
    print("  FAIL  %s" % msg)


def check(cond, msg, detail=""):
    if cond:
        ok(msg)
    else:
        bad("%s%s" % (msg, ": " + detail if detail else ""))


# ------------------------------------------------------------------ fixtures

TMP = tempfile.mkdtemp(prefix="nerd-font-test-")


def make_archive(name, members):
    """A synthetic .tar.xz of `members` (file names); returns (path, sha256)."""
    path = os.path.join(TMP, name)
    with tarfile.open(path, "w:xz") as tar:
        for member in members:
            data = ("synthetic %s\n" % member).encode()
            info = tarfile.TarInfo(member)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    with open(path, "rb") as fh:
        return path, hashlib.sha256(fh.read()).hexdigest()


def make_bin(name, without=()):
    """A PATH directory: symlinks to the real tools, plus the two stubs."""
    bindir = os.path.join(TMP, name)
    os.makedirs(bindir)
    for tool in TOOLS + STUB_TOOLS:
        if tool not in without:
            os.symlink(shutil.which(tool), os.path.join(bindir, tool))
    for stub, body in (("curl", CURL_STUB), ("fc-cache", FC_CACHE_STUB)):
        if stub not in without:
            path = os.path.join(bindir, stub)
            with open(path, "w") as fh:
                fh.write(body)
            os.chmod(path, 0o755)
    return bindir


def render(os_name="linux", **pin):
    """The template as chezmoi would render it on `os_name`, optionally re-pinned."""
    data = {"chezmoi": {"os": os_name}}
    if pin:
        data["packages"] = {"nerd_font": pin}
    with open(SCRIPT) as src:
        p = subprocess.run(["chezmoi", "execute-template", "--source", REPO,
                            "--override-data", json.dumps(data)],
                           stdin=src, check=False, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("chezmoi did not render the script: %s" % p.stderr.strip())
    return p.stdout


class Machine:
    """One throwaway home directory and the stub state that goes with it."""

    def __init__(self, name, bindir, xdg=True):
        self.root = os.path.join(TMP, name)
        self.home = os.path.join(self.root, "home")
        self.log = os.path.join(self.root, "log")
        os.makedirs(self.home)
        self.bindir = bindir
        self.xdg = os.path.join(self.root, "data") if xdg else None
        self.fonts_root = os.path.join(self.xdg or os.path.join(self.home, ".local", "share"),
                                       "fonts")

    def run(self, script_text, archive, curl_fails=False):
        script = os.path.join(self.root, "install-nerd-font.sh")
        with open(script, "w") as fh:
            fh.write(script_text)
        for suffix in (".curl", ".fc-cache"):
            if os.path.exists(self.log + suffix):
                os.remove(self.log + suffix)
        env = {"PATH": self.bindir, "HOME": self.home,
               "STUB_LOG": self.log, "STUB_ARCHIVE": archive}
        if self.xdg:
            env["XDG_DATA_HOME"] = self.xdg
        if curl_fails:
            env["STUB_CURL_FAIL"] = "1"
        return subprocess.run([shutil.which("bash"), script], env=env, cwd=self.root,
                              check=False, capture_output=True, text=True)

    def calls(self, stub):
        try:
            with open("%s.%s" % (self.log, stub)) as fh:
                return fh.read().splitlines()
        except FileNotFoundError:
            return []

    def tree(self):
        """Every path under the fonts root, relative to it, with file contents."""
        found = {}
        for dirpath, dirnames, filenames in os.walk(self.fonts_root):
            for entry in dirnames:
                found[os.path.relpath(os.path.join(dirpath, entry), self.fonts_root)] = None
            for entry in filenames:
                path = os.path.join(dirpath, entry)
                with open(path) as fh:
                    found[os.path.relpath(path, self.fonts_root)] = fh.read()
        return found


OLD_FONTS = ["Synth-Regular.ttf", "Synth-Bold.ttf", "SynthOld-Regular.ttf"]
NEW_FONTS = ["Synth-Regular.ttf", "Synth-Bold.ttf", "SynthNew-Regular.ttf"]
OLD_ARCHIVE, OLD_SHA = make_archive("old.tar.xz", OLD_FONTS + ["README.md", "LICENSE.txt"])
NEW_ARCHIVE, NEW_SHA = make_archive("new.tar.xz", NEW_FONTS + ["README.md"])
EMPTY_ARCHIVE, EMPTY_SHA = make_archive("empty.tar.xz", ["README.md"])


def pin(version, sha, name="SynthNerdFont"):
    return dict(name=name, version=version, archive="Synth.tar.xz", sha256=sha)


def installed(fonts, version, sha, name="SynthNerdFont"):
    """The tree() a complete install of `fonts` leaves behind."""
    want = {name: None,
            name + "/.installed": "%s Synth.tar.xz %s\n" % (version, sha)}
    want.update({"%s/%s" % (name, f): "synthetic %s\n" % f for f in fonts})
    return want


# -------------------------------------------------------------------- suites

def renders_suite():
    for os_name in ("darwin", "windows"):
        text = render(os_name)
        check(text.strip() == "", "renders nothing on %s, so chezmoi skips it" % os_name,
              repr(text[:80]))

    text = render("linux")
    check(text.startswith("#!/usr/bin/env bash\n"), "on linux line 1 is the bash shebang",
          repr(text[:40]))
    check("{{" not in text and "}}" not in text, "no template syntax survives the render")

    if not shutil.which("shellcheck"):
        print("  skip  shellcheck not on PATH: rendered script not linted")
        return
    p = subprocess.run(["shellcheck", "--shell=bash", "-"], input=text,
                       check=False, capture_output=True, text=True)
    check(p.returncode == 0, "the rendered script is clean under shellcheck", p.stdout[:400])


def pins_suite():
    with open(PACKAGES) as fh:
        packages = fh.read()
    # packages.yaml is read as text: the repo has no YAML parser to lean on and
    # the render below is the real consumer.
    block = packages.split("\n  nerd_font:\n", 1)
    if len(block) != 2:
        bad("packages.yaml has no packages.nerd_font block")
        return
    fields = dict(re.findall(r"^    (\w+): (\S+)$", block[1], re.M))
    check(re.fullmatch(r"v\d+\.\d+\.\d+", fields.get("version", "")) is not None,
          "version is a release tag", repr(fields.get("version")))
    check(fields.get("archive", "").endswith(".tar.xz"), "archive is a .tar.xz asset",
          repr(fields.get("archive")))
    check(re.fullmatch(r"[0-9a-f]{64}", fields.get("sha256", "")) is not None,
          "sha256 is 64 lowercase hex digits", repr(fields.get("sha256")))
    check(re.fullmatch(r"[A-Za-z0-9]+", fields.get("name", "")) is not None,
          "name is a plain directory name", repr(fields.get("name")))

    text = render("linux")
    for key in ("name", "version", "archive", "sha256"):
        line = '%s="%s"' % (key, fields.get(key))
        check(line in text.splitlines(), "the rendered script carries %s from packages.yaml" % key)

    apt = re.findall(r"^    - (\S+)$", packages.split("\n  apt:\n", 1)[1], re.M)
    for package in ("curl", "xz-utils", "fontconfig"):
        check(package in apt, "apt installs %s for the script" % package)


def installs_suite(bindir):
    m = Machine("fresh", bindir)
    p = m.run(render(**pin("v1.0.0", OLD_SHA)), OLD_ARCHIVE)
    check(p.returncode == 0, "a fresh install exits 0", p.stderr[:300])
    check(m.tree() == installed(OLD_FONTS, "v1.0.0", OLD_SHA),
          "every .ttf, and nothing else, is in fonts/SynthNerdFont/", repr(sorted(m.tree())))
    want_url = "https://github.com/ryanoasis/nerd-fonts/releases/download/v1.0.0/Synth.tar.xz"
    check(m.calls("curl") == [want_url], "it downloads the pinned release asset once",
          repr(m.calls("curl")))
    font_dir = os.path.join(m.fonts_root, "SynthNerdFont")
    check(m.calls("fc-cache") == ["-f " + font_dir], "it refreshes the font cache for that directory",
          repr(m.calls("fc-cache")))
    modes = {oct(os.stat(os.path.join(font_dir, f)).st_mode & 0o777) for f in OLD_FONTS}
    check(modes == {"0o644"}, "font files are 0644", repr(modes))

    before = m.tree()
    p = m.run(render(**pin("v1.0.0", OLD_SHA)), OLD_ARCHIVE)
    check(p.returncode == 0 and m.calls("curl") == [] and m.calls("fc-cache") == []
          and m.tree() == before,
          "a second run downloads nothing and changes nothing",
          "exit %d, curl %r" % (p.returncode, m.calls("curl")))

    p = m.run(render(**pin("v2.0.0", NEW_SHA)), NEW_ARCHIVE)
    check(p.returncode == 0 and m.tree() == installed(NEW_FONTS, "v2.0.0", NEW_SHA),
          "a new pin replaces the directory and drops the old release's files",
          "exit %d, %r" % (p.returncode, sorted(m.tree())))

    m = Machine("no-xdg", bindir, xdg=False)
    p = m.run(render(**pin("v1.0.0", OLD_SHA)), OLD_ARCHIVE)
    check(p.returncode == 0 and m.tree() == installed(OLD_FONTS, "v1.0.0", OLD_SHA),
          "without XDG_DATA_HOME it installs under ~/.local/share/fonts", p.stderr[:300])


def refuses_suite(bindir):
    cases = (
        ("a checksum mismatch", pin("v2.0.0", "0" * 64), NEW_ARCHIVE, False, "Checksum mismatch"),
        ("a failed download", pin("v2.0.0", NEW_SHA), NEW_ARCHIVE, True, ""),
        ("an archive with no fonts", pin("v2.0.0", EMPTY_SHA), EMPTY_ARCHIVE, False, "no .ttf"),
    )
    for i, (label, new_pin, archive, curl_fails, message) in enumerate(cases):
        m = Machine("refuse-%d" % i, bindir)
        p = m.run(render(**new_pin), archive, curl_fails=curl_fails)
        check(p.returncode != 0 and message in p.stderr and m.tree() == {},
              "%s on a fresh machine exits non-zero and installs nothing" % label,
              "exit %d, stderr %r, %r" % (p.returncode, p.stderr[:200], sorted(m.tree())))
        check(m.calls("fc-cache") == [], "%s does not touch the font cache" % label)

        m.run(render(**pin("v1.0.0", OLD_SHA)), OLD_ARCHIVE)
        before = m.tree()
        p = m.run(render(**new_pin), archive, curl_fails=curl_fails)
        check(p.returncode != 0 and before == installed(OLD_FONTS, "v1.0.0", OLD_SHA)
              and m.tree() == before,
              "%s leaves the existing install exactly as it was" % label,
              "exit %d, %r" % (p.returncode, sorted(m.tree())))


def degrades_suite():
    m = Machine("no-fc-cache", make_bin("bin-no-fc-cache", without=("fc-cache",)))
    p = m.run(render(**pin("v1.0.0", OLD_SHA)), OLD_ARCHIVE)
    check(p.returncode == 0 and m.tree() == installed(OLD_FONTS, "v1.0.0", OLD_SHA)
          and "fc-cache not found" in p.stdout,
          "without fc-cache the fonts are installed and the skip is reported",
          "exit %d, stderr %r" % (p.returncode, p.stderr[:200]))

    for tool in ("curl", "xz", "sha256sum"):
        m = Machine("no-" + tool, make_bin("bin-no-" + tool, without=(tool,)))
        p = m.run(render(**pin("v1.0.0", OLD_SHA)), OLD_ARCHIVE)
        check(p.returncode != 0 and "'%s' is required" % tool in p.stderr and m.tree() == {},
              "without %s it says so and installs nothing" % tool,
              "exit %d, stderr %r, %r" % (p.returncode, p.stderr[:200], sorted(m.tree())))


print("nerd font install tests (%s)" % os.path.relpath(SCRIPT, REPO))
try:
    if not shutil.which("chezmoi"):
        print("  skip  chezmoi not on PATH: the template cannot be rendered, nothing checked")
    else:
        renders_suite()
        pins_suite()
        missing = [t for t in TOOLS + STUB_TOOLS + ("bash",) if not shutil.which(t)]
        if missing:
            print("  skip  %s not on PATH: the rendered script was not run" % ", ".join(missing))
        else:
            bindir = make_bin("bin")
            installs_suite(bindir)
            refuses_suite(bindir)
            degrades_suite()
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("nerd font install tests: %s"
      % ("FAILED (%d)" % failures if failures else "all good"))
sys.exit(1 if failures else 0)
