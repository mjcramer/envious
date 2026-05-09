# Templates

Copier project templates. Scaffold a new project with:

```shell
copier copy ~/.local/share/templates/<template-name> <destination>
```

## Available templates

| Template | Description | Key variables |
|----------|-------------|---------------|
| `scala-zio` | Scala 3 service — ZIO 2, ZIO HTTP, ZIO Config, ZIO Logging | `project_name`, `github_username`, `author_email` |
| `scala-pekko` | Scala 3 service — Apache Pekko typed actors, Pekko HTTP, PureConfig | same |
| `bash-script` | Complete bash script — getopts, logging helpers, arch detection, source guard | `script_name`, `description`, `use_colors` |
| `python-subcommands` | Python CLI with argparse subcommands | `script_name`, `description` |
| `python_argparse` | Python CLI with simple argparse (no subcommands) | `packages` |
| `http-server` | Minimal Python HTTP server | `packages` |
| `makefile-process` | Makefile start/stop/restart/status targets for a background process | `process_name`, `start_command` |
