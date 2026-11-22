"""Git sources (ADR 0016): the only module that runs Git.

A source is a Core (later a Team) Git repository, identified by its canonical URL. Only stable vX.Y.Z tags are followed, never a
branch. Git runs with an allowlisted environment, no global or system config, explicit -c overrides, one credential helper
from a closed list (the person's, else the one Git's own configuration declares), and the TLS settings http.schannelCheckRevoke and
http.sslBackend from a closed list (http_settings). Trees are read with ls-tree/cat-file, never through tar: regular files only, every path checked. lock.toml
records the URL, tag, tag object, commit and tree digest of the active content, and the previous one for rollback."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import unquote, urlsplit

from .core import KitError

STABLE_TAG = re.compile(r'^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
PRERELEASE_TAG = re.compile(r'^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-rc\.(0|[1-9]\d*)$')
CREDENTIAL_HELPERS = ('manager', 'manager-core', 'osxkeychain', 'libsecret', 'wincred')
ENV_KEPT = ('PATH', 'HOME', 'USERPROFILE', 'SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'LANG', 'LC_ALL',
            'SSH_AUTH_SOCK', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY', 'https_proxy',
            'http_proxy', 'no_proxy', 'DISPLAY', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS')
# Workstation TLS settings the kit passes on (http_settings): Git key as config prints it -> (name, accepted value -> passed value).
HTTP_SETTINGS = {
    'http.schannelcheckrevoke': ('http.schannelCheckRevoke', {**dict.fromkeys(('true', 'yes', 'on', '1'), 'true'),
                                                             **dict.fromkeys(('false', 'no', 'off', '0'), 'false')}),
    'http.sslbackend': ('http.sslBackend', {'schannel': 'schannel', 'openssl': 'openssl'}),
}
WINDOWS_RESERVED = re.compile(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$', re.I)
# Tests only, set by patching (never from the environment): local bare repositories over file://.
LOCAL_FOR_TESTS = False


class SourceError(KitError):
    """A source cannot be used; kind is auth, network, not-found, refused-origin, tag-moved, invalid or revoked."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


# --- URL ---------------------------------------------------------------------------------------------------------------

def canonical_url(url, schemes=('https', 'ssh')):
    """The canonical form of a Git URL, or SourceError(refused-origin). https, and ssh when allowed; scp form becomes ssh://;
    host lower-case IDNA without default port; no credentials (except the git user over ssh); one percent-decoding; no '..',
    '//' or empty segment; a single .git suffix."""
    text = str(url).strip()
    def refuse(why):
        raise SourceError('refused-origin', 'Git URL refused ('+why+'): '+text)
    scp = re.match(r'^([A-Za-z0-9._-]+)@([A-Za-z0-9.-]+):(?!//)(.+)$', text)
    if scp and '://' not in text:
        text = 'ssh://'+scp.group(1)+'@'+scp.group(2)+'/'+scp.group(3)
    if LOCAL_FOR_TESTS and text.startswith('file://'):
        return 'file://'+str(Path(text[len('file://'):]).resolve().as_posix()).rstrip('/')
    parts = urlsplit(text)
    scheme = parts.scheme.lower()
    if scheme not in ('https', 'ssh'):
        refuse('only https and ssh are accepted')
    if scheme not in schemes:
        refuse(scheme+' is not in git.allowed_schemes')
    if parts.query or parts.fragment:
        refuse('no query or fragment')
    if parts.password is not None or (parts.username is not None and not (scheme == 'ssh' and parts.username == 'git')):
        refuse('no credentials in the URL')
    try:
        host = (parts.hostname or '').encode('idna').decode('ascii').lower()
    except UnicodeError:
        refuse('invalid host')
    if not host or not re.fullmatch(r'[a-z0-9.-]+', host):
        refuse('invalid host')
    port = parts.port
    netloc = ('git@' if scheme == 'ssh' else '')+host+(':'+str(port) if port and port != {'https': 443, 'ssh': 22}[scheme] else '')
    path = unquote(parts.path)
    segments = path.strip('/').split('/') if path.strip('/') else []
    if path.startswith('//') or '//' in path or not segments or any(s in ('', '.', '..') for s in segments) or '\\' in path:
        refuse('invalid path')
    while segments[-1].endswith('.git'):
        segments[-1] = segments[-1][:-4]
    if not segments[-1]:
        refuse('invalid path')
    return scheme+'://'+netloc+'/'+'/'.join(segments)+'.git'


