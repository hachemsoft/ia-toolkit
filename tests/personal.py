"""Test helper: the person's settings written as ~/.ai-kit/aikit.toml (AI Kit 3), from a dict in the engine's vocabulary
(extra_skills, disabled_*, skill_prefix, hooks, mcp {name: true/false}, frictions, share_frictions, parallel_agents)."""
from pathlib import Path

from installer.toml_files import dump_toml

LISTS = ('extra_skills', 'disabled_skills', 'extra_commands', 'disabled_commands', 'extra_agents', 'disabled_agents')


def aikit_data(settings):
    data = {'schema': 1}
    user = {k: list(v) for k, v in settings.items() if k in LISTS}
    if 'skill_prefix' in settings:
        user['skill_prefix'] = settings['skill_prefix']
    if user:
        data['user'] = user
    if settings.get('hooks'):
        data['hooks'] = dict(settings['hooks'])
    mcp = settings.get('mcp') or {}
    if mcp:
        if any(not isinstance(v, bool) for v in mcp.values()):
            raise ValueError('AI Kit 3: a personal MCP server definition is not supported; use the Core or a Team')
        data['mcp'] = {k: v for k, v in (('enabled', sorted(n for n, v in mcp.items() if v)), ('denied', sorted(n for n, v in mcp.items() if not v))) if v}
    frictions = {}
    if 'frictions' in settings:
        frictions['capture'] = settings['frictions']
    if settings.get('share_frictions') is False:
        frictions['publication'] = 'disabled'
    if frictions:
        data['frictions'] = frictions
    if 'parallel_agents' in settings:
        data['agents'] = {'parallel': settings['parallel_agents']}
    unknown = set(settings) - set(LISTS) - {'skill_prefix', 'hooks', 'mcp', 'frictions', 'share_frictions', 'parallel_agents'}
    if unknown:
        raise ValueError('not an AI Kit 3 setting: '+', '.join(sorted(unknown)))
    return data


def write_personal(home, settings):
    """~/.ai-kit/aikit.toml for these settings; returns its path."""
    path = Path(home)/'.ai-kit'/'aikit.toml'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_toml(aikit_data(settings)), encoding='utf-8')
    return path
