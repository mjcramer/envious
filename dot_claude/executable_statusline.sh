#!/usr/bin/env bash
# Claude Code status line.
#
# Reads the status-line JSON payload on stdin and renders two lines:
#   1. location / git branch / model / effort / mode flags
#   2. context window usage / cost / diff stats / rate limits
#
# Every field is optional: anything missing from the payload is simply omitted,
# so this keeps working across Claude Code versions. When the window is too
# narrow for everything, fields are shed in a chosen order rather than letting
# the terminal clip whatever happens to be at the end.
#
# Environment:
#   CLAUDE_STATUSLINE_COLS  terminal width in columns. Overrides every form of
#                           detection; export it if the line lays out narrower
#                           than the window (`set -x CLAUDE_STATUSLINE_COLS 200`
#                           in fish, and restart Claude Code so it inherits it).
#   CLAUDE_STATUSLINE_RIGHT_MARGIN
#                           extra columns kept free at the right. Default 0: the
#                           right groups end at the true edge of the status
#                           line's area. Set it to the width of anything you
#                           keep permanently in Claude Code's right-hand column,
#                           plus 1 (e.g. 11 for "/rc active").
#
# Rendering helpers are shared with subagent-statusline.sh; see statusline-lib.sh.
# statusline-width-probe.sh, alongside both, reports what any given invocation
# can actually see.

set -uo pipefail

input=$(cat)

# Sourced from alongside this script, wherever chezmoi put it. Without the
# library there is nothing to render with, so fall back to the bare directory.
LIB="${BASH_SOURCE[0]%/*}/statusline-lib.sh"
if [[ ! -r "$LIB" ]]; then
  printf '%s' "${PWD}"
  exit 0
fi
# shellcheck source=statusline-lib.sh
. "$LIB"

# Last-resort output: the directory is all we know, clipped to the end so that
# even this cannot wrap. No trailing newline — it renders as a blank extra line.
degrade() {
  set_width
  clip_head "${PWD}" "$FIT_COLS"
  exit 0
}

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
  CUR_DIR AGENT VIM PR SESSION_NAME VERSION \
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
        .version
      ] | map(if . == null then "" else tostring end) | join("\u001f")' 2>/dev/null)

# jq failed or gave us nothing usable.
[[ -n "${CUR_DIR:-}" ]] || degrade

# This payload carries no width of its own — the docs describe a `columns` field
# only for the subagent status line — so the environment is the only source.
set_width

MAX_LEVEL_1=9
MAX_LEVEL_2=6

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
#   3  PR number — it belongs to the branch, so it goes just before it and a
#      PR is never shown without the branch it was opened from
#   4  git branch — in a worktree the directory tail already names it
#   5  directory to its last component
#   6  vim mode
#   7  model name
#   8  the ⚡ / 🧠off flags — later than the model because they are modes you
#      set and then forget, and forgetting them changes how the session behaves
#   9  the directory and agent name clipped against a budget so that the line
#      cannot overflow however narrow the window is
build_line1() {
  local level=$1 dir agent budget share flags=''

  dir=$(tilde_path "$CUR_DIR")
  if   (( level >= 5 )); then dir=$(elide_path "$dir" 1)
  elif (( level >= 1 )); then dir=$(elide_path "$dir" 2)
  fi

  agent=$AGENT
  if (( level >= 9 )); then
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
  if (( level < 4 )) && [[ -n "$BRANCH" ]]; then
    local br=$BRANCH
    (( level >= 1 )) && br=${br##*/}
    LEFT+="${SEP}${PURPLE}⎇ ${br}${R}${DIRTY}"
  fi
  # Directly after the branch; after the directory if git could not name one,
  # since the number came from the payload and still identifies the work.
  if (( level < 3 )) && [[ -n "$PR" ]]; then LEFT+=" ${BLUE}#${PR}${R}"; fi

  RIGHT=''
  if (( level < 7 )) && [[ -n "$MODEL" ]]; then
    RIGHT+="${GOLD}${B}${MODEL}${R}"
    if (( level < 2 )) && [[ -n "$EFFORT" ]]; then RIGHT+="${D}${GOLD}:${EFFORT}${R}"; fi
  fi

  if (( level < 8 )); then
    [[ "$FAST"     == "true"  ]] && flags+="${CYAN}⚡${R}"
    [[ "$THINKING" == "false" ]] && flags+="${D}${GREY}🧠off${R}"
  fi
  if (( level < 2 )) && [[ -n "$STYLE" && "$STYLE" != "default" && "$STYLE" != "null" ]]; then
    flags+=" ${CYAN}${STYLE}${R}"
  fi
  if (( level < 6 )) && [[ -n "$VIM" ]]; then flags+=" ${GREEN}${VIM}${R}"; fi
  if [[ -n "$agent" ]]; then flags+=" ${PURPLE}@${agent}${R}"; fi

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
    [[ -n "$limits" ]] && limits+="$DOT"
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
LEFT1=$LEFT; RIGHT1=$RIGHT
fit build_line2 "$MAX_LEVEL_2"
LEFT2=$LEFT; RIGHT2=$RIGHT

# Left groups flush left, right groups flush right: both right groups end at
# FIT_COLS, the right edge of the column Claude Code draws the status line in.
line1=$(render "$LEFT1" "$RIGHT1")
line2=$(render "$LEFT2" "$RIGHT2")

# No trailing newline: it would render as an extra blank status line.
printf '%s\n%s' "$line1" "$line2"
