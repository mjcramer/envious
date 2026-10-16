# Claude tooling review: simplify, clarify, standardise on Python

Date: 2026-10-02, amended 2026-10-05 (section 1 decisions), 2026-10-13
(interpreter strategy replaced; section 1b), 2026-10-14 (decisions 14-16:
Intel Macs, `brew`, `-S`; section 1b) and 2026-10-16 (decisions 17-18:
`chezmoi apply` and the Makefile routes denied to agents, `brew update`
confirmed; section 1b). Scope: everything under `dot_claude/` that is a
script, the chezmoi self-test, `tests/`, the Makefile `test` target, and the
unmerged branch `agent/craft-engineer/crew-launch-naming`.
Status: design. Steps 0 and 1 of the plan are on `main`; nothing else is
implemented. Section 11 lists what changed from the previous versions (d4a896e,
and before it e31a951 and 8612dd6).

## Conclusions

1. **Python ≥ 3.12, stdlib only, for every hook and both status lines; the
   interpreter is the OS package manager's, named by an absolute shebang that
   chezmoi renders per OS and, on macOS, per architecture.**
   `#!/opt/homebrew/bin/python3 -ISB` on Apple Silicon,
   `#!/usr/local/bin/python3 -ISB` on Intel Macs, `#!/usr/bin/python3 -ISB` on
   Linux (Ubuntu 24.04 or newer). The path comes from one partial,
   `.chezmoitemplates/python-shebang`; each entry point is a `.tmpl` whose
   first line is `#!{{ template "python-shebang" . }}`. There is no interpreter
   search, no re-exec, no environment override and no fallback: a machine whose
   interpreter is missing or older than 3.12 fails visibly. `-S` means no
   `site-packages` of any kind is on `sys.path`, so **no hook may ever import a
   third-party package** without revisiting decision 16. Section 3.
2. **The guard fails closed when it cannot run.** `settings.json` calls it as
   `~/.claude/hooks/guard-infra.py || exit 2`. A missing interpreter (`sh`
   exit 126), a missing or non-executable file (127/126), a `SyntaxError` (1)
   and the two-line version gate (`sys.exit(...)`, 1) all become exit 2, which
   Claude Code treats as a block with the hook's stderr as the reason. The
   deliberate fail-*open* on an unparsable payload (decision 2) is a separate
   policy and is unaffected: it only applies once the guard is running.
   Section 3.3.
3. **Provisioning is already done.** Homebrew `python` and apt `python3` are
   in `.chezmoidata/packages.yaml` and installed by
   `run_onchange_before_install-packages.sh.tmpl`. Nothing is added: no mise
   pin, no new script. Section 4.
4. **Latency is unchanged by the port.** Homebrew 3.14 starts in 13 ms with
   `-IB` and 9 ms with `-ISB` (`-S` skips `site`); the Python status-line stub
   measured 31 ms against bash's 32 ms before `-S`. The 19 ms re-exec path of
   the previous design no longer exists. Section 3.5.
5. **Keep `guard-infra.py` self-contained and change its algorithm as little
   as possible.** Split *rules* (data) from *engine* (code); self-protection
   extends to `~/.claude/bin` and `~/.claude/lib` (including `__pycache__`);
   new deny rules cover writes to the interpreter's own paths under both
   Homebrew prefixes, which on macOS are user-writable, and **every
   state-changing `brew` command (and `make brew`) is denied to agents**:
   packages belong in `.chezmoidata/packages.yaml` and only chezmoi runs
   `brew`. **So is every `chezmoi` command that writes the destination or the
   persistent state (`apply`, `update`, `init`, `destroy`, `purge`, `state
   delete|delete-bucket|reset|set`, ...) and every Makefile route to one
   (`make apply` through the `%:` catch-all, `make chez-apply`, `make
   chez-delete-state`)**: applying is the human's; the agent verifies with
   `chezmoi diff`/`status`/`verify`, hands over the command and waits
   (decision 17, 6.2). `security-reviewer` gates every step that touches it.
6. **Shared code in one package, `~/.claude/lib/claudetools/`.** `crew`
   becomes six modules of 40-200 lines. The unmerged `crew-launch-naming` work
   is folded into those modules during extraction (section 2.8).
7. **Behavioural tests run before `chezmoi apply` *and* the deployed `crew` is
   still exercised end to end after it.** `tests/` is `unittest` under
   `make test` (on `main`). The crew end-to-end suite is written once and runs
   against the source tree from `make test` and against `~/.claude/bin/crew`
   from the chezmoi self-test, which also probes the guard through the exact
   command string in `settings.json` with an empty `PATH`.
8. **`title.sh` is ported, last, and `jq` leaves `~/.claude`'s dependency
   list.** `settings.json` calls every script directly (shebang and exec bit).

## 1. Decisions taken (2026-10-05, binding)

| # | Decision | Where it lands | Status after 1b |
|---|---|---|---|
| 1 | Python floor is **3.12 or later**, not 3.9 | 3.3, tests `test_entrypoints.py` | stands |
| 2 | Guard **stays fail-open** on an unparsable payload; written policy, tested | 2.2, 3.3, 6.2 row "unparsable payload" | stands |
| 3 | **Port `title.sh`** last; retires `jq` | step 11 | stands |
| 4 | `settings.json` **calls scripts directly** (shebang + exec bit), never `python3 <path>` | 5.3, steps 2, 4, 10, 11 | stands; now load-bearing, since the shebang is the only thing that picks the interpreter |
| 5 | **Extend guard self-protection** to `~/.claude/bin` and `~/.claude/lib` | step 2, 6.2 | stands |
| 6 | Chezmoi self-test **keeps a full crew end-to-end run**; unit tests still under `make test` | 6.3, step 12 | stands |
| 7 | **Fold `crew-launch-naming` in** during the restructure; the branch stays unmerged | 2.8, steps 4, 5, 6, 7 | stands, untouched by 1b |

### 1b. Decisions taken (2026-10-13, 2026-10-14 and 2026-10-16, binding)

Decisions 8-13 are from 2026-10-13; 14-16 from 2026-10-14; 17-18 from
2026-10-16. All are the human's.

