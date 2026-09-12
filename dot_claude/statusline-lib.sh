# Shared rendering helpers for the Claude Code status lines.
#
# Sourced by statusline.sh (the main two-line status bar) and by
# subagent-statusline.sh (one row per subagent in the agent panel). It defines
# functions and constants only — sourcing it has no other effect.
#
# The central idea both scripts are built on: a line is a left group and a right
# group built at a "level". Level 0 is everything; each step up drops or shortens
# the least informative thing still present. `fit` raises the level until the
# line fits the known width, so a narrow window loses fields in an order we chose
# rather than having its tail clipped by whatever is rendering it — and the tail
# is where the fields that identify a session live.
#
# Environment:
#   CLAUDE_STATUSLINE_COLS          terminal width in columns, overriding
#                                   detection. Export it if the line ever lays
#                                   out narrower than the window; see
#                                   usable_cols() below.
#   CLAUDE_STATUSLINE_RIGHT_MARGIN  extra columns kept free at the right, on
#                                   top of Claude Code's footer chrome; see
#                                   right_margin() below. Default 0, the true
#                                   edge.

# ---------------------------------------------------------------- palette ---
R=$'\e[0m'; B=$'\e[1m'; D=$'\e[2m'
BLUE=$'\e[38;5;39m'; PURPLE=$'\e[38;5;140m'; GOLD=$'\e[38;5;215m'
CYAN=$'\e[38;5;80m'; GREEN=$'\e[38;5;71m'; YELLOW=$'\e[38;5;179m'
RED=$'\e[38;5;167m'; GREY=$'\e[38;5;245m'

SEP="${D}${GREY} │ ${R}"
DOT="${D}${GREY} · ${R}"

# ------------------------------------------------------------- text width ---

