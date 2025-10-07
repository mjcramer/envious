#!/usr/bin/env bash

set -euo pipefail
echo farts
{{ if eq .chezmoi.os "darwin" -}}
# Brewfile hash: {{ include "Brewfile" | sha256sum }}
prefix="[install brew packages]"

if ! command -v brew >/dev/null 2>&1; then
  echo "$prefix Installing brew...."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)"
else
  echo "$prefix Brew is already installed."
fi

echo "$prefix ✅ Updating packages,,,"

brewfile="Brewfile"
brew update
brew bundle install --file $brewfile && brew bundle cleanup --force --file $brewfile

echo "$prefix ✅ Brew has finished sucessfully!"

{{ else if eq .chezmoi.os "linux" -}}

prefix="[install apt packages]"

# Check if we're on Ubuntu or Debian
if [ ! -f /etc/os-release ]; then
    echo "$prefix Cannot determine OS - /etc/os-release not found"
    exit 1
fi

. /etc/os-release

if [ "$ID" != "ubuntu" ] && [ "$ID" != "debian" ]; then
    echo "$prefix Not Ubuntu or Debian (detected: $ID) - skipping apt package installation"
    exit 0
fi

echo "$prefix Detected $NAME - installing apt packages..."

sudo apt update && sudo apt install -y \
{{ range .packages.apt -}}
    {{ . }} \
{{ end -}}

echo "$prefix  ✅ Apt package installation complete!"

{{ else }}

echo "Unable to determine package manager for {{ .chezmoi.os }}, skipping package installation..."

{{ end -}}
