SHELL := /usr/bin/env bash


.PHONY: brew-install
brew:
	@brew update 
	@brew bundle install --file Brewfile && brew bundle cleanup --force --file Brewfile

mac:
	@scripts/bootstrap-mac.sh
	@bash scripts/macos.defaults.sh || true

wsl:
	@scripts/bootstrap-wsl.sh

iterm:
	@echo "Linking iTerm2 settings..."
	@mkdir -p "$$HOME/Library/Application Support/iTerm2"
	@rsync -a --delete "settings/iterm2/" "$$HOME/Library/Application Support/iTerm2/"
	@echo "✅ iTerm2 settings copied. (Restart iTerm2)"

chez-init:
	@chezmoi init --source "$(PWD)/dotfiles" --apply

chez-apply:
	@chezmoi apply -v

uninstall-nix:
	@echo "Review before running: remove nix-daemon + /nix (macOS)."
