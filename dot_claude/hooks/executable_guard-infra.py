#!/usr/bin/env python3
"""
PreToolUse guard for Bash commands in Claude Code.

Reads the hook payload on stdin, inspects tool_input.command, and:
  - DENIES destructive / irreversible infra commands (returns a reason to Claude)
  - forces an ASK (interactive confirmation) for anything that looks production-scoped
  - otherwise ALLOWS by exiting 0 with no output (normal permission rules still apply)

WHAT THIS CAN AND CANNOT DO. Pattern-matching a command line is harm reduction, not
enforcement. It raises the cost of an accident; it does not stop a determined path. A
mutation can live in a file the pattern never sees (`gh api graphql --input x.json`), and
a token with `repo` scope can merge a PR by routes no regex enumerates. The rule "no agent
lands a pull request" is only true when the token cannot do it: use a fine-grained PAT
without `administration`, and protect the branch server-side. Treat everything below as a
seatbelt, not a lock.

Extend DENY_PATTERNS / ASK_PATTERNS to match your stack. Test with:
  echo '{"tool_name":"Bash","tool_input":{"command":"terraform destroy"}}' | python3 guard-infra.py
"""
import json
import re
import sys

# `git -C <path> push` is the idiomatic form for working across worktrees, and it defeats
# every \bgit\s+push\b style pattern below -- as does `git --git-dir=... merge`, and as do
# quotes around a subcommand (`gh 'pr' merge`). Anthropic's own permission docs note the
# glob layer does not stop these either. Strip both before matching so the patterns see a
# canonical command. Anything added here must be a *global* option that takes no subcommand.
# A value for a git global option: single-quoted, double-quoted, or bare. Worktree paths
# with spaces are ordinary, and `-C \S+` would swallow only the first half of one.
_VAL = r"(?:\"[^\"]*\"|'[^']*'|\S+)"

# `git -C <path> push` is the idiomatic form for working across worktrees, and it defeats
# every \bgit\s+push\b style pattern -- as do the other global options, quoting, and line
# continuations. Anthropic's permission globs do not see through these either. IGNORECASE
# because the filesystem is case-insensitive here: `GIT --version` runs.
GIT_GLOBAL_OPTS = re.compile(
    r"\bgit\s+((?:"
    r"-C\s+" + _VAL + r"|-c\s+" + _VAL +
    r"|--(?:git-dir|work-tree|namespace|exec-path|attr-source|super-prefix|config-env)"
    r"(?:=|\s+)" + _VAL +
    r"|-P|-p|--paginate|--no-pager|--bare|--no-replace-objects|--no-optional-locks"
    r"|--no-lazy-fetch|--no-advice|--literal-pathspecs|--glob-pathspecs"
    r"|--noglob-pathspecs|--icase-pathspecs"
    r")\s+)+",
    re.IGNORECASE,
)


def normalize(cmd: str):
    """Return (raw, stripped) forms of a command, both flattened to single spaces.

    Patterns are matched against BOTH. Stripping global options is what lets
    `git -C /x push` match a rule written as `git push`, but it also deletes evidence:
    `git -c remote.origin.url=... push` becomes a bare `git push`, and the rule aimed at
    repointing a remote would never see it. Matching both forms avoids trading one blind
    spot for another.

    Not a security boundary on its own -- see the note at the top of this file.
    """
    raw = " ".join(cmd.replace("\\\n", " ").split())
    raw = " ".join(tok for tok in raw.split() if tok != "\\")
    stripped = GIT_GLOBAL_OPTS.sub("git ", raw).replace("'", "").replace('"', "")
    return raw, stripped


