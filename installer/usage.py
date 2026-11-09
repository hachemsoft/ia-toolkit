"""usage: what the CLIs' own logs show about the kit, locally; nothing is sent."""
import json
import re
from types import SimpleNamespace
from datetime import datetime, timezone

from . import resolve
from .core import (content_root, ROOT, KitError, read_json, json_bytes, load_commands, _ts, friction_id, fixed_frictions)
from .adapters import ADAPTERS
from .interface import ContextHost


def usage(home, since_days=42, as_json=None, min_sessions=10, min_prompts=50):
    """Usage report for the usage review (docs/usage-review.md): commands typed, skills activated, agents called, from the logs each CLI already writes."""
    from collections import Counter
    state = read_json(home/'.ai-kit/state.json')
    if not state:
        raise KitError('Kit not installed: run ai-kit init.')
    catalog = resolve.skill_catalog(content_root())
    installed = state.get('installed') or next(a for a in ADAPTERS if isinstance(a, ContextHost)).installed_from_files(state)
    installed_skills, installed_commands, installed_agents = (sorted(installed.get(k, [])) for k in ('skills', 'commands', 'agents'))
    cutoff = datetime.now(timezone.utc).timestamp() - since_days*86400
    c = count_events(home, state, installed_skills, installed_commands, installed_agents, cutoff)
    commands, skills, agents, sessions_by = c.commands, c.skills, c.agents, c.sessions_by
    sessions, prompts = len(c.sessions_seen), c.prompts
    # What the logs can show: a skill or an agent counts as unused only when every session of the window comes from a CLI
    # whose logs show it; otherwise its absence proves nothing and nothing is recommended about it.
    used_clis = [a for a in ADAPTERS if sessions_by[a.NAME]]
    def measurable(kind):
        return bool(used_clis) and all(kind in a.OBSERVES for a in used_clis)
    def observing(kind):
        return [a.LABEL for a in ADAPTERS if kind in a.OBSERVES]
    unused_commands = [c for c in installed_commands if commands[c] == 0]
    skill_names = [s for s in installed_skills if s not in installed_commands]  # a skill named after a command is measured by the command
    unused_skills = [s for s in skill_names if skills[s] == 0] if measurable('skill') else []
    unused_agents = [a for a in installed_agents if agents[a] == 0] if measurable('agent') else []
    not_observable = {kind: names for kind, names in (('skills', skill_names), ('agents', installed_agents)) if not measurable(kind[:-1])}
    required_by_used = required_by(commands, skills, catalog)
    def core_candidates():
        out = []
        for s in unused_skills:
            entry = catalog.get(s, {})
            if entry.get('tier') == 'core' and s not in required_by_used and entry.get('category') in ('workflow','tool'):
                out.append(s)
        return out
    frictions, fixed_own = read_frictions(home, cutoff)
    frictions_by_category = Counter(str(f.get('category')) for f in frictions)
    enough = sessions >= min_sessions and prompts >= min_prompts
    report = {'window_days': since_days, 'sessions': sessions, 'prompts': prompts, 'errors': c.errors, 'unreadable_logs': c.unread,
              'sessions_with_the_kit': len(c.kit_sessions),
              'sessions_by_cli': {name: len(s) for name, s in sessions_by.items() if s},
              'observed_by': {kind: observing(kind) for kind in ('prompt', 'skill', 'agent')},
              'not_observable': not_observable,
              'commands': dict(commands), 'skills': dict(skills), 'agents': dict(agents),
              'unused_commands': unused_commands, 'unused_skills': unused_skills, 'unused_agents': unused_agents,
              'core_candidates_to_demote': core_candidates() if enough and measurable('skill') else [], 'enough_data': enough,
              'frictions': frictions, 'frictions_by_category': dict(frictions_by_category),
              'unknown_commands': dict(c.unknown_commands), 'repeated_prompts': c.repeated, 'frictions_fixed': fixed_own}
    print_report(report, c, not_observable, used_clis, observing, min_sessions, min_prompts)
    if as_json:
        as_json.write_text(json_bytes(report).decode('utf-8'), encoding='utf-8')
    return 0


