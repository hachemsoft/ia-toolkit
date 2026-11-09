"""Is NEWS.md well formed? The whats-new hook skips a section it cannot read; this check refuses it before the merge.

Usage: python3 scripts/check_news.py [path to NEWS.md]
Each entry: `## <YYYY-MM-DD> <id> : <title>` (id: 3 to 32 of a-z, 0-9, -; unique), then optional lines `teams: x`
(AI Kit 2 has no profiles: a profiles: line is refused), `teams: x` (teams of organization.toml or practices/20-<team>.md), `until: YYYY-MM-DD`, then
the text. Exit code 1 with one line per problem, 0 otherwise. No network, no model call.
"""
import importlib.util
import os
import re
import sys
from datetime import date

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, ROOT)
from installer.settings import profile_ids, team_ids  # noqa: E402

META_LINE = re.compile(r'^([a-z_]+):\s')


def hook_module():
    spec = importlib.util.spec_from_file_location('ai_kit_whats_new', os.path.join(ROOT, 'runtime', 'hooks', 'whats-new.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_date(text):
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def problems(text, profiles, teams):
    hook = hook_module()
    found, seen = [], set()
    lines = text.splitlines()
    for number, line in enumerate(lines, 1):
        if line.startswith('## ') and not hook.HEADING.match(line):
            found.append('line '+str(number)+': a heading must be "## <YYYY-MM-DD> <id> : <title>" (id: 3 to 32 of a-z, 0-9, -): '+line)
        elif hook.HEADING.match(line):
            # Metadata lines right after the heading: only the three keys the hook reads.
            for following in lines[number:]:
                if not following.strip():
                    break
                key = META_LINE.match(following)
                if key and key.group(1) not in ('profiles', 'teams', 'until'):
                    found.append('line '+str(number)+': unknown metadata "'+key.group(1)+'" (profiles, teams, until)')
                elif not key:
                    break
    current = None
    for number, line in enumerate(lines, 1):
        if hook.HEADING.match(line):
            current = hook.HEADING.match(line).group(2)
        elif line.startswith('## '):
            current = None
        elif line.startswith('# ') and current:
            found.append('line '+str(number)+': entry '+current+': a "# " heading inside the entry cuts its text (use ### or plain text)')
    for entry in hook.parse_news(text):
        where = 'entry '+entry['id']+': '
        if entry['id'] in seen:
            found.append(where+'id used twice')
        seen.add(entry['id'])
        if not valid_date(entry['date']):
            found.append(where+'invalid date '+entry['date'])
        if entry['until'] and not valid_date(entry['until']):
            found.append(where+'invalid until date '+entry['until'])
        for profile in entry['profiles']:
            if profile not in profiles:
                found.append(where+'unknown profile '+profile+' (profiles: '+', '.join(profiles)+')')
        for team in entry['teams']:
            if team not in teams:
                found.append(where+'unknown team '+team+(' (teams: '+', '.join(teams)+')' if teams else ' (no team declared)'))
        if not entry['text']:
            found.append(where+'no text')
    return found


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = argv[0] if argv else os.path.join(ROOT, 'NEWS.md')
    try:
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
    except OSError as exc:
        print('Cannot read '+path+': '+str(exc))
        return 1
    found = problems(text, profile_ids(), team_ids())
    for line in found:
        print(line)
    if found:
        return 1
    print(os.path.basename(path)+': '+str(len(hook_module().parse_news(text)))+' entries, well formed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