# A blocked phrase that is only being talked about is not a command: the text of a commit
# message, or the string a search is looking for. Matching those denied
# `git commit -m "explain why terraform destroy is blocked"` and `grep -rn "drop table" .`
# scrub() takes that text out before the patterns run. It is deliberately narrow. Anything
# the shell would still execute or write to stays in: a word holding `$(...)` or backticks,
# a redirection and its target, and every other command on the line.
_PIECE = re.compile(
    r"(?P<nl>\n)"
    r"|(?P<ws>[^\S\n]+)"
    r"|(?P<quoted>\"(?:\\.|[^\"\\])*\"|'[^']*')"
    r"|(?P<redir>\d*[<>]+&?\d*-?|&>>?)"
    r"|(?P<sep>[;|&()]+)"
    r"|(?P<bare>(?:\\.|[^\s;|&()<>\"'])+)",
    re.DOTALL,
)
SEARCH_TOOLS = {"grep", "egrep", "fgrep", "rg"}
_MESSAGE_FLAG = re.compile(r"-[a-zA-Z]*m|--message")


def _text(word):
    return "".join(piece for _, piece in word[1])


def _inert(word):
    """True when dropping the word cannot hide something the shell would run or write."""
    text = _text(word)
    return "$(" not in text and "`" not in text and not any(k == "redir" for k, _ in word[1])


def _search_args(words):
    """Indexes of a search command's arguments, leaving redirections and their targets."""
    drop, keep_next = set(), False
    for i, word in words:
        if keep_next or not _inert(word):
            keep_next = word[1][-1][0] == "redir"   # `> file`: the target is the next word
            continue
        drop.add(i)
    return drop


def _message_args(words):
    """Indexes of the values given to `git commit -m` / `--message`."""
    drop, take = set(), False
    for i, word in words:
        text = _text(word)
        if take:
            take = False
            if _inert(word):
                drop.add(i)
        elif _MESSAGE_FLAG.fullmatch(text):
            take = True
        elif text.startswith("--message=") and _inert(word):
            drop.add(i)
    return drop


def _scrub_segment(seg):
    words = [(i, tok) for i, tok in enumerate(seg) if tok[0] == "word"]
    while words and re.fullmatch(r"\w+=.*", _text(words[0][1]), re.DOTALL):
        words = words[1:]                           # leading VAR=value assignments
    if not words:
        return "".join(_text(t) if t[0] == "word" else t[1] for t in seg)
    command, args = _text(words[0][1]).rsplit("/", 1)[-1], words[1:]
    names = [_text(w) for _, w in args]
    drop = set()
    if command in SEARCH_TOOLS:
        if not any(n == "--pre" or n.startswith("--pre=") for n in names):   # rg --pre runs a command
            drop = _search_args(args)
    elif command == "git" and "grep" in names:
        drop = _search_args(args[names.index("grep") + 1:])
    elif command == "git" and "commit" in names:
        drop = _message_args(args[names.index("commit") + 1:])
    return "".join("" if i in drop else (_text(t) if t[0] == "word" else t[1])
                   for i, t in enumerate(seg))


def scrub(cmd: str) -> str:
    """Remove commit-message and search-pattern text from a command line."""
    cmd = cmd.replace("\\\n", " ")
    tokens, pos = [], 0
    for m in _PIECE.finditer(cmd):
        if m.start() != pos:
            return cmd      # unreadable (an unclosed quote, say): scrub nothing
        pos = m.end()
        kind = m.lastgroup
        if kind in ("quoted", "bare", "redir"):
            if tokens and tokens[-1][0] == "word":
                tokens[-1][1].append((kind, m.group()))
            else:
                tokens.append(("word", [(kind, m.group())]))
        else:
            tokens.append(("ws" if kind == "ws" else "break", m.group()))
    if pos != len(cmd):
        return cmd
    out, seg = [], []
    for tok in tokens + [("break", "")]:
        if tok[0] == "break":
            out.append(_scrub_segment(seg) + tok[1])
            seg = []
        else:
            seg.append(tok)
    return "".join(out)


