---
status: accepted
since: 0.17.0 (reconstructed from the CHANGELOG)
---
# The orchestrator names no CLI; one adapter module per CLI, behind a typed interface

`installer/cli.py` builds a neutral plan (`Plan`: what to install, with nothing specific to a CLI) and talks only to the adapter interface declared in `installer/interface.py` (`Adapter`, plus the optional `ContextHost` and `LiveCheck`); each CLI is one module in `installer/adapters/` with the same methods. Before, the orchestrator had grown to over 1,300 lines with one CLI's paths everywhere, and supporting a second CLI meant editing it in many places. A test checks that every adapter follows the interface, and the installation snapshot test proves that a refactor of the orchestrator changes no installed byte.

**Consequences**: identity, live checks, deletion scope and usage events all come from the adapter, never from a path the orchestrator guesses; `cli.py` stays under the 800-line ceiling by construction.