def authorize(url, git):
    """SourceError(refused-origin) unless the canonical URL passes git.allowed_hosts and git.allowed_groups. A key IT did
    not write (None) restricts nothing; an empty list allows nothing (ADR 0015: an IT "none" is never read as "all")."""
    if url.startswith('file://') and LOCAL_FOR_TESTS:
        return
    parts = urlsplit(url)
    hosts, groups = git.get('allowed_hosts'), git.get('allowed_groups')
    if hosts is not None and parts.hostname not in hosts:
        if not hosts:
            raise SourceError('refused-origin', 'git.allowed_hosts is empty in managed.toml: no Git host is allowed (IT removes the key to lift the restriction): '+url)
        raise SourceError('refused-origin', 'Host '+str(parts.hostname)+' is not in git.allowed_hosts ('+', '.join(hosts)+'): '+url)
    path = parts.path.lstrip('/')
    if groups is not None and not any(path.startswith(g.strip('/')+'/') for g in groups):
        if not groups:
            raise SourceError('refused-origin', 'git.allowed_groups is empty in managed.toml: no group is allowed (IT removes the key to lift the restriction): '+url)
        raise SourceError('refused-origin', 'Group not in git.allowed_groups ('+', '.join(groups)+'): '+url)


def source_id(url):
    return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]


# --- Running Git -------------------------------------------------------------------------------------------------------

def engine_dir(kit):
    folder = kit/'sources'
    (folder/'empty-hooks').mkdir(parents=True, exist_ok=True)
    empty = folder/'empty.gitconfig'
    if not empty.exists():
        empty.write_bytes(b'')
    return folder


