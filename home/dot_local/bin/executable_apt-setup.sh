#!/usr/bin/env bash
set -euo pipefail

if ! command -v apt >/dev/null 2>&1; then
  exit 0
fi

sudo apt-get update -y
sudo apt-get install -y \
  bash-completion build-essential ca-certificates curl direnv fd-find fzf git grc htop iftop jq make nmap openssh-client tree unzip watch wget zip zsh

# mise
if ! command -v mise >/dev/null 2>&1; then
  curl https://mise.jdx.dev/install.sh | sh
fi

echo "✅ apt baseline installed."
