# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this repo is

A personal dotfiles and environment provisioning repo managed by [chezmoi](https://www.chezmoi.io/). It targets both macOS (Homebrew) and Linux (apt/Ubuntu/Debian), and provisions shell config, tooling, scripts, and application configs.

Bootstrap from scratch:
```bash
sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply mjcramer/envious
```

## Key commands

```bash
# Apply dotfiles from a local checkout
chezmoi init --source . --apply

# Re-apply after changes
chezmoi apply -v

# Preview what would change
chezmoi diff

# Sync from remote and re-apply
chezmoi update && chezmoi apply

# Run Homebrew bundle (macOS)
make brew

# Reset chezmoi script state (force re-run of run_once/run_onchange scripts)
make chez-delete-state
```

## Chezmoi conventions

File naming drives chezmoi behavior:

| Prefix/suffix | Meaning |
|---|---|
| `dot_` | Becomes `.` in the home directory |
| `private_` | Written with restricted permissions (600/700) |
| `readonly_` | Written read-only |
| `executable_` | Written with execute bit |
| `.tmpl` suffix | Processed as a Go template before writing |
| `run_once_` | Script runs once (tracked by content hash) |
| `run_onchange_` | Script re-runs whenever its content changes |
| `run_after_` | Script runs after all other scripts |

Templates have access to chezmoi data variables (e.g., `.chezmoi.os`, `.email`, `.username`) and the data defined in `.chezmoidata/packages.yaml` (accessed as `.packages.*`).

## Repository layout

- `.chezmoidata/packages.yaml` — package lists for Homebrew (brews, casks, VS Code extensions) and apt; consumed by the install script template
- `.chezmoiscripts/` — provisioning scripts that run automatically:
  - `run_once_enable-sudo.sh.tmpl` — grants passwordless sudo (Linux)
  - `run_onchange_before_install-packages.sh.tmpl` — installs/updates all packages via Homebrew or apt
- `private_dot_config/` — application configs deployed to `~/.config/`:
  - `fish/` — Fish shell config, functions, conf.d integrations (chezmoi, mise, direnv, brew, docker, tide prompt), and Fisher plugin list
  - `git/readonly_config.tmpl` — git config template (injects `.email`)
  - `nvim/readonly_init.lua` — Neovim config
  - `iterm2/` — iTerm2 plist
- `dot_local/bin/` — personal scripts deployed to `~/.local/bin/` (AWS helpers, Docker helpers, Kubernetes helpers, git utilities, etc.)
- `dot_local/private_share/templates/` — [copier](https://copier.readthedocs.io/) project templates for bootstrapping new scripts/projects
- `dot_zshrc` — Zsh config (primarily switches to Fish for interactive shells)
- `dot_m2/settings.xml` — Maven settings
- `dot_sbt/1.0/` — Global sbt plugins config
- `run_after_clean-up.sh.tmpl` — Runs last after all other scripts

## Shell setup

The primary interactive shell is **Fish** via the Tide prompt. `.zshrc` hands off to Fish for interactive use. Fish conf.d files handle tool integrations: `mise` (runtime version manager), `direnv`, `brew`, and `docker`.

Fisher plugins: `autopair.fish`, `tide@v6`, `franciscolourenco/done`.

## Templating patterns

- Use `{{ .chezmoi.os }}` to branch on `darwin` vs `linux`
- Package lists are iterated with `{{ range .packages.homebrew.brews }}` etc.
- Secrets/personal values (`email`, `username`) come from chezmoi data, not hardcoded
- The `include` function combined with `sha256sum` in script templates (e.g., the Fisher install script) forces re-runs when the referenced file changes

## Copier templates

`dot_local/private_share/templates/` contains copier scaffolding templates. Use the `scaffold` wrapper (deployed to `~/.local/bin/scaffold`) instead of invoking copier directly:

```bash
scaffold                     # fzf picker with variable preview
scaffold list                # plain list of available templates
scaffold <template>          # scaffold into current directory
scaffold <template> <dest>   # scaffold into destination
```

Fish tab completion is wired up — `scaffold <TAB>` expands to template names. Override the templates directory with `TEMPLATES_DIR=/path scaffold ...`.

**Scala templates** (both use Scala 3.8, sbt 1.12, Java 21, Docker via sbt-native-packager, GitHub Actions):
- `scala-zio` — ZIO 2 + ZIO HTTP + ZIO Config (HOCON) + ZIO Logging/SLF4J
- `scala-pekko` — Apache Pekko typed actors + Pekko HTTP + PureConfig + scala-logging

Both ask for `project_name`, `description`, `github_username`, `author_name`, `author_email`. The package is derived as `io.github.<github_username>.<project_slug>` and the source tree is generated under `src/main/scala/io/github/{{github_username}}/{{project_slug}}/` using copier's Jinja2 directory-name rendering.

**Other templates:** `bash-script` (getopts, logging, arch detection, source guard; `use_colors` parameter injects ANSI variables and colored helpers), `python-subcommands`, `python_argparse`, `http-server`, `makefile-process`.
