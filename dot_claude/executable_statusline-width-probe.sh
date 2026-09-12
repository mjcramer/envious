#!/usr/bin/env bash
# Diagnostic status line: reports everything an invocation can learn about the
# terminal it is being rendered into, and how many columns Claude Code keeps for
# itself. Not a status line to live with — point `statusLine` at it for one
# session, read the report, put the real one back.
#
# It is deployed to ~/.claude/ rather than kept in the repo's tests/ on purpose.
# tests/** is excluded from chezmoi's targets, so a `statusLine` command pointing
# into tests/ resolves to nothing and the probe silently never runs — which is
# how the first attempt at this produced no data at all. Here it sits next to the
# scripts it is diagnosing, at a path that does not depend on where the repo is
# checked out or on ~ being expanded by whatever runs the command.
#
# Use it by setting in ~/.claude/settings.json:
#
#   "statusLine": {"type": "command", "padding": 0,
#                  "command": "/Users/mjcramer/.claude/statusline-width-probe.sh"}
#
# It appends a block per render to /tmp/statusline-probe.txt (override with
# CLAUDE_STATUSLINE_PROBE_OUT) and prints two rows:
#
#   1. a one-line summary of every width source
#   2. a ruler — digits 1-9 then a letter per completed ten (A=10, B=20, …,
#      X=240). The last character still visible is the usable width; subtract it
#      from the terminal width and the difference is what the interface reserves,
#      which is RESERVED_COLS in statusline-lib.sh. Renders while a notification
#      is showing (MCP error, context-low warning, /rc) show how much of the
#      right of the row it covers, which is what notice_margin() keeps free.
#      usable_cols below is net of both.
#
# The file is the primary output: it survives a status line that is itself being
# truncated, and it accumulates, so resizing the window between renders gives
# several samples to compare.
#
# DELETE /tmp/statusline-probe.txt WHEN YOU ARE DONE. It is written 0600, but it
# still describes this machine — process tree, paths, every variable the session
# carries — and it has no reason to outlive the investigation that needed it.
#
# The environment is recorded as variable *names* only, with each value's length.
# Listing the names is what answers the question the dump exists for — whether
# anything at all carries a terminal width — and it answers it completely,
# without this script having to decide which values are safe to write down. The
# session carries a messaging token; a length cannot leak one.

set -uo pipefail

OUT=${CLAUDE_STATUSLINE_PROBE_OUT:-/tmp/statusline-probe.txt}

payload=$(cat)          # drain stdin so Claude Code never sees a broken pipe

# ------------------------------------------------------------------ sources ---

# Size of a terminal device, "rows cols", or empty. The redirection form is used
# rather than `stty -f` / `stty -F` because BSD and GNU spell that flag
# differently and this has to run on both.
tty_size() {
  { stty size < "$1"; } 2>/dev/null
}

own_tty=$(ps -o tty= -p $$ 2>/dev/null | tr -d ' ')
own_size=$(tty_size /dev/tty)
tput_cols=$(tput cols 2>/dev/null)
tput_lines=$(tput lines 2>/dev/null)

# Walk up the process tree, recording each ancestor's terminal and the size that
# terminal reports. This is the route the status line itself now uses: the child
# has no terminal but its parent, Claude Code, does.
ancestors=''
ancestor_hit=''
pid=$PPID
for _ in 1 2 3 4 5 6; do
  [[ "$pid" =~ ^[0-9]+$ ]] || break
  (( pid > 1 )) || break
  line=$(ps -o ppid=,tty=,comm= -p "$pid" 2>/dev/null) || break
  [[ -n "$line" ]] || break
  read -r next tty comm <<<"$line"
  size='-'
  if [[ "$tty" =~ ^[a-zA-Z][a-zA-Z0-9/]*$ ]] && [[ -r "/dev/$tty" ]]; then
    size=$(tty_size "/dev/$tty")
    size=${size:-unreadable}
    [[ -z "$ancestor_hit" && "$size" == *' '* ]] && ancestor_hit=${size##* }
  fi
  ancestors+="  pid=$pid ppid=$next tty=[$tty] comm=[$comm] stty=[$size]"$'\n'
  pid=$next
done

# What the deployed library decides, given all of the above. This is the answer
# that actually matters: everything else is evidence for why it decided that.
lib_says='(library not readable)'
lib_assumed=''
LIB="${BASH_SOURCE[0]%/*}/statusline-lib.sh"
if [[ -r "$LIB" ]]; then
  # shellcheck source=statusline-lib.sh
  . "$LIB"
  lib_says=$(usable_cols)
  lib_assumed=$ASSUMED_COLS
fi

# ------------------------------------------------------------------- report ---

ruler=''
letters=ABCDEFGHIJKLMNOPQRSTUVWX
for (( group = 0; group < 24; group++ )); do
  ruler+='123456789'"${letters:group:1}"
done

# 600: the dump is redacted but it still describes this machine in detail.
umask 077

{
  printf '=== statusline probe %s pid=%s ===\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$$"
  printf 'usable_cols() -> %s   (ASSUMED_COLS=%s, CLAUDE_STATUSLINE_COLS=[%s])\n' \
    "$lib_says" "${lib_assumed:-?}" "${CLAUDE_STATUSLINE_COLS:-unset}"
  printf 'COLUMNS=[%s] LINES=[%s]  (shell variables; the name list below says whether they were exported)\n' \
    "${COLUMNS:-unset}" "${LINES:-unset}"
  printf 'own tty=[%s] stty=[%s]\n' "${own_tty:-none}" "${own_size:-none}"
  printf 'tput cols=[%s] lines=[%s] TERM=[%s] TERMINFO=[%s]\n' \
    "${tput_cols:-none}" "${tput_lines:-none}" "${TERM:-unset}" "${TERMINFO:-unset}"
  printf 'PPID=%s  first ancestor terminal width=[%s]\n' "$PPID" "${ancestor_hit:-none}"
  printf 'ancestors:\n%s' "${ancestors:-  (none)}"

  printf -- '--- stdin payload (%d bytes, verbatim) ---\n' "${#payload}"
  printf '%s\n' "$payload"

  printf -- '--- environment (%d variables, names and value lengths only) ---\n' \
    "$(env | wc -l | tr -d ' ')"
  env | LC_ALL=C sort | while IFS= read -r kv; do
    value=${kv#*=}
    printf '%s <%d chars>\n' "${kv%%=*}" "${#value}"
  done

  printf -- '--- ruler (%d columns) ---\n%s\n\n' "${#ruler}" "$ruler"
} >>"$OUT" 2>&1

# No trailing newline on the last row: it would render as a blank status line.
printf 'probe -> %s | usable_cols=%s COLUMNS=[%s] own-stty=[%s] ancestor=[%s] tput=[%s]\n' \
  "$OUT" "$lib_says" "${COLUMNS:-unset}" "${own_size:-none}" "${ancestor_hit:-none}" \
  "${tput_cols:-none}"
printf '%s' "$ruler"