| # | Decision | Consequence |
|---|---|---|
| 8 | **No `pyfloor`**: no entry-point preamble, no re-exec, no `CLAUDE_PYTHON`, no `CLAUDE_PYFLOOR_DIRS`, no interpreter search | old section 3 replaced; `lib/pyfloor.py`, `tests/test_pyfloor.py` and the preamble leave the layout and the plan |
| 9 | **No mise for Python**: no `[tools] python` pin, no `run_onchange_after_00-mise-tools` script | old section 4 replaced; old open question 1 (pin vs install-only) is moot |
| 10 | **The OS package manager's Python**: Homebrew `python` on macOS, apt `python3` on Linux | section 4 verifies both are already provisioned |
| 11 | **Per-OS absolute shebang rendered by chezmoi**: `/opt/homebrew/bin/python3` on darwin, `/usr/bin/python3` on linux | section 3.3 chooses the chezmoi mechanism (`.chezmoitemplates` partial + `.tmpl` entry points) |
| 12 | **Linux targets are Ubuntu 24.04 or newer**; floor stays 3.12; below the floor fails visibly, no fallback | old open question 3 (`ask` vs `deny` with no interpreter) is moot: no guard code runs when the interpreter is missing, so the only possible answer is the `\|\| exit 2` block; a too-old interpreter is the same block with a clearer message (3.3) |
| 13 | **Keep it simple**: prefer deleting mechanism to adding it | the 3.9-safe-syntax rule for entry files is dropped (it existed only so the preamble could run on 3.9); old open question 2 (the backstop) was defaulted to yes and stands |
| 14 | **Intel Macs are in scope** (2026-10-14): the partial renders `/usr/local/bin/python3` on darwin/amd64 and `/opt/homebrew/bin/python3` on darwin/arm64; Linux stays `/usr/bin/python3` | closes old open question 1; the partial gains an `.chezmoi.arch` branch (3.3); the interpreter-path deny group covers `/usr/local/{bin,Cellar,opt,lib}` python paths as well as `/opt/homebrew` (6.2); `test_entrypoints.py` and the self-test check the per-arch line (6.1, 6.3); **not tested on Intel hardware** (3.1) |
| 15 | **Agents never run `brew`; only chezmoi does, through the install-packages script** (2026-10-14; the human's words: "only chezmoi should run brew commands, why would an agent run brew commands?") | closes old open question 2 and replaces the "`brew` verbs naming python ask" rule: every state-changing `brew` command and `make brew` are **denied** by the guard, read-only `brew` stays allowed (6.2); the deny message points at `.chezmoidata/packages.yaml` and `chezmoi apply` |
| 16 | **Add `-S`**: the shebang flags are `-ISB` (2026-10-14) | closes old open question 3; `site` is never imported by a hook, so no `.pth` in any `site-packages` (including Homebrew's user-writable one) can run inside the guard (3.3); starts 4 ms faster (3.5); a test asserts `site` is absent (6.1); **constraint: no third-party package in any hook, ever, without revisiting this decision** (5.4) |
| 17 | **Agents never run `chezmoi apply`, or anything else that writes chezmoi's target state or persistent state to the host; applying is the human's** (2026-10-16) | closes old open question 1 and the loophole decision 15 left (an agent edits `packages.yaml`, then applies it); the guard gains a **deny** group over every `chezmoi` verb that writes the destination or the state (`apply` in every spelling including `--dry-run`, `update`, `init`, `edit --apply\|-a\|--watch`, `destroy`, `purge`, `merge`, `merge-all`, `upgrade`, `edit-config`, `secret keyring set\|delete`, `ssh`, `state delete\|delete-bucket\|reset\|set`) and over the Makefile routes (`make apply` via the `%:` catch-all, `make chez-apply`, `make chez-delete-state`, `make update\|init\|upgrade\|purge\|merge-all\|edit-config\|mac`), with the message "applying is the human's: hand over the exact `chezmoi diff` / `chezmoi apply` command and wait"; read-only verbs (`diff`, `status`, `verify`, `managed`, `doctor`, `data`, `cat`, `dump`, `execute-template`, `*-path`, `ignored`, `unmanaged`, `help`, `--version`, `state data\|dump\|get\|get-bucket`) stay allowed because agents verify with them; verbs that write only the source directory (`add`, `re-add`, `chattr`, `forget`, `import`, plain `edit`) stay allowed on the human's criterion (open question 2); the classification, the Makefile analysis, the dry-run decision and the recovery path are in 6.2; the step-2 row and the `security-reviewer` surface in 7 and 10 follow |
| 18 | **`brew update` stays in the brew deny group** (2026-10-16) | closes old open question 2; the regex and the row in 6.2 stand as written on 2026-10-14; the note in 6.2 that flagged it as this review's judgement is replaced by the decision |

## 2. Findings per file

Line references are to `main` at 52bf08c unless stated. "Simplify" means
remove or merge; "clarify" means the same behaviour, easier to read.

### 2.1 `dot_claude/bin/executable_crew` (688 lines, Python)

What makes it hard to review:

- **Six concerns in one file**, in this order: git wrapper and path helpers
  (73-185), transcript/launch discovery (188-266), naming (107-174, 292-306),
  workspace lifecycle (341-521), CLI (525-657), dispatch (660-688). A reviewer
  of a naming change has to hold the lifecycle code in mind to know who calls
  what.
- **Undocumented format assumptions about Claude Code are scattered** across
  docstrings and comments rather than listed once. They are the riskiest thing
  in the file because a Claude Code release can silently invalidate any of them:
  - the transcript is JSONL with `message.content[]` blocks of type `tool_use`
    (name `Agent` or `Task`) and `tool_result` (188-216); only the last 4 MiB
    is read (61);
  - at `WorktreeCreate`, `name` is `agent-<hex>` for a subagent and `agent_type`
    is the *caller's* type (59, 292-306);
  - `base_ref` vocabulary is `head`/`HEAD`/`fresh`/`<ref>` (135-148);
  - a `.meta.json` beside `agent_transcript_path` carries `toolUseId` and
    `description` (254-261); failing that, `background_tasks[].id` matches
    `agent_id` (263-265);
  - an agent wants a worktree if the launch says `isolation: worktree` or its
    frontmatter does (219-230);
  - `WorktreeRemove` carries `worktree_path` and no agent identity (499-504).
  The unmerged branch adds two more: `tool_use_id` in the create payload
  (newer than 2.1.287), and "the transcript is written behind the
  conversation, so poll for up to 2 s".
- **Three copies of "find a free suffix"**: `new_branch_name` (155-160),
  `free_task` (167-174), and the loop inside `adopt_branch` (423-425).
- **Two overlapping rename routines**: `adopt_branch` (413-431) and `settle`
  (434-454). `hook_stop` (457-496) chooses between them with three booleans
  (`labelled`, `blind`, `wrong`) computed inline; which path runs is not
  obvious.
- **Implicit state schema in git config**: `branch.<b>.agent-base` and
  `branch.<b>.agent-launch` are read and written in five places (120-126,
  233-235, 362, 486-492) with the key names as string literals.
- `workspace_name()` (292-306) is one expression with a twelve-line docstring;
  the docstring is the valuable part and belongs in the format-assumptions
  list, not on a getter.
- Inline `import fnmatch, shutil` (277); `repo_name()` (87-88) is an alias for
  `.name`.
- Legacy cleanup of symlinks "left by older versions" (653-655) in `cmd_clean`.
- Error policy is only in code: a hook exception exits 1 for `hook-create` and
  0 otherwise (675-677). Right call, needs stating in the module docstring.
- The lock file `crew.lock` in the git common dir (177-184) is not mentioned in
  the header, and `crew clean` does not take it.

Simplify: one suffix function; merge `adopt_branch` into `settle`; drop
`repo_name`; drop the legacy symlink sweep (nothing older than fa7e46f can have
made one). Clarify: split by concern as in section 5; name the config keys as
constants; collect every Claude Code format assumption into one documented
module (`launches.py`) with the release it was observed in.

### 2.2 `dot_claude/hooks/executable_guard-infra.py` (Python, safety-critical)

Line references are to 52bf08c; the file has grown on `main` since (steps 0
and 1 added rules and the regression table), but the findings stand.

- **Two comment blocks say the same thing** (25-31 and 34-37 both explain why
  `git -C` is stripped).
- **`scrub()` and its helpers (74-169) are 95 lines of hand-rolled shell
  tokenizer** operating on anonymous nested tuples: a "word" is
  `("word", [(kind, text), ...])`, a token list is indexed positionally, and
  `_text`, `_inert`, `_search_args`, `_message_args` all reach into those
  tuples. The algorithm is sound and narrow by design; the representation is
  what costs a reviewer. Clarify with a `Word`/`Piece` `NamedTuple` and named
  fields. Do **not** swap the tokenizer for `shlex`: it would change which
  inputs bail out (unclosed quotes) and how redirections tokenize (`2>&1`
  becomes three tokens), and the regression table on `main` is the equivalence
  proof any such change would have to pass first.
- **Policy and engine are interleaved.** `DENY_PATTERNS`/`ASK_PATTERNS` are
  120+ lines of `(regex, reason)` tuples, each one a policy decision, living in
  the same file as the matcher. After the split a one-rule policy change is a
  two-line diff in a data file that imports only `re`.
- **The deny and ask loops are copy-pasted**, including the dual `flat`/`raw`
  match. One `classify(cmd) -> Decision` and one printer.
- **Two sources of truth for the same intent.** `settings.json` `ask`/`deny`
  globs and the hook's lists overlap (`gh pr merge`, `terraform destroy`,
  `git push --force`, ...). That is deliberate defence in depth (the globs
  cannot see through `git -C`), but nothing says so. State it in the rules
  file header; do not de-duplicate.
- **Fail-open on malformed input**: unparsable JSON allows the command.
  **Decided (decision 2): it stays.** Claude Code's own permission rules still
  apply, and a fail-closed guard would block every Bash call the day a Claude
  Code release changes the payload shape. The policy is stated in the engine's
  module docstring in those words, and the regression table pins it
  (`unparsable payload -> allow, exit 0, no output`; on `main` as
  `test_fail_open_is_silent_and_exits_zero`). The *other* way the guard can
  fail to run, dying before it reads anything (interpreter missing or too old,
  file missing, syntax error), is not covered by that policy and is handled
  fail-closed instead; section 3.3.
- **Self-protection gap**: the "guardrails are not yours to overwrite" rules
  cover `.claude/(hooks|settings|agents)` only. `~/.claude/bin/crew` and the
  new `~/.claude/lib/` are not covered by the hook. **Decided (decision 5):
  extend the group to `(hooks|settings|agents|bin|lib)`.** Because the regex
  matches the path prefix, `~/.claude/hooks/__pycache__/...` and
  `~/.claude/lib/claudetools/__pycache__/...` are covered by the same rule;
  6.2 adds explicit rows so that stays true.
- **No rule protects the interpreter itself.** `/opt/homebrew/bin/python3` is
  a symlink into `/opt/homebrew/Cellar/python@3.14/...` and both `bin/` and
  `Cellar/` are owned by the user (`drwxrwxr-x mjcramer admin`, verified
  2026-10-13). Writing a file or symlink there replaces the guard's
  interpreter; so does a `.pth` in `/opt/homebrew/lib/python3.14/site-packages`
  (`site` executes `import` lines from `.pth` files at every start, and `-I`
  removes only the *user* site, not this one). Today `#!/usr/bin/env python3`
  already resolves there in every terminal session, so this is not new
  exposure, but pinning the path makes it explicit. New deny rules in 6.2 for
  both Homebrew prefixes (decision 14); `-I` in the shebang closes the
  environment-variable route and `-S` the `site-packages` route (decision 16,
  3.3); `brew` itself is denied to agents (decision 15).
- **It runs under whatever `python3` is first on `PATH`** (`#!/usr/bin/env
  python3`, and `settings.json` says `python3 ~/.claude/hooks/guard-infra.py`
  on top). In a session started from the desktop app that is Apple's 3.9.6.
  Today's code happens to be 3.9-safe, so it works by luck; the moment a
  3.10+ construct lands in it, the hook dies with a `SyntaxError` and exit 1,
  which Claude Code treats as a non-blocking error: the command runs. Section
  3 makes that impossible.

Simplify: remove the duplicate comment; one classify loop. Clarify: rules file +
engine file; named tuples in `scrub`; regression table. Nothing about *what* is
denied or asked changes except the self-protection extension and the
interpreter-path rules.

### 2.3 `dot_claude/hooks/executable_title.sh` (6 lines, bash + jq)

Three `jq` forks (15 ms) on four events (`SessionStart`, `UserPromptSubmit`,
`Stop`, `CwdChanged`). Nothing is wrong with it. The output contract
(`{"terminalSequence": ...}`) is undocumented in-file. It is the only reason
`jq` is still required by `~/.claude` once the status lines are ported.
**Decided (decision 3): port it, last**, as a ~20-line Python file with the
same shebang as everything else; on any failure it prints nothing.

### 2.4 `dot_claude/executable_statusline.sh` (244), `executable_subagent-statusline.sh` (169), `statusline-lib.sh` (352): 765 lines of bash

What makes it hard to review:

- **Every bash trap carries its own explanatory comment**, which is the honest
  measure of how much a reviewer must know: U+001F field join because tab is
  IFS (54-56); `local` expands all words before assigning any (lib 84-86);
  tilde substitution must land in an assignment first (lib 94-96); extglob
  state at parse time (lib 35-40); `10#` to defeat octal (lib 203); globals
  `LEFT`/`RIGHT`/`STRIPPED`/`COLS`/`FIT_COLS` as return channels (lib 41-49,
  320-335; statusline 122-172, 231-236). None of these exist in Python.
- **Width detection (lib 164-313, 150 lines) is the most-fought-over code** in
  the repo (five commits: fffb30d, 260a70f, 1598888, 8b0388b, e6d48a2). The
  algorithm (override, `COLUMNS`, own tty, ancestor walk via `ps`, assume 80)
  is right and must be kept exactly. The implementation forks `ps` up to four
  times plus `stty` and `cut` per level.
- **Dead reference**: statusline.sh 26-27 mentions `statusline-width-probe.sh`,
  which is no longer in the repo.
- **`vislen` (lib 55-62) special-cases two emoji.** Any other wide glyph is
  miscounted. The test harness already measures with
  `unicodedata.east_asian_width`; the Python port uses the same, so the
  implementation and its test finally agree.
- **`fit` re-runs the build function up to ten times** (lib 325-335), and each
  build forks a subshell per helper (`$(tilde_path)`, `$(elide_path)`,
  `$(clip_tail)`, `$(pct_color)`, `$(meter)`, `$(fmt_tokens)`, ...). That is
  where the time goes, besides `git`.
- **The two scripts duplicate structure, not code**: shed-order ladders
  (statusline 122-172 vs subagent 84-133) and the degrade/exit choreography
  (statusline 43-52, 87-88; subagent 19-22, 50). The shed order is a comment
  (statusline 109-121, 188-191; subagent 67-83) that must be kept in sync with
  `(( level >= N ))` tests by hand.
- **subagent 135-167 builds JSON by alternating id/content lines and a `jq`
  reshape**, which only works because 46-47 strips newlines from descriptions.
  In Python it is `json.dumps` per row.
- `RESERVED_COLS=5` (lib 166-185) is tied to Claude Code 2.1.269's footer
  layout and pinned by the test. Keep, with the comment.
- In a desktop-app session (`PATH` = `/usr/bin:/bin:/usr/sbin:/sbin`,
  section 3.1) there is no `jq`, so today's status line already degrades to
  the bare directory there. The port, with an absolute shebang, makes it work.

Simplify: one entry flow shared by both renderers; one `vislen`; drop the probe
reference. Clarify: port to Python, with the shed order expressed as a table so
the comment *is* the code.

### 2.5 `dot_claude/settings.json` (277 lines)

Fine as wiring. Carry through the migration:

- Invocation is inconsistent: `python3 ~/.claude/bin/crew hook-create` and
  `python3 ~/.claude/hooks/guard-infra.py` versus `~/.claude/statusline.sh` and
  `~/.claude/hooks/title.sh`. **Decided (decision 4): direct executable paths
  everywhere.** The `python3 <path>` form pins `python3` from `PATH` before the
  script runs and ignores the shebang entirely; with the direct form the
  shebang is the one and only interpreter choice.
- The guard's line becomes `~/.claude/hooks/guard-infra.py || exit 2`
  (section 3.3, the backstop). Hook commands in shell form run through
  `sh -c` on macOS and Linux (hooks reference, re-read 2026-10-13), so `||`
  is available.
- `Edit(~/.claude/*.sh)` (162) must become `Edit(~/.claude/*.py)`, and
  `Edit(~/.claude/lib/**)` must be added, in the same commit that deploys the
  `.py` files. Security-relevant.
- The `env` block (lines 2-4, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`) is an
  ordinary settings key and can also be set from a project's
  `.claude/settings.json` (settings reference, read 2026-10-13: "An `env` block
  inside a settings file is an ordinary key and follows the levels above";
  hooks "inherit the parent environment"). A committed project file could
  therefore set `PYTHONPATH` or `PYTHONHOME` for the hooks. With no
  `CLAUDE_PYTHON`/`CLAUDE_PYFLOOR_DIRS` there is nothing of ours to set, and
  `-I` in the shebang makes every `PYTHON*` variable inert (3.3), so the env
  block no longer matters to the interpreter. It still matters to the hook
  *logic* only in the way any environment does; nothing in `~/.claude` reads a
  variable to decide what to run.
- `Stop` has two hook groups with one hook each (207-224); cosmetic.

### 2.6 `.chezmoiscripts/run_onchange_after_claude-agent-team-selftest.sh.tmpl` (268; ~335 with the unmerged branch)

- **Mixes deployment checks with behavioural tests.** Prerequisites, settings
  wiring, agents present, PATH hint (25-46, 258-262) are deployment checks and
  belong here. The guard probes (48-53) and the crew end-to-end suite (55-256)
  are behavioural tests. **Decided (decision 6): the end-to-end run stays
  post-apply**, but it is written once, in Python, and run twice (6.3).
- **JSON built with `printf '%s'`** (109, 124, 142, 150, 180, 187): a path
  containing `"` or `\` breaks the payload silently.
- **A Python pty driver embedded in a bash heredoc** (213-238) to answer
  `[y/N]`: that is a Python test pretending to be bash.
- **Timing-dependent test in the unmerged branch** (`sleep 0.5` then append to
  the transcript, in the background): flaky by construction in bash; in Python
  the writer is a `threading.Timer` and the poll loop takes an injectable
  clock.
- **Runs post-apply** (265: "chezmoi apply already wrote the files; fix and
  re-run"). A failure is reported after the broken state is live. That is
  accepted (decision 6): `make test` is the pre-apply gate, the self-test is
  the "what actually got deployed" gate.
- **The guard probes bypass the shebang** (`python3 "$CLAUDE_DIR/hooks/guard-infra.py"`,
  line 48). After step 2 the interpreter choice *is* the shebang, so a probe
  that supplies its own `python3` tests nothing about the deployment. Step 2
  adds two probes through the real `settings.json` command string; step 12
  rewrites the file.
- The trigger is four `sha256sum` includes (5-8). With a package it is a dozen
  files; 6.3 gives the verified template form (`glob` is **not** relative to
  the source dir; it needs `joinPath .chezmoi.sourceDir`). The entry-point
  file names change to `.tmpl` in step 2, and the `include` lines must follow.

### 2.7 `tests/` and the Makefile

- `tests/statusline-test.py` (982 lines) is a custom `ok`/`bad` harness, not
  `unittest`, and runs the bash scripts via subprocess **once per bash on the
  box** (961-964) because macOS ships bash 3.2. After the port that loop and
  the `bash_version` plumbing go away. The property checks themselves (`fits`,
  `flush`, `keeps`, `sheds`) are exactly the right tests and survive the port
  unchanged, because they feed JSON to a script path and read lines back.
  `width_source_suite` (680-773) sources the bash lib directly
  (`. "$LIB" && usable_cols`, 669); it becomes an import of `width.py` with
  `ps` shimmed the same way (PATH) or monkeypatched.
- `tests/ssh-signing-test.py` is out of scope.
- On `main` (436ae03, a049b2e): `make test` runs `python3 -B -m unittest
  discover`, `tests/support.py` provides `run_guard`/`guard`, and
  `tests/test_guard.py` holds the regression table. `support.run_guard` runs
  `[sys.executable, script]`; step 2 adds `-ISB` so the test interpreter sees
  the same `sys.path` the shebang gives, and points `GUARD` at the renamed
  `.tmpl` source.

### 2.8 The unmerged branch `agent/craft-engineer/crew-launch-naming` (folded in)

`git diff main...agent/craft-engineer/crew-launch-naming`: 163 insertions, 25
deletions, two files. It adds to `crew`: a bounded poll of the transcript
(`LAUNCH_WAIT=2.0`, `LAUNCH_POLL=0.1`, `next_launch` returning `(launch,
waited)`), `tool_use_id` matching in a new `match_launch`, a `Capture` class
and `debug_dir()` that write every hook payload to `~/.claude/crew-debug/`
(0600) while that directory exists, a module-docstring paragraph about the
capture, and a note in `workspace_name` that 2.1.287 sends exactly the common
fields plus `name`. It adds ~70 lines of bash to the self-test: the capture
file check, the late-arriving launch (`sleep 0.5` in the background), the
`tool_use_id` pair, and a "waits then falls back" assertion on the blind path.

**Decision 7: nothing from it is merged as-is.** The branch stays for reference
and `craft-engineer` ports each piece into the module it belongs to:

| Piece of the branch | Absorbed by | Step |
|---|---|---|
| `Capture`, `debug_dir()`, `DEBUG_DIR`, the `log()` hook into the capture | `hookio.py` (`Capture`, `debug_dir`, `log`, `run_hook` wraps the run) | 4 |
| Module docstring paragraph on `~/.claude/crew-debug` | `bin/executable_crew.tmpl` docstring (the user manual) | 4 |
| `LAUNCH_WAIT`, `LAUNCH_POLL`, `next_launch` poll loop | `launches.py` with `clock`/`sleep` injectable | 5 |
| `match_launch` with `tool_use_id` preference | `launches.py` | 5 |
| `workspace_name` note on the 2.1.287 payload | `launches.py` module docstring (the assumptions list) | 5 |
| `create_workspace` log lines with `waited` | `workspace.py` | 5 |
| Self-test: capture file is 0600 and holds payload + log | `tests/test_crew_e2e.py` | 7 |
| Self-test: late-arriving launch | `tests/test_launches.py` (fake clock, deterministic) and one real-time case in `test_crew_e2e.py` (`threading.Timer`) | 5, 7 |
| Self-test: `tool_use_id` pair, oldest-unclaimed after a claim | `tests/test_launches.py` and `test_crew_e2e.py` | 5, 7 |
| Self-test: blind path waits then falls back (`after waiting [1-9]` on stderr) | `tests/test_crew_e2e.py` | 7 |

For `security-reviewer`: the capture file holds the agent's
`last_assistant_message` verbatim, which in a work repo can include PHI or
secrets. It is opt-in (the directory must exist) and owner-only, which is
adequate; it goes in the data-retention notes, and nothing ever creates the
directory.

## 3. The interpreter: pinned per OS by chezmoi

### 3.1 What each OS provides

| Host | Path in the shebang | Version | Checked how |
|---|---|---|---|
| macOS, Apple Silicon | `/opt/homebrew/bin/python3` | 3.14.7 | `--version` on this Mac, 2026-10-13; it is a symlink to `../Cellar/python@3.14/3.14.7/bin/python3`, resolving into the framework build; `/opt/homebrew`, `bin/` and `Cellar/` are user-owned |
| macOS, Intel | `/usr/local/bin/python3` | same formula | **In scope (decision 14)**; rendered when `.chezmoi.arch` is `amd64` (Go's `GOARCH`; this Mac reports `arm64`, verified 2026-10-14). Homebrew FAQ: "`/usr/local` for macOS on Intel (legacy, Tier 3 support)"; Homebrew makes `/usr/local/{bin,Cellar,opt,lib}` user-writable there, so the same deny rows apply. Not present on this Mac (`ls` 2026-10-14); **nothing here has run on an Intel Mac**, so the first `chezmoi apply` on one is the acceptance test |
| macOS, Apple's own | `/usr/bin/python3` | 3.9.6 | `--version` 2026-10-13. **Never used**: below the floor. The Linux shebang names this path, which is why the shebang must be rendered per OS and not shared |
| Ubuntu 24.04 (noble) | `/usr/bin/python3` | 3.12.3 (`3.12.3-0ubuntu2.1`) | packages.ubuntu.com, read 2026-10-13; **not tested on a Linux box** |
| Ubuntu 22.04, Debian 12 | `/usr/bin/python3` | 3.10 / 3.11 | documentation; **out of scope** (decision 12): the gate in 3.3 refuses them with a message |

The two things that broke `#!/usr/bin/env python3` (a desktop-app session
whose `PATH` is the launchd default `/usr/bin:/bin:/usr/sbin:/sbin`, so `env`
finds 3.9.6; and a mise shim resolving by the current directory to whatever a
project pins) are both answered by not consulting `PATH` at all. `PATH` can be
empty and the hooks still run (probed in 6.3).

### 3.2 Options weighed for rendering the shebang

| Option | Shape | Trade-off | Verdict |
|---|---|---|---|
| **A. Inline template in each entry** | `#!{{ if eq .chezmoi.os "darwin" }}/opt/homebrew/bin/python3{{ else }}/usr/bin/python3{{ end }} -ISB` as line 1 of five `.tmpl` files | no new file; the same branch repeated five times, and the Intel branch (decision 14) in five places | rejected: it is the kind of line that drifts |
| **B. One partial in `.chezmoitemplates/`, referenced by each entry** | `.chezmoitemplates/python-shebang` holds the branch; each entry's line 1 is `#!{{ template "python-shebang" . }}` | one new 6-line file; five `.tmpl` renames; the mapping lives in exactly one place; verified to render and keep the exec bit (3.3) | **chosen** |
| **C. A wrapper interpreter `~/.claude/bin/python3`** that `exec`s the right binary | shebang `#!/usr/bin/env ~/.claude/bin/python3` is invalid (`~`); needs `env -S` with an absolute path, so a `.tmpl` anyway, plus a wrapper and an extra `sh` start | more mechanism than A or B, for nothing | rejected |
| **D. A config template (`.chezmoi.toml.tmpl`) exporting a `python` data variable** | entries become `#!{{ .python }}` | the repo does have a `.chezmoi.toml.tmpl` (correction, 2026-10-16: the earlier "no config template today" was wrong), but it is rendered into `~/.config/chezmoi/chezmoi.toml` only by `chezmoi init` or an `--init` flag, never by a plain `chezmoi apply`, so a change to the mapping would silently not take effect on the next apply; and `init` is denied to agents by decision 17 | rejected |
| **E. `output "brew" "--prefix"` at render time** | derives `/opt/homebrew` vs `/usr/local` on any Mac | `brew` must be on `PATH` when chezmoi renders, which is not true on a fresh box until the before-script has run and the shell re-sourced; a render failure blocks every file | rejected; `.chezmoi.arch` gives the same answer with no dependency (decision 14) |

### 3.3 The design

**`.chezmoitemplates/python-shebang`** (new; the whole file):

```
{{- /* Interpreter for every Python entry point under ~/.claude (docs/claude-tooling-review.md §3).
       Absolute on purpose: PATH is not consulted. -I ignores PYTHON* variables, the user
       site-packages and the script directory; -S skips site entirely (no site-packages,
       no .pth), so hooks are stdlib-only; -B never writes __pycache__ into ~/.claude. */ -}}
{{- if eq .chezmoi.os "darwin" -}}
{{- if eq .chezmoi.arch "amd64" -}}
/usr/local/bin/python3 -ISB
{{- else -}}
/opt/homebrew/bin/python3 -ISB
{{- end -}}
{{- else -}}
/usr/bin/python3 -ISB
{{- end -}}
```

The nested form was rendered through `chezmoi --source <scratch>
execute-template` on 2026-10-14 (chezmoi 2.72.1): `#!/opt/homebrew/bin/python3
-ISB` on this darwin/arm64 Mac. The `amd64` branch is the same template with a
different literal and has only been read, not rendered on an Intel Mac (3.1).

**Each entry point** is `executable_<name>.tmpl` and starts:

```python
#!{{ template "python-shebang" . }}
"""<module docstring>"""
import sys
if sys.version_info < (3, 12):
    sys.exit("guard-infra: needs Python >= 3.12, got " + sys.version.split()[0]
             + " (" + sys.executable + "); install it with brew/apt and run chezmoi apply")
```

The partial yields the path and flags only; the `#!` is in the entry file, so
the *source* file is valid Python and `make test` runs it by path under an
explicit interpreter (verified: `python3 -IB dot_claude/hooks/executable_x.py.tmpl`
runs). chezmoi renders `executable_x.py.tmpl` to `x.py` with mode 0755 and
the partial expanded (verified with `chezmoi --source <scratch> dump`/`cat`,
chezmoi 2.72.1 on 2026-10-13: `"perm": 493`, first line
`#!/opt/homebrew/bin/python3 -IB`; the flags are literal text in the partial,
so the `-ISB` form changes nothing about the mechanism, and the arch-branching
partial was re-rendered on 2026-10-14).
The source-state reference confirms `executable_` and `.tmpl` compose for
regular files. `chezmoi --source <repo> execute-template` also resolves the
partial, which is what `tests/test_entrypoints.py` uses (6.1).

**The flags.** `-I` (isolated mode) implies `-E` (ignore every `PYTHON*`
environment variable, so `PYTHONPATH`/`PYTHONHOME` from any settings `env`
block or shell are inert), `-s` (no user site-packages, which is a
user-writable directory on both OSes) and, since 3.11, `-P` (the script's
directory is not put on `sys.path`). `-B` stops bytecode writes, so a
`__pycache__` under `~/.claude` is never created by our own scripts and its
presence is tamper evidence (the self-test checks).

`-S` (decision 16) skips the `site` module. Without it, `site` runs at every
interpreter start and processes `.pth` files in each `site-packages` it adds
to `sys.path`; a `.pth` line that starts with `import` is *executed*, which
is the documented mechanism and the reason the directory matters. `-I` (via
`-s`) removes only the *user* site (`~/Library/Python/3.x/lib/python/site-packages`,
`~/.local/lib/python3.x/site-packages`); it does **not** remove the system
site, and on macOS that is `/opt/homebrew/lib/python3.14/site-packages` (or
`/usr/local/lib/...` on Intel), which Homebrew leaves user-writable. The deny
rules in 6.2 stop the agent's own Bash tool from writing there; `-S` makes the
guard indifferent to what is there. Verified 2026-10-14 on
`/opt/homebrew/bin/python3` (3.14.7): `-ISB -c 'import sys; print("site" in
sys.modules)'` prints `False` (`-IB` prints `True`), and a scratch script with
`#!/opt/homebrew/bin/python3 -ISB` as line 1 runs with
`sys.flags.isolated/no_site/dont_write_bytecode/safe_path/ignore_environment/no_user_site`
all set and `sys.path` exactly `[python314.zip, lib/python3.14, lib-dynload]`.
The hooks are stdlib-only by design (section 8), so nothing is lost; the
constraint this creates is recorded in 5.4.

**One token, not three.** The flags are written `-ISB`, never `-I -S -B`.
macOS splits the shebang's trailing text on whitespace, so either form would
work there (combined form verified 2026-10-14 by running the scratch script);
Linux passes everything after the interpreter path as **one** argument, so
`-I -S -B` would reach Python as the single option string `"-I -S -B"` and
fail on the space. `-ISB` is a valid single option group on both and is the
only portable spelling. (Linux behaviour is from the kernel's documented
`binfmt_script` semantics, not tested here.) Cost: `-I` alone is within noise;
`-S` saves about 4 ms (3.5).

Because of `-P`, an entry that imports a sibling adds the directory itself,
and **appends** rather than inserts, so the stdlib always wins over anything
in `~/.claude` (review note: never put `lib` at the front of `sys.path`):

```python
import os
sys.path.append(os.path.dirname(os.path.realpath(__file__)))          # guard: hooks/guard_rules.py
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))  # crew, status lines
```

**The version gate** is two lines and the only "mechanism" kept. It exists for
the message: without it a sub-floor machine reports whatever the first
incompatible construct happens to be, as a `SyntaxError` traceback. The gate
cannot run if the file does not parse on the old interpreter (the whole file
is compiled first); in that case the `SyntaxError` is the visible failure, and
that is accepted. There is no longer any rule about which syntax an entry file
may use; the test is that it parses under 3.12 (6.1).

**The backstop in `settings.json`**: `~/.claude/hooks/guard-infra.py || exit 2`.
Claude Code treats a hook exit of 2 as a block and shows the hook's stderr as
the reason; any other non-zero exit is a *non-blocking* error and the command
runs (hooks reference, re-read 2026-10-13). The backstop turns every way the
guard can fail to start into exit 2. Measured on this Mac, 2026-10-13:

| Guard failure | Without backstop | With `\|\| exit 2` | What the human sees |
|---|---|---|---|
| shebang interpreter missing (`/opt/homebrew/bin/python3` absent) | `sh` exit 126, "bad interpreter: No such file or directory" | 2, blocked | the `sh` message naming the path |
| interpreter present but < 3.12 | gate: exit 1 | 2, blocked | "guard-infra: needs Python >= 3.12, got 3.9.6 (/usr/bin/python3); ..." |
| interpreter < 3.12 and the file uses newer syntax | `SyntaxError`, exit 1 | 2, blocked | the traceback |
| `SyntaxError` on a ≥ 3.12 interpreter (a bad edit shipped) | exit 1 | 2, blocked | the traceback |
| file missing / not executable | `sh` 127 / 126 | 2, blocked | the `sh` message |
| `guard_rules.py` missing or broken | `ImportError`, exit 1 | 2, blocked | the traceback |
| unparsable payload or non-Bash tool, guard running | exit 0, no output | 0, **allowed** | nothing (decision 2; a different policy, unaffected) |

A block on every Bash command is a hard stop for the session's shell use; the
fix (`chezmoi apply`, whose before-script installs Homebrew `python` / apt
`python3`; or `brew install python` / `apt install python3` by hand) is made
by the human from a terminal, and the message says so. An agent cannot make
it: `brew install` is denied (decision 15), `chezmoi apply` is denied
(decision 17) and `sudo apt` asks. The human's terminal is never in the
guard's path: the guard is a `PreToolUse` hook on Claude Code's Bash tool and
sees nothing else (6.2, "the recovery path"). The other entry points keep
their own policy: `crew hook-create` exits 1 with the message on stderr
(Claude Code reports a hook error and the agent starts without a worktree,
visibly); `hook-stop`/`hook-remove` and the CLI exit 1 with the message; the
status lines print nothing and Claude Code shows no status line; `title.py`
prints nothing.

**Failure modes, stated.**

- Interpreter missing or too old: the guard blocks everything with a message;
  crew and the status lines fail visibly as above; the chezmoi self-test fails
  its prerequisite check (6.3) with the same message. No fallback.
- `brew upgrade python` replaces the Cellar directory; the `bin/python3`
  symlink is re-pointed by the same operation. The shebang path is stable
  across upgrades, which is the property the mise path lacked. Between
  `brew unlink python` and `brew link python` the guard blocks (visible).
- The interpreter path is user-writable on macOS (`/opt/homebrew/bin`,
  `Cellar`, `opt`, `lib/python3.x/site-packages`; the same four under
  `/usr/local` on Intel). A process running as the user can replace the
  guard's interpreter; so can it replace `settings.json`. Seatbelt, not lock:
  the guard denies the agent's own Bash tool the direct routes (6.2 rows),
  `-I` denies the environment routes, `-S` makes `site-packages` irrelevant to
  the guard, and every state-changing `brew` command is denied (decision 15).
  On Linux `/usr/bin` is root-owned and `sudo` already asks.
- `brew` run from inside something the agent wrote is not seen by the guard.
  The guard classifies the Bash tool's command text, after `normalize()` and
  `scrub()`; `brew install x` inside `sh -c "..."`, a heredoc, or a `&&` chain
  is still in that text and is denied. `brew` inside a script the agent first
  writes to disk and then runs (`bash setup.sh`), or produced by decoding
  (`base64 -d | sh`), is not. That residual is accepted and is the same gap
  every rule in the guard has (`terraform destroy` in a script is equally
  invisible); nothing in this design closes it, and the mitigations are the
  ones that already exist: the write itself goes through the Write/Edit tools
  and is visible in the transcript, the deny rules on the interpreter paths
  catch the *effect* of the commonest payload, and `-ISB` means the guard's own
  process is unaffected by whatever lands in `site-packages`. `chezmoi apply`
  (which would run `brew bundle` on the agent's behalf) is itself denied to
  agents in every spelling, as are the Makefile routes to it (decision 17,
  6.2), so the before-script only ever runs when the human applies. The same
  residual applies to it: `chezmoi apply` inside a script the agent writes and
  then runs is not seen.
- A stray `{{` anywhere in a `.tmpl` entry breaks rendering of that file at
  `chezmoi apply` (verified: `function "a" not defined`, exit 1); chezmoi
  stops with an error rather than deploying a broken file, and
  `test_entrypoints.py` catches it pre-apply. No entry point contains one
  today (grep, 2026-10-13).
- A `PreToolUse` hook that hangs does not block (timeout = non-blocking); the
  guard spawns nothing and reads only stdin, so this is unchanged.

### 3.4 What is moot now

The 3.9-safe-syntax rule for entry files, the `on_too_old` table of per-entry
behaviours, `CLAUDE_PYTHON`, `CLAUDE_PYFLOOR_DIRS`, the re-exec loop guard, the
candidate-directory search and its `python3.14-config` decoy case, the
`pyfloor.main()` bash helper and the Makefile `PY` variable. None of it has a
replacement; the shebang is the whole mechanism.

### 3.5 Measurements

This Mac (Apple Silicon, macOS 26.6.2), warm, median. Status-line numbers are
from 2026-10-05 and still apply (they were taken on Homebrew 3.14 direct, which
is exactly what the shebang now names; with `-S` they should be ~4 ms lower,
not re-measured); the flag costs are from 2026-10-13, re-run 2026-10-14
(median of 30, `subprocess` from Python) for the `-ISB` row.

| Command | ms |
|---|---|
| `/opt/homebrew/bin/python3 -c pass` | 13.4 (14.1 on 2026-10-05; 13.2 on 2026-10-14) |
| `/opt/homebrew/bin/python3 -I -c pass` | 13.7 (12.9 on 2026-10-14) |
| `/opt/homebrew/bin/python3 -IB -c pass` | 13.0 (2026-10-14) |
| `/opt/homebrew/bin/python3 -IS -c pass` | 9.3 (9.1 on 2026-10-14) |
| `/opt/homebrew/bin/python3 -ISB -c pass` (the shebang) | 9.0 (2026-10-14) |
| `/bin/sh -c 'python3.14 -c pass \|\| exit 2'` | 18.1 |
| status-line stub (payload + `git rev-parse` + `git status --porcelain`), 3.14 direct | 30.9 |
| current guard, allow, 3.14 direct | 18.2 |
| `bash statusline.sh` with `COLUMNS=200` (today) | 31.8 |
| `bash title.sh` (today) | 14.6 |

Latency-neutral, as before; the 19 ms degraded path of the previous design is
gone because there is no degraded path.

## 4. Provisioning

Already in place; nothing to add.

- `.chezmoidata/packages.yaml` lists `python` under `packages.homebrew.brews`
  and `python3` under `packages.apt` (verified 2026-10-13).
- `.chezmoiscripts/run_onchange_before_install-packages.sh.tmpl` builds a
  Brewfile from `.packages.homebrew.*` and runs `brew bundle` on darwin, and
  runs `sudo apt install -y` over `.packages.apt` on Ubuntu/Debian (verified by
  reading the script). It is a `before` script, so the interpreter exists
  before any `.tmpl` entry point is written and before the self-test runs.
- Homebrew's `python` formula tracks the current 3.x (3.14.7 today) and always
  satisfies the floor. apt's `python3` on Ubuntu 24.04 is 3.12.3 (documented,
  not tested); 24.10 and later are newer. The install script also accepts
  Debian; Debian 13 ships 3.13, Debian 12 ships 3.11 and fails the gate. That
  is the decision-12 behaviour, not a bug.
- mise: no change. The existing `python/3.13.15` under
  `~/.local/share/mise/installs` is unrelated to the hooks and may be pruned.
- Makefile: unchanged. `make test` runs `python3 -B` from `PATH`, which in a
  terminal is the mise shim falling through to Homebrew 3.14 on this Mac and
  apt's 3.12 on Linux; `tests/__init__.py` gains a one-line
  `sys.version_info >= (3, 12)` assertion with a message so a wrong `python3`
  fails the run before any test does.
- `security-reviewer`'s point that `/opt/homebrew` is user-writable is a
  property of Homebrew, not of this design; it is handled by rules (6.2), not
  by provisioning.

## 5. Target structure

### 5.1 Layout (source, left; deployed, right)

```
.chezmoitemplates/python-shebang                                        new, 6 lines
dot_claude/                                   ~/.claude/
  settings.json                                 settings.json
  executable_statusline.py.tmpl                 statusline.py              entry, ~130
  executable_subagent-statusline.py.tmpl        subagent-statusline.py     entry, ~100
  bin/executable_crew.tmpl                      bin/crew                   entry, ~40
  hooks/executable_guard-infra.py.tmpl          hooks/guard-infra.py       entry + engine, ~170
  hooks/guard_rules.py                          hooks/guard_rules.py       data, ~150
  hooks/executable_title.py.tmpl                hooks/title.py             entry, ~20
  lib/claudetools/__init__.py                   lib/claudetools/           VERSION, ~10
  lib/claudetools/hookio.py                                                ~110 (with Capture)
  lib/claudetools/gitx.py                                                  ~120
  lib/claudetools/launches.py                                              ~160 (with the poll)
  lib/claudetools/workspace.py                                             ~200
  lib/claudetools/crew_hooks.py                                            ~120
  lib/claudetools/crew_cli.py                                              ~170
  lib/claudetools/textfmt.py                                               ~90
  lib/claudetools/width.py                                                 ~100
  lib/claudetools/layout.py                                                ~40
```

Gone from the previous layout: `lib/pyfloor.py`, the mise config change and
`run_onchange_after_00-mise-tools.sh.tmpl`.

chezmoi rules that make this work: `executable_` and `.tmpl` compose; the
`executable_` prefix is per file, so the package files have no prefix and are
deployed `644`; `lib/` and `hooks/` are plain directories; hyphenated
entry-point names cannot be imported, which is right for entry points. Only
the five entry points are templates; `guard_rules.py` and `claudetools/` are
plain files. Each entry point locates its imports relative to itself
(`realpath` first, so a symlinked `~/.claude` still works) and appends to
`sys.path` (3.3).

`guard-infra.py` imports `guard_rules` and nothing else of ours, so a broken
crew or status line cannot take the guard down, and a reviewer of the guard
reads two files, one of which is data.

`.chezmoiignore` already has the `__pycache__`/`*.pyc` lines (step 0, on
`main`).

### 5.2 Module map and contracts

Skeletons are given here, not as files on this branch: any file under
`dot_claude/` is deployed by the next `chezmoi apply`, and an empty guard or
status line in `~/.claude` is a live regression. `craft-engineer` creates the
files in the steps of section 7.

**Entry-point header** (identical in all five except the program name in the
message and the `sys.path` line; 3.3 gives the text).

**`hookio.py`** (~110): everything about talking to Claude Code.

```python
def read_payload(stream=sys.stdin) -> dict:
    """The hook/status-line JSON on stdin, or {} when it is missing or unparsable.
    Never raises: a hook that dies on input is worse than one that does nothing."""

def dig(d: dict, *keys: str, default=None):
    """d[k1][k2]... or default when any level is missing or not a dict (jq's `//`)."""

def log(msg: str) -> None:
    """One '[crew] ...' line on stderr; also recorded by the active Capture, if any."""

def permission(decision: str, reason: str) -> str:
    """The PreToolUse hookSpecificOutput JSON for decision in {'deny', 'ask'}."""

def run_hook(handler, *, fatal: bool) -> int:
    """Read the payload, call handler(payload), return its exit code. On any
    exception: log it and return 1 when fatal (WorktreeCreate: a missing path
    must fail loudly) else 0. Wraps the run in a Capture when debug_dir() is set,
    writing the payload before the handler runs and the log lines after."""

DEBUG_DIR = Path.home() / ".claude" / "crew-debug"
def debug_dir() -> Path | None:
    """$CREW_DEBUG_DIR or DEBUG_DIR, only if it already exists. Nothing creates it."""
class Capture:                 # from crew-launch-naming, unchanged in behaviour
    def __init__(self, directory: Path, hook: str, payload: dict): ...
    def note(self, msg: str) -> None: ...
    def write(self) -> None: ...   # 0600; a failure is logged and otherwise ignored
```

**`gitx.py`** (~120): the only module that spawns `git`.

```python
AGENT_BASE = "agent-base"       # branch.<b>.agent-base   -> the branch it was cut from
AGENT_LAUNCH = "agent-launch"   # branch.<b>.agent-launch -> tool_use id that launched it

def git(*args: str, cwd=None, check=True) -> str: ...
def main_checkout(cwd) -> Path: ...
def current_branch(path) -> str: ...
def is_dirty(path) -> bool: ...
def branch_exists(main, branch) -> bool: ...
def branch_config(path, branch, key) -> str: ...
def set_branch_config(path, branch, key, value) -> None: ...
def is_merged(path, branch, base) -> bool: ...
def worktrees(main) -> list[tuple[Path, str]]: ...
def resolve_base(main, base_ref) -> tuple[str, str]:
    """(branch name, sha) for a WorktreeCreate base_ref: ''/'head'/'HEAD' -> HEAD,
    'fresh' -> origin/HEAD if it exists, else any ref git can verify, else HEAD."""
@contextmanager
def locked(main): """flock on <git-common-dir>/crew.lock; one hook per repo at a time."""
```

**`launches.py`** (~160): every assumption about Claude Code's transcript and
hook payloads, in one place, each with the release it was observed in
(including: 2.1.287 sends exactly the common fields plus `name` at
`WorktreeCreate`; newer releases add `tool_use_id` and `description`; the
transcript lags the conversation by up to ~1 s). This is the module to re-read
when a Claude Code upgrade breaks naming.

```python
TRANSCRIPT_TAIL = 4 * 1024 * 1024
LAUNCH_WAIT, LAUNCH_POLL = 2.0, 0.1
GENERATED_NAME = re.compile(r"agent-[0-9a-f]{8,}")

class Launch(NamedTuple):
    agent: str; task: str; tool_use_id: str

def pending_launches(transcript_path) -> list[dict]:
    """Agent/Task tool_use blocks in the transcript tail with no tool_result yet, oldest first."""
def wants_worktree(call: dict, cwd) -> bool: ...
def claimed_launches(main) -> set[str]: ...
def match_launch(calls, taken, payload) -> Launch | None:
    """payload['tool_use_id'] names the call when present and nothing else is considered;
    otherwise the oldest unclaimed call that wants a worktree."""
def next_launch(main, payload, *, clock=time.monotonic, sleep=time.sleep) -> tuple[Launch | None, float]:
    """Poll the transcript for up to LAUNCH_WAIT under the repo lock; (launch, seconds waited)."""
def launch_record(payload) -> dict:
    """{'toolUseId', 'description'} from <agent_transcript>.meta.json, else from background_tasks, else {}."""
```

**`workspace.py`** (~200): naming and lifecycle. Pure functions over `gitx`.

```python
BRANCH_PREFIX = "agent/"
IN_CHECKOUT_AGENTS = {"spike-engineer"}

def safe_slug(s) -> str: ...
def task_slug(text) -> str: ...
def ws_root(main) -> Path: ...
def ws_path(main, suffix) -> Path: ...
def free_suffix(main, agent, task, keep=None) -> str:
    """task, task-2, task-3 ... the first with neither workspace nor branch (one function; three copies today)."""
def branch_agent(branch) -> str: ...
def create_workspace(main, payload) -> Path: ...
def commit_leftovers(path, agent, summary) -> bool: ...
def settle(main, path, branch, agent, launch: dict) -> tuple[Path, str]:
    """Rename branch and directory to agent/<agent>/<task> and <repo>.<agent>.<task>.
    Absorbs adopt_branch: a branch that already has the right agent keeps its slug."""
def copy_worktreeinclude(main, dest) -> None: ...
def only_here(path, branch) -> int | None: ...
def find_workspace(cwd, agent) -> tuple[Path, str]: ...
def summarize(payload) -> str: ...
```

**`crew_hooks.py`** (~120): `hook_create`, `hook_stop`, `hook_remove`, each
taking a payload and returning an exit code. `hook_stop` becomes readable by
naming its decision: `needs_settle = blind or mislabelled` computed by a
helper with a docstring.

**`crew_cli.py`** (~170): `cmd_list`, `cmd_path`, `cmd_diff`, `cmd_clean`,
and `main(argv)`. Same exit codes and streams as today (the end-to-end suite
pins them: usage on stdout exit 0; unknown subcommand on stderr exit 2).

**`bin/executable_crew.tmpl`** (~40): the header (3.3); the docstring (the
current module docstring plus the `crew-debug` paragraph from the branch,
which together are the user manual); `sys.exit(crew_cli.main(sys.argv))`.

**`hooks/guard_rules.py`** (~150): `DENY: list[Rule]`, `ASK: list[Rule]`
with `Rule = NamedTuple(pattern: re.Pattern, reason: str)`, grouped under the
same headings as today, with a header that explains the relationship to the
`settings.json` globs (first layer) and the hook (second layer, sees through
`git -C`). The self-protection group reads
`\.claude/(hooks|settings|agents|bin|lib)`; a new group, "the interpreter is
not yours to replace", holds the rules in 6.2. Imports `re` and `typing` only.

**`hooks/executable_guard-infra.py.tmpl`** (~170): the header; `normalize`,
`scrub` and its helpers (with `Word`/`Piece` named tuples); and:

```python
class Decision(NamedTuple):
    verdict: str          # "deny" | "ask" | "allow"
    reason: str

def classify(cmd: str) -> Decision:
    """The first DENY rule matching either the scrubbed+normalised or the raw form,
    else the first ASK rule, else allow. Pure; this is what the tests call."""

def main() -> int:
    """Policy (decision 2, 2026-10-05): an unparsable payload and a non-Bash tool both
    ALLOW with no output and exit 0. Claude Code's own permission rules still apply, and
    a guard that denies on a payload it cannot read would block every Bash call the day
    the payload shape changes. A guard that cannot *start* (interpreter missing or too
    old, file broken) is a different case: it exits non-zero and the `|| exit 2` in
    settings.json turns that into a block. Nothing in this file may catch that."""
```

**`textfmt.py`** (~90): palette constants, `vislen` via `unicodedata`,
`strip_ansi`, `clip_tail`, `clip_head`, `elide_path`, `tilde_path`,
`short_model`, `to_int`, `pct_color`, `fmt_tokens`, `meter`, `fmt_reset`.
All pure, all return strings.

**`width.py`** (~100): `RESERVED_COLS = 5`, `right_margin(term)`,
`ancestor_cols(pid, depth=4, ps=subprocess.run)`, `usable_cols(env=os.environ)`,
`resolve(given=None) -> tuple[int, int]` returning `(cols, fit_cols)`. The
order of sources is unchanged and documented in the same words as today.
`stty size` becomes `fcntl.ioctl(fd, termios.TIOCGWINSZ, ...)` on the opened
tty; `ps -o ppid=,tty= -p` stays (there is no stdlib way to get another
process's tty on macOS).

**`layout.py`** (~40): `MIN_GAP = 3`, `fit(build, max_level, fit_cols) ->
tuple[str, str]`, `render(left, right, fit_cols) -> str`. `build(level)`
returns `(left, right)`; no globals.

**Entry points** `statusline.py`, `subagent-statusline.py`: header, payload
in, `git` state once, `build_line1/2` or `build_row` written as a shed table:

```python
SHED_LINE1 = {  # level -> what is dropped or shortened at that level; the comment is the code
    1: "dir to 2 components, branch to last component",
    2: "output style, effort suffix",
    ...
}
MAX_LEVEL_1 = max(SHED_LINE1)
```

**`hooks/executable_title.py.tmpl`** (~20): header; `{"terminalSequence":
"\x1b]0;<basename of cwd> · <agent_type or 'default'>\x07"}` on stdout; the
output contract documented in the docstring; nothing on any failure.

### 5.3 `settings.json` after the migration

```
statusLine.command            ~/.claude/statusline.py
subagentStatusLine.command    ~/.claude/subagent-statusline.py
PreToolUse  Bash              ~/.claude/hooks/guard-infra.py || exit 2
WorktreeCreate                ~/.claude/bin/crew hook-create
WorktreeRemove                ~/.claude/bin/crew hook-remove
SubagentStop  <agents>        ~/.claude/bin/crew hook-stop
SessionStart, UserPromptSubmit, Stop, CwdChanged
                              ~/.claude/hooks/title.py
permissions.deny              + Edit(~/.claude/lib/**), Edit(~/.claude/*.py); - Edit(~/.claude/*.sh)
```

### 5.4 What is easy to change later and what is not

Easy: rules in `guard_rules.py`; the interpreter path and flags (one partial,
rendered on the next `chezmoi apply`); the floor (one tuple in five headers;
change all five at once); shed order; colours; `LAUNCH_WAIT`;
`IN_CHECKOUT_AGENTS`. Expensive: the git-config schema (`agent-base`,
`agent-launch`) and the workspace/branch naming scheme, because existing
worktrees on disk carry them and every agent prompt states them. The plan
changes none of the expensive ones.

**Fixed by decision 16, not merely expensive: no hook, status line, `crew`
module or `claudetools` module may import anything outside the standard
library, ever.** `-S` means there is no `site-packages` on `sys.path` at all,
so a third-party import does not degrade, it raises `ModuleNotFoundError`
at start, which for the guard is a block on every Bash command. Adding one
means revisiting decision 16 (dropping `-S` and re-opening the `.pth`
exposure), not just `pip install`. `test_entrypoints.py` enforces it
statically (6.1, `test_imports_are_stdlib_or_ours`).

### 5.5 Failure modes

Stated, and now mostly tested: an unreadable hook payload is a no-op (`crew`)
or an allow (`guard`, decision 2); a status line that cannot parse its payload
prints the bare directory (main) or nothing (subagent); `hook-create` is the
only hook whose failure exits non-zero, because Claude Code reads its stdout
as the working directory and silence would misplace the agent; a guard that
cannot start blocks (3.3), never passes. Where the data-integrity risk sits:
`hook-stop` commits whatever is in the tree and renames branches, so it keeps
its rule of acting only on a payload that names both agent and cwd, and only
under the repo lock.

## 6. Tests

### 6.1 Shape

`tests/` is a package of `unittest` modules discovered by
`python3 -B -m unittest discover -s tests -t .` from `make test` (on `main`),
pre-apply, against the source files (run by path, or loaded with `importlib`
for the hyphenated names). The existing `tests/statusline-test.py` property
harness is kept and converted to `unittest.TestCase` methods in place; its
`run()` already feeds a payload to a script path, so it tests the `.py.tmpl`
entry points with a one-line change (`[BASH, SCRIPT]` becomes
`[sys.executable, "-ISB", SCRIPT]`).

```
tests/
  __init__.py         + assert sys.version_info >= (3, 12) with a message               step 2
  support.py          on main; step 2: GUARD -> executable_guard-infra.py.tmpl, run with -ISB;
                      later: scratch_repo(); ps shim; pty driver; crew_argv()           step 2, 7
  test_guard.py       the regression table (6.2); on main, rows added in step 2
  test_entrypoints.py the entry-point tests (below)                                      step 2
  test_launches.py    transcript parsing, tool_use_id matching, poll with fake clock    step 5
  test_workspace.py   slugs, free_suffix, settle, resolve_base                          step 5
  test_crew_e2e.py    hook-create / hook-stop / hook-remove / clean on a scratch repo,
                      dual-target (6.3); includes the three crew-launch-naming cases   step 7
  test_crew_cli.py    list / path / diff / clean (pty for the y/N answer)               step 7
  test_statusline.py  the current property suites: fits, flush, keeps, sheds, edge     step 8b
  test_subagent.py    the current subagent_suite                                        step 9
  test_width.py       the current width_source_suite, importing width.py               step 8a
  ssh-signing-test.py unchanged, out of scope
```

**`test_entrypoints.py`** covers every `dot_claude/**/executable_*.tmpl`
(discovered by glob, so a new entry point is tested without being listed):

| Test | Checks |
|---|---|
| `test_first_line_is_the_shared_shebang` | line 1 is exactly `#!{{ template "python-shebang" . }}` |
| `test_no_other_template_syntax` | no `{{` or `}}` anywhere after line 1 (a stray one breaks `chezmoi apply`; 3.3) |
| `test_version_gate_is_first_statement` | the first statement after the docstring and `import sys` is the `sys.version_info < (3, 12)` gate (parsed with `ast`, not regex) |
| `test_parses_under_3_12` | `ast.parse(src, feature_version=(3, 12))` succeeds; so does `compile()` under the running interpreter |
| `test_runs_by_path_in_isolated_mode` | `[sys.executable, "-ISB", path]` with an empty payload exits per the entry's policy (guard: 0 and silent; crew with no args: usage, 0; status lines: 0; title: 0) and leaves no `__pycache__` beside the source |
| `test_rejected_below_floor` | when `/usr/bin/python3` exists and is < 3.12 (macOS), running each entry under it exits 1 and stderr contains `needs Python >= 3.12`, **or** is a `SyntaxError`; skipped with a reason elsewhere |
| `test_partial_names_all_three_interpreters` | `.chezmoitemplates/python-shebang` contains exactly three interpreter lines, each ending ` -ISB`: `/usr/local/bin/python3` inside an `eq .chezmoi.arch "amd64"` branch nested inside `eq .chezmoi.os "darwin"`, `/opt/homebrew/bin/python3` in that branch's `else`, `/usr/bin/python3` in the outer `else`; nothing else that looks like a path; no flag string other than `-ISB` (a regression to `-IB`, or a split `-I -S -B`, fails here) |
| `test_rendered_shebang_for_this_os_and_arch` | with `chezmoi` on `PATH`: `chezmoi --source <repo> execute-template '#!{{ template "python-shebang" . }}'` equals the line expected for `platform.system()`/`platform.machine()`: `#!/opt/homebrew/bin/python3 -ISB` for Darwin/arm64, `#!/usr/local/bin/python3 -ISB` for Darwin/x86_64, `#!/usr/bin/python3 -ISB` for Linux (verified form, 3.3); skipped with a reason without chezmoi. Each OS/arch is covered when the suite runs there and by the self-test; **the Intel branch has no machine to run on today** (3.1) |
| `test_rendered_interpreter_exists_and_meets_floor` | the path from the previous test exists, is executable, and `<path> -ISB -c 'import sys; print(sys.version_info[:2])'` is ≥ (3, 12); skipped when chezmoi is absent |
| `test_site_is_not_imported` (decision 16) | the rendered shebang line is split into interpreter and flags and run as `[<path>, <flags>, "-c", "import sys; raise SystemExit(0 if 'site' not in sys.modules and sys.flags.no_site and sys.flags.isolated else 1)"]`, exit 0; **and** the same assertion run under `[sys.executable, "-ISB", ...]` so `make test` checks it without chezmoi. A separate case runs the guard entry itself under `-ISB` with a payload for `python3 -c "import sys; print('site' in sys.modules)"` and only asserts it is allowed, so the test does not reach into the guard's process (verified by hand 2026-10-14: `-ISB` gives `False`, `-IB` gives `True`) |
| `test_imports_are_stdlib_or_ours` (decision 16) | every `dot_claude/**/*.py` and `*.py.tmpl` is parsed with `ast`; every top-level and function-level `import`/`from` root name is in `sys.stdlib_module_names` or in `{"guard_rules", "claudetools"}`; the failure message cites decision 16 |
| `test_settings_calls_entries_directly` | every hook and status-line `command` in `dot_claude/settings.json` starts with `~/.claude/` (no `python3 ` prefix) and the guard's ends with `\|\| exit 2` |

### 6.2 Must-keep regression tests

**`guard-infra` (the gate for any change to the file; `security-reviewer`
owns the table).** Each row is `(command, expected verdict)`; the table on
`main` is seeded from every existing self-test probe, every rule in both
lists, and every evasion the comments document. Step 2 adds the rows marked
*new*.

| Must deny | Must ask | Must allow |
|---|---|---|
| `terraform destroy`; `tofu destroy -auto-approve` | `terraform apply` | `terraform plan` |
| `git -C /x push --force origin main` (global-option stripping) | `git push` | `git log --oneline` |
| `gh 'pr' merge`, `gh "pr" merge` (quote stripping) | `gh pr create` | `gh pr view 12` |
| `gh pr \`<newline>`merge` (line continuation) | `git merge feature` (no `--no-ff`); `git merge --no-ff agent/x` (still a HEAD move) | `git log --oneline` |
| `gh api graphql -f query='mutation {...}'`; `--input body.json` | `kubectl --context prod-w apply -f x` | `kubectl get pods` |
| `gh api -X PUT repos/o/r/branches/main/protection` | `sudo ls` | `gh api repos/o/r/branches/main/protection` (read; the hook allows, the `settings.json` glob still denies) |
| `rm ~/.claude/hooks/guard-infra.py`; `mv x ~/.claude/settings.json` | `ssh robot-7` | `cat ~/.claude/settings.json` |
| `cp x ~/.claude/hooks/`; `cp -t ~/.claude/hooks x` | `systemctl restart foo` | `cp ~/.claude/hooks/guard-infra.py /tmp/` (copy out) |
| *new:* `rm ~/.claude/bin/crew`; `echo x > ~/.claude/lib/claudetools/gitx.py`; `cp x ~/.claude/lib/claudetools/`; `cp x ~/.claude/hooks/__pycache__/`; `rm -rf ~/.claude/lib/claudetools/__pycache__` | | *new:* `cat ~/.claude/lib/claudetools/gitx.py`; `cp ~/.claude/bin/crew /tmp/` |
| *new, interpreter (Apple Silicon):* `ln -sf /tmp/py /opt/homebrew/bin/python3`; `cp x /opt/homebrew/bin/python3.14`; `rm /opt/homebrew/Cellar/python@3.14/3.14.7/bin/python3`; `echo x > /opt/homebrew/opt/python@3.14/bin/python3`; `tee /opt/homebrew/lib/python3.14/site-packages/evil.pth`; `chmod +x /opt/homebrew/bin/python3`; `open('/opt/homebrew/bin/python3','w')`; `cp x /usr/bin/python3` (Linux; `sudo` would ask anyway, deny is cheaper to reason about) | | *new:* `/opt/homebrew/bin/python3 -c 'print(1)'`; `cat /opt/homebrew/bin/python3`; `ls /opt/homebrew/Cellar/python@3.14`; `/usr/local/bin/python3 -c 'print(1)'`; `ls -l /usr/local/opt/python@3.14` |
| *new, interpreter (Intel, decision 14):* the same seven under `/usr/local`: `ln -sf /tmp/py /usr/local/bin/python3`; `cp x /usr/local/bin/python3.14`; `rm /usr/local/Cellar/python@3.14/3.14.7/bin/python3`; `echo x > /usr/local/opt/python@3.14/bin/python3`; `tee /usr/local/lib/python3.14/site-packages/evil.pth`; `chmod +x /usr/local/bin/python3`; `open('/usr/local/bin/python3','w')` | | *new:* `cp x /usr/local/bin/mytool` (not a python path: the rule keys on the basename/directory, not the prefix) |
| *new, brew (decision 15):* `brew install python`; `brew install jq`; `brew upgrade`; `brew upgrade python@3.14`; `brew reinstall python`; `brew uninstall python`; `brew remove x`; `brew rm x`; `brew link --overwrite python`; `brew unlink python`; `brew tap foo/bar`; `brew untap foo/bar`; `brew cleanup`; `brew autoremove`; `brew pin python`; `brew unpin python`; `brew postinstall python`; `brew update`; `brew bundle`; `brew bundle install --file Brewfile`; `brew bundle cleanup --force --file Brewfile`; `brew bundle dump`; `brew services start x`; `brew services stop x`; `brew services restart x`; `brew services run x` | | *new, brew read-only:* `brew list`; `brew list python`; `brew info python`; `brew --prefix`; `brew --prefix python`; `brew --version`; `brew config`; `brew deps python`; `brew outdated`; `brew search python`; `brew doctor`; `brew bundle check --file Brewfile`; `brew bundle list`; `brew services list`; `brew services info x` |
| *new, brew option-before-subcommand (as kubectl/terraform):* `brew --verbose install x`; `brew -v upgrade`; `brew -q install x`; `brew --debug tap foo/bar`; `brew bundle --file Brewfile install`; `brew bundle --verbose`; `HOMEBREW_NO_AUTO_UPDATE=1 brew install x`; `brew 'install' x` (quote stripping); `cd ~/envious && brew bundle`; `sh -c "brew install x"`; `brew install x \|\| true` | | `brew --verbose list`; `brew -v info python`; `brew bundle --file Brewfile check`; `grep -rn "brew install" .` (scrub); `git commit -m "deny brew install to agents"` (scrub); `rg "brew upgrade" docs/` (scrub) |
| *new, make brew (decision 15):* `make brew`; `make -C ~/envious brew`; `make -n brew`; `make -j4 brew`; `make brew mac`; `cd ~/envious && make brew` | | `make test`; `make help`; `make -n test`; `grep brew Makefile` |
| `echo x > ~/.claude/agents/a.md`; `open('~/.claude/settings.json','w')` | `git checkout main`; `git stash` | `git stash list` |
| `git -c remote.origin.url=evil push` (raw form, not stripped) | `git worktree add ../x` | `git worktree list` |
| `GIT_CONFIG_KEY_0=remote.origin.url git push` | `-e prod`; `ENV=production make` | `grep -rn "drop table" .` (scrub) |
| `git branch -D agent/x`; `git branch -d agent/x`; `git reset --hard origin/main` | `rmmod foo`; `fwupdmgr update` | `git branch -d feature` |
| `crew clean --all` | `aws --profile prod s3 ls` | `git commit -m "explain why terraform destroy is blocked"` (scrub) |
| `rm -rf /`; `rm -rf ~`; `rm -rf .`; `rm -rf *` | `helm upgrade x` | `rm -rf build/` |
| `kubectl delete ns x`; `kubectl delete pods --all` | `kubectl scale deploy x`; `kubectl delete pod x` | `kubectl rollout status deploy/x` |
| `git add .env`; `git add secrets.pem` | | `git add .env.example` |
| `aws rds delete-db-instance --skip-final-snapshot` | | `aws rds delete-tags` |
| `docker system prune`; `vault kv delete x` | | `rg --pre cat "terraform destroy"` must **not** be scrubbed (deny) |
| `git merge --squash x`; `git merge --ff-only x` | | non-`Bash` tool payload |
| | | **unparsable payload: allow, exit 0, no output (decision 2; the policy row)** |

The interpreter rows are the regex form of the review note "`/opt/homebrew` is
user-writable, so a write to `/opt/homebrew/bin/python3` or the Cellar replaces
the guard's interpreter": deny the file operations (`rm mv cp ln install tee
dd truncate chmod chown`, `>`/`>>` redirects, `open(..., 'w')`) on any path
under `(/opt/homebrew|/usr/local)/(bin|Cellar|opt|lib)/` whose basename or
directory starts with `python` (decision 14 adds the `/usr/local` prefix; on
Apple Silicon that directory is root-owned and empty, so the extra alternation
costs nothing and never fires there). The `.pth` row stays although `-S` makes
the guard immune to it (decision 16): the rule now protects the interpreter
the *human* runs, and defence in depth is cheap.

**The `brew` rows (decision 15)** are one deny group, with the message
*"Homebrew is chezmoi's: packages belong in `.chezmoidata/packages.yaml` and
are applied by the human with `chezmoi apply`"*, written in the guard's
existing option-spanning form (`_OPTS` sits between the tool and the verb,
bounded by the shell segment, exactly as the kubectl and terraform rules):

```python
# Decision 15: agents never run brew; chezmoi's install-packages script does.
_BREW_MSG = ("Homebrew is chezmoi's: packages belong in .chezmoidata/packages.yaml "
             "and are applied by the human with chezmoi apply")
(r"\bbrew" + _OPTS + r"(install|reinstall|upgrade|uninstall|remove|rm|link|unlink|tap|untap"
 r"|cleanup|autoremove|pin|unpin|postinstall|update)\b", _BREW_MSG),
(r"\bbrew" + _OPTS + r"services\s+(start|stop|restart|run)\b", _BREW_MSG),
# `brew bundle` with no verb installs; only `check` and `list` are read-only.
(r"\bbrew" + _OPTS + r"bundle\b(?!(\s+-{1,2}[\w-]+(?:[= ]\S+)?)*\s+(check|list)\b)", _BREW_MSG),
# `make brew` is `brew update && brew bundle install && brew bundle cleanup --force` (Makefile, read 2026-10-14).
(r"\bmake" + _OPTS + r"brew\b", _BREW_MSG),
```

The regexes are the shape, not the proof; the table rows are the contract and
`security-reviewer` owns both. They were run against every brew and `make
brew` row above through the guard's own `scrub()`, `normalize()` and `_OPTS`
on 2026-10-14 (44 deny, 27 allow, no misses, no over-denies) from a scratch
script, not from `tests/`; step 2 puts them in the table proper. Notes on the
edges:

- `brew update` is in the deny group although the human's list named neither
  it nor the read-only set with it: it rewrites the tap checkouts under the
  user-writable prefix (what `brew install` will later build from) and it is
  the first thing `make brew` runs. If it should be allowed, strike it from
  the regex and move its row; nothing else depends on it.
- Read-only verbs the human named (`list info --prefix --version config deps
  outdated search doctor`, `bundle check`, `bundle list`) are allowed by not
  being listed, which is the guard's default; the allow rows pin them so a
  future widening of the regex cannot take them silently. `brew services`
  with no verb, `list` and `info` are read-only and allowed the same way.
- The `bundle` lookahead allows `check`/`list` only as the first non-option
  word after `bundle`, so `brew bundle install --file check` is still denied
  (`check` there is a value, not the verb).
- `make -f brew.mk x` would be denied by the `\sbrew\b` match on the file
  name, and `brew search update` by the `\supdate\b` match on the query.
  Accepted: that is the looseness every `_OPTS` rule has, there is no such
  file in this repo, and the cost of an over-deny is one visible message.
- The guard sees the Bash tool's command text only. `brew` in `sh -c`, a
  heredoc or a chain is in that text and is denied; `brew` in a script the
  agent writes and then executes is not (3.3 failure modes states what covers
  that and what does not). `chezmoi apply`, `make chez-apply` and the
  Makefile's `%:` catch-all (`make apply` runs `chezmoi apply`) all run `brew
  bundle` legitimately on the human's behalf; none is guarded today (grep of
  the guard and `settings.json`, 2026-10-14) and whether they should be is
  open question 1 in section 9, not part of this group.
- `sudo brew ...` is refused by Homebrew itself and asks via the `sudo` rule
  before the brew rule is reached; no row needed.

Also pinned: the output shape (`hookSpecificOutput.permissionDecision`,
`hookEventName: PreToolUse`), exit code 0 on every path once the guard is
running, that `rm -rf` of a cwd-relative path is allowed. Any row whose
expectation changes is a policy change and goes through `security-reviewer`.

**`crew`** (`test_crew_e2e.py`, `test_launches.py`): every scenario in the
current self-test 55-256 plus the four from the folded-in branch, on a scratch
repo under `tempfile`: naming from the transcript; blind creation then settle
at stop; `tool_use_id` preference; oldest-unclaimed ordering after a claim;
the late-arriving launch (fake clock in `test_launches.py`; one real-time
`threading.Timer` case in the e2e suite); blind path waits then falls back;
capture file 0600 with payload and log; stdout contract of `hook-create`
(exactly one line, the path); `hook-stop` no-op on `{}`; in-checkout commit
for `spike-engineer`; `hook-remove` keeps the workspace; `clean` without a
tty removes nothing; `clean` keeps unmerged work unless `--all`;
`path`/`list`/`diff` output.

**Status lines**: the four properties (`fits`, `flush`, `keeps`, `sheds`),
`RESERVED = 5`, the width-source precedence, the subagent row contract (one
JSON object per line, nothing on failure), the two-emoji widths (now general),
and the bare-directory output on an unparsable payload.

### 6.3 The chezmoi self-test (decision 6): one suite, two targets

`tests/support.py` gets

```python
def crew_argv() -> list[str]:
    """How to run crew under test. With $CREW set (the chezmoi self-test points it at
    ~/.claude/bin/crew) run it directly, so the shebang, exec bit and version gate are what
    is tested; otherwise [sys.executable, "-ISB", <source path of executable_crew.tmpl>]."""
```

and `test_crew_e2e.py` uses only that. `make test` runs it against the source;
the chezmoi script runs the same file against the deployment:

```bash
# The interpreter is whatever the deployed guard's shebang names; nothing else is consulted.
PY="$(sed -n '1s/^#!//p' "$CLAUDE_DIR/hooks/guard-infra.py" | cut -d' ' -f1)"
[ -x "$PY" ] && "$PY" -ISB -c 'import sys; sys.exit(sys.version_info < (3, 12))' \
  && ok "interpreter $PY >= 3.12" || bad "interpreter $PY missing or < 3.12 (chezmoi apply installs it; or brew/apt install python by hand)"
"$PY" -ISB -c 'import sys; sys.exit("site" in sys.modules)' && ok "site not imported under -ISB" || bad "site imported: shebang flags are not -ISB"
( cd "{{ .chezmoi.sourceDir }}" && CREW="$CLAUDE_DIR/bin/crew" "$PY" -ISB -m unittest -q tests.test_crew_e2e )
```

The script keeps, in bash, what only it can know: `git` present; the
interpreter prerequisite above; the rendered shebang's first line equals the
expected line for `{{ .chezmoi.os }}`/`{{ .chezmoi.arch }}` (the per-OS,
per-arch acceptance test: the script carries the same three-way branch as the
partial, written out, so a partial that renders the wrong path on an Intel Mac
is caught by the first `chezmoi apply` there); no
`__pycache__` under `~/.claude` (3.3: our scripts never write one);
`settings.json` parses and wires five hooks and two status lines to paths
that exist and are executable; the eight agent files exist; `crew help` exits
0 on stdout; `~/.claude/bin` on `PATH` hint; and the guard probes, run
**through the command string read out of `settings.json`** (`sh -c "$cmd"`,
exactly as Claude Code does), four of them as today plus two for section 3:

- `PATH= sh -c "$cmd"` with `terraform destroy` still denies (the shebang is
  absolute; no `PATH` is needed);
- `sh -c "${cmd/guard-infra.py/does-not-exist.py}"` exits 2 with non-empty
  stderr (the backstop fires on a hook that cannot start).

About 110 lines of bash, down from 268 (335 with the branch). Trigger, in the
form verified against chezmoi 2.72.1 on 2026-10-05 (`glob` returns nothing
for a source-relative pattern; `include` accepts the absolute paths it
returns), with the new file names:

```
# {{ range glob (joinPath .chezmoi.sourceDir "dot_claude/hooks/*") }}{{ include . | sha256sum }} {{ end }}
# {{ range glob (joinPath .chezmoi.sourceDir "dot_claude/lib/claudetools/*.py") }}{{ include . | sha256sum }} {{ end }}
# {{ include "dot_claude/bin/executable_crew.tmpl" | sha256sum }}
# {{ include "dot_claude/settings.json" | sha256sum }}
# {{ include ".chezmoitemplates/python-shebang" | sha256sum }}
# {{ include "tests/test_crew_e2e.py" | sha256sum }}  {{ include "tests/support.py" | sha256sum }}
```

## 7. Build plan

Each step is one branch, one `--no-ff` merge, and leaves `chezmoi apply`
producing a working `~/.claude`. Rollback for every step is
`git revert -m 1 <merge>` followed by `chezmoi apply`; the Rollback column says
what else, if anything. **SR** = `security-reviewer` sign-off before merge.
Steps 0 and 1 are on `main` (436ae03, a049b2e and the guard follow-ups).

| # | Step | ~diff | Done when | SR | Rollback notes |
|---|---|---|---|---|---|
| 0 | `.chezmoiignore` pycache lines; Makefile `unittest discover`; `tests/__init__.py`, `tests/support.py` | done | on `main` | | |
| 1 | `tests/test_guard.py`: the regression table against the current guard, including the fail-open row | done | on `main` | done | |
| 2 | **Pin the interpreter.** `.chezmoitemplates/python-shebang` with the three-way os/arch branch and `-ISB` (3.3, decisions 14, 16); rename `executable_guard-infra.py` and `executable_crew` to `.tmpl` with the header (3.3); `settings.json`: the four `python3 <path>` lines become direct, the guard's gains `\|\| exit 2`, `Edit(~/.claude/lib/**)` deny added; guard rules: self-protection `bin\|lib`, the interpreter-path deny group over both `/opt/homebrew` and `/usr/local` python paths, and the `brew`/`make brew` **deny** group with the packages.yaml message (6.2, decision 15); `tests/test_entrypoints.py` incl. `test_site_is_not_imported` and `test_imports_are_stdlib_or_ours`; `support.py` (`-ISB`) and `tests/__init__.py` per 6.1; the two guard probes, the interpreter prerequisite, the `site` probe and the per-os/arch shebang check added to the existing self-test (6.3); the self-test `include` lines follow the renames | 300 | `make test` incl. the *new* table rows (Intel paths, brew deny, brew read-only allow, option-before-subcommand, `make brew`); after `chezmoi apply`, `head -1 ~/.claude/hooks/guard-infra.py` is the per-OS/arch line ending `-ISB` and the self-test's new probes pass; by hand once: `sh -c "$(jq -r ...PreToolUse command...)"` with `PATH=` denies `terraform destroy`, and `brew install python` is denied with the packages.yaml message | **SR** (policy: backstop, interpreter-path deny incl. `/usr/local`, `brew`/`make brew` deny, `Edit` deny, `-ISB`) | Revert restores `env python3` and the `python3 <path>` lines; a stray `.chezmoitemplates/` file is inert |
| 3 | Guard restructure: `guard_rules.py` + engine; `classify()`; `Word`/`Piece`; drop the duplicate comment; fail-open and cannot-start docstrings | 300 | the full table unchanged (no row moves) | **SR** (refactor; the table is the proof) | Revert restores the single file; a stray `guard_rules.py` is inert |
| 4 | `lib/claudetools/{__init__,hookio,gitx}.py` extracted; `crew` imports them via the appended `lib` path; absorbs `Capture`/`debug_dir`/docstring from the branch (2.8) | 300 | existing bash self-test green; `make test` | | Revert: `crew` self-contained again; stray `lib/` inert |
| 5 | `launches.py` + `workspace.py` extracted (with `free_suffix` and the `settle`/`adopt_branch` merge); absorbs the poll, `match_launch`, the 2.1.287 note; `tests/test_launches.py`, `tests/test_workspace.py` | 340 | self-test; new unit tests | | Behaviour change is limited to the merged rename path and the new 2 s wait |
| 6 | `crew_hooks.py` + `crew_cli.py`; `bin/executable_crew.tmpl` becomes the ~40-line entry; drop the legacy symlink sweep | 300 | self-test | | |
| 7 | `tests/test_crew_e2e.py` (dual-target via `crew_argv()`, every scenario from the self-test plus the four from the branch) and `tests/test_crew_cli.py` (pty) | 340 | `make test`; `CREW=~/.claude/bin/crew make test` also green against the deployment | | No deploy change |
| 8a | `textfmt.py`, `width.py`, `layout.py` + `tests/test_width.py` (ported `width_source_suite`) | 280 | unit tests | | No deploy change: nothing imports them yet |
| 8b | `executable_statusline.py.tmpl`; harness gains `--script` and runs both `.sh` and `.py.tmpl`; `test_entrypoints.py` picks it up by glob | 260 | property suite green for both | | Not wired into `settings.json` yet; the `.sh` still renders |
| 9 | `executable_subagent-statusline.py.tmpl`; `subagent_suite` runs both | 180 | property suite | | same |
| 10 | `settings.json` points at the `.py` status lines; delete the three `.sh`; delete the multi-bash loop and `bash_version` from the harness; `Edit(~/.claude/*.sh)` becomes `*.py` | 150 net negative | property suite; self-test | **SR** (permissions) | Revert then `chezmoi apply` re-deploys the `.sh` files |
| 11 | `hooks/executable_title.py.tmpl`; `settings.json` four entries; delete `title.sh`; `jq` removed from the self-test prerequisites | 50 | manual: the title changes on `cd`; `test_entrypoints.py` | **SR** light (settings) | Revert re-deploys `title.sh` |
| 12 | Self-test `.tmpl` rewritten per 6.3: bash smoke checks, rendered-shebang and no-pycache checks, guard probes through the `settings.json` command strings, `test_crew_e2e` against `~/.claude/bin/crew`, verified `glob` trigger | -150 | `chezmoi apply` on this box; once on an Ubuntu 24.04 target | **SR** light (the probes are the deployed acceptance test of step 2) | The old script returns and re-runs on its content change |
| 13 | AGENTS.md "Repository layout" gains `.chezmoitemplates/`, `dot_claude/lib/`, `tests/`; the chezmoi conventions table gains the `#!{{ template "python-shebang" . }}` rule for Python entry points | 20 | | | |

Dependencies and parallelism: 3 follows 2 (same file); 4-7 follow 2 and are
independent of 8a-10, so two branches can run side by side once 2 is in; 8a
can start any time; 8b and 9 need 2 (the partial); 10 waits for 8b and 9; 11
waits for 10; 12 waits for 3, 7, 10 and 11; 13 is last. Keep one branch per
step; sizes are the upper bound, not a target.

Suggested first task for `craft-engineer`: **step 2.** It is the one piece
every later step depends on, it is the only step that changes what runs the
guard, and it is small enough for `security-reviewer` to read whole. It was
blocked on old open question 1 (Intel) and is unblocked by decisions 14-16;
nothing in section 9 gates it now.

## 8. Options considered and rejected

- **Keep bash for the status lines, restructure only the Python.** Rejected:
  765 of the 1,650 lines under review are the bash, every bash-specific trap
  in them is already documented as a trap, and the measured latency case for
  bash does not exist on this machine (3.5).
- **Everything Python, but single self-contained files and no shared package.**
  Rejected for `crew` and the status lines: the duplicated git wrapper, payload
  reader and text helpers are exactly the code that drifts between copies.
  Accepted for the guard, where a small blast radius is the point.
- **One package including the guard.** Rejected: the safety control must be
  reviewable without reading `crew`, and must keep working when the package is
  mid-refactor.
- **Interpreter search and re-exec (`pyfloor`), mise-provisioned Python, a
  3.9-safe preamble.** The previous design (8612dd6). Withdrawn by decisions
  8-9 and 13: it answered a question ("what if no modern Python is on the
  box?") that the OS package manager already answers, at the cost of ~80 lines
  of resolver, a syntax rule for five files, two environment variables, a
  second provisioning path and a per-entry degraded-behaviour table.
- **`#!/usr/bin/env python3` with a 3.9 floor so nothing needs selecting.**
  Rejected by decision 1; and never complete: a `PATH` without `python3` at
  all, or a project pinning 2.7 via mise, breaks it the same silent way.
- **Shebang options A, C, D, E** in 3.2 (inline per file, wrapper
  interpreter, config-template variable, `brew --prefix` at render time).
- **A single shared shebang for both OSes** (`/usr/bin/python3`). Rejected:
  on macOS that is Apple's 3.9.6, which is below the floor; `/usr/local/bin`
  is empty on Apple Silicon.
- **`uv run` / PEP 723.** Rejected: one more tool, network on first run, and
  the same `PATH` problem for `uv` itself.
- **Fail-closed on an unparsable payload.** Rejected by decision 2 (2.2).
- **An `ask` JSON when the interpreter is too old** (the previous design's
  guard behaviour). Moot: it needed 3.9-safe code to run on the old
  interpreter. The block is the visible failure decision 12 asks for.
- **A 3.12 python from apt on older Ubuntu/Debian.** Out of scope by decision
  12; the gate reports it.
- **Replace `scrub()`'s tokenizer with `shlex`.** Deferred, not rejected:
  possible later as its own `security-reviewer`-gated step, with the table as
  the equivalence proof.
- **Third-party libraries (`click`, `rich`, `pytest`).** Out: stdlib-only, no
  pip on the host, both OSes; and with `-S` (decision 16) there is no
  `site-packages` on `sys.path` at all, so it is not a preference but a
  property of the shebang (5.4).
- **Merge `crew-launch-naming` first, then extract.** Rejected by decision 7.
- **Intel Macs out of scope** (the partial's darwin branch always
  `/opt/homebrew`). Rejected by decision 14: one nested template line and a
  row of deny paths against a guard that is dead on day one of such a machine.
- **`brew` asks, and only on verbs that name python** (the previous design's
  rule). Replaced by decision 15: there is no legitimate agent use of a
  state-changing `brew` command in this repo's model, where packages are data
  in `.chezmoidata/packages.yaml` and chezmoi's before-script is the only
  thing that runs `brew bundle`; an ask invites exactly the "agent installs
  something to make its task easier" path the human does not want, and a deny
  with a message that names the file is the cheaper control.
- **`-IB` without `-S`** (the previous default, "the deny rules cover the
  directory and `-S` is the less familiar flag"). Replaced by decision 16: the
  deny rules only stop the agent's *own* Bash tool from writing a `.pth`;
  `-S` makes the guard indifferent to the directory's contents regardless of
  who wrote them, and the 4 ms is a bonus.
- **`-I -S -B` as three shebang tokens.** Works on macOS, breaks on Linux
  (3.3); `-ISB` only.

## 9. Open questions for the human

None of these gates step 2.

1. **Is `chezmoi apply` (and the Makefile routes to it) guarded?** Decision
   15 says only chezmoi runs `brew`, which makes `chezmoi apply` the one
   command through which an agent could still change installed packages
   (its before-script runs `brew bundle` from `.chezmoidata/packages.yaml`,
   which an agent can edit; `packages.yaml` is a plain file under no deny
   rule). Today neither the guard nor `settings.json` mentions `chezmoi`,
   `make chez-apply`, or the Makefile's `%:` catch-all (`make apply` is
   `chezmoi apply`) (grep, 2026-10-14). The human's working rules already say
   no host changes without asking, and this doc assumes `chezmoi apply` is the
   human's act throughout. Whether it should be a guard `ask` or `deny` is a
   policy decision outside this review; raised, not designed.
2. **`brew update` in the deny group.** Not in either of the human's lists
   (6.2 explains why it was put in deny). Confirm, or strike it; one regex
   alternation and one row either way.

Old questions 1 (Intel), 2 (`brew` breadth) and 3 (`-S`) are answered by
decisions 14-16 (section 1b). Older questions 1 (mise pin) and 3 (`ask` vs
`deny` with no interpreter) are moot; older question 2 (the backstop) was
defaulted to yes and is a measured, tested part of the design.

## 10. Hand-offs

- `craft-engineer`: steps 2-13 in order; each step's gate is in the table;
  first task is step 2, unblocked as of 2026-10-14.
- `security-reviewer`: steps 2, 3, 10, 11, 12; the `crew-debug` capture
  retention note (2.8) lands with step 4. For step 2 specifically: the
  `|| exit 2` backstop, `-ISB` and the stdlib-only constraint it hardens
  (5.4), the `sys.path.append` rule, the interpreter-path deny group over both
  Homebrew prefixes, the `brew`/`make brew` deny group and its regexes with
  the residual-risk statement (6.2, 3.3), the `Edit(~/.claude/lib/**)` deny,
  the env-block note in 2.5, and open question 1 (`chezmoi apply` unguarded)
  as a policy item to take to the human.
- `infra-engineer`: nothing; no new infrastructure.

## 11. Change log

### 11.1 Changes from e31a951 (2026-10-13)

Recorded 2026-10-14. Decisions 14-16 (section 1b) are the human's; they
answer the three open questions of e31a951 and everything below follows from
them. Nothing else in the design moved.

- **Intel Macs in scope (decision 14).** The partial (3.3) nests an
  `eq .chezmoi.arch "amd64"` branch inside the darwin branch:
  `/usr/local/bin/python3` on Intel, `/opt/homebrew/bin/python3` on Apple
  Silicon, `/usr/bin/python3` on Linux. 3.1's Intel row is in scope and
  marked untested on hardware. 3.2 rows A and E reference the decision
  instead of the question. 6.1: `test_partial_names_all_three_interpreters`
  and `test_rendered_shebang_for_this_os_and_arch` replace the two-way tests.
  6.2: the seven interpreter deny rows are repeated under `/usr/local`, the
  prefix in the rule becomes `(/opt/homebrew|/usr/local)`, and an allow row
  pins that a non-python path under `/usr/local/bin` is untouched. 6.3: the
  self-test's rendered-shebang check carries the os/arch branch.
- **Agents never run `brew` (decision 15).** The "`brew` verbs naming python
  ask" rule is gone. 6.2 gains a deny group with the packages.yaml message:
  `install reinstall upgrade uninstall remove rm link unlink tap untap cleanup
  autoremove pin unpin postinstall update`, `services start|stop|restart|run`,
  `bundle` in every form but `check`/`list`, and `make brew` (the Makefile
  runs `brew update`, `brew bundle install`, `brew bundle cleanup --force`;
  read 2026-10-14). Read-only `brew` is allowed and pinned by rows. Rows cover
  option-before-subcommand, quote stripping, env prefix, `sh -c`, chains and
  scrub, in the guard's existing `_OPTS` form; the four regexes were checked
  against all 71 rows through the current guard's `scrub`/`normalize`. The
  residual (brew inside a script the agent writes, then runs) is stated in
  3.3's failure modes as not covered. Conclusion 5, 3.3's "fix from a
  terminal" paragraph, 3.3's failure-mode bullet and section 8 follow.
  `brew update` is in the group on this review's judgement, flagged as open
  question 2.
- **`-S` added (decision 16).** The flags are `-ISB` everywhere the doc
  said `-IB`: conclusions 1 and 4, the partial, 2.7, 6.1 (harness,
  `support.py`, the entry-point tests), 6.3 (`crew_argv`, the prerequisite
  line, the e2e invocation) and step 2. 3.3 rewrites the flags paragraph:
  `site` executes `.pth` `import` lines at start, `-I` removes only the user
  site, the Homebrew system site is user-writable, `-S` skips `site`
  entirely; and states why the flags are one token (`-I -S -B` breaks on
  Linux). 3.5 adds the `-IB` and `-ISB` rows (13.0 vs 9.0 ms, 2026-10-14).
  6.1 adds `test_site_is_not_imported` and `test_imports_are_stdlib_or_ours`;
  6.3 adds a `site` probe. 5.4 records the constraint: no third-party
  package in any hook, ever, without revisiting decision 16. Section 8 lists
  the withdrawn `-IB`-only default and the three-token form.
- **Verified 2026-10-14 on this Mac (darwin/arm64, chezmoi 2.72.1, Homebrew
  python 3.14.7):** a scratch script with `#!/opt/homebrew/bin/python3 -ISB`
  runs with all six flags set and `site` absent; `-ISB -c` prints `False`
  for `'site' in sys.modules` and `-IB` prints `True`; the nested partial
  renders `#!/opt/homebrew/bin/python3 -ISB`; `.chezmoi.arch` is `arm64`
  here; `make -n brew` prints the three brew lines; the current guard denies
  `sh -c "terraform destroy"`, `terraform 'destroy'`, `TF_LOG=1 terraform
  destroy` and `terraform destroy || true`, which is the basis for the same
  brew rows. **Assumed, not verified:** that `.chezmoi.arch` is `amd64` on
  an Intel Mac (Go `GOARCH`; no Intel Mac available), that Homebrew on Intel
  makes `/usr/local/{bin,Cellar,opt,lib}` user-writable (Homebrew docs), and
  that Linux passes the shebang's trailing text as a single argument
  (kernel `binfmt_script` semantics; not run on Linux).
- **Open questions (9)** are now: whether `chezmoi apply`/`make apply` should
  be guarded (raised by decision 15, not designed), and `brew update`.
  Step 2 is unblocked (7, 10).

### 11.2 Changes from 8612dd6 (2026-10-05)

Recorded 2026-10-13. Decisions 8-13 (section 1b) are the human's, not this
review's; the sections below follow from them.

- **Interpreter strategy replaced (decisions 8, 10, 11).** `pyfloor`, the
  3.9-safe preamble, the re-exec, `CLAUDE_PYTHON`, `CLAUDE_PYFLOOR_DIRS` and
  the fixed-directory search are removed. Section 3 is now: a per-OS absolute
  shebang (`/opt/homebrew/bin/python3` / `/usr/bin/python3`, `-IB`) rendered
  from one `.chezmoitemplates/python-shebang` partial into `.tmpl` entry
  points (3.2 weighs five ways to render it; the partial won), a two-line
  version gate for the message, and the `|| exit 2` backstop. The chezmoi
  mechanics were verified on a scratch source (`executable_` + `.tmpl`
  compose, mode 0755, `execute-template --source` resolves the partial, a
  stray `{{` fails the render).
- **Fail-closed table (3.3).** Each way the guard can fail to start was run
  with and without the backstop on this Mac; every one is exit 2 with the
  backstop. The fail-open-on-unparsable-payload policy (decision 2) is stated
  separately and is unchanged.
- **Provisioning (decision 9).** The mise pin and
  `run_onchange_after_00-mise-tools` are gone; section 4 verifies that
  `packages.yaml` and the before-script already install Homebrew `python` and
  apt `python3`. Ubuntu 24.04's 3.12.3 is from packages.ubuntu.com, not a test.
- **Linux scope (decision 12).** Ubuntu 24.04 or newer; older releases fail
  the gate visibly. The previous design's "apt cannot be relied on" reasoning
  about 22.04 and Debian 12 is withdrawn as out of scope.
- **Security notes from the reviews of the abandoned step-2 work** are carried
  into step 2 and 6.2: deny rules for writes and symlinks under
  `/opt/homebrew/{bin,Cellar,opt,lib}` python paths; self-protection extended
  to `bin|lib` with explicit `__pycache__` rows; `Edit(~/.claude/lib/**)`
  deny; `lib` appended to `sys.path`, never inserted at the front; `-I` makes
  the settings `env` block (which a project file can set) irrelevant to the
  interpreter.
- **Intel Macs** are open question 1 with a default of in scope.
- **Tests (6.1).** `test_pyfloor.py` is gone; `test_entrypoints.py` is
  rewritten around the shebang: shared first line, no stray template syntax,
  gate present, parses under 3.12, runs by path under `-IB`, rejected below
  the floor, partial names both interpreters, rendered line matches this OS,
  rendered interpreter exists and meets the floor, `settings.json` calls
  entries directly with the backstop.
- **Self-test (6.3).** Prerequisite becomes "the interpreter the deployed
  guard's shebang names exists and is ≥ 3.12"; probes are `PATH=` deny and a
  missing-file backstop check instead of the re-exec probe; a rendered-shebang
  and no-`__pycache__` check are added; `include` lines follow the `.tmpl`
  renames.
- **Build plan (7).** Steps 0 and 1 marked done on `main`. Step 2 is now
  "pin the interpreter" and absorbs the security items; step 3 is a pure
  refactor; the Makefile `PY` variable and mise work are dropped; the
  self-test gains its two new probes in step 2 rather than waiting for 12;
  step 13 documents the shebang convention in AGENTS.md.
- **Options (8)** lists the withdrawn design and why; **open questions (9)**
  are three new ones (Intel, `brew` policy breadth, `-S`), with the three old
  ones closed.
- Section 2.8 / decision 7 (`crew-launch-naming`) is unchanged.
