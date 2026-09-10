#!/usr/bin/env bash
# Claude Code subagent status line — the row body for each subagent in the
# agent panel below the prompt, replacing the default "name · description ·
# token count".
#
# Unlike the main status line this is invoked once per refresh tick for ALL
# visible rows, and the contract is JSON lines rather than text: one
# {"id": ..., "content": ...} object per row we want to override, newline
# terminated. A task we say nothing about keeps its default rendering, so
# printing nothing at all is a safe degradation and that is what every failure
# path here does.
#
# Rendering helpers are shared with statusline.sh; see statusline-lib.sh.

set -uo pipefail

input=$(cat)

# Nothing to render with, or nothing to render it from: leave every row alone.
LIB="${BASH_SOURCE[0]%/*}/statusline-lib.sh"
[[ -r "$LIB" ]] || exit 0
command -v jq >/dev/null 2>&1 || exit 0
# shellcheck source=statusline-lib.sh
. "$LIB"

# The payload carries `columns`, documented as the usable row width — already
# net of whatever the panel spends on its own framing, so it is used as-is with
# no margin subtracted. Absent (older Claude Code), the environment is the only
# source, and it will almost certainly say "unknown": a panel row is narrower
# than the terminal, so ASSUMED_COLS is an over-estimate there rather than a
# safe one. Nothing better is available; the degradation below is what keeps
# that from being a disaster.
set_width "$(printf '%s' "$input" | jq -r '.columns // "" | tostring' 2>/dev/null)"

# Field order must match the read loop below. Newlines and tabs are squashed to
# spaces because a row body is a single line by contract, and `description` is
# free text that can carry either.
FIELDS=10
tasks=()
while IFS= read -r field; do
  tasks+=("$field")
done < <(printf '%s' "$input" | jq -r '
  .tasks[]?
  | [ .id, .name, .type, .status, .description,
      .model, .effort, .contextWindowSize, .tokenCount, .cwd ]
  | map(if . == null then "" else tostring end)
  | map(gsub("[\\n\\r\\t]"; " "))
  | .[]' 2>/dev/null)

(( ${#tasks[@]} >= FIELDS )) || exit 0

MAX_LEVEL_ROW=9

# Colour the leading dot by status. The status vocabulary is not documented, so
# anything unrecognised stays grey rather than being guessed at — the dot is
# always present and only its colour is a claim.
status_color() {
  case "$1" in
    running|active|in_progress) printf '%s' "$GREEN" ;;
    done|completed|success)     printf '%s' "$BLUE" ;;
    failed|error)               printf '%s' "$RED" ;;
    pending|queued|waiting)     printf '%s' "$YELLOW" ;;
    *)                          printf '%s' "$GREY" ;;
  esac
}

# Shed order, one step per level:
#   1  directory to its last two components, description to 40 columns
#   2  description to 24 columns, effort suffix
#   3  directory to its last component
#   4  the agent type, when it differs from the name
#   5  description
#   6  model name
#   7  token count
#   8  context percentage
#   9  the name and the directory clipped against a budget, so the row cannot
#      overflow however narrow the panel is
#
# Eliding the directory comes before dropping the description because elision
# keeps everything that identifies the worktree — the tail — while dropping the
# description loses it outright. The name and the full directory tail are last:
# they are the two fields that say *which* agent and *which* worktree a row is,
# and they are exactly what was being cut off before.
build_row() {
  local level=$1 dir desc budget share pct

  dir=$(tilde_path "$ROW_CWD")
  if   (( level >= 3 )); then dir=$(elide_path "$dir" 1)
  elif (( level >= 1 )); then dir=$(elide_path "$dir" 2)
  fi

  desc=$ROW_DESC
  if   (( level >= 5 )); then desc=''
  elif (( level >= 2 )); then desc=$(clip_tail "$desc" 24)
  elif (( level >= 1 )); then desc=$(clip_tail "$desc" 40)
  fi

  local name=$ROW_NAME
  if (( level >= 9 )); then
    # Chrome is the dot, its trailing space, and the two spaces before the dir.
    budget=$(( FIT_COLS - 4 ))
    (( budget < 4 )) && budget=4
    share=$(( (budget + 1) / 2 ))
    name=$(clip_tail "$name" "$share")
    dir=$(clip_head "$dir" $(( budget - share )))
  fi

  LEFT="$(status_color "$ROW_STATUS")●${R}"
  [[ -n "$name" ]] && LEFT+=" ${PURPLE}${B}${name}${R}"
  # The type only earns its columns when it says something the name does not.
  if (( level < 4 )) && [[ -n "$ROW_TYPE" && "$ROW_TYPE" != "$ROW_NAME" ]]; then
    LEFT+="${D}${PURPLE}:${ROW_TYPE}${R}"
  fi
  [[ -n "$dir" ]] && LEFT+="  ${BLUE}${dir}${R}"
  [[ -n "$desc" ]] && LEFT+="${DOT}${D}${desc}${R}"

  RIGHT=''
  if (( level < 6 )) && [[ -n "$ROW_MODEL" ]]; then
    RIGHT+="${GOLD}$(short_model "$ROW_MODEL")${R}"
    if (( level < 2 )) && [[ -n "$ROW_EFFORT" ]]; then RIGHT+="${D}${GOLD}:${ROW_EFFORT}${R}"; fi
  fi

  if (( level < 8 )) && (( ROW_CTX_MAX > 0 )); then
    pct=$(( ROW_TOKENS * 100 / ROW_CTX_MAX ))
    [[ -n "$RIGHT" ]] && RIGHT+="$SEP"
    RIGHT+="$(pct_color "$pct")${pct}%${R}"
  fi

  if (( level < 7 )) && (( ROW_TOKENS > 0 )); then
    [[ -n "$RIGHT" ]] && RIGHT+="$DOT"
    RIGHT+="${D}${GREY}$(fmt_tokens "$ROW_TOKENS")${R}"
  fi
}

# id and content on alternate lines, so the pairs can be turned into JSON in a
# single jq pass at the end rather than forking jq once per row.
pairs=''
i=0
while (( i + FIELDS <= ${#tasks[@]} )); do
  ROW_ID=${tasks[$i]}
  ROW_NAME=${tasks[$(( i + 1 ))]}
  ROW_TYPE=${tasks[$(( i + 2 ))]}
  ROW_STATUS=${tasks[$(( i + 3 ))]}
  ROW_DESC=${tasks[$(( i + 4 ))]}
  ROW_MODEL=${tasks[$(( i + 5 ))]}
  ROW_EFFORT=${tasks[$(( i + 6 ))]}
  ROW_CTX_MAX=$(to_int "${tasks[$(( i + 7 ))]}")
  ROW_TOKENS=$(to_int "${tasks[$(( i + 8 ))]}")
  ROW_CWD=${tasks[$(( i + 9 ))]}
  i=$(( i + FIELDS ))

  # No id, no way to address the row: leave it to the default rendering.
  [[ -n "$ROW_ID" ]] || continue

  LEFT=''; RIGHT=''
  fit build_row "$MAX_LEVEL_ROW"
  pairs+="${ROW_ID}
$(render "$LEFT" "$RIGHT")
"
done

[[ -n "$pairs" ]] || exit 0

# jq does the JSON escaping, including the ANSI escapes in the content.
printf '%s' "$pairs" | jq -Rsc '
  split("\n") as $l
  | range(0; $l | length; 2)
  | select($l[.] != "")
  | {id: $l[.], content: ($l[. + 1] // "")}'
