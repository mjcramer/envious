#!/usr/bin/env bash
# Claude Code status line.
#
# Reads the status-line JSON payload on stdin and renders two lines:
#   1. location / git branch / model / effort / mode flags
#   2. context window usage / cost / diff stats / rate limits
#
# Every field is optional: anything missing from the payload is simply omitted,
# so this keeps working across Claude Code versions.

set -uo pipefail

input=$(cat)

# Without jq there is nothing to parse; degrade to the bare directory.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "${PWD}"
  exit 0
fi

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
if [[ -z "${CUR_DIR:-}" ]]; then
  printf '%s\n' "${PWD}"
  exit 0
fi

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

# ----------------------------------------------------------------- line 1 ---
line1=''

# Directory, shortened against $HOME.
dir=${CUR_DIR/#$HOME/\~}
line1+="${BLUE}${B}${dir}${R}"

# Git branch, with a marker when the tree is dirty.
if branch=$(git --no-optional-locks -C "$CUR_DIR" symbolic-ref --quiet --short HEAD 2>/dev/null) \
   || branch=$(git --no-optional-locks -C "$CUR_DIR" rev-parse --short HEAD 2>/dev/null); then
  dirty=''
  if [[ -n $(git --no-optional-locks -C "$CUR_DIR" status --porcelain 2>/dev/null | head -1) ]]; then
    dirty="${YELLOW}*${R}"
  fi
  line1+="${SEP}${PURPLE}⎇ ${branch}${R}${dirty}"
fi

# Model, plus effort level when the model exposes one.
if [[ -n "$MODEL" ]]; then
  line1+="${SEP}${GOLD}${B}${MODEL}${R}"
  [[ -n "$EFFORT" ]] && line1+="${D}${GOLD}:${EFFORT}${R}"
fi

# Mode flags.
flags=''
[[ "$FAST"     == "true"  ]] && flags+="${CYAN}⚡${R}"
[[ "$THINKING" == "false" ]] && flags+="${D}${GREY}🧠off${R}"
[[ -n "$STYLE" && "$STYLE" != "default" && "$STYLE" != "null" ]] && flags+=" ${CYAN}${STYLE}${R}"
[[ -n "$VIM" ]] && flags+=" ${GREEN}${VIM}${R}"
[[ -n "$AGENT" ]] && flags+=" ${PURPLE}@${AGENT}${R}"
[[ -n "$PR" ]] && flags+=" ${BLUE}#${PR}${R}"
[[ -n "$flags" ]] && line1+="${SEP}${flags# }"

# ----------------------------------------------------------------- line 2 ---
line2=''

# Context window meter.
ctx_pct=$(to_int "$CTX_PCT")
ctx_col=$(pct_color "$ctx_pct")
line2+="${D}${GREY}ctx${R} ${ctx_col}$(meter "$ctx_pct")${R} ${ctx_col}${ctx_pct}%"
if (( $(to_int "$CTX_MAX") > 0 )); then
  line2+=" ${D}${GREY}$(fmt_tokens "$(to_int "$CTX_USED")")/$(fmt_tokens "$(to_int "$CTX_MAX")")${R}"
fi

# Session cost, once it rounds to something worth showing.
if [[ "$COST" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  cost_fmt=$(printf '%.2f' "$COST")
  [[ "$cost_fmt" != "0.00" ]] && line2+="${SEP}${GREEN}\$${cost_fmt}${R}"
fi

# Lines changed this session.
added=$(to_int "$ADDED"); removed=$(to_int "$REMOVED")
if (( added > 0 || removed > 0 )); then
  line2+="${SEP}${GREEN}+${added}${R}${D}/${R}${RED}-${removed}${R}"
fi

# Subscription rate limits.
limits=''
if [[ -n "$RL5" ]]; then
  p=$(to_int "$RL5")
  limits+="$(pct_color "$p")5h ${p}%$(fmt_reset "$RL5_RESET")${R}"
fi
if [[ -n "$RL7" ]]; then
  p=$(to_int "$RL7")
  [[ -n "$limits" ]] && limits+="${D}${GREY} · ${R}"
  limits+="$(pct_color "$p")7d ${p}%$(fmt_reset "$RL7_RESET")${R}"
fi
[[ -n "$limits" ]] && line2+="${SEP}${limits}"

printf '%b\n%b\n' "$line1" "$line2"