def count_events(home, state, installed_skills, installed_commands, installed_agents, cutoff):
    """What the CLIs' logs show over the window, from the neutral events each adapter returns (prompt, skill, agent, error)."""
    from collections import Counter
    commands, skills, agents = Counter(), Counter(), Counter()
    unknown_commands = Counter()
    repeated = errors = prompts = 0
    sessions_seen, seen_texts = set(), {}
    sessions_by, prompts_by = {a.NAME: set() for a in ADAPTERS}, {a.NAME: 0 for a in ADAPTERS}
    # Each adapter reads its CLI's logs and returns neutral events (prompt, skill, agent, error).
    unread = []  # CLIs whose logs exist but gave no event at all: their format probably changed
    kit_sessions = set()  # sessions where the kit did something: a kit command typed, a kit skill or agent activated
    for adapter in ADAPTERS:
        recognised = 0
        for event in adapter.history(home, state):
            recognised += 1
            if event.get('ts', 0) < cutoff:
                continue
            session = event.get('session')
            if session:
                sessions_seen.add(session)
                sessions_by[adapter.NAME].add(session)
            if event['kind'] == 'prompt':
                prompts_by[adapter.NAME] += 1
            kind = event['kind']
            if kind == 'error':
                errors += 1
            elif kind == 'skill':
                skills[event['name']] += 1
                if event['name'] in installed_skills:
                    kit_sessions.add(session)
            elif kind == 'agent':
                agents[event['name']] += 1
                if event['name'] in installed_agents:
                    kit_sessions.add(session)
            elif kind == 'prompt':
                prompts += 1
                shown = event['text']
                match = re.match(r'^[$/]([a-z][a-z0-9:-]*)', shown)
                if match:
                    if match.group(1) in installed_commands:
                        commands[match.group(1)] += 1
                        kit_sessions.add(session)
                    elif not any(match.group(1) in a.BUILTIN_COMMANDS for a in ADAPTERS):
                        unknown_commands[match.group(1)] += 1
                text = ' '.join(shown.split()).lower()
                if len(text) >= 15:
                    seen = seen_texts.setdefault(session, set())
                    if text in seen:
                        repeated += 1
                    seen.add(text)
        chosen = adapter.NAME in (state.get('targets') or (state.get('installed') or {}).get('clis') or [])
        if chosen and not recognised and any(next(home.glob(pattern), None) for pattern in getattr(adapter, 'LOGS', ())):
            unread.append(adapter.LABEL)
    kit_sessions.discard(None)
    return SimpleNamespace(commands=commands, skills=skills, agents=agents, unknown_commands=unknown_commands,
                           repeated=repeated, errors=errors, prompts=prompts, sessions_seen=sessions_seen,
                           sessions_by=sessions_by, unread=unread, kit_sessions=kit_sessions)


def required_by(commands, skills, catalog):
    """Skills a typed command or an activated skill needs, dependencies of the catalog followed."""
    by_name = {c['name']: c for c in load_commands()}
    required_by_used = set(skills)
    for name in commands:
        required_by_used.update(by_name.get(name, {}).get('skills', []))
    frontier = list(required_by_used)
    while frontier:
        for dependency in catalog.get(frontier.pop(), {}).get('requires', []):
            if dependency not in required_by_used:
                required_by_used.add(dependency)
                frontier.append(dependency)
    return required_by_used


