"""managed-settings: the files IT deploys so that the kit's guardrails hold whatever a person or an agent changes on the
workstation. Generated from organization.toml; nothing is installed, nothing outside the output folder is written."""
import json
from pathlib import Path

from .core import ROOT, KitError, read_json
from .settings import organization

# Written by an agent, these would switch a guardrail off or change what every session loads. 30_USER.md and
# ~/.ai-kit/learning stay writable: /me and /learn write there.
KIT_FILES = ('~/.ai-kit/overrides.toml', '~/.ai-kit/state.json', '~/.ai-kit/hooks/**', '~/.ai-kit/bin/**', '~/.ai-kit/backups/**',
             '~/.ai-kit/runtime/**', '~/.ai-kit/schemas/**', '~/.ai-kit/context/00_*', '~/.ai-kit/context/10_*', '~/.ai-kit/context/20_*')
CLAUDE_FILES = ('~/.claude/settings.json', '~/.claude/CLAUDE.md', '~/.claude/agents/ai-kit-*', '~/.claude/skills/ai-kit-*/**', '~/.claude.json')
POSIX_PYTHON = '"$HOME/.ai-kit/runtime/venv/bin/python"'
POSIX_HOOKS = '"$HOME/.ai-kit/hooks/'


def locked(org, manifest):
    """The guardrails to enforce: those the organization locks, or every guardrail on by default when it locks none."""
    names = org.get('locked_hooks') or [n for n, spec in manifest.items() if spec.get('default')]
    unknown = [n for n in names if n not in manifest]
    if unknown:
        raise KitError('organization.toml locked_hooks: unknown guardrail '+', '.join(unknown)+' (known: '+', '.join(sorted(manifest))+').')
    return names


def command(spec):
    return POSIX_PYTHON+' -I '+POSIX_HOOKS+spec['script']+'"'


def claude(names, manifest, hooks_only):
    from .adapters.claude import hook_matcher
    settings = {'permissions': {'deny': ['Edit('+p+')' for p in KIT_FILES + CLAUDE_FILES]},
                'hooks': {'PreToolUse': [{'matcher': hook_matcher(manifest[n]['matcher']),
                                          'hooks': [{'type': 'command', 'command': command(manifest[n]), 'timeout': 20}]} for n in names]}}
    if hooks_only:
        settings['allowManagedHooksOnly'] = True
    return json.dumps(settings, indent=2)+'\n'


def gemini(names, manifest):
    settings = {'hooks': {}, 'security': {'disableYoloMode': True}}
    for n in names:
        spec = manifest[n]
        settings['hooks'].setdefault(spec['event'], []).append(
            {'matcher': spec['matcher'], 'hooks': [{'name': 'ai-kit-'+n, 'type': 'command', 'command': command(spec)}]})
    return json.dumps(settings, indent=2)+'\n'


def codex():
    return ('# Codex CLI requirements: the agent writes only inside the repo it works in (so never to ~/.codex or ~/.ai-kit),\n'
            '# and the person cannot start it without a sandbox or without approvals.\n'
            'allowed_sandbox_modes = ["read-only", "workspace-write"]\n'
            'allowed_approval_policies = ["untrusted", "on-request"]\n')




def managed_settings(out, hooks_only=False):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise KitError(str(out)+' is not empty: give a new folder, nothing is overwritten.')
    manifest = read_json(ROOT/'runtime'/'hooks'/'hooks.json')['hooks']
    names = locked(organization(), manifest)
    files = {'claude-code/managed-settings.json': claude(names, manifest, hooks_only),
             'gemini-cli/settings.json': gemini(names, manifest),
             'codex/requirements.toml': codex(),
             'README.txt': (ROOT/'templates'/'managed-settings-README.txt').read_text(encoding='utf-8').format(version=(ROOT/'VERSION').read_text(encoding='utf-8').strip(), hooks=', '.join(names),
                                         hooks_only=' With allowManagedHooksOnly, hooks from any other source are ignored.' if hooks_only else '')}
    for rel, text in files.items():
        path = out/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    print('Managed settings written to '+str(out)+' ('+', '.join(sorted(files))+'). Where to deploy them: README.txt.')
    return 0
