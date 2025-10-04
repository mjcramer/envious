# envious

Dotfiles + dev environment setup for macOS and WSL (Ubuntu).

- Dotfiles: **chezmoi**
- macOS: **Homebrew** (+ Brewfile)
- WSL: **apt** (scripted)
- Tool versions: **mise** with `.tool-versions`

## Quick start

### macOS
1) `./scripts/bootstrap-mac.sh`
2) `make iterm`    # optional, syncs settings/iterm2/
3) `chezmoi init --source ./dotfiles --apply`

### Windows WSL (Ubuntu)
1) `./scripts/bootstrap-wsl.sh`
2) `chezmoi init --source ./dotfiles --apply`