# Global options sit between a tool and its subcommand: `terraform -chdir=infra destroy`,
# `kubectl --context dev delete ns x`, `aws --profile dev kms schedule-key-deletion`. A
# rule written as `\btool\s+subcommand` misses every one of them, and the settings.json
# allow for `Bash(terraform:*)` then runs the command without asking. _OPTS spans whatever
# lies between the two words but stops at a shell separator, so the subcommand must belong
# to the same command as the tool (normalize() has already joined lines with spaces, so a
# newline is not a separator here). Keeping every scan inside one segment is also what
# keeps it linear: the old gcloud/az rules nested two unbounded `.*` and took minutes on a
# long command, which is longer than the hook timeout -- and a timed-out hook does not block.
#
# Where a rule needs two words that are not adjacent (`apply ... -auto-approve`,
# `delete ... --all`, or gcloud/az which put the resource before the verb: `gcloud sql
# instances delete X`, `az group delete`), it looks for each one independently with a
# lookahead over the same segment, `(?=[^;|&]*\sWORD\b)`. Two lookaheads cost two scans;
# `A[^;|&]*B[^;|&]*C` costs one scan per candidate B, which a repeated word turns cubic.
_OPTS = r"\b[^;|&]*?\s"

DENY_PATTERNS = [
    # Terraform / OpenTofu
    (r"\b(terraform|tofu)" + _OPTS + r"destroy\b", "terraform destroy is never run by an agent"),
    # Terraform takes `-destroy` and `--destroy` alike.
    (r"\b(terraform|tofu)\b(?=[^;|&]*\sapply\b)(?=[^;|&]*\s--?destroy\b)", "terraform destroy is never run by an agent"),
    (r"\b(terraform|tofu)" + _OPTS + r"state\s+(rm|mv|push)\b", "manual Terraform state surgery must be done by a human"),
    (r"\b(terraform|tofu)\b(?=[^;|&]*\sapply\b)(?=[^;|&]*-auto-approve)", "terraform apply -auto-approve bypasses plan review"),
    (r"\b(terraform|tofu)" + _OPTS + r"workspace\s+delete\b", "deleting a Terraform workspace is irreversible"),
    # Kubernetes / Helm
    (r"\bkubectl" + _OPTS + r"delete\s+(ns|namespaces?)\b", "deleting a namespace destroys everything in it"),
    (r"\bkubectl\b(?=[^;|&]*\sdelete\b)(?=[^;|&]*\s--all\b)", "kubectl delete --all is too broad"),
    (r"\bkubectl" + _OPTS + r"delete\s+(pv|pvc|persistentvolume)", "deleting persistent volumes destroys data"),
    (r"\bhelm\s+(uninstall|delete)\b", "helm uninstall must be run by a human"),
    # Cloud CLIs — deletion of durable resources / audit & backup controls
    (r"\baws\b(?=[^;|&]*\ss3\s+(rb|rm)\b)(?=[^;|&]*(--force|--recursive))", "recursive S3 deletion"),
    (r"\baws" + _OPTS + r"kms\s+(schedule-key-deletion|disable-key)\b", "KMS key deletion makes encrypted data unrecoverable"),
    (r"\baws" + _OPTS + r"(rds|dynamodb|ec2)\s+delete-(?!tags\b)", "deleting a stateful AWS resource"),
    (r"\baws\b(?=[^;|&]*\srds\b)(?=[^;|&]*--skip-final-snapshot)", "skipping the final RDS snapshot"),
    (r"\baws" + _OPTS + r"(cloudtrail\s+(stop-logging|delete-trail)|backup\s+delete-)", "disabling audit logging or deleting backups"),
    (r"\baws\b(?=[^;|&]*\ss3api\s+put-bucket-versioning\b)(?=[^;|&]*Suspended)", "suspending S3 versioning"),
    # `\s` before the verb, not `\b`: `rsync -az --delete` is neither az nor a delete verb.
    (r"\bgcloud\b(?=[^;|&]*\s(delete|destroy)\b)(?=[^;|&]*\s(sql|kms|storage|compute|container)\b)",
     "deleting a stateful GCP resource"),
    (r"\bgsutil\s+(rm|rb)\b.*-r", "recursive GCS deletion"),
    (r"\baz\b(?=[^;|&]*\s(delete|purge)\b)(?=[^;|&]*\s(sql|keyvault|storage|vm|aks|group|postgres|mysql|cosmosdb|backup)\b)",
     "deleting a stateful Azure resource"),
    # Databases
    (r"\bdrop\s+(database|table|schema)\b", "DROP DATABASE/TABLE/SCHEMA"),
    (r"\btruncate\s+table\b", "TRUNCATE TABLE"),
    (r"\bpg_dropcluster\b", "dropping a Postgres cluster"),
    # Git / GitHub
    (r"\bgh\s+pr\s+merge\b", "landing a pull request is the human's call alone"),
    (r"\bgh\s+api\b.*/pulls/[^/\s]+/merge", "merging a pull request through the API"),
    (r"api\.github\.com.*/pulls/[^/\s]+/merge", "merging a pull request through the API"),
    (r"\bmergePullRequest\b", "merging a pull request through the GraphQL API"),
    # Read queries are fine; a mutation is not, and a body in a file cannot be inspected.
    (r"\bgh\s+api\s+graphql\b.*\bmutation\b", "a GraphQL mutation can land a pull request"),
    (r"\bgh\s+api\s+graphql\b.*--input\b", "a GraphQL body in a file cannot be inspected"),
    (r"\bgh\s+alias\s+set\b", "a gh alias can rename a denied command"),
    # Only the WRITE methods. Reading protection state is how you check the backstop exists.
    (r"\bgh\s+api\b(?=.*(branches/[^\s]*/protection|rulesets))(?=.*(?:--method|-X)\s*=?\s*(?:PUT|POST|PATCH|DELETE))",
     "branch protection is the backstop; it is not yours to change"),
    # The guard is a file. rm/mv/truncate reach it without going through Edit, so the
    # Edit(~/.claude/...) denies do not cover them -- the docs are explicit that they do not
    # apply to subprocesses that write files indirectly.
    # Match only commands that WRITE there. An earlier version matched the path anywhere,
    # which denied `cat ~/.claude/settings.json` -- reading the config is routine and fine.
    (r"\b(rm|mv|dd|truncate|tee|shred|unlink|chmod|chown)\b[^;|&]*\.claude/(hooks|settings|agents)",
     "the agent guardrails are not the agent's to remove or overwrite"),
    # cp and install only write to their destination. Copying a guardrail file OUT, to
    # back it up or compare it, is a read.
    (r"\b(cp|install)\b[^;|&]*\s\S*\.claude/(hooks|settings|agents)[^\s;|&]*\s*(?:$|[;|&])",
     "the agent guardrails are not the agent's to remove or overwrite"),
    (r"\b(cp|install)\b[^;|&]*\s(-t|--target-directory)[= ]?\S*\.claude/(hooks|settings|agents)",
     "the agent guardrails are not the agent's to remove or overwrite"),
    (r">>?\s*\S*\.claude/(hooks|settings|agents)",
     "redirecting over the agent guardrails"),
    (r"\.claude/(hooks|settings|agents)[^\s,]*\s*,\s*[wa]\b",
     "opening the agent guardrails for writing"),
    (r"\bgit\s+remote\s+(add|remove|rm|set-url|set-branches|set-head|rename)\b", "changing where this repo points"),
    (r"\bgit\s+config\b.*\bremote\.[^\s]*\.(url|pushurl)\b", "git config remote.<name>.url repoints the remote just as set-url does"),
    # `-c remote.origin.url=...` and `--config-env=remote.origin.url=...` repoint the
    # remote for one command without touching any config file. Matched on the raw form,
    # since normalize() strips exactly these options away.
    (r"\bgit\b.*\bremote\.[^\s=]*\.(url|pushurl)\s*=", "repointing the remote inline, for this command only"),
    (r"\bgit\s+config\b.*\binsteadOf\b", "an insteadOf rewrite silently redirects every push and fetch"),
    (r"\bGIT_CONFIG_KEY_\d+\s*=", "GIT_CONFIG_* env vars inject config without touching a config file"),
    # CLAUDE.md says never force-push, to any branch. The first rule names the branches that
    # matter most so the reason says so; the second takes the rest. A force is `--force`,
    # `--force-with-lease`, an `f` anywhere in a flag cluster (`-uf`), or a `+refspec`.
    (r"\bgit\s+push\b(?=[^;|&]*\s(--force(-with-lease)?\b|-[a-zA-Z]*f[a-zA-Z]*\b|\+\S))"
     r"(?=[^;|&]*\b(main|master|prod|production|release)\b)",
     "force-push to a protected branch"),
    (r"\bgit\s+push\b[^;|&]*\s(--force(-with-lease)?\b|-[a-zA-Z]*f[a-zA-Z]*\b|\+\S)",
     "a force-push is never run by an agent, whatever the branch"),
    # (?-i:...) because the patterns run case-insensitively, and `git branch -d` is the
    # safe form: it refuses to delete a branch that has not been merged.
    (r"\bgit\s+(branch\s+(?-i:-D)|reset\s+--hard\s+origin)", "destructive git history operation"),
    (r"\bgit\s+worktree\s+remove\b.*(--force|-f\b)", "force-removing a worktree discards an agent's work"),
    (r"\bgit\s+branch\s+-[dD]\s+agent/", "deleting an agent branch"),
    (r"\bcrew\s+clean\b", "removing agent workspaces is the human's call; crew clean is theirs to run"),
    # A merge without --no-ff leaves no merge commit, so `git log --merges` cannot show
    # where the change came from and `git revert -m 1` has nothing to revert. That is the
    # whole basis on which local merging was allowed.
    (r"\bgit\s+merge\b.*(--ff-only|--squash)", "merges must be --no-ff so they can be reverted in one step"),
    # Filesystem / host
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+(/|~|\$HOME|\.\.?|\*)(\s|$)", "recursive rm on a root/home/cwd path"),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+/(etc|var|usr|boot|opt|srv)\b", "recursive rm on a system directory"),
    (r"\bmkfs\b|\bdd\s+.*of=/dev/", "disk formatting / raw device write"),
    (r"\bdocker\s+(system|volume)\s+prune\b", "docker prune removes volumes/images"),
    (r"\bsystemctl\s+(disable|mask)\b.*(auditd|rsyslog|journald)", "disabling audit/log services"),
    # Secrets hygiene
    # Within the `git add` itself, and not the committed placeholders (.env.example).
    (r"\bgit\s+add\b[^;|&]*\.(env|pem|key|p12|pfx)\b(?!\.(example|sample|template|dist)\b)",
     "adding secret material to git"),
    (r"\bvault\s+(kv\s+)?(delete|destroy|metadata\s+delete)\b", "deleting Vault secrets"),
]

