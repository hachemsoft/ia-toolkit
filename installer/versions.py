"""Versions of the kit's skills and agents. Each one carries a version in its catalog (semver: patch for a wording, minor
for a behaviour added, major when what it produces or needs changes); versions.lock.json records each version with a
digest of the content. A content changed under the same version is refused by the tests: the lock cannot be updated
until the version is raised."""
import hashlib
import json
import re

from .core import ROOT, KitError, inside, read_json

LOCK = ROOT/'versions.lock.json'
SEMVER = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')
CATALOGS = (('skills', 'skills/catalog.json'), ('agents', 'agents/catalog.json'))


def parse(version):
    match = SEMVER.fullmatch(str(version))
    return tuple(int(part) for part in match.groups()) if match else None


def content_digest(path):
    """Digest of a skill folder (every file, by relative path) or of an agent file, line endings normalised: a Windows
    checkout (CRLF) gives the same digest."""
    digest = hashlib.sha256()
    # Sorted on the relative path as text: Windows compares Path objects case-insensitively, which changes the order.
    files = sorted((p for p in path.rglob('*') if p.is_file()), key=lambda p: p.relative_to(path).as_posix()) if path.is_dir() else [path]
    for file in files:
        rel = file.relative_to(path).as_posix() if path.is_dir() else file.name
        digest.update(rel.encode('utf-8') + b'\0' + file.read_bytes().replace(b'\r\n', b'\n') + b'\0')
    return digest.hexdigest()[:16]


def catalog_versions():
    """{kind: {name: version}} from the catalogs (entries with a path; a skill replaced_by another has none)."""
    return {kind: {name: entry.get('version') for name, entry in read_json(ROOT/rel).items() if 'path' in entry}
            for kind, rel in CATALOGS}


def current():
    """{kind: {name: {version, digest}}} for the kit as it is now."""
    result = {}
    for kind, rel in CATALOGS:
        entries = {}
        for name, entry in read_json(ROOT/rel).items():
            if 'path' in entry:
                entries[name] = {'version': entry.get('version'), 'digest': content_digest(inside(ROOT, entry['path']))}
        result[kind] = entries
    return result


def problems(lock=None):
    """What stops the lock from being written: a missing or invalid version, a content changed under the same version,
    a version going down."""
    lock = read_json(LOCK) if lock is None else lock
    found = []
    for kind, entries in current().items():
        for name, now in sorted(entries.items()):
            label = kind[:-1] + ' ' + name
            if parse(now['version']) is None:
                found.append(label + ': "version" missing or not like 1.2.3 in ' + dict(CATALOGS)[kind] + '.')
                continue
            before = lock.get(kind, {}).get(name)
            if not before:
                continue
            if now['digest'] != before['digest'] and now['version'] == before['version']:
                found.append(label + ' changed, still ' + now['version'] + ': raise its version in ' + dict(CATALOGS)[kind]
                             + ' (patch for a wording, minor for a behaviour added, major when what it produces or needs changes).')
            elif parse(before['version']) and parse(now['version']) < parse(before['version']):
                found.append(label + ': version ' + now['version'] + ' is lower than ' + before['version'] + '.')
    return found


def stale(lock=None):
    """Components whose lock entry no longer matches (new, removed, or a new version): versions.py --update records them."""
    lock = read_json(LOCK) if lock is None else lock
    now = current()
    return sorted(kind[:-1] + ' ' + name for kind in now for name in set(now[kind]) | set(lock.get(kind, {}))
                  if now[kind].get(name) != lock.get(kind, {}).get(name))


def write_lock():
    found = problems()
    if found:
        raise KitError('\n'.join(found))
    LOCK.write_text(json.dumps(current(), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
