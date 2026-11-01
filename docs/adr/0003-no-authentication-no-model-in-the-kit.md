---
status: accepted
since: 0.11.0, hardened in 0.36.0 (reconstructed from the CHANGELOG)
---
# The kit never handles authentication or model choice

The kit writes no authentication setting and no model name: the keys that once did so in the personal or organization settings are ignored and reported by `update` and `doctor`, and agents carry no model header (they inherit the session's model on every CLI). Signing in and choosing a model follow the organization's IT procedure and each CLI's own mechanism; a model forced by the kit applied to everyone, and a personal file replacing the defaults silently dropped the organization's authentication. `doctor --live` still diagnoses a sign-in or quota failure, but says what to set in the CLI, never in a kit file.

**Consequences**: what an earlier version wrote in a CLI's files stays and becomes the person's; `uninstall` keeps it. The kit's own documentation says where to sign in, CLI by CLI, and nothing more.