def workstation_config(args, global_config):
    """`git config <args>` as the workstation's Git reads it, outside any repository: Git's own configuration (system and
    installation level) and global_config as the person's; lines of output, [] on any failure."""
    env = {k: os.environ[k] for k in ENV_KEPT if k in os.environ}
    env.update({'GIT_CONFIG_GLOBAL': str(global_config), 'GIT_TERMINAL_PROMPT': '0'})
    if 'GIT_CONFIG_SYSTEM' in os.environ:
        env['GIT_CONFIG_SYSTEM'] = os.environ['GIT_CONFIG_SYSTEM']
    with tempfile.TemporaryDirectory() as empty:  # outside any repository: no local config is read
        env['GIT_CEILING_DIRECTORIES'] = str(Path(empty).parent)
        try:
            proc = subprocess.run(['git', 'config', *args], cwd=empty, env=env, capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return []
    return [v.strip() for v in proc.stdout.decode('utf-8', 'replace').splitlines() if v.strip()] if proc.returncode == 0 else []


def git_level_helpers():
    """The credential.helper values Git's own configuration declares (system and installation level, never the person's
    global one nor a repository's): Git for Windows writes manager there, the Xcode git of macOS osxkeychain."""
    return workstation_config(['--get-all', 'credential.helper'], os.devnull)


def http_settings(home):
    """-c overrides for the TLS settings the workstation's Git declares (the person's ~/.gitconfig over Git's own
    configuration, last value wins as in Git), each from a closed list; any other value or http.* key is not passed.
    Issue #17: behind a proxy that inspects TLS, schannel cannot check revocation unless http.schannelCheckRevoke=false."""
    found = {}
    for line in workstation_config(['--get-regexp', r'^http\.(schannelcheckrevoke|sslbackend)$'], Path(home)/'.gitconfig'):
        key, _, value = line.partition(' ')
        found[key.lower()] = value.strip().lower()
    overrides = []
    for key, (name, accepted) in HTTP_SETTINGS.items():
        if found.get(key) in accepted:
            overrides.append(name+'='+accepted[found[key]])
    return overrides


def credential_helper(home):
    """The credential helper the kit passes to Git, from a closed list (a !command or a path is refused): the person's own,
    declared in ~/.gitconfig, wins; without one, the helper Git's own configuration declares, when every value it declares
    is in the list."""
    config = home/'.gitconfig'
    declared = []
    if config.is_file():
        for line in config.read_text(encoding='utf-8', errors='replace').splitlines():
            m = re.match(r'\s*helper\s*=\s*(.*?)\s*$', line)
            if m:
                declared.append(m.group(1).strip('"'))
    if declared:
        return declared[-1] if declared[-1] in CREDENTIAL_HELPERS else None
    values = [v for v in git_level_helpers() if v]
    return values[-1] if values and all(v in CREDENTIAL_HELPERS for v in values) else None


def git(args, kit, git_dir=None, schemes=('https', 'ssh'), input_bytes=None, timeout=300, home=None, local_bundle=False):
    """git with the neutralized environment; returns stdout bytes or raises SourceError classified."""
    folder = engine_dir(kit)
    env = {k: os.environ[k] for k in ENV_KEPT if k in os.environ}
    env.update({'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': str(folder/'empty.gitconfig'), 'GIT_ASKPASS': '', 'SSH_ASKPASS': ''})
    if not sys.stdin.isatty():
        env.update({'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'})
    overrides = ['core.fsmonitor=false', 'core.hooksPath='+str(folder/'empty-hooks'), 'protocol.allow=never', 'protocol.https.allow=always',
                 'http.followRedirects=false', 'core.autocrlf=false', 'http.sslVerify=true', 'core.sshCommand=ssh', 'credential.helper=']
    if 'ssh' in schemes:
        overrides.append('protocol.ssh.allow=always')
    if LOCAL_FOR_TESTS or local_bundle:
        overrides.append('protocol.file.allow=always')  # a git bundle file the person gave (sync --from-bundle)
    if os.name == 'nt':
        overrides.append('core.longpaths=true')
    helper = credential_helper(Path(home) if home else Path(kit).parent)  # the installation's home (--home), kit = <home>/.ai-kit
    if helper:
        overrides.append('credential.helper='+helper)
    overrides += http_settings(Path(home) if home else Path(kit).parent)  # http.sslVerify=true above is never lifted
    command = ['git'] + [a for o in overrides for a in ('-c', o)]
    if git_dir is not None:
        prepare_cache(git_dir)
        command += ['--git-dir', str(git_dir)]
    try:
        proc = subprocess.run(command + list(args), input=input_bytes, capture_output=True, env=env, timeout=timeout)
    except FileNotFoundError:
        raise SourceError('invalid', 'git was not found: install Git (IT can provide it), then run the command again.') from None
    except subprocess.TimeoutExpired:
        raise SourceError('network', 'git '+args[0]+' did not answer within '+str(timeout)+' s.') from None
    if proc.returncode != 0:
        err = proc.stderr.decode('utf-8', 'replace').strip()
        low = err.lower()
        kind = ('auth' if any(w in low for w in ('authentication', 'permission denied', 'could not read username', 'terminal prompts disabled', '403'))
                else 'not-found' if any(w in low for w in ('not found', 'does not exist', "couldn't find remote ref", '404', 'does not appear to be a git repository'))
                else 'network' if any(w in low for w in ('could not resolve', 'timed out', 'connection', 'unable to access'))
                else 'invalid')
        raise SourceError(kind, 'git '+args[0]+' failed ('+kind+'): '+err.splitlines()[-1][:300] if err else 'git '+args[0]+' failed')
    return proc.stdout


def prepare_cache(git_dir):
    """A bare cache with the engine's own config, rewritten before each call; alternates, grafts and shallow refused."""
    git_dir = Path(git_dir)
    for name in ('objects/info/alternates', 'objects/info/http-alternates', 'info/grafts', 'shallow'):
        if (git_dir/name).exists():
            raise SourceError('invalid', 'The source cache '+str(git_dir)+' holds '+name+', which the kit refuses: delete the folder, then sync again.')
    if (git_dir/'HEAD').exists():
        (git_dir/'config').write_text('[core]\n\trepositoryformatversion = 0\n\tbare = true\n', encoding='utf-8')


# --- Tags --------------------------------------------------------------------------------------------------------------

def remote_tags(url, kit, schemes=('https', 'ssh'), home=None):
    """{tag: {'tag_object': sha, 'commit': sha}} for the eligible-looking tags of the remote (ls-remote, no fetch)."""
    resolved = git(['ls-remote', '--get-url', url], kit, schemes=schemes, home=home).decode('utf-8').strip()
    if resolved != url and not (LOCAL_FOR_TESTS and url.startswith('file://')):
        raise SourceError('refused-origin', 'Git rewrites '+url+' into '+resolved+': the kit refuses a rewritten origin.')
    out = git(['ls-remote', '--tags', url], kit, schemes=schemes, home=home).decode('utf-8')
    tags = {}
    for line in out.splitlines():
        sha, _, ref = line.partition('\t')
        if not ref.startswith('refs/tags/'):
            continue
        name = ref[len('refs/tags/'):]
        peeled = name.endswith('^{}')
        name = name[:-3] if peeled else name
        if not (STABLE_TAG.match(name) or PRERELEASE_TAG.match(name)):
            continue
        entry = tags.setdefault(name, {'tag_object': sha, 'commit': sha})
        if peeled:
            entry['commit'] = sha
        else:
            entry['tag_object'] = sha
    return tags


def tag_key(name):
    m = STABLE_TAG.match(name) or PRERELEASE_TAG.match(name)
    numbers = [int(g) for g in m.groups()]
    return (numbers[0], numbers[1], numbers[2], 1 if len(numbers) == 3 else 0, numbers[3] if len(numbers) == 4 else 0)


def choose_tag(tags, locked=None, allow_prerelease=False):
    """The highest eligible tag; never lower than the locked one (only rollback goes back)."""
    eligible = [t for t in tags if STABLE_TAG.match(t) or (allow_prerelease and PRERELEASE_TAG.match(t))]
    if not eligible:
        raise SourceError('not-found', 'No stable tag vX.Y.Z in the source: ask its owner to publish one.')
    best = max(eligible, key=tag_key)
    if locked and tag_key(best) < tag_key(locked):
        raise SourceError('invalid', 'The highest tag '+best+' is lower than the active '+locked+': only ai-kit rollback goes back.')
    return best


def check_seen(kit, url, tags):
    """Every tag seen keeps its SHA: a known tag that moved blocks (tag-moved). Records the new ones."""
    path = engine_dir(kit)/(source_id(url)+'.seen.json')
    seen = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    moved = sorted(t for t, e in tags.items() if t in seen and seen[t] != e['commit'])
    if moved:
        raise SourceError('tag-moved', 'Tag '+', '.join(moved)+' of '+url+' now points to another commit. Nothing was changed. '
                          'Tell the owner of the repository: a published tag must never move.')
    seen.update({t: e['commit'] for t, e in tags.items()})
    path.write_text(json.dumps(seen, indent=1, sort_keys=True), encoding='utf-8')


def revoked(commit, git_settings):
    return commit in set(git_settings.get('revoked') or [])


# --- Cache and extraction ----------------------------------------------------------------------------------------------

def cache_dir(kit, url):
    return engine_dir(kit)/(source_id(url)+'.git')


SSH_KEY_TYPE = re.compile(r'(ssh-|ecdsa-|sk-)[A-Za-z0-9@.-]+\s')  # a line of git.signers that starts with the key itself


def verify_signature(kit, cache, tag, signers):
    """IT's git.signers (SSH public keys, as in an allowed-signers file): the tag must carry an SSH signature from one of them,
    and the signed tag object must be the one of this tag: a signed v1.0.0 served under another name is refused. A line
    that already has its principal (name key-type key) is kept as it is; a bare key gets one."""
    if not signers:
        return
    allowed = engine_dir(kit)/'allowed_signers'
    allowed.write_text(''.join(('ai-kit ' if SSH_KEY_TYPE.match(key.strip()) else '')+key.strip()+'\n' for key in signers), encoding='utf-8')
    try:
        git(['-c', 'gpg.format=ssh', '-c', 'gpg.ssh.allowedSignersFile='+str(allowed), 'verify-tag', '--raw', tag], kit, git_dir=cache)
        header = git(['cat-file', 'tag', 'refs/tags/'+tag], kit, git_dir=cache).decode('utf-8', 'replace').split('\n\n', 1)[0]
    except SourceError:
        raise SourceError('invalid', 'Tag '+tag+' is not signed by a key IT lists (managed.toml git.signers): nothing was changed.') from None
    named = next((line[len('tag '):].strip() for line in header.splitlines() if line.startswith('tag ')), '')
    if named != tag:
        raise SourceError('invalid', 'Tag '+tag+' carries the signed tag object of '+(named or 'another tag')+': a signature is for one tag only. Nothing was changed.')


def fetch(kit, url, tag, expected_commit, schemes=('https', 'ssh'), home=None):
    """Only this tag into the bare cache; the fetched commit must be the one ls-remote announced."""
    cache = cache_dir(kit, url)
    if not (cache/'HEAD').exists():
        cache.mkdir(parents=True, exist_ok=True)
        git(['init', '--bare', '--quiet', str(cache)], kit, schemes=schemes, home=home)
    git(['fetch', '--quiet', '--no-tags', '--no-write-fetch-head', url, 'refs/tags/'+tag+':refs/tags/'+tag], kit, git_dir=cache, schemes=schemes, home=home)
    commit = git(['rev-parse', 'refs/tags/'+tag+'^{commit}'], kit, git_dir=cache, home=home).decode().strip()
    if commit != expected_commit:
        raise SourceError('tag-moved', 'Tag '+tag+' fetched at '+commit+' while the remote announced '+expected_commit+'. Nothing was changed.')
    return cache


def bundle_tags(kit, bundle):
    """{tag: {'tag_object', 'commit'}} of a git bundle file (sync --from-bundle): the offline origin of the configured Core."""
    bundle = Path(bundle).resolve()
    if not bundle.is_file():
        raise SourceError('not-found', 'Bundle not found: '+str(bundle))
    # No 'git bundle verify' here (it needs a repository): the fetch from the bundle checks it.
    tags = {}
    for line in git(['bundle', 'list-heads', str(bundle)], kit, local_bundle=True).decode('utf-8').splitlines():
        sha, _, ref = line.partition(' ')
        if not ref.startswith('refs/tags/'):
            continue
        name = ref[len('refs/tags/'):]
        peeled = name.endswith('^{}')
        name = name[:-3] if peeled else name
        if STABLE_TAG.match(name) or PRERELEASE_TAG.match(name):
            entry = tags.setdefault(name, {'tag_object': sha, 'commit': sha})
            entry['commit' if peeled else 'tag_object'] = sha
    return tags  # an annotated tag's commit is known once fetched (fetch_bundle)


def fetch_bundle(kit, url, bundle, tag):
    """The tag from the bundle file into the cache of the configured Core URL; returns (cache, commit)."""
    cache = cache_dir(kit, url)
    if not (cache/'HEAD').exists():
        cache.mkdir(parents=True, exist_ok=True)
        git(['init', '--bare', '--quiet', str(cache)], kit)
    git(['fetch', '--quiet', '--no-tags', '--no-write-fetch-head', str(Path(bundle).resolve()), 'refs/tags/'+tag+':refs/tags/'+tag], kit, git_dir=cache, local_bundle=True)
    commit = git(['rev-parse', 'refs/tags/'+tag+'^{commit}'], kit, git_dir=cache).decode().strip()
    return cache, commit


def safe_path(path, seen_lower):
    """SourceError(invalid) for a path that could escape, hide or clash on a Windows or macOS checkout."""
    parts = PurePosixPath(path).parts
    bad = (not parts or path.startswith('/') or '\\' in path or ':' in path
           or any(p in ('.', '..') or p.lower() == '.git' or WINDOWS_RESERVED.match(p) or p.endswith(('.', ' ')) for p in parts))
    if bad:
        raise SourceError('invalid', 'The source holds a path the kit refuses: '+path)
    for depth in range(1, len(parts)+1):
        key = '/'.join(parts[:depth]).lower()
        owner = seen_lower.setdefault(key, '/'.join(parts[:depth]))
        if owner != '/'.join(parts[:depth]):
            raise SourceError('invalid', 'Two paths differ only by case (they clash on Windows and macOS): '+owner+', '+path)


# What a Core or a Team may hold: text files, a few megabytes in all. Beyond these bounds the source is refused from its
# listing, before one file is read. A source is read in batches, so the memory used does not grow with its size.
MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES, BATCH_BYTES = 20000, 20 * 1024 * 1024, 200 * 1024 * 1024, 32 * 1024 * 1024


def megabytes(size):
    return str(max(1, size // (1024 * 1024)))+' MB'


def extract(kit, cache, commit, dest, home=None):
    """The tree of commit written to dest (a new empty folder) with ls-tree and cat-file; returns its digest. Regular files only:
    a symbolic link or a submodule is refused, and so is a tree beyond the bounds above."""
    listing = git(['ls-tree', '-r', '-l', '-z', '--full-tree', commit], kit, git_dir=cache, home=home)
    entries, seen, total = [], {}, 0
    for record in listing.split(b'\0'):
        if not record:
            continue
        meta, _, raw = record.partition(b'\t')
        mode, kind, sha, size = meta.decode().split()
        path = raw.decode('utf-8')
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise SourceError('invalid', 'The source holds '+('a symbolic link' if mode == '120000' else 'a submodule' if mode == '160000' else 'an entry of mode '+mode)+', refused: '+path)
        safe_path(path, seen)
        size = int(size)
        if size > MAX_FILE_BYTES:
            raise SourceError('invalid', 'The source holds a file larger than '+megabytes(MAX_FILE_BYTES)+', refused: '+path)
        total += size
        entries.append((path, sha, size))
        if len(entries) > MAX_FILES:
            raise SourceError('invalid', 'The source holds more than '+str(MAX_FILES)+' files, refused.')
        if total > MAX_TOTAL_BYTES:
            raise SourceError('invalid', 'The source holds more than '+megabytes(MAX_TOTAL_BYTES)+' in all, refused.')
    batches, held = [[]], 0
    for entry in entries:
        if batches[-1] and held + entry[2] > BATCH_BYTES:
            batches.append([])
            held = 0
        batches[-1].append(entry)
        held += entry[2]
    lines, dest = [], Path(dest)
    for batch in batches:
        if not batch:
            continue
        blobs = git(['cat-file', '--batch'], kit, git_dir=cache, input_bytes=''.join(sha+'\n' for _, sha, _size in batch).encode(), home=home)
        position = 0
        for path, sha, listed in batch:
            header_end = blobs.index(b'\n', position)
            got_sha, kind, size = blobs[position:header_end].decode().split()
            if got_sha != sha or kind != 'blob' or int(size) != listed:
                raise SourceError('invalid', 'Unexpected object while reading the source: '+path)
            data = blobs[header_end+1:header_end+1+int(size)]
            position = header_end+1+int(size)+1
            target = dest.joinpath(*PurePosixPath(path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            lines.append(path+'\0'+hashlib.sha256(data).hexdigest())
    return hashlib.sha256('\n'.join(sorted(lines)).encode('utf-8')).hexdigest()


def prune_cache(kit, url, keep_tags):
    """Only the tags cited by lock.toml stay in the cache; unreachable objects go."""
    cache = cache_dir(kit, url)
    if not (cache/'HEAD').exists():
        return
    refs = git(['for-each-ref', '--format=%(refname)', 'refs/tags'], kit, git_dir=cache).decode().split()
    for ref in refs:
        if ref[len('refs/tags/'):] not in keep_tags:
            git(['update-ref', '-d', ref], kit, git_dir=cache)
    git(['gc', '--quiet', '--prune=now'], kit, git_dir=cache)


# --- Engine lock -------------------------------------------------------------------------------------------------------

class EngineLock:
    """~/.ai-kit/engine.lock: one kit command that changes files at a time. A lock left by a dead process (POSIX), or older than
    an hour (Windows, where the pid cannot be probed without extra modules), is taken over."""

    def __init__(self, kit):
        self.path = kit/'engine.lock'

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, 'w') as out:
                    out.write(str(os.getpid()))
                return self
            except FileExistsError:
                if not self.stale():
                    raise KitError('Another ai-kit command is changing files ('+str(self.path)+'). Wait for it to finish, then run again.') from None
                self.path.unlink(missing_ok=True)
        raise KitError('Could not take '+str(self.path)+'.')

    def stale(self):
        try:
            pid = int(self.path.read_text(encoding='utf-8').strip() or 0)
        except (OSError, ValueError):
            return True
        if os.name == 'nt':
            return time.time() - self.path.stat().st_mtime > 3600
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        return False

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


def new_temp():
    return Path(tempfile.mkdtemp(prefix='ai-kit-source-'))


def remove_temp(folder):
    shutil.rmtree(folder, ignore_errors=True)
