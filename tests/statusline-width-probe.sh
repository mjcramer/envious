#!/usr/bin/env bash
# Measures what the status line can actually know about the terminal, and how
# many columns Claude Code keeps for itself. It is a diagnostic, not a status
# line: point `statusLine` at it for one session, read the two rows, put your
# real status line back.
#
# Two questions it answers, neither of which can be answered from a script run
# by a tool rather than by Claude Code's own status-line machinery:
#
#   1. Does Claude Code set COLUMNS?  The docs say it sets COLUMNS and LINES to
#      the terminal's real dimensions. Measured on 2.1.267, a child process
#      spawned for a *tool* call instead sees COLUMNS=0, no controlling
#      terminal, and `tput cols` = 80 on a much wider window. Row 1 says which
#      of those the status line itself gets.
#
#   2. How many columns does the interface reserve?  `padding` (0 here) is
#      documented as adding indentation on top of "the interface's built-in
#      spacing", and that spacing is never given a number. Row 2 is a ruler:
#      digits 1-9 then a letter for each completed group of ten (A=10, B=20,
#      ... , X=240). Read the last character you can see and you have the
#      usable width; subtract it from COLUMNS and you have the reserve. That
#      number goes in RESERVED_COLS in dot_claude/statusline-lib.sh.
#
# To use it, temporarily set in ~/.claude/settings.json:
#   "statusLine": {"type": "command",
#                  "command": "~/projects/mjcramer/envious/tests/statusline-width-probe.sh",
#                  "padding": 0}
# It reads nothing and writes nothing; the payload on stdin is discarded.

set -uo pipefail

cat >/dev/null   # drain the payload so Claude Code does not see a broken pipe

stty_cols=$({ stty size </dev/tty; } 2>/dev/null | cut -d' ' -f2)
tput_cols=$(tput cols 2>/dev/null)

printf 'COLUMNS=[%s] LINES=[%s] stty=[%s] tput=[%s] TERM=[%s] tty=[%s]\n' \
  "${COLUMNS:-unset}" "${LINES:-unset}" "${stty_cols:-none}" "${tput_cols:-none}" \
  "${TERM:-unset}" "$(ps -o tty= -p $$ 2>/dev/null | tr -d ' ')"

# Deliberately longer than any plausible window: where it stops being visible
# is the measurement. Letters mark each completed ten.
ruler=''
letters=ABCDEFGHIJKLMNOPQRSTUVWX
for (( group = 0; group < 24; group++ )); do
  ruler+='123456789'"${letters:group:1}"
done
printf '%s' "$ruler"
