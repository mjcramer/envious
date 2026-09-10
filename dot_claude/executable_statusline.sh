#!/usr/bin/env bash
# Claude Code status line.
#
# Reads the status-line JSON payload on stdin and renders two lines:
#   1. location / git branch / model / effort / mode flags
#   2. context window usage / cost / diff stats / rate limits
#
# Every field is optional: anything missing from the payload is simply omitted,
# so this keeps working across Claude Code versions. When the window is too
# narrow for everything, fields are shed in a chosen order (see "fitting")
# rather than letting the terminal clip whatever happens to be at the end.

set -uo pipefail

input=$(cat)

# ------------------------------------------------------------- text width ---

# Drop the colour sequences from a string. Everything we emit is an SGR
# (ESC "[" params "m"), so consuming up to the terminating "m" is enough — and
# unlike an extglob pattern this does not depend on a shell option having been
# set at the time the function was parsed.
strip_ansi() {
  local s=$1 out=''
  while [[ "$s" == *$'\e['* ]]; do
    out+=${s%%$'\e['*}
    s=${s#*$'\e['}
    s=${s#*m}
  done
  printf '%s' "$out$s"
}

# Visible width of a string: ANSI colour sequences contribute nothing, and the
# two emoji we use occupy two cells each while counting as one character.
# ${#s} is character-counted only in a multibyte locale; in the C locale it
# over-counts our box-drawing glyphs, which costs a field rather than clipping.
vislen() {
  local plain stripped wide=0 rest
  plain=$(strip_ansi "$1")
  stripped=${plain//⚡/}; (( wide += ${#plain} - ${#stripped} ))
  rest=$stripped
  stripped=${rest//🧠/}; (( wide += ${#rest} - ${#stripped} ))
  printf '%d' $(( ${#plain} + wide ))
}

# Clip plain ASCII text, keeping the front and marking the cut. Used for the
# agent name, where the front is what identifies it.
clip_tail() {
  local s=$1 max=$2
  (( max < 1 )) && max=1
  if (( ${#s} > max )); then printf '%s…' "${s:0:$(( max - 1 ))}"; else printf '%s' "$s"; fi
}

# Clip plain text, keeping the end. Used for the directory: the tail is the
# part that names the worktree (envious.craft-engineer), so it is what we keep.
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

# ------------------------------------------------------------------ width ---

# Columns Claude Code keeps for itself. `padding` in the statusLine setting is
# 0 here, and it only adds indentation *on top of* the interface's own spacing,
# so this covers that spacing plus one cell of slack — a line that ends in the
# very last column wraps on terminals with immediate (non-deferred) wrap. Raise
# this by the same amount if `padding` is ever raised.
RESERVED_COLS=2

# What to lay out against when the width cannot be measured. Assuming more than
# the terminal has is exactly what clips the end of the line, so assume the
# classic 80 — less the same margin, since 80 is a terminal width like the
# measured ones.
ASSUMED_COLS=$(( 80 - RESERVED_COLS ))

# Usable width for one line, or 0 when it cannot be determined.
#
# Claude Code captures our stdout rather than attaching us to the terminal, so
# neither the controlling tty nor terminfo can answer this: the documented
# source is $COLUMNS, which Claude Code sets to the terminal's real dimensions
# before running us. The rest of the chain only matters when this script is run
# by hand from a shell.
usable_cols() {
  local w=''

  # 1. The payload. `columns` is documented as the usable row width for the
  #    subagent status line and is not (yet) sent to this one, so it is read
  #    opportunistically: if it ever arrives it is already the usable width and
  #    needs no margin subtracted.
  if [[ "${PAYLOAD_COLS:-}" =~ ^[0-9]+$ ]] && (( PAYLOAD_COLS > 0 )); then
    printf '%d' "$PAYLOAD_COLS"
    return
  fi

  # 2. $COLUMNS — what Claude Code documents that it sets for us.
  if [[ "${COLUMNS:-}" =~ ^[0-9]+$ ]] && (( COLUMNS > 0 )); then
    w=$COLUMNS
  else
    # 3. The controlling terminal. Braces matter: redirecting stdin from a
    #    missing /dev/tty is reported by the shell itself, so the whole group
    #    needs its stderr silenced.
    w=$({ stty size </dev/tty; } 2>/dev/null | cut -d' ' -f2)
    if [[ ! "$w" =~ ^[0-9]+$ ]] || (( w == 0 )); then
      # 4. terminfo. It answers 80 both for a real 80-column terminal and for
      #    one it could not measure, and under Claude Code it is always the
      #    second case — so a bare 80 from tput is not evidence of anything.
      w=$(tput cols 2>/dev/null)
      [[ "$w" == 80 ]] && w=''
    fi
  fi

  # 5. Give up.
  if [[ ! "$w" =~ ^[0-9]+$ ]] || (( w <= RESERVED_COLS )); then
    printf '0'
    return
  fi
  printf '%d' $(( w - RESERVED_COLS ))
}

# Last-resort output: the directory is all we know, clipped to the end so that
# even this cannot wrap. No trailing newline here either — it would render as
# an extra blank status line.
degrade() {
  local cols
  cols=$(usable_cols)
  (( cols > 0 )) || cols=$ASSUMED_COLS
  clip_head "${PWD}" "$cols"
  exit 0
}

# ------------------------------------------------------------------ input ---

# Without jq there is nothing to parse.
command -v jq >/dev/null 2>&1 || degrade

# Pull every field in one jq pass. Fields are joined with U+001F rather than
# tabs: tab counts as IFS whitespace, so runs of empty fields would collapse
# and shift every later value into the wrong variable.
IFS=$'\x1f' read -r \
  MODEL EFFORT FAST THINKING STYLE \
  CTX_PCT CTX_USED CTX_MAX \
  COST ADDED REMOVED \
  RL5 RL5_RESET RL7 RL7_RESET \
  CUR_DIR AGENT VIM PR SESSION_NAME VERSION PAYLOAD_COLS \
  < <(printf '%s' "$input" | jq -r '[
        .model.display_name,
        .effort.level,
        .fast_mode,
        .thinking.enabled,
        .output_style.name,
        (.context_window.used_percentage // 0),
        (.context_window.total_input_tokens // 0),
        (.context_window.context_window_size // 0),
        (.cost.total_cost_usd // 0),
        (.cost.total_lines_added // 0),
        (.cost.total_lines_removed // 0),
        .rate_limits.five_hour.used_percentage,
        .rate_limits.five_hour.resets_at,
        .rate_limits.seven_day.used_percentage,
        .rate_limits.seven_day.resets_at,
        (.workspace.current_dir // .cwd // ""),
        .agent.name,
        .vim.mode,
        .pr.number,
        .session_name,
        .version,
        .columns
      ] | map(if . == null then "" else tostring end) | join("\u001f")' 2>/dev/null)

# jq failed or gave us nothing usable.
[[ -n "${CUR_DIR:-}" ]] || degrade

# ---------------------------------------------------------------- palette ---
R=$'\e[0m'; B=$'\e[1m'; D=$'\e[2m'
BLUE=$'\e[38;5;39m'; PURPLE=$'\e[38;5;140m'; GOLD=$'\e[38;5;215m'
CYAN=$'\e[38;5;80m'; GREEN=$'\e[38;5;71m'; YELLOW=$'\e[38;5;179m'
RED=$'\e[38;5;167m'; GREY=$'\e[38;5;245m'

SEP="${D}${GREY} │ ${R}"

# ---------------------------------------------------------------- helpers ---

# Round a possibly-float string to an integer. Anything non-numeric (including
# an absent field) becomes 0, so the arithmetic below can never abort.
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

# A 10-cell meter for a 0-100 percentage.
meter() {
  local pct=$1 width=10 filled i out=''
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

# Recomputed now that the payload has been parsed, in case it carried a width.
COLS=$(usable_cols)
if (( COLS > 0 )); then FIT_COLS=$COLS; else FIT_COLS=$ASSUMED_COLS; fi

# Column the right group starts at when the width is unknown. Keeps the layout
# spread out without pushing it toward an edge we are only guessing at.
FALLBACK_COL=52

# Smallest gap that still reads as two separate groups.
MIN_GAP=3

# ---------------------------------------------------------------- fitting ---
# Each line is built as a left group and a right group at a "level": 0 is the
# full line, and each step up drops or shortens the least informative thing
# still present. `fit` raises the level until the line fits, so a narrow window
# loses fields in a chosen order instead of having its tail clipped — and the
# tail is exactly where @agent and #pr live. The directory tail and the agent
# name are the last to go: they are what say which checkout and which agent
# this session is.
#
# The steps are deliberately fine-grained. Dropping two things in one step
# costs a field that would have fitted on its own, which is how a 27-column
# directory ends up on an 80-column window next to an empty half.
MAX_LEVEL_1=8
MAX_LEVEL_2=6

# Sets LEFT and RIGHT to the richest version of the line that fits.
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

render() {
  local left=$1 right=$2 lw rw gap
  if [[ -z "$right" ]]; then printf '%s' "$left"; return; fi
  lw=$(vislen "$left"); rw=$(vislen "$right")
  gap=$(( FIT_COLS - lw - rw ))
  # With no measured width, spread to the fallback column rather than out to an
  # edge we are guessing at, but never further than the assumed width allows.
  if (( COLS == 0 )) && (( gap > FALLBACK_COL - lw )); then gap=$(( FALLBACK_COL - lw )); fi
  (( gap < MIN_GAP )) && gap=$MIN_GAP
  printf '%s%*s%s' "$left" "$gap" '' "$right"
}

# ----------------------------------------------------------------- line 1 ---

# Git state is read once rather than per level: the build below runs up to
# MAX_LEVEL_1+1 times and these are the only forks in it that touch the disk.
BRANCH=''; DIRTY=''
if BRANCH=$(git --no-optional-locks -C "$CUR_DIR" symbolic-ref --quiet --short HEAD 2>/dev/null) \
   || BRANCH=$(git --no-optional-locks -C "$CUR_DIR" rev-parse --short HEAD 2>/dev/null); then
  if [[ -n $(git --no-optional-locks -C "$CUR_DIR" status --porcelain 2>/dev/null | head -1) ]]; then
    DIRTY="${YELLOW}*${R}"
  fi
fi

# Shed order, one step per level:
#   1  directory to its last two components, branch to its last component
#   2  output style, effort suffix
#   3  git branch — in a worktree the directory tail already names it
#   4  directory to its last component
#   5  vim mode
#   6  model name
#   7  the ⚡ / 🧠off flags — later than the model because they are modes you
#      set and then forget, and forgetting them changes how the session behaves
#   8  PR number, and the directory and agent name clipped against a budget so
#      that the line cannot overflow however narrow the window is
build_line1() {
  local level=$1 dir agent budget share flags=''

  dir=${CUR_DIR/#$HOME/\~}
  if   (( level >= 4 )); then dir=$(elide_path "$dir" 1)
  elif (( level >= 1 )); then dir=$(elide_path "$dir" 2)
  fi

  agent=$AGENT
  if (( level >= 8 )); then
    budget=$(( FIT_COLS - MIN_GAP ))
    (( budget < 4 )) && budget=4
    if [[ -n "$agent" ]]; then
      share=$(( budget / 2 ))
      agent=$(clip_tail "$agent" $(( share - 1 )))   # -1 for the leading "@"
      budget=$(( budget - share ))
    fi
    dir=$(clip_head "$dir" "$budget")
  fi

  LEFT="${BLUE}${B}${dir}${R}"
  if (( level < 3 )) && [[ -n "$BRANCH" ]]; then
    local br=$BRANCH
    (( level >= 1 )) && br=${br##*/}
    LEFT+="${SEP}${PURPLE}⎇ ${br}${R}${DIRTY}"
  fi

  RIGHT=''
  if (( level < 6 )) && [[ -n "$MODEL" ]]; then
    RIGHT+="${GOLD}${B}${MODEL}${R}"
    if (( level < 2 )) && [[ -n "$EFFORT" ]]; then RIGHT+="${D}${GOLD}:${EFFORT}${R}"; fi
  fi

  if (( level < 7 )); then
    [[ "$FAST"     == "true"  ]] && flags+="${CYAN}⚡${R}"
    [[ "$THINKING" == "false" ]] && flags+="${D}${GREY}🧠off${R}"
  fi
  if (( level < 2 )) && [[ -n "$STYLE" && "$STYLE" != "default" && "$STYLE" != "null" ]]; then
    flags+=" ${CYAN}${STYLE}${R}"
  fi
  if (( level < 5 )) && [[ -n "$VIM" ]]; then flags+=" ${GREEN}${VIM}${R}"; fi
  if [[ -n "$agent" ]]; then flags+=" ${PURPLE}@${agent}${R}"; fi
  if (( level < 8 )) && [[ -n "$PR" ]]; then flags+=" ${BLUE}#${PR}${R}"; fi

  if [[ -n "$flags" ]]; then
    [[ -n "$RIGHT" ]] && RIGHT+="$SEP"
    RIGHT+="${flags# }"
  fi
}

# ----------------------------------------------------------------- line 2 ---

CTX_PCT_I=$(to_int "$CTX_PCT")
CTX_USED_I=$(to_int "$CTX_USED")
CTX_MAX_I=$(to_int "$CTX_MAX")
ADDED_I=$(to_int "$ADDED")
REMOVED_I=$(to_int "$REMOVED")

COST_FMT=''
if [[ "$COST" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  COST_FMT=$(printf '%.2f' "$COST")
  [[ "$COST_FMT" == "0.00" ]] && COST_FMT=''
fi

# Shed order, one step per level: the rate-limit reset suffixes, the token
# counts, the meter, the 7-day limit, the 5-hour limit, the diff stats. Cost
# survives everything — it is four columns and it is the number that changes
# people's behaviour.
build_line2() {
  local level=$1 ctx_col p limits=''

  ctx_col=$(pct_color "$CTX_PCT_I")
  LEFT="${D}${GREY}ctx${R} "
  if (( level < 3 )); then LEFT+="${ctx_col}$(meter "$CTX_PCT_I")${R} "; fi
  LEFT+="${ctx_col}${CTX_PCT_I}%${R}"
  if (( level < 2 )) && (( CTX_MAX_I > 0 )); then
    LEFT+=" ${D}${GREY}$(fmt_tokens "$CTX_USED_I")/$(fmt_tokens "$CTX_MAX_I")${R}"
  fi

  RIGHT=''
  [[ -n "$COST_FMT" ]] && RIGHT+="${GREEN}\$${COST_FMT}${R}"

  if (( level < 6 )) && (( ADDED_I > 0 || REMOVED_I > 0 )); then
    [[ -n "$RIGHT" ]] && RIGHT+="$SEP"
    RIGHT+="${GREEN}+${ADDED_I}${R}${D}/${R}${RED}-${REMOVED_I}${R}"
  fi

  if (( level < 5 )) && [[ -n "$RL5" ]]; then
    p=$(to_int "$RL5")
    limits+="$(pct_color "$p")5h ${p}%"
    (( level < 1 )) && limits+="$(fmt_reset "$RL5_RESET")"
    limits+="${R}"
  fi
  if (( level < 4 )) && [[ -n "$RL7" ]]; then
    p=$(to_int "$RL7")
    [[ -n "$limits" ]] && limits+="${D}${GREY} · ${R}"
    limits+="$(pct_color "$p")7d ${p}%"
    (( level < 1 )) && limits+="$(fmt_reset "$RL7_RESET")"
    limits+="${R}"
  fi
  if [[ -n "$limits" ]]; then
    [[ -n "$RIGHT" ]] && RIGHT+="$SEP"
    RIGHT+="${limits}"
  fi
}

# ----------------------------------------------------------------- output ---
LEFT=''; RIGHT=''

fit build_line1 "$MAX_LEVEL_1"
line1=$(render "$LEFT" "$RIGHT")
fit build_line2 "$MAX_LEVEL_2"
line2=$(render "$LEFT" "$RIGHT")

# No trailing newline: it would render as an extra blank status line.
printf '%s\n%s' "$line1" "$line2"
