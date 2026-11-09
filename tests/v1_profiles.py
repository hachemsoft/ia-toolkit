"""The six V1 profiles, frozen (AI Kit 3 has no profiles, ADR 0018). Tests that described a job by its profile now give
the same resources as personal choices, the way the migration carries them over: what the Core default lacks becomes
extra_skills, extra_agents and extra_commands."""
import json
from pathlib import Path

PROFILES = json.loads((Path(__file__).resolve().parent/'fixtures/v1-profiles.json').read_text(encoding='utf-8'))


def choices_for(role):
    """The extra_* choices that give a V1 profile's resources on top of the Core default (general gives none)."""
    if role in (None, 'general', 'core'):
        return None
    from installer.settings import core_selection
    core, profile = core_selection(), PROFILES[role]
    found = {'extra_skills': [s for s in profile['skills'] if s not in core['skills']],
             'extra_agents': [a for a in profile['agents'] if a not in core['agents']],
             'extra_commands': [c for c in profile.get('commands') or [] if c not in core['commands']]}
    if 'commands' not in profile:  # a V1 profile without a list installed every command whose skills it had
        from installer.core import load_commands
        found['extra_commands'] = [c['name'] for c in load_commands() if c['name'] not in core['commands']
                                   and all(s in profile['skills'] for s in c['skills'])]
    return {k: v for k, v in found.items() if v} or None


def apply_as(role, home, *args, **kwargs):
    """installer.cli.apply with a V1 profile's resources as personal choices."""
    from installer.cli import apply
    from installer.settings import personal_settings
    choices = choices_for(role)
    if choices:
        mine = personal_settings(Path(home)/'.ai-kit')  # the person's own lists stay: the role's resources are added to them
        merged = {k: list(mine.get(k, [])) + [n for n in v if n not in mine.get(k, [])] for k, v in choices.items()}
        kwargs['choices'] = {**merged, **(kwargs.get('choices') or {})}
    return apply(role, home, *args, **kwargs)
