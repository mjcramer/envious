#!/usr/bin/env bash
# Usage: ./cleanup-gh-runs.sh [days_old] [repo]
# Defaults: 14 days, current repo

set -euo pipefail

DAYS=${1:-14}
REPO=${2:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}
CUTOFF=$(date -d "-${DAYS} days" --utc +%Y-%m-%dT%H:%M:%SZ)

echo "Deleting runs older than ${DAYS} days (before ${CUTOFF}) in ${REPO}..."

deleted=0
page=1

while true; do
  run_ids=$(gh api "repos/${REPO}/actions/runs?per_page=100&page=${page}" \
    --jq ".workflow_runs[] | select(.created_at < \"${CUTOFF}\") | .id")

  [[ -z "$run_ids" ]] && break

  for id in $run_ids; do
    gh api -X DELETE "repos/${REPO}/actions/runs/${id}" && ((deleted++)) || true
    echo "  Deleted run $id"
  done

  ((page++))
done

echo "Done. Deleted ${deleted} runs."
