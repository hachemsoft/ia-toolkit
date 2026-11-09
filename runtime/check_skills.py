"""Checks what a skill, an agent or a command carries before it is merged: patterns an agent must never be told to
follow, secrets, and scripts nobody declared. Detection, not a sandbox: it finds the obvious forms; review (CODEOWNERS)
and the CLIs' permissions and managed settings remain the barrier.

Usage: python3 runtime/check_skills.py                     the kit's skills/, agents/ and commands/
       python3 runtime/check_skills.py <path>... [--allow <file>]...
A project repo runs it on its own skills from a checkout of the kit at a tag:
       python3 <kit>/runtime/check_skills.py .agents/skills
Exit code 1 when something is found, with file:line, the rule and why.
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT_PATHS = ('skills', 'agents', 'commands')
# The scripts the kit ships inside skills, reviewed: templates a skill copies, never run by the kit itself.
KIT_ALLOWED = ('skills/internal/common/manual-steps/template.sh', 'skills/internal/common/diagnosing-bugs/scripts/hitl-loop.template.sh')
TEXT = {'.md', '.txt', '.json', '.toml', '.yaml', '.yml'}

RULES = (
    ('pipe-to-shell', re.compile(r'\b(?:curl|wget)\b[^\n|`]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b'
                                 r'|\b(?:iwr|irm|Invoke-WebRequest|Invoke-RestMethod)\b[^\n|`]*\|\s*iex\b', re.I),
     'downloads and runs code in one step: nobody reviews what runs'),
    ('prompt-injection', re.compile(r'\b(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+)?(?:of\s+)?(?:the\s+|your\s+)?'
                                    r'(?:previous|prior|above|earlier|system)\s+(?:instructions|rules|prompts?|messages?)\b', re.I),
     'asks the agent to drop the instructions it was given'),
    ('permission-bypass', re.compile(r'--dangerously-skip-permissions|--yolo\b|\bbypassPermissions\b|danger-full-access'
                                     r'|approval[_-]?polic(?:y|ies)\s*=\s*"?never', re.I),
     'starts the agent without confirmations or sandbox'),
    ('guardrail-off', re.compile(r'\b(?:disable|turn\s+off|switch\s+off|bypass|deactivate)\s+(?:the\s+|a\s+|all\s+|every\s+)?'
                                 r'(?:kit\'?s?\s+)?(?:guardrails?|protected-paths|dbt-prod-guard|sandbox)\b', re.I),
     'tells the agent to remove a guardrail; only the person turns one off, in aikit.toml'),
    ('config-write', re.compile(r'\b(?:write|edit|modify|change|append|overwrite)\b[^\n]{0,40}(?:~|\$HOME|%USERPROFILE%)[/\\]'
                                r'(?:\.claude[/\\]settings\.json|\.claude\.json|\.codex[/\\]config\.toml|\.gemini[/\\]settings\.json'
                                r'|\.ai-kit[/\\](?:overrides\.toml|state\.json|hooks))', re.I),
     'tells the agent to change the kit\'s or a CLI\'s configuration (ADR 0006)'),
)


def secret_pattern():
    """The kit's one list of secret forms (runtime/friction.py), so a token caught in a friction is caught here too."""
    spec = importlib.util.spec_from_file_location('ai_kit_friction', ROOT/'runtime'/'friction.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SECRET


def scan_text(path, text, secret):
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        for rule, pattern, why in RULES:
            if pattern.search(line):
                found.append((path, number, rule, why))
        if secret.search(line):
            found.append((path, number, 'secret', 'a key, token or password written in clear; use ${VARIABLE}'))
    return found


def scan(paths, allowed):
    secret = secret_pattern()
    found = []
    for base in paths:
        files = [base] if base.is_file() else sorted(p for p in base.rglob('*') if p.is_file())
        for path in files:
            if path.name.startswith('.') or path.name.startswith('LICENSE'):
                continue
            listed = path.resolve() in allowed
            if path.suffix.lower() not in TEXT and not listed:
                found.append((path, 0, 'undeclared-file', 'a script or binary in a skill can run anything: review it, then list it with --allow'))
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            found += scan_text(path, text, secret)
    return found


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    paths, allowed, i = [], set(), 0
    while i < len(argv):
        if argv[i] == '--allow' and i + 1 < len(argv):
            allowed.add(Path(argv[i + 1]).resolve())
            i += 2
            continue
        paths.append(Path(argv[i]))
        i += 1
    if not paths:
        paths = [ROOT/p for p in KIT_PATHS]
        allowed |= {(ROOT/p).resolve() for p in KIT_ALLOWED}
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print('Not found: '+', '.join(missing))
        return 2
    found = scan(paths, allowed)
    for path, line, rule, why in found:
        print(f'{path}:{line}: {rule}: {why}' if line else f'{path}: {rule}: {why}')
    print('Skills check: '+(str(len(found))+' finding(s).' if found else 'nothing found.'))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
