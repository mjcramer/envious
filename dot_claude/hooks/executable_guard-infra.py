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


DENY_PATTERNS = [
    # Terraform / OpenTofu
    (r"\b(terraform|tofu)\s+destroy\b", "terraform destroy is never run by an agent"),
    (r"\b(terraform|tofu)\s+state\s+(rm|mv|push)\b", "manual Terraform state surgery must be done by a human"),
    (r"\b(terraform|tofu)\s+apply\b.*-auto-approve", "terraform apply -auto-approve bypasses plan review"),
    (r"\b(terraform|tofu)\s+workspace\s+delete\b", "deleting a Terraform workspace is irreversible"),
    # Kubernetes / Helm
    (r"\bkubectl\s+delete\s+(ns|namespace)\b", "deleting a namespace destroys everything in it"),
    (r"\bkubectl\s+delete\b.*\s--all\b", "kubectl delete --all is too broad"),
    (r"\bkubectl\s+delete\s+(pv|pvc|persistentvolume)", "deleting persistent volumes destroys data"),
    (r"\bhelm\s+(uninstall|delete)\b", "helm uninstall must be run by a human"),
    # Cloud CLIs — deletion of durable resources / audit & backup controls
    (r"\baws\s+s3\s+(rb|rm)\b.*(--force|--recursive)", "recursive S3 deletion"),
    (r"\baws\s+kms\s+(schedule-key-deletion|disable-key)\b", "KMS key deletion makes encrypted data unrecoverable"),
    (r"\baws\s+(rds|dynamodb|ec2)\s+delete-", "deleting a stateful AWS resource"),
    (r"\baws\s+rds\b.*--skip-final-snapshot", "skipping the final RDS snapshot"),
    (r"\baws\s+(cloudtrail\s+(stop-logging|delete-trail)|backup\s+delete-)", "disabling audit logging or deleting backups"),
    (r"\baws\s+s3api\s+put-bucket-versioning\b.*Suspended", "suspending S3 versioning"),
    (r"\bgcloud\b.*\b(delete|destroy)\b.*(sql|kms|storage|compute\s+instances|container\s+clusters)", "deleting a stateful GCP resource"),
    (r"\bgsutil\s+(rm|rb)\b.*-r", "recursive GCS deletion"),
    (r"\baz\b.*\b(delete|purge)\b.*(sql|keyvault|storage|vm|aks)", "deleting a stateful Azure resource"),
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
    # Edit(~/.claude/**) deny does not cover them -- the docs are explicit that it does not
    # apply to subprocesses that write files indirectly.
    # Match only commands that WRITE there. An earlier version matched the path anywhere,
    # which denied `cat ~/.claude/settings.json` -- reading the config is routine and fine.
    (r"\b(rm|mv|cp|dd|truncate|tee|install|shred|unlink|chmod|chown)\b[^;|&]*\.claude/(hooks|settings|agents)",
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
    (r"\bgit\s+push\b.*(--force|-f\b|\+)\s*.*\b(main|master|prod|production|release)\b", "force-push to a protected branch"),
    (r"\bgit\s+push\b.*\b(main|master|prod|production|release)\b.*(--force|-f\b)", "force-push to a protected branch"),
    (r"\bgit\s+(branch\s+-D|reset\s+--hard\s+origin)", "destructive git history operation"),
    (r"\bgit\s+worktree\s+remove\b.*(--force|-f\b)", "force-removing a worktree discards an agent's work"),
    (r"\bgit\s+branch\s+-[dD]\s+agent/", "deleting an agent branch"),
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
    (r"\bgit\s+add\b.*\.(env|pem|key|p12|pfx)\b", "adding secret material to git"),
    (r"\bvault\s+(kv\s+)?(delete|destroy|metadata\s+delete)\b", "deleting Vault secrets"),
]

ASK_PATTERNS = [
    (r"\b(terraform|tofu)\s+apply\b", "terraform apply"),
    (r"\b(terraform|tofu)\s+import\b", "terraform import modifies state"),
    (r"\b(kubectl|helm|kustomize)\b.*(--context|--kube-context)[= ]\S*prod", "kubectl/helm against a prod context"),
    (r"\bkubectl\s+(apply|delete|patch|rollout|scale|drain|cordon)\b", "kubectl write operation"),
    (r"\bhelm\s+(upgrade|install|rollback)\b", "helm release change"),
    (r"\b(aws|gcloud|az)\b.*(--profile|--project|--subscription)[= ]\S*prod", "cloud CLI against a prod account"),
    (r"\b(terraform|tofu)\s+workspace\s+select\s+\S*prod", "selecting the prod Terraform workspace"),
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
    (r"\bgit\s+(checkout|switch|merge|rebase|reset|stash|cherry-pick|restore)\b", "git operation that moves HEAD or discards changes"),
    (r"\bgit\s+worktree\s+(add|remove|prune)\b", "manual worktree change (crew manages these)"),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # malformed input: don't block
    if payload.get("tool_name") != "Bash":
        return 0
    cmd = (payload.get("tool_input") or {}).get("command", "") or ""
    raw, flat = normalize(cmd)

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
