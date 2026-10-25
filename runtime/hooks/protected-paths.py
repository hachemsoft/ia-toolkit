#!/usr/bin/env python3
"""Garde-fou Gemini (BeforeTool, write_file|replace) : refuse l'écriture sous un chemin protégé.

Les chemins protégés sont des motifs glob, un par ligne, dans <repo>/.ai-kit/protected-paths (ou l'ancien <repo>/.gemini/protected-paths), commentaires avec #.
Exemple : target/**  ·  models/legacy/**  ·  *.lock  ·  dbt_project.yml
Sans fichier de motifs, tout est autorisé. Sortie : JSON {"decision": "deny", "reason": ...} ou {}.
"""
import fnmatch
import json
import os
import re
import sys

# Fichier des chemins protégés d'un dossier : .ai-kit/protected-paths (neutre, toutes CLI), et l'ancien .gemini/protected-paths, lu aussi.
PATTERN_FILES = (os.path.join('.ai-kit', 'protected-paths'), os.path.join('.gemini', 'protected-paths'))

def patterns(directory):
    found = []
    for name in PATTERN_FILES:
        try:
            with open(os.path.join(directory, name), encoding='utf-8') as handle:
                found += [line.strip() for line in handle if line.strip() and not line.lstrip().startswith('#')]
        except OSError:
            continue
    return found

def pattern_dirs(cwd):
    """Dossiers dont le fichier des chemins protégés s'applique : du dossier de lancement jusqu'à la racine du repo
    (le premier dossier qui contient .git). Un monorepo lancé depuis un sous-dossier reste protégé par la racine."""
    dirs, current = [], os.path.abspath(cwd)
    while True:
        dirs.append(current)
        if os.path.exists(os.path.join(current, '.git')):
            return dirs
        parent = os.path.dirname(current)
        if parent == current:
            return [os.path.abspath(cwd)]
        current = parent

def matches(relative, pattern):
    # '**' couvre aussi zéro dossier ; fnmatch ne le fait pas seul. Comparaison insensible à la casse (macOS, Windows).
    relative, pattern = relative.lower(), pattern.lower()
    candidates = {pattern, pattern.replace('/**', ''), pattern.replace('**/', '')}
    if any(fnmatch.fnmatchcase(relative, c) for c in candidates):
        return True
    # Préfixe de dossier avec frontière : target/** protège target/x.sql, pas targets/x.sql.
    return any(relative == p[:-3] or relative.startswith(p[:-3] + '/') for p in candidates if p.endswith('/**'))

def deny_output(payload, reason):
    """Refus dans la forme que la CLI attend : Codex et les CLI au format PreToolUse valident strictement leur sortie."""
    if payload.get('hook_event_name') == 'PreToolUse':
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
    return {'decision': 'deny', 'reason': reason}

def as_text(value):
    """Une commande peut arriver en chaîne ou en liste d'arguments (Codex : ["bash", "-lc", "..."])."""
    if isinstance(value, list):
        return ' '.join(str(v) for v in value)
    return str(value or '')

PATCH_HEADER = re.compile(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$|^\+\+\+ b/(.+)$', re.M)

def target_paths(tool, args):
    """Fichiers qu'un appel d'outil va écrire : un chemin direct (Gemini, agy, CLI au format Write/Edit) ou les en-têtes d'un patch (Codex apply_patch)."""
    if not isinstance(args, dict):
        args = {'input': args}
    for key in ('file_path', 'TargetFile', 'AbsolutePath', 'FilePath', 'path', 'Path'):
        if isinstance(args.get(key), str) and args.get(key):
            return [args[key]]
    if 'patch' in tool.lower():
        found = []
        for value in args.values():
            for match in PATCH_HEADER.finditer(as_text(value)):
                found.append(next(g for g in match.groups() if g).strip())
        return found
    return []

def use_utf8():
    """Les CLI envoient et lisent de l'UTF-8 ; sous Windows, la console vaut cp1252 par défaut : la forcer pour l'entrée et la sortie."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

def main():
    use_utf8()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print('{}')
        return
    # Formes d'entrée : Gemini CLI (tool_name / tool_input.file_path), Antigravity (toolCall.name / toolCall.args.TargetFile...),
    # Codex (hook_event_name PreToolUse, apply_patch dont les chemins sont dans les en-têtes du patch).
    call = payload.get('toolCall') or {}
    tool = str(payload.get('tool_name') or call.get('name') or '')
    if not re.search(r'write|replace|edit|patch', tool, re.I):
        print('{}')
        return
    args = payload.get('tool_input') or call.get('args') or {}
    paths = target_paths(tool, args)
    workspace = (payload.get('workspacePaths') or [None])[0]
    cwd = payload.get('cwd') or workspace or os.getcwd()
    if not paths:
        print('{}')
        return
    for file_path in paths:
        decision = check(file_path, cwd)
        if decision:
            print(json.dumps(deny_output(payload, decision), ensure_ascii=False))
            return
    print('{}')

def check(file_path, cwd):
    """Raison du refus si le fichier tombe sous un chemin protégé, sinon None."""
    absolute = file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    for directory in pattern_dirs(cwd):
        try:
            relative = os.path.relpath(os.path.normpath(absolute), os.path.normpath(directory)).replace(os.sep, '/')
        except ValueError:
            # Windows : autre lecteur que ce dossier, donc hors de ses motifs.
            continue
        if relative == '..' or relative.startswith('../'):
            continue
        for pattern in patterns(directory):
            if not matches(relative, pattern):
                continue
            return 'Refusé par le kit : « ' + relative + ' » correspond au chemin protégé « ' + pattern + ' » déclaré dans les chemins protégés du repo (.ai-kit/protected-paths). Proposer le changement à une personne plutôt que de l’écrire.'
    return None

if __name__ == '__main__':
    main()
