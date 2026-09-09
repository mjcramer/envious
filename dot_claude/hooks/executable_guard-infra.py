#!/usr/bin/env python3
"""
PreToolUse guard for Bash commands in Claude Code.

Reads the hook payload on stdin, inspects tool_input.command, and:
  - DENIES destructive / irreversible infra commands (returns a reason to Claude)
  - forces an ASK (interactive confirmation) for anything that looks production-scoped
  - otherwise ALLOWS by exiting 0 with no output (normal permission rules still apply)

Extend DENY_PATTERNS / ASK_PATTERNS to match your stack. Test with:
  echo '{"tool_name":"Bash","tool_input":{"command":"terraform destroy"}}' | python3 guard-infra.py
"""
import json
import re
import sys

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
    # Git
    (r"\bgit\s+push\b.*(--force|-f\b|\+)\s*.*\b(main|master|prod|production|release)\b", "force-push to a protected branch"),
    (r"\bgit\s+push\b.*\b(main|master|prod|production|release)\b.*(--force|-f\b)", "force-push to a protected branch"),
    (r"\bgit\s+(branch\s+-D|reset\s+--hard\s+origin)", "destructive git history operation"),
    (r"\bgit\s+worktree\s+remove\b.*(--force|-f\b)", "force-removing a worktree discards an agent's work"),
    (r"\bgit\s+branch\s+-[dD]\s+agent/", "deleting an agent branch"),
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
    # the human's working branch is read-only to agents: anything that moves HEAD or discards work asks
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
    flat = " ".join(cmd.split())

    for pattern, reason in DENY_PATTERNS:
        if re.search(pattern, flat, re.IGNORECASE):
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
        if re.search(pattern, flat, re.IGNORECASE):
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