ASK_PATTERNS = [
    # `apply tfplan` (a saved plan) applies without terraform's own confirmation prompt, so
    # this ask is the only one it gets.
    (r"\b(terraform|tofu)" + _OPTS + r"apply\b", "terraform apply"),
    (r"\b(terraform|tofu)" + _OPTS + r"import\b", "terraform import modifies state"),
    (r"\b(kubectl|helm|kustomize)\b.*(--context|--kube-context)[= ]\S*prod", "kubectl/helm against a prod context"),
    (r"\bkubectl" + _OPTS + r"(apply|delete|patch|scale|drain|cordon)\b", "kubectl write operation"),
    (r"\bkubectl" + _OPTS + r"rollout\s+(?!status\b|history\b)", "kubectl write operation"),
    (r"\bhelm\s+(upgrade|install|rollback)\b", "helm release change"),
    (r"\b(aws|gcloud|az)\b.*(--profile|--project|--subscription)[= ]\S*prod", "cloud CLI against a prod account"),
    (r"\b(terraform|tofu)" + _OPTS + r"workspace\s+select\s+\S*prod", "selecting the prod Terraform workspace"),
    (r"\bansible(-playbook)?\b.*(-i|--inventory)[= ]\S*prod", "ansible against prod inventory"),
    (r"(?:^|\s)(-e|--env|--environment)[= ]?prod(uction)?\b", "explicit prod environment flag"),
    (r"(?:^|\s)(ENV|ENVIRONMENT|STAGE|DEPLOY_ENV)=prod(uction)?\b", "prod environment variable"),
    (r"\bsudo\b", "sudo"),
    # hardware: anything that reprograms a device or changes what the kernel has loaded
    (r"\b(fwupdmgr\s+(install|update|downgrade)|flashrom\b.*-w|dfu-util\b.*-D|avrdude\b.*-U)",
     "flashing firmware is one-way on most devices"),
    (r"\b(rmmod|modprobe\s+-r)\b", "removing a kernel module can drop a live device"),
    (r"\budevadm\s+(control|trigger)\b", "reloading udev re-enumerates devices"),
    (r"\b(hdparm|nvme\s+format|blkdiscard|eject)\b", "low-level storage/device operation"),
    (r"\bsystemctl\s+(restart|stop|disable|mask)\b", "service restart/stop"),
    (r"\bssh\s+\S*(prod|robot|kiosk|device)", "ssh to a production/fleet host"),
    (r"\bgit\s+push\b", "git push"),
    (r"\bgh\s+pr\s+create\b", "opening a pull request"),
    (r"\b(curl|wget)\b.*\bapi\.github\.com\b", "a direct call to the GitHub API"),
    (r"\bgh\s+workflow\s+(run|dispatch)\b", "dispatching a workflow, which may merge on your behalf"),
    (r"\bgh\s+pr\s+review\b.*--approve", "approving a pull request"),
    # the human's working branch is read-only to agents: anything that moves HEAD or discards work asks
    (r"\bgit\s+merge\b(?!.*--no-ff)", "merge without --no-ff -- the merge commit is what makes this revertable"),
    (r"\bgit\s+(checkout|switch|merge|rebase|reset|cherry-pick|restore)\b", "git operation that moves HEAD or discards changes"),
    (r"\bgit\s+stash\b(?!\s+(list|show)\b)", "git operation that moves HEAD or discards changes"),
    (r"\bgit\s+worktree\s+(add|remove|prune)\b", "manual worktree change (crew manages these)"),
]


