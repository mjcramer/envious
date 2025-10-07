SHELL := /usr/bin/env bash


.PHONY: brew-install
brew:
	@brew update
	@brew bundle install --file Brewfile && brew bundle cleanup --force --file Brewfile

mac:
	@scripts/bootstrap-mac.sh
	@bash scripts/macos.defaults.sh || true

# wsl:
# 	@scripts/bootstrap-wsl.sh

# iterm:
# 	@echo "Linking iTerm2 settings..."
# 	@mkdir -p "$$HOME/Library/Application Support/iTerm2"
# 	@rsync -a --delete "settings/iterm2/" "$$HOME/Library/Application Support/iTerm2/"
# 	@echo "✅ iTerm2 settings copied. (Restart iTerm2)"

# chez-init:
# 	@chezmoi init --source "$(PWD)/dotfiles" --apply

chez-apply:
	@chezmoi apply -v

.PHONY: chez-delete-state
chez-delete-state:
	chezmoi state delete-bucket --bucket=entryState
	chezmoi state delete-bucket --bucket=scriptState


# docker run --rm -it --user vscode --workdir /home/vscode mcr.microsoft.com/devcontainers/base:ubuntu