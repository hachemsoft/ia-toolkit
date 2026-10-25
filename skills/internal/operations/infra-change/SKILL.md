---
name: infra-change
description: "Prepare or review an infrastructure or delivery change: Terraform, Kubernetes, Helm, CI/CD pipeline, Dockerfile, cloud configuration. Triggers: modify the pipeline, add a resource, change a deployment, open a port, bump an image version, review this Terraform plan."
---

# infra-change

Read `AGENTS.md`, the environment layout (folders, workspaces, overlays, Helm values) and how the repo deploys: who applies, from where, with which account. Work on the development or staging environment the repo designates; never production without an explicit instruction. Before any change, state the blast radius: resources created, modified, destroyed or recreated, services affected, possible outage. Produce the read-only proof the repo provides (`terraform plan`, `helm diff`, `kubectl diff`, `--dry-run`, pipeline validation) and read it line by line; an unintended destruction or replacement stops the work. Never run `apply`, `destroy`, a deployment or any command that modifies a shared environment: propose the command and leave it to the person or the pipeline. Check least privilege (IAM permissions, ports, public exposure), the absence of plaintext secrets (variables, files, pipeline logs) and version pinning (images, modules, providers, actions). Write the rollback before delivery. Describe the delivery with the mr skill, with the plan or diff as evidence.

## Rationalizations and rebuttals
| Excuse | Rebuttal |
| --- | --- |
| "It's just a variable, no need for a plan" | A variable can recreate a resource; the plan tells you in ten seconds. |
| "I'll apply in dev, it won't break anything" | A shared environment is still shared; propose the command, do not run it. |
| "I'll use `latest`, it will always be up to date" | An unpinned version changes without review; pin it and bump the version through a merge request (MR). |
| "Rollback, we'll see if it breaks" | Without a written rollback, the incident lasts as long as it takes to invent one. |
