---
status: accepted, amended: organization-specific facts go in the organization's own Core and Team repositories and in `managed.toml`, not in an `organization.toml`
since: 0.11.0 and 0.20.0 (reconstructed from the CHANGELOG)
---
# A generic, public repository, in English, that names no organization and no competing product

The repository names no organization, project, region, person, headcount or schedule, and no competing product or kit; the only third parties named are the CLIs the kit targets and the upstream sources it redistributes under their licence. Everything is in English (docs, messages, playbooks, templates, tests); agents reply in the person's language. The public repository is the single source, mirrored one way into an organization's own hosting: a private fact published once cannot be taken back, and one language keeps one text for every mirror.

**Consequences**: organization-specific facts go in `organization.toml` and the team practice files, never in the code or the docs; checked by hand before each release, since a test cannot know every name.
