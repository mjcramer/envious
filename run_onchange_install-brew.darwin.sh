#!/usr/bin/env bash

set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

brewfile="Brewfile"
brew update
brew bundle install --file $brewfile && brew bundle cleanup --force --file $brewfile

echo "✅ Brew has finished sucessfully!"

# sudo nano /etc/pam.d/sudo
# Add this line at the very top:
# auth       sufficient     pam_tid.so