MAX_COMMAND_CHARS = 8 * 1024


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # malformed input: don't block
    if payload.get("tool_name") != "Bash":
        return 0
    cmd = (payload.get("tool_input") or {}).get("command", "") or ""

    # A few rules still backtrack, and a PreToolUse hook that outlives its timeout is
    # skipped, not failed: a 28 KB command once ran past the 600 s limit and would have
    # been allowed. No command needs to be this long on one line, so ask before scanning.
    if len(cmd) > MAX_COMMAND_CHARS:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    f"Command guard: a {len(cmd) // 1024} KB command is more than the guard will "
                    f"scan ({MAX_COMMAND_CHARS // 1024} KB); move the content into a file "
                    f"— confirm before running."
                ),
            }
        }))
        return 0

    raw, flat = normalize(scrub(cmd))

    for pattern, reason in DENY_PATTERNS:
        if re.search(pattern, flat, re.IGNORECASE) or re.search(pattern, raw, re.IGNORECASE):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Blocked by the command guard: {reason}. Hand the exact command to the human "
                        f"to run manually, and explain the rollback path."
                    ),
                }
            }))
            return 0

    for pattern, reason in ASK_PATTERNS:
        if re.search(pattern, flat, re.IGNORECASE) or re.search(pattern, raw, re.IGNORECASE):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": f"Command guard: {reason} — confirm before running.",
                }
            }))
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
