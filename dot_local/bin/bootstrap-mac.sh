#!/usr/bin/env bash
set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

brew bundle --file="$(git rev-parse --show-toplevel)/Brewfile"

if command -v mise >/dev/null 2>&1; then
  mise install || true
fi

echo "✅ mac bootstrap complete."
