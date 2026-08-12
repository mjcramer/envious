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
| `terraform-makefile` | Terraform root Makefile plus provider-specific component Makefiles | `provider`, `project_name`, `owner_account`, `modules`, `components` |

The `terraform-makefile` template requires `AWS_REGION` for AWS projects. Enter a GCP owner email address or a 12-digit AWS owner account ID. Each component includes a provider/backend `main.tf`. `AWS_TERRAFORM_BUCKET`, `AWS_TERRAFORM_KEY`, `AWS_KMS_ALIAS`, and `AWS_EKS_CLUSTER_NAME` may be overridden from their generated defaults.

### Terraform Makefile

Run:

```bash
scaffold terraform-makefile ./infrastructure
```

Choose `gcp` or `aws`, enter a project name containing only alphanumeric characters and dashes, enter the owner account, optionally enter module names (blank means no modules), then enter component names separated by spaces, for example:

```text
network security
```

Any module names entered at the prompt are prefixed with the project name in `terraform.mk`. For example, project `my-project` with modules `subsystem system` generates `my-project-subsystem my-project-system`; no modules are generated when the module prompt is left blank.

The generated project contains only the selected provider implementation:

```text
infrastructure/
├── terraform.mk
├── network/
│   ├── main.tf
│   └── Makefile
└── security/
    ├── main.tf
    └── Makefile
```

### Bootstrap components

Run these commands from each generated component directory. Set `TF_VAR_environment` before running any target because it is used to derive the component name.

For GCP, also set the billing account, project ID, and region. The bootstrap targets create or configure the project, encryption key, and Terraform state bucket before initializing Terraform:

```bash
export TF_VAR_environment=dev
export GCP_BILLING_ACCOUNT=000000-000000-000000
export GCP_PROJECT_ID=my-gcp-project
export GCP_REGION=us-central1

make project
make encryption
make storage
make init
make plan
make apply
```

For AWS, set the region. `make project` verifies that the active credentials belong to the configured owner account; `make storage` also creates the KMS key before configuring the state bucket:

```bash
export TF_VAR_environment=dev
export AWS_REGION=us-east-1

make project
make encryption
make storage
make init
make plan
make apply
```

Run `make credentials` after applying when the component provisions a Kubernetes cluster.
