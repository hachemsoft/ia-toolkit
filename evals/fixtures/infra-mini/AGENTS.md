# Web infrastructure

Terraform for the web tier. Environments: `dev` (default workspace), `prod` (applied by the pipeline only).

## Verifying your work
| Stack | Changed | Full |
| --- | --- | --- |
| Terraform | `terraform fmt -check && terraform validate && terraform plan` | the same |

## Things the agent gets wrong
- Never run `terraform apply`: the pipeline applies after review.
