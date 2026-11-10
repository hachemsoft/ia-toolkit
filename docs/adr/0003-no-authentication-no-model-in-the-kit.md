---
status: accepted
since: 0.11.0, hardened in 0.36.0 (reconstructed from the CHANGELOG)
---
# The kit never handles authentication or model choice

The kit writes no authentication setting and no model name, and agents carry no model header: they inherit the session's
model on every CLI. An authentication or model key in `aikit.toml` is reported as an unknown key and ignored. Signing in
and choosing a model follow the organization's IT procedure and each CLI's own mechanism. `doctor --live` still diagnoses a
sign-in or quota failure, but says what to set in the CLI, never in a kit file.

**Why**: a model forced by the kit applies to everyone, and a personal file replacing the defaults silently dropped the
organization's authentication.

**Consequences**: the kit's documentation says where to sign in, CLI by CLI, and nothing more.
