# Templates

Copier project templates. Scaffold a new project with:

```shell
copier copy ~/.local/share/templates/<template-name> <destination>
```

## Available templates

| Template | Description |
|----------|-------------|
| `scala-zio` | Scala 3 service with ZIO 2, ZIO HTTP, ZIO Config, ZIO Logging |
| `scala-pekko` | Scala 3 service with Apache Pekko (typed actors), Pekko HTTP, PureConfig |
| `python_argparse` | Python CLI script with argparse |
| `http-server` | Minimal Python HTTP server |
| `flake-shell` | Nix flake dev shell |

## Snippet files

Single-file references (copy manually or use as paste-from):

- `executable_bash_headers.sh` — standard bash script header with error handling
- `executable_bash_getopts.sh` — getopts argument parsing pattern
- `executable_bash_heredoc.sh` — heredoc usage examples
- `executable_bash_pretty.sh` — color output helpers
- `executable_bash_script_dir.sh` — reliable `SCRIPT_DIR` resolution
- `executable_bash_source_only.sh` — guard to prevent direct execution
- `executable_bash_check_arch.sh` — architecture detection
- `ansi_colors` — ANSI color reference
- `shell.nix` — basic nix-shell template
- `ssh.config.bastian` — SSH bastion host config pattern
- `Makefile.start_stop_process` — Makefile pattern for managing a background process
