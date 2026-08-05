# Templates

Copier project templates. Use the deployed `scaffold` wrapper to create a project:

```bash
scaffold <template-name> <destination>
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
| `terraform-makefile` | Terraform root Makefile plus provider-specific component Makefiles | `provider`, `components` |

The `terraform-makefile` template requires `AWS_REGION` for AWS projects. `AWS_TERRAFORM_BUCKET`, `AWS_KMS_ALIAS`, and `AWS_EKS_CLUSTER_NAME` may be overridden from their generated defaults.

### Terraform Makefile

Run:

```bash
scaffold terraform-makefile ./infrastructure
```

Choose `gcp` or `aws`, then enter component names separated by spaces, for example:

```text
network security
```

The generated project contains only the selected provider implementation:

```text
infrastructure/
├── terraform.mk
├── network/Makefile
└── security/Makefile
```
