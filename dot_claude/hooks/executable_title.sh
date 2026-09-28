#!/bin/bash
input=$(cat)
dir=$(jq -r '.cwd // empty' <<<"$input")
agent=$(jq -r '.agent_type // "default"' <<<"$input")
seq=$(printf '\033]0;%s · %s\007' "${dir##*/}" "$agent")
jq -nc --arg seq "$seq" '{terminalSequence: $seq}'
