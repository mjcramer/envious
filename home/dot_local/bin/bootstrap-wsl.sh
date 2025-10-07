#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
"$repo_root/scripts/apt-setup.sh"

if command -v "$HOME/.local/bin/mise" >/dev/null 2>&1; then
  "$HOME/.local/bin/mise" install || true
elif command -v mise >/dev/null 2>&1; then
  mise install || true
fi

echo "✅ WSL bootstrap complete."
