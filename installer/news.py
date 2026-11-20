"""NEWS.md of a Core: the rule the whats-new hook reads it by (problems, also run by scripts/check_news.py in CI) and
`ai-kit news --add`, which writes one entry and keeps it only when that rule still holds (4.19.0). Nothing is committed,
tagged or sent: the entry reaches workstations with the Core's next tag and their `ai-kit sync`."""
from datetime import date
import importlib.util
import re
import unicodedata
from pathlib import Path

from .core import ROOT, KitError

MAX_TEXT = 1500  # the session-start text is capped (whats-new CONTEXT_LIMIT, 8000) and shared with the CHANGELOG section
META_LINE = re.compile(r'^([a-z_]+):\s')
TEAM_NAME = re.compile(r'[A-Za-z0-9._-]{1,64}')
ID = re.compile(r'[a-z0-9-]{3,32}')
NEXT_STEPS = ('Next: review the text (it reaches every agent\'s context), open a merge request on the Core, then tag vX.Y.Z '
              'after the merge; workstations get it at their next ai-kit sync.')


def hook_module():
    """The whats-new hook itself, so that the check reads NEWS.md exactly as the hook will."""
    spec = importlib.util.spec_from_file_location('ai_kit_whats_new', ROOT/'runtime'/'hooks'/'whats-new.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_date(text):
    try:
        date.fromisoformat(text)
        return bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', text))
    except ValueError:
        return False


def problems(text):
    """One line per problem the whats-new hook would trip on (a section skipped, cut or doubled); [] when it reads in full."""
    hook = hook_module()
    found, seen = [], set()
    lines = text.splitlines()
    for number, line in enumerate(lines, 1):
        if line.startswith('## ') and not hook.HEADING.match(line):
            found.append('line '+str(number)+': a heading must be "## <YYYY-MM-DD> <id> : <title>" (id: 3 to 32 of a-z, 0-9, -): '+line)
        elif hook.HEADING.match(line):
            # Metadata lines right after the heading: only the keys the hook reads.
            for following in lines[number:]:
                if not following.strip():
                    break
                key = META_LINE.match(following)
                if key and key.group(1) not in ('teams', 'until'):
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
        if not entry['text']:
            found.append(where+'no text')
    return found


def slug(title):
    """An entry id from a title: ASCII lower case, a-z 0-9 and -, at most 32 characters."""
    ascii_title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+', '-', ascii_title).strip('-')[:32].rstrip('-')


def entry_text(day, entry_id, title, text, teams, until, newline):
    lines = ['## '+day+' '+entry_id+' : '+title]
    if teams:
        lines.append('teams: '+', '.join(teams))
    if until:
        lines.append('until: '+until)
    return newline.join(lines + [''] + text.splitlines() + ['', ''])


def refuse_inputs(title, text, teams, until, entry_id, today):
    if not title.strip() or '\n' in title or '\r' in title:
        raise KitError('The title is one line, not empty.')
    if not text.strip():
        raise KitError('The text is empty.')
    if len(text) > MAX_TEXT:
        raise KitError('The text has '+str(len(text))+' characters; at most '+str(MAX_TEXT)+': the session-start announcements share a small budget.')
    for line in text.splitlines():
        if line.startswith('# ') or line.startswith('## '):
            raise KitError('A text line starts with "# " or "## ", which would cut the entry or start another one: use ### or plain text.')
    for team in teams:
        if not TEAM_NAME.fullmatch(team):
            raise KitError('Team name not accepted: '+repr(team)+' (letters, digits, ".", "_", "-").')
    if until is not None:
        if not valid_date(until):
            raise KitError('Invalid until date '+until+': YYYY-MM-DD.')
        if until < today:
            raise KitError('The until date '+until+' is already past: the entry would never show.')
    if not ID.fullmatch(entry_id):
        raise KitError('No usable id from this title ('+repr(entry_id)+'): give one with --id (3 to 32 of a-z, 0-9, -).')


def core_news_file(path, home):
    """NEWS.md of a Core repository: the folder holds NEWS.md and aikit.toml, and is not under ~/.ai-kit (the kit's own copies)."""
    folder = Path(path).expanduser().resolve()
    if folder.is_relative_to((Path(home)/'.ai-kit').resolve()):
        raise KitError('Refused: '+str(folder)+' is under ~/.ai-kit, the kit\'s own copies; write in your Core repository instead.')
    if not (folder/'aikit.toml').is_file() or not (folder/'NEWS.md').is_file():
        raise KitError('Not a Core repository: '+str(folder)+' needs NEWS.md and aikit.toml (give it with --path).')
    return folder/'NEWS.md'


def add_entry(path, title, text, id=None, teams=(), until=None, today=None, home=None):
    """Writes the entry before the first one of the Core's NEWS.md, then keeps it only when the file still reads in full
    (problems); otherwise the file is put back as it was. Returns (entry id, NEWS.md path)."""
    today = today or date.today().isoformat()
    home = home or Path.home()
    entry_id = id or slug(title)
    teams = [t.strip() for t in teams if t.strip()]
    title, text = title.strip(), text.strip('\n').rstrip()
    refuse_inputs(title, text, teams, until, entry_id, today)
    news_file = core_news_file(path, home)
    original = news_file.read_bytes()
    current = original.decode('utf-8-sig')
    if any(e['id'] == entry_id for e in hook_module().parse_news(current)):
        raise KitError('The id '+entry_id+' is already used in '+str(news_file)+': give another one with --id.')
    newline = '\r\n' if '\r\n' in current else '\n'
    entry = entry_text(today, entry_id, title, text, teams, until, newline)
    first = re.search(r'^## ', current, re.MULTILINE)
    if first:
        updated = current[:first.start()] + entry + current[first.start():]
    else:
        updated = current.rstrip('\r\n') + newline*2 + entry.rstrip('\r\n') + newline
    bom = original.startswith(b'\xef\xbb\xbf')
    news_file.write_bytes((b'\xef\xbb\xbf' if bom else b'') + updated.encode('utf-8'))
    found = problems(updated)
    if found or not any(e['id'] == entry_id for e in hook_module().parse_news(updated)):
        news_file.write_bytes(original)
        raise KitError('NEWS.md would not read in full, put back as it was:\n'+'\n'.join(found or ['the new entry is not read back']))
    return entry_id, news_file
