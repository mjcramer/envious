# Working rules (user-level)

These apply to **every** session and every agent — the orchestrator, each specialist, and any teammate. Rules about how the orchestrator routes work live in `~/.claude/agents/orchestrator.md`, not here, so that a teammate is never told it is the lead.

I work at Queue, which builds robotic vending machines that dispense prescription medication, so much of what I touch handles PHI (HIPAA) or is dispensing-safety-critical. Treat every environment as regulated unless I say otherwise.

## Restrictions

- Absolutely no modification of the host system without asking. This includes installing applications and making changes to system configuration.

## Git

1. **My working branch is read-only to you.** Never edit, commit, stash, checkout, or reset in my checkout. Every change to a repo goes through a specialist in its own worktree on an `agent/<name>/…` branch cut from my current branch. That includes one-line fixes.
   *The single exception, by my explicit choice:* `spike-engineer` works in my checkout and commits its own finish there as `[spike-engineer #N] …`. It is the only agent that may, and nothing else in these rules is relaxed for it — it still never checks out, merges, rebases, resets, stashes, or pushes.
2. **Local git is fine with my approval; the GitHub merge button is mine alone.**
   - The **orchestrator** may merge an agent branch into my branch, push, and open a PR — each one with my approval at the time. Specialists never merge, push, or open PRs; they hand their branch to the orchestrator.
   - **Never merge a pull request.** Not `gh pr merge`, not the equivalent API call, not by any other route. Landing a PR on GitHub is mine and only mine, however trivial the change and whatever I have approved locally.
3. **Always `--no-ff`.** Every merge leaves a merge commit naming the branch it came from, so I can see where a change arrived (`git log --merges`) and back the whole thing out in one step (`git revert -m 1 <merge>`) with the branch still around to inspect.
4. Never delete an agent workspace or an `agent/` branch.

## Hard rules

- No secrets in code, commits, logs, or memory. Point to the secrets manager instead.
- No PHI in logs, test fixtures, dashboards, or memory files. Use synthetic data.
- Never run: `terraform destroy`, force-pushes, `kubectl delete` of namespaces or with `--all`, database drops, bulk `rm -rf`, KMS key deletion, disabling backups/versioning/audit logs. A hook in `~/.claude/settings.json` blocks these; do not try to work around it.
- Production-context commands (`--context *prod*`, `workspace select prod`, `--profile *prod*`, `-e prod`) prompt for confirmation. Expect that and do not hide them inside scripts to avoid the prompt.
- Nothing is applied to production or fleet devices by an agent. Produce the exact command and the rollback, and wait for me.
- Prefer reversible actions. State the rollback for any change you propose.

## Conventions

- Environments: assume `dev`, `staging`, `prod` unless the repo says otherwise; confirm the account/context mapping before acting.
- Severity: SEV1/P1 = patient-impacting, dispensing halted, PHI exposure, or data integrity in doubt.
- Every alert that pages must link to a runbook; every backup must have a tested restore procedure.
- Timestamps in PT.

## Formatting

- **Separate process from answer.** When a turn includes tool calls or step-by-step narration, print a '\033[1;94m━━━━━━━━━━━━━━━━━━━━ FINAL ANSWER ━━━━━━━━━━━━━━━━━━━━\033[0m\n' line before the final response: everything above it is working, everything below it is the answer. Short turns with no tool calls do not need one.
- **Lead with the conclusion.** Findings first, then reasoning. Do not make me read to the end to find out what you did or what you found.
- Be concise. Long is not the same as thorough.
