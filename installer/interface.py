"""Contrat entre l'orchestrateur (cli.py) et les adaptateurs (adapters/*.py).

- Plan : ce qu'il faut installer, construit une fois par l'orchestrateur, neutre vis-à-vis des CLI.
- DoctorContext : ce que l'orchestrateur prête aux contrôles des adaptateurs.
- Adapter : ce que chaque module d'adaptateur doit fournir ; ContextHost et LiveCheck sont des capacités facultatives.

Un adaptateur est un module Python : les protocoles décrivent ses attributs et fonctions de module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, Set, Tuple, runtime_checkable


@dataclass
class Plan:
    """Plan neutre d'une installation. Les adaptateurs le lisent et ajoutent leurs écritures via managed_write."""
    home: Path
    kit: Path
    state: Dict[str, Any]
    old_files: Dict[str, str]
    overrides: Dict[str, Any]
    profile_id: str
    profile: Dict[str, Any]
    catalog: Dict[str, Any]
    selected: List[str]  # skills retenus
    skill_sources: List[Tuple[str, Path]]  # (nom du skill, dossier source)
    commands: List[Dict[str, Any]]
    context_names: List[str]  # couches gérées, dans l'ordre (00_KIT.md, 10_…, 20_…)
    kit_text: str
    practice_names: List[str]
    practice_texts: List[str]
    context_dir: Path  # dossier des couches et de 30_USER.md
    user_file: Path
    user_context_text: str
    agents: List[Tuple[str, Dict[str, Any]]]  # (nom, définition)
    models: Dict[str, Any]
    hooks_dir: Path
    hook_manifest: Dict[str, Any]
    enabled_hooks: Dict[str, Any]
    enabled_mcp: Dict[str, Any]
    writes: Dict[Path, bytes]  # écritures non suivies (fichiers de l'utilisateur, réglages fusionnés)
    deletes: List[Path]
    managed_write: Callable[[Path, bytes, str], None]  # écriture suivie dans l'état, refusée si le fichier a été modifié
    agent_body: Callable[[Dict[str, Any]], str]  # prompt complet d'un agent, pratiques incluses
    agent_markdown: Dict[str, str] = field(default_factory=dict)  # agents rendus par Gemini, réutilisés par agy
    blocks: Dict[str, str] = field(default_factory=dict)  # empreintes des blocs gérés dans des fichiers de l'utilisateur
    migrated_prefs: bool = False
    adapter_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # données privées d'un adaptateur, par NAME


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
    NAME: str  # valeur de --target
    LABEL: str  # nom affiché
    COMMAND: str  # exécutable
    HOME_DIR: str  # dossier de la CLI, relatif au dossier personnel
    BUILTIN_COMMANDS: Set[str]  # commandes intégrées, ignorées par usage
    MANAGED_PREFIXES: Tuple[str, ...]

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
    """La CLI ne lit son contexte que dans son dossier : si elle est active, les couches et 30_USER.md y sont écrits."""
    def context_dir(self, home: Path) -> Path: ...
    def installed_from_files(self, state: Dict[str, Any]) -> Dict[str, List[str]]: ...


@runtime_checkable
class LiveCheck(Protocol):
    """La CLI sait faire un appel réel au modèle, avec diagnostic."""
    def live(self, home: Path) -> int: ...
