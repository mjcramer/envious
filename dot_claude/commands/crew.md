---
description: Show and manage your agent workspaces — who worked, on what branch, what changed
argument-hint: [list | log <agent> | diff <agent> [N] | task <agent> [slug] | merge-cmd <agent>]
allowed-tools: Bash(crew:*), Bash(git log:*), Bash(git diff:*), Bash(git status:*), Bash(git branch:*)
---

Run the `crew` agent-workspace manager and report what it says.

Arguments: `$ARGUMENTS`

## What to run

- **No arguments** → run `crew list`.
- **Otherwise** → run `crew $ARGUMENTS` verbatim.

`crew` lives at `~/.claude/bin/crew`. If it is not on PATH, invoke it as
`python3 ~/.claude/bin/crew ...` rather than reporting a failure.

Run it from inside the user's repository. If the session's working directory is
an agent worktree (a sibling directory named `<repo>.<something>`), run it from
the main checkout instead so the listing covers every workspace.

## How to report back

Do not simply paste the raw table. Read it and tell the user what it means:

- **`crew list`** — for each workspace: which agent, how many commits ahead of its
  base, how many iterations, and whether the workspace has uncommitted changes.
  Call out anything unmerged that has been sitting there, and anything with
  `ITER 0` and commits (work that did not come through the stop hook).
  If there are no workspaces, say so plainly — it means nothing has been
  delegated yet, which is not an error.
- **`crew log <agent>`** — summarise the iteration history: what each round did,
  and what is on the branch versus its base.
- **`crew diff <agent>`** — summarise the change: files touched, rough +/- size,
  and what actually moved. Show the diff itself only if it is short or the user
  asks for it.
- **`crew merge-cmd <agent>`** — show the commands, and remind the user that
  merging is theirs to run. Never merge on their behalf.

If the command exits non-zero, say what failed and what the fix is. A message
like `no workspace for '<agent>'` usually means that agent has not run yet in
this repository, or ran before the workspace index existed — say that rather
than presenting it as a crash.

## Never

- Never merge, rebase, push, or delete a branch or workspace as part of this
  command. It is read-only apart from `crew task`, which only sets a marker for
  the next invocation.
