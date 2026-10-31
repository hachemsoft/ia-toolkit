"""Contract between the orchestrator (cli.py) and the adapters (adapters/*.py).

- Plan: what to install, built once by the orchestrator, neutral with respect to the CLIs.
- DoctorContext: what the orchestrator lends to the adapters' checks.
- Adapter: what each adapter module must provide; ContextHost and LiveCheck are optional capabilities.

An adapter is a Python module: the protocols describe its module attributes and functions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, Set, Tuple, runtime_checkable


@dataclass
class Plan:
    """Neutral plan of an installation. The adapters read it and add their writes through managed_write."""
    home: Path
    kit: Path
    state: Dict[str, Any]
    old_files: Dict[str, str]
    overrides: Dict[str, Any]
    profile_id: str
    profile: Dict[str, Any]
    catalog: Dict[str, Any]
    selected: List[str]  # selected skills
    skill_sources: List[Tuple[str, Path]]  # (skill name, source folder)
    commands: List[Dict[str, Any]]
    context_names: List[str]  # managed layers, in order (00_KIT.md, 10_…, 20_…)
    kit_text: str
    practice_names: List[str]
    practice_texts: List[str]
    context_dir: Path  # folder of the layers and 30_USER.md
    user_file: Path
    user_context_text: str
    agents: List[Tuple[str, Dict[str, Any]]]  # (name, definition)
    models: Dict[str, Any]
    hooks_dir: Path
    hook_manifest: Dict[str, Any]
    enabled_hooks: Dict[str, Any]
    enabled_mcp: Dict[str, Any]
    writes: Dict[Path, bytes]  # untracked writes (user files, merged settings)
    deletes: List[Path]
    active: List[str]  # NAME of the active adapters, in ADAPTERS order
    managed_write: Callable[[Path, bytes, str], None]  # write tracked in the state, refused if the file was modified
    agent_body: Callable[[Dict[str, Any]], str]  # full prompt of an agent, practices included
    agent_markdown: Dict[str, str] = field(default_factory=dict)  # agents rendered by Gemini, reused by agy
    blocks: Dict[str, str] = field(default_factory=dict)  # digests of the managed blocks in user files
    migrated_prefs: bool = False
    notices: List[str] = field(default_factory=list)  # lines for the person: a refused synchronisation, a moved file
    adapter_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # private data of an adapter, by NAME
    skill_notes: Dict[str, str] = field(default_factory=dict)  # appended to a skill's SKILL.md: optional skills not installed

    def skill_file(self, skill: str, source: Path, src: Path) -> bytes:
        """Bytes of a skill file as installed: the source, plus for SKILL.md what to do without its optional skills."""
        data = src.read_bytes()
        if src == source/'SKILL.md' and self.skill_notes.get(skill):
            data = data.rstrip(b'\n') + b'\n\n' + self.skill_notes[skill].encode('utf-8')
        return data


@dataclass
class DoctorContext:
    profile: Dict[str, Any]
    load_commands: Callable[[], List[Dict[str, Any]]]
    managed_context_names: Callable[[Dict[str, Any]], List[str]]
    allowed_domains: Callable[[], List[str]]
    domain_allowed: Callable[[str, List[str]], bool]


Status = Callable[[bool, str], None]


@runtime_checkable
class Adapter(Protocol):
    NAME: str  # value of --target
    LABEL: str  # display name
    COMMAND: str  # executable
    HOME_DIR: str  # CLI folder, relative to the home folder
    BUILTIN_COMMANDS: Set[str]  # built-in commands, ignored by usage
    MANAGED_PREFIXES: Tuple[str, ...]
    # How the CLI applies an agent's tool list (agents/*.json "tools"): 'native' (the CLI restricts the tools),
    # 'instruction' (only the agent's prompt says it; nothing technical prevents a write) or 'unavailable' (no agents).
    AGENT_TOOLS: str
    # What history() can really see in the CLI's logs: 'prompt' (so commands typed), 'skill', 'agent', 'error'.
    # The usage report never counts as unused what no log of the person's CLIs can show.
    OBSERVES: Set[str]

    def present(self, home: Path) -> bool: ...
    def is_managed(self, rel: str) -> bool: ...
    def active_account(self, home: Path) -> Optional[str]: ...
    def install(self, p: Plan) -> None: ...
    def finalize(self, p: Plan, active: bool = True) -> None: ...
    def summary(self, p: Plan) -> Optional[str]: ...
    def doctor(self, home: Path, state: Dict[str, Any], status: Status, ctx: DoctorContext) -> None: ...
    def doctor_hint(self) -> Optional[str]: ...
    def history(self, home: Path, state: Dict[str, Any]) -> Iterator[Dict[str, Any]]: ...


@runtime_checkable
class ContextHost(Protocol):
    """The CLI only reads its context from its own folder: if it is active, the layers and 30_USER.md are written there."""
    def context_dir(self, home: Path) -> Path: ...
    def installed_from_files(self, state: Dict[str, Any]) -> Dict[str, List[str]]: ...


@runtime_checkable
class LiveCheck(Protocol):
    """The CLI can make a real call to the model, with diagnosis."""
    def live(self, home: Path) -> int: ...