def read_frictions(home, cutoff):
    """Frictions logged by /friction within the window (~/.ai-kit/frictions.jsonl), and those of this person a released
    version says it fixed: "(frictions: a1b2c3, …)" in the kit's CHANGELOG."""
    frictions, own_ids = [], []
    frictions_file = home/'.ai-kit/frictions.jsonl'
    if frictions_file.is_file():
        for line in frictions_file.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            entry['id'] = entry.get('id') or friction_id(entry.get('ts'), entry.get('text'))  # lines written before ids existed
            own_ids.append(entry['id'])
            if _ts(entry.get('ts')) >= cutoff:
                frictions.append({k: entry.get(k) for k in ('id', 'ts', 'category', 'command', 'text', 'cli', 'os', 'kit', 'profile', 'source') if entry.get(k) is not None})
    # Frictions of this person that a released version says it fixed: "(frictions: a1b2c3, …)" in the kit's CHANGELOG.
    changelog = ROOT/'CHANGELOG.md'
    fixed = fixed_frictions(changelog.read_text(encoding='utf-8')) if changelog.is_file() else {}
    fixed_own = {fid: fixed[fid] for fid in own_ids if fid in fixed}
    return frictions, fixed_own


def print_report(report, c, not_observable, used_clis, observing, min_sessions, min_prompts):
    """The report as the person reads it; the same figures as the JSON."""
    since_days, sessions, prompts, errors = report['window_days'], report['sessions'], report['prompts'], report['errors']
    commands, skills, agents, unknown_commands = c.commands, c.skills, c.agents, c.unknown_commands
    kit_sessions, unread, repeated = c.kit_sessions, c.unread, c.repeated
    unused_commands, unused_skills, unused_agents = report['unused_commands'], report['unused_skills'], report['unused_agents']
    frictions, frictions_by_category, fixed_own = report['frictions'], report['frictions_by_category'], report['frictions_fixed']
    enough = report['enough_data']
    print('Window: '+str(since_days)+' days | '+str(sessions)+' sessions | '+str(prompts)+' prompts | '+str(errors)+' errors'
          + (' | the kit used in '+str(len(kit_sessions))+' of them ('+str(round(100*len(kit_sessions)/sessions))+' %)' if sessions else ''))
    for label in unread:
        print('[Check] '+label+': its logs exist but nothing in them was recognised; their format may have changed with a new version of the CLI, so its counts are missing here (versions checked: docs/cli/matrice.md).')
    print('Commands typed: '+(', '.join(k+' ×'+str(v) for k,v in commands.most_common()) or 'none'))
    print('Skills activated: '+(', '.join(k+' ×'+str(v) for k,v in skills.most_common()) or 'none'))
    print('Agents called: '+(', '.join(k+' ×'+str(v) for k,v in agents.most_common()) or 'none'))
    print('Never used: '+str(len(unused_commands))+' commands'+('' if 'skills' in not_observable else ', '+str(len(unused_skills))+' skills')
          + ('' if 'agents' in not_observable else ', '+str(len(unused_agents))+' agents')+'.')
    if not used_clis:
        print('No session in the window: skills and agents not measurable.')
    for kind in not_observable if used_clis else ():
        print('Not observable: '+kind+' activations do not appear in the logs of '+', '.join(a.LABEL for a in used_clis if kind[:-1] not in a.OBSERVES)
              + (' (only in '+', '.join(observing(kind[:-1]))+'\'s)' if observing(kind[:-1]) else '')+'; no recommendation about '+kind+'.')
    print('Unknown commands typed: '+(', '.join('/'+k+' ×'+str(v) for k,v in unknown_commands.most_common()) or 'none')+' | requests repeated within one session: '+str(repeated))
    if fixed_own:
        print('Your frictions fixed by the kit: '+', '.join(fid+' in '+str(version) for fid, version in fixed_own.items()))
    print('Frictions logged: '+str(len(frictions))+(' ('+', '.join(k+' ×'+str(v) for k,v in sorted(frictions_by_category.items(), key=lambda kv: -kv[1]))+')' if frictions else '')+'; /friction to log one.')
    if not enough:
        print('Not enough data to recommend (threshold: '+str(min_sessions)+' sessions and '+str(min_prompts)+' prompts in the window; --min-sessions and --min-prompts to adjust it). No recommendation.')
    elif report['core_candidates_to_demote']:
        print('Candidates to remove from the core (never activated, not required by a used command): '+', '.join(report['core_candidates_to_demote']))
    else:
        print('No core skill to remove over this window.')
    print('Procedure: docs/usage-review.md. The logs read are local; nothing is sent.')
