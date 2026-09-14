SHELL := /usr/bin/env bash


.PHONY: brew-install
brew:
	@brew update
	@brew bundle install --file Brewfile && brew bundle cleanup --force --file Brewfile

mac:
	@scripts/bootstrap-mac.sh
	@bash scripts/macos.defaults.sh || true

chez-apply:
	@chezmoi apply -v

# Repo-local tests. These run against the chezmoi *source* files, so they can be
# run before applying anything.
.PHONY: test
test:
	@tests/statusline-test.py

.PHONY: chez-delete-state
chez-delete-state:
	chezmoi state delete-bucket --bucket=entryState
	chezmoi state delete-bucket --bucket=scriptState


# docker run --rm -it --user vscode --workdir /home/vscode mcr.microsoft.com/devcontainers/base:ubuntu
