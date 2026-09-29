---
description: Show your agent workspaces — who worked, on what branch, what changed
argument-hint: [list | path <agent> | diff <agent> [branch]]
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
  base, and whether the workspace has uncommitted changes. Call out anything
  unmerged that has been sitting there. An agent has one workspace per run, so
  the same agent can appear more than once.
  If there are no workspaces, say so plainly — it means nothing has been
  delegated yet, which is not an error.
- **`crew path <agent>`** — give the path, and the `cd` command to get there.
- **`crew diff <agent> [branch]`** — summarise the change: files touched, rough
  +/- size, and what actually moved. Show the diff itself only if it is short or
  the user asks for it. Without a branch it compares against the branch the
  workspace was cut from.

If the command exits non-zero, say what failed and what the fix is. A message
like `no workspace for '<agent>'` usually means that agent has not run yet in
this repository — say that rather than presenting it as a crash.

## Never

- Never merge, rebase, push, or delete a branch or workspace as part of this
  command. It is read-only.
