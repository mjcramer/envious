SHELL := /usr/bin/env bash


.PHONY: help
help: ## Print this help message
	@printf "\033[34mmake\033[0m [\033[36m<target>\033[0m]...\n"
	@printf "   where \033[36m<target>\033[0m can be one or more of the following...\n\n"
	@grep -h -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
	@printf "\n"

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
	@tests/ssh-signing-test.py

.PHONY: chez-delete-state
chez-delete-state:
	chezmoi state delete-bucket --bucket=entryState
	chezmoi state delete-bucket --bucket=scriptState


%: ## Pass to chezmoi
	chezmoi $*