# Drop the colour sequences from a string, into $STRIPPED. Everything we emit is
# an SGR (ESC "[" params "m"), so consuming up to the terminating "m" is enough
# — and unlike an extglob pattern this does not depend on a shell option having
# been set at the time the function was parsed. Returns through a global because
# its only caller already runs inside a command substitution, and a second fork
# per width measurement is the one cost here that is paid in a loop.
strip_ansi() {
  local s=$1 out=''
  while [[ "$s" == *$'\e['* ]]; do
    out+=${s%%$'\e['*}
    s=${s#*$'\e['}
    s=${s#*m}
  done
  STRIPPED=$out$s
}

# Visible width of a string: ANSI colour sequences contribute nothing, and the
# two emoji we use occupy two cells each while counting as one character.
# ${#s} is character-counted only in a multibyte locale; in the C locale it
# over-counts our box-drawing glyphs, which costs a field rather than clipping.
vislen() {
  local wide=0 rest gone
  strip_ansi "$1"
  gone=${STRIPPED//⚡/}; (( wide += ${#STRIPPED} - ${#gone} ))
  rest=$gone
  gone=${rest//🧠/}; (( wide += ${#rest} - ${#gone} ))
  printf '%d' $(( ${#STRIPPED} + wide ))
}

# Clip plain ASCII text, keeping the front and marking the cut. Used for names,
# where the front is what identifies them.
clip_tail() {
  local s=$1 max=$2
  (( max < 1 )) && max=1
  if (( ${#s} > max )); then printf '%s…' "${s:0:$(( max - 1 ))}"; else printf '%s' "$s"; fi
}

# Clip plain text, keeping the end. Used for directories: the tail is the part
# that names the worktree (envious.craft-engineer), so it is what we keep.
clip_head() {
  local s=$1 max=$2
  (( max < 1 )) && max=1
  if (( ${#s} > max )); then printf '…%s' "${s:$(( ${#s} - max + 1 ))}"; else printf '%s' "$s"; fi
}

# Keep only the last <keep> components of a path. Same reasoning as clip_head:
# drop the leading components, never the tail.
elide_path() {
  local p=$1 keep=$2 count=0 drop rest tail
  # Separate statements: bash expands every word of a `local` before it assigns
  # any of them, so `local rest=$p` on the line above would read the caller's p.
  rest=$p; tail=$p
  while [[ "$rest" == */* ]]; do rest=${rest#*/}; count=$(( count + 1 )); done
  drop=$(( count + 1 - keep ))
  (( drop <= 0 )) && { printf '%s' "$p"; return; }
  while (( drop > 0 )); do tail=${tail#*/}; drop=$(( drop - 1 )); done
  printf '…/%s' "$tail"
}

# Shorten a path against $HOME, the way a shell prompt does. The substitution
# has to land in an assignment first: inside double quotes the backslash in the
# replacement is not removed, and the path comes back with a literal "\~".
tilde_path() {
  local p=${1/#$HOME/\~}
  printf '%s' "$p"
}

# Model IDs arrive resolved ("claude-opus-5", "claude-haiku-4-5-20251001"). The
# vendor prefix and the date stamp are the same on every row, so they are pure
# overhead in a column that has to compete with the agent's name.
short_model() {
  local m=${1#claude-}
  printf '%s' "${m%-2[0-9][0-9][0-9][0-9][0-9][0-9][0-9]}"
}

# --------------------------------------------------------------- numbers ---

# Round a possibly-float string to an integer. Anything non-numeric (including
# an absent field) becomes 0, so the arithmetic elsewhere can never abort.
to_int() {
  local v=${1:-}
  [[ "$v" =~ ^-?[0-9]+([.][0-9]+)?$ ]] || { printf '0'; return; }
  printf '%.0f' "$v"
}

# Colour by utilisation: green under 50%, amber under 80%, red above.
pct_color() {
  local p=$1
  if   (( p >= 80 )); then printf '%s' "$RED"
  elif (( p >= 50 )); then printf '%s' "$YELLOW"
  else                     printf '%s' "$GREEN"
  fi
}

# Compact token counts: 1234 -> 1.2k, 1234567 -> 1.2M
fmt_tokens() {
  local n=${1:-0}
  if   (( n >= 1000000 )); then printf '%d.%dM' $(( n / 1000000 )) $(( (n % 1000000) / 100000 ))
  elif (( n >= 1000 ));    then printf '%d.%dk' $(( n / 1000 ))    $(( (n % 1000) / 100 ))
  else                          printf '%d' "$n"
  fi
}

# A meter of <width> cells for a 0-100 percentage.
meter() {
  local pct=$1 width=${2:-10} filled i out=''
  (( pct < 0 )) && pct=0
  (( pct > 100 )) && pct=100
  filled=$(( (pct * width + 50) / 100 ))
  for (( i = 0; i < width; i++ )); do
    if (( i < filled )); then out+='█'; else out+='░'; fi
  done
  printf '%s' "$out"
}

# "resets_at" may be epoch seconds or an ISO timestamp; only handle the former
# portably, and stay silent otherwise.
fmt_reset() {
  local at=${1:-} now delta
  [[ "$at" =~ ^[0-9]+$ ]] || return 0
  now=$(date +%s)
  delta=$(( at - now ))
  (( delta <= 0 )) && return 0
  if (( delta >= 86400 )); then printf ' %dd' $(( delta / 86400 ))
  elif (( delta >= 3600 )); then printf ' %dh' $(( delta / 3600 ))
  else printf ' %dm' $(( delta / 60 ))
  fi
}

# ------------------------------------------------------------------ width ---

# Columns Claude Code's footer keeps for itself, subtracted from a *terminal*
# width to get the width the status line is actually drawn in.
#
# Read out of the Claude Code 2.1.269 binary rather than guessed. The footer is
#
#   Box{width: columns, flexDirection: "row", flexWrap: "wrap",
#       paddingX: 2, columnGap: 1}
#     ├─ Box{flexShrink: 1}   the status line, then the footer hints
#     └─ Box{flexShrink: 0, marginLeft: "auto"}   notifications, /rc, /goal
#
# and Claude Code sizes the hint line that shares the left column with the
# same arithmetic: `rowWidth = columns - 2*paddingX - (columnGap + <measured
# width of the right column>)`. So the left column is columns - 5 wide while the
# right column is empty, and each line inside it is drawn `wrap: "truncate"`
# at that width. The 2 columns of right padding also keep a full-width line out
# of the terminal's last cell, so no allowance for deferred wrap is needed.
#
# The `statusLine.padding` setting (0 here) is a further paddingX inside the
# left column; if it is ever raised, raise this by twice as much.
RESERVED_COLS=5

# Extra columns to keep free at the right, beyond RESERVED_COLS, from
# CLAUDE_STATUSLINE_RIGHT_MARGIN. Default 0, which is the confirmed edge.
#
# The right column is empty unless something is showing in it: a notification
# (MCP error, auto-update, context-low, verbose token count), "/rc active" (or
# "/rc" once it has been seen a few times), "/goal active", "memory paused".
# While one is, the status line column shrinks by its width plus the gap and
# the end of the right group is truncated. The script cannot see those — they
# are not in the payload — so the default lays out for the usual empty column
# and accepts that trade. Anyone who keeps something there permanently (remote
# control left on is the likely one: 10 columns for "/rc active", 3 for "/rc",
# plus 1 for the gap) sets the margin to match. Capped at half of what is
# left after RESERVED_COLS so a large value cannot leave nothing to lay out in.
right_margin() {
  local term=$1 m=0
  if [[ "${CLAUDE_STATUSLINE_RIGHT_MARGIN:-}" =~ ^[0-9]+$ ]]; then
    m=$(( 10#$CLAUDE_STATUSLINE_RIGHT_MARGIN ))
  fi
  (( m > (term - RESERVED_COLS) / 2 )) && m=$(( (term - RESERVED_COLS) / 2 ))
  (( m < 0 )) && m=0
  printf '%d' "$m"
}

# What to lay out against when the width cannot be measured at all. Assuming
# more than the window has is exactly what clips the end of a line, so assume
# the classic 80 — less the same chrome, since 80 is a terminal width like the
# measured ones. It is a floor, not a guess at this terminal: raising it would
# just trade one wrong constant for another. Set CLAUDE_STATUSLINE_COLS if
# detection ever fails on a wide window.
ASSUMED_COLS=$(( 80 - RESERVED_COLS - $(right_margin 80) ))

# How far up the process tree to look for a terminal. The status line is a
# grandchild of Claude Code at worst (a shell wrapper, then Claude Code itself),
# so this only has to clear a couple of levels; the bound is what stops a
# surprising process tree from costing a fork per ancestor all the way to init.
ANCESTOR_DEPTH=4

# Terminal width from the nearest ancestor process that has a controlling
# terminal, or empty. This is the only source that works under Claude Code.
#
# We have no terminal of our own, but the process that spawned us does, and its
# device is readable: `stty size < /dev/ttys000` answers with the live window
# size. Opening it cannot steal it — a terminal that is already some other
# session's controlling terminal is never adopted as ours — and `stty` only
# issues an ioctl, so there is no read to raise SIGTTIN either.
#
# One `ps` per level, which is also what advances the walk: each answer carries
# the parent to try next as well as this level's terminal, so finding a terminal
# at the first level costs a single fork.
ancestor_cols() {
  local pid=$1 depth=$ANCESTOR_DEPTH line next tty w
  while (( depth > 0 )) && [[ "$pid" =~ ^[0-9]+$ ]] && (( pid > 1 )); do
    line=$(ps -o ppid=,tty= -p "$pid" 2>/dev/null) || return
    [[ -n "$line" ]] || return
    read -r next tty <<<"$line"
    # No terminal is reported as "?" (Linux) or "??" (macOS); a real one is a
    # device name under /dev, relative and never absolute ("ttys000", "pts/3").
    if [[ "$tty" =~ ^[a-zA-Z][a-zA-Z0-9/]*$ ]] && [[ -r "/dev/$tty" ]]; then
      w=$({ stty size < "/dev/$tty"; } 2>/dev/null | cut -d' ' -f2)
      if [[ "$w" =~ ^[0-9]+$ ]] && (( w > 0 )); then printf '%s' "$w"; return; fi
    fi
    pid=$next
    depth=$(( depth - 1 ))
  done
}

# Usable width for one line, or 0 when it cannot be determined.
#
# Claude Code does export COLUMNS for the status line. 2.1.267 to 2.1.269 all
# run it with `{columns, rows} = process.stdout; if (columns) env.COLUMNS =
# String(columns)`, the same stdout the footer is laid out against, and bash
# keeps an inherited COLUMNS with no terminal. It is skipped only when
# process.stdout has no column count. A COLUMNS of 0 was once measured here and
# is still unexplained, so 0 is treated as "not given" and the terminal is asked
# instead.
#
# tput is not consulted at all: with no terminal it answers terminfo's default
# of 80 whatever the real size is, and a wrong width is worse than no width. No
# width lays out conservatively; a wrong one overflows and gets clipped.
#
# Sources, best first. Each is a *terminal* width, so the same chrome
# (RESERVED_COLS and right_margin) comes off whichever one answered.
usable_cols() {
  local w=''

  # 1. Explicit override. Detection has been wrong before on this path, and this
  #    is the one source that cannot be: export CLAUDE_STATUSLINE_COLS=<n> and
  #    the layout uses n columns regardless of what anything else reports.
  if [[ "${CLAUDE_STATUSLINE_COLS:-}" =~ ^[0-9]+$ ]] && (( CLAUDE_STATUSLINE_COLS > 0 )); then
    w=$CLAUDE_STATUSLINE_COLS

  # 2. What the docs say Claude Code sets for us. Kept ahead of the terminal
  #    because a future version that really does set it knows better than we do
  #    how much of the window the status line gets. A literal 0 is not a width.
  elif [[ "${COLUMNS:-}" =~ ^[0-9]+$ ]] && (( COLUMNS > 0 )); then
    w=$COLUMNS

  else
    # 3. Our own controlling terminal, for when this is run by hand from a
    #    shell. Braces matter: redirecting stdin from a missing /dev/tty is
    #    reported by the shell itself, so the whole group needs stderr silenced.
    w=$({ stty size </dev/tty; } 2>/dev/null | cut -d' ' -f2)

    # 4. Failing that, the terminal of whoever spawned us — the Claude Code case.
    [[ "$w" =~ ^[0-9]+$ ]] || w=$(ancestor_cols "$PPID")
  fi

  # 5. Give up, and let the caller lay out for ASSUMED_COLS.
  if [[ ! "$w" =~ ^[0-9]+$ ]] || (( w <= RESERVED_COLS )); then
    printf '0'
    return
  fi
  printf '%d' $(( w - RESERVED_COLS - $(right_margin "$w") ))
}

# Set COLS (measured usable width, 0 if unknown) and FIT_COLS (what to lay out
# against). An argument is taken as an already-usable width that needs no margin
# subtracted — the subagent payload's `columns` field is exactly that.
set_width() {
  local given=${1:-}
  if [[ "$given" =~ ^[0-9]+$ ]] && (( given > 0 )); then
    COLS=$given
  else
    COLS=$(usable_cols)
  fi
  if (( COLS > 0 )); then FIT_COLS=$COLS; else FIT_COLS=$ASSUMED_COLS; fi
}

# ----------------------------------------------------------------- layout ---

# Smallest gap that still reads as two separate groups.
MIN_GAP=3

# Sets LEFT and RIGHT to the richest version of the line that fits.
#
# The steps a build function takes are deliberately fine-grained: dropping two
# things in one step costs a field that would have fitted on its own, which is
# how a 27-column directory ends up on an 80-column window next to an empty half.
fit() {
  local build=$1 max=$2 level=0 lw rw
  while :; do
    "$build" "$level"
    (( level >= max )) && return 0
    lw=$(vislen "$LEFT"); rw=$(vislen "$RIGHT")
    (( rw > 0 )) && lw=$(( lw + MIN_GAP ))
    (( lw + rw <= FIT_COLS )) && return 0
    level=$(( level + 1 ))
  done
}

# Join a line's two groups: the left group flush left, the right group flush
# right, ending exactly at FIT_COLS. Every line rendered at one width therefore
# ends its right group in the same column, the right edge of the status line's
# area. That holds with an unknown width too: the lines end at ASSUMED_COLS,
# which is a floor, so they cannot run past the real edge.
#
# The gap never drops below MIN_GAP. The build functions' last level clips
# against FIT_COLS, so a line that fitted never needs more than that.
render() {
  local left=$1 right=$2 lw rw gap
  if [[ -z "$right" ]]; then printf '%s' "$left"; return; fi
  lw=$(vislen "$left"); rw=$(vislen "$right")
  gap=$(( FIT_COLS - lw - rw ))
  (( gap < MIN_GAP )) && gap=$MIN_GAP
  printf '%s%*s%s' "$left" "$gap" '' "$right"
}
