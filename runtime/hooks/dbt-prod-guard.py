#!/usr/bin/env python3
"""Garde-fou Gemini (BeforeTool, run_shell_command) : refuse une commande dbt visant un target de production.

Autorisation ponctuelle : AI_KIT_ALLOW_PROD=1 dans l'environnement de la session.
Targets considérés comme production : prod, production, prd, ou la liste AI_KIT_PROD_TARGETS (séparée par des virgules).
Sortie : JSON {"decision": "deny", "reason": ...} ou {} pour laisser passer. Jamais d'exception vers Gemini.
"""
import json
import os
import re
import sys

class _Hit:
    def __init__(self, target):
        self._target = target
    def group(self, _index):
        return self._target

def default_target_hit(command, targets, payload):
    """Sans --target ni DBT_TARGET, le target par défaut vient de profiles.yml (--profiles-dir, DBT_PROFILES_DIR, ~/.dbt) : refuser s'il est en production."""
    if re.search(r'(?:--target|-t)(?:[\s=]|$)|\bDBT_TARGET=', command, re.I):
        return None
    match = re.search(r'--profiles-dir[\s=]+[\'"]?([^\s\'"]+)', command)
    cwd = payload.get('cwd') or (payload.get('workspacePaths') or [None])[0] or os.getcwd()
    candidates = []
    if match:
        candidates.append(os.path.join(cwd, match.group(1)) if not os.path.isabs(match.group(1)) else match.group(1))
    if os.environ.get('DBT_PROFILES_DIR'):
        candidates.append(os.environ['DBT_PROFILES_DIR'])
    candidates += [cwd, os.path.join(os.path.expanduser('~'), '.dbt')]
    for directory in candidates:
        path = os.path.join(directory, 'profiles.yml')
        try:
            with open(path, encoding='utf-8') as handle:
                text = handle.read()
        except OSError:
            continue
        # Lecture minimale sans PyYAML : les lignes `target: <nom>` indentées d'un niveau sous un profil.
        for found in re.findall(r'^[ \t]+target:[ \t]*[\'"]?([A-Za-z0-9_-]+)', text, re.M):
            if found.lower() in targets:
                return _Hit(found + ' (target par défaut de ' + path + ')')
        return None
    return None

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

SHELL_TOOLS = ('run_shell_command', 'run_command', 'shell', 'local_shell', 'exec_command', 'unified_exec', 'container.exec', 'Bash')

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print('{}')
        return
    # Trois formes d'entrée : Gemini CLI (tool_name / tool_input.command), Antigravity (toolCall.name / toolCall.args.CommandLine),
    # Codex (hook_event_name PreToolUse, tool_name / tool_input.command en chaîne ou en liste).
    call = payload.get('toolCall') or {}
    tool = payload.get('tool_name') or call.get('name')
    if tool not in SHELL_TOOLS:
        print('{}')
        return
    args = payload.get('tool_input') or call.get('args') or {}
    if not isinstance(args, dict):
        args = {'command': args}
    command = as_text(args.get('command') or args.get('cmd') or args.get('CommandLine'))
    # `dbt`, `./dbt`, `/chemin/dbt`, `dbt.exe`, toute casse (systèmes de fichiers insensibles à la casse).
    if not re.search(r'(^|[\s;&|/\\])dbt(\.exe)?(\s|$)', command, re.I):
        print('{}')
        return
    targets = [t.strip().lower() for t in os.environ.get('AI_KIT_PROD_TARGETS', 'prod,production,prd').split(',') if t.strip()]
    alternation = '|'.join(re.escape(t) for t in targets)
    # --target prod, --target=prod, -t prod, -tprod, guillemets simples ou doubles autour de la valeur.
    hits = (re.search(r'(?:--target|-t)(?:[\s=]+|(?<=-t))[\'"]?(' + alternation + r')[\'"]?(?![\w-])', command, re.I)
            or re.search(r'\bDBT_TARGET=[\'"]?(' + alternation + r')[\'"]?(?![\w-])', command, re.I))
    if not hits:
        hits = default_target_hit(command, targets, payload)
    if not hits:
        print('{}')
        return
    if os.environ.get('AI_KIT_ALLOW_PROD') == '1':
        print(json.dumps({'systemMessage': 'ai-kit : commande dbt sur un target de production autorisée par AI_KIT_ALLOW_PROD=1.'}))
        return
    print(json.dumps(deny_output(payload, 'Refusé par le kit : commande dbt sur le target de production « ' + hits.group(1) + ' ». Utiliser le target de développement déclaré dans AGENTS.md. Une personne autorisée peut exporter AI_KIT_ALLOW_PROD=1 pour cette session.'), ensure_ascii=False))

if __name__ == '__main__':
    main()
