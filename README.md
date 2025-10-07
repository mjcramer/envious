## envious

A personal dotfiles and scripts collection driven by Chezmoi. It provisions shell configuration, common tooling, and handy scripts/templates across macOS and Linux.


```
sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply mjcramer/envious
```




### What this repo provides
- **Dotfiles**: `zsh`, `fish`, `git`, `htop`, `iterm2`, `nvim` and more under `private_dot_config/` and top-level dotfiles
- **Scripts**: bootstrap and helper scripts in `dot_local/bin/` and `.chezmoiscripts/`
- **Packages**: curated package lists (e.g., `apt`) in `.chezmoidata/packages.yaml`
- **Templates**: reusable script templates under `dot_local/private_share/templates/`

### Requirements
- macOS or Linux
- [Chezmoi](https://www.chezmoi.io/)

### Quick start (GitHub remote)
```bash
# 1) Install chezmoi (macOS example)
brew install chezmoi

# 2) Initialize and apply this repo
chezmoi init --apply mjcramer/envious
```

### Quick start (local checkout)
```bash
# 1) From a local clone of this repo
cd /path/to/envious

# 2) Initialize chezmoi using the local working tree
chezmoi init --source . --apply
```

### What happens during apply
- Dotfiles are placed into your home directory (respecting templates and privacy rules)
- Helper scripts in `.chezmoiscripts/` may run on certain events (e.g., first run, changes)
- Package install scripts may run to install common tools

### macOS notes
- Homebrew packages are managed via `Brewfile`
- iTerm2 profile under `private_dot_config/iterm2/`

### Linux notes
- `apt` packages are defined in `.chezmoidata/packages.yaml`
- Install hooks such as `run_onchange_before_install-packages.sh.tmpl` leverage that list

### Updating
```bash
# Pull latest changes and re-apply
chezmoi update
chezmoi apply
```

### Repository layout (high-level)
- `dot_local/` — personal scripts and shared templates
- `.chezmoiscripts/` — event-driven provisioning scripts
- `.chezmoidata/` — data files used by templates/scripts (e.g., packages)
- `private_dot_config/` — application configs (git, fish, zsh, nvim, iterm2, etc.)
- `Brewfile` — Homebrew bundle for macOS

### Related: Nix-based setup
Prefer declarative provisioning with Nix? See the companion repo `nix-envy` in this workspace for a flake-based macOS/Linux configuration.

### Safety and overrides
- Review scripts in `.chezmoiscripts/` before first apply
- Adjust package lists and templates to your environment
- Use `chezmoi diff` to preview changes at any time

### License
This repository is intended for personal use. Use at your own risk; adapt as needed.
