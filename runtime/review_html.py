#!/usr/bin/env python3
"""Write review.html, a visual version of a review guide (review-guide skill, spec docs/sdlc/2026-11-14-review-aids/spec-html.md).

Usage: python3 review_html.py --guide <review-guide.md> [--base REF] [--repo PATH] [--out <review.html>]
The page holds the guide, then the change's diff, one block per file in the guide's order, and lets a person comment on a
line or a section; "Finish" copies review-comments.md to the clipboard and offers to download it. One self-contained file:
CSS and JavaScript inline, no request outside it (a Content-Security-Policy pins its blocks), every text from the repository
escaped. Git runs in read mode only (rev-parse, merge-base, diff, ls-files) with the repository's hooks, fsmonitor,
external diff and textconv neutralized. Standard library only, no connection, no model.
Output: the path written, on stdout. Exit code 0, or 2 when the guide or the repository cannot be read.
"""
import argparse
import base64
import hashlib
import html
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

FOLD_LINES = 2000
MAX_NEW_FILE = 1_000_000  # bytes: a bigger new file is folded, not read
REF = re.compile(r'(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.\w+):(\d+)(?:-\d+)?')


class RepoError(Exception):
    pass


# --- Git, read-only ----------------------------------------------------------------------------------------------------

def git(repo, *args, check=True):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    settings = ['-c', 'core.fsmonitor=false', '-c', 'core.hooksPath='+os.devnull, '-c', 'core.quotePath=false', '-c', 'color.ui=false',
                '-c', 'diff.noprefix=false', '-c', 'diff.mnemonicPrefix=false', '-c', 'diff.suppressBlankEmpty=false']
    proc = subprocess.run(['git', *settings, '-C', str(repo), *args],
                          capture_output=True, env=env, timeout=60, stdin=subprocess.DEVNULL)
    if check and proc.returncode != 0:
        raise RepoError(proc.stderr.decode('utf-8', 'replace').strip() or 'git '+args[0]+' failed')
    return proc.stdout.decode('utf-8', 'replace') if proc.returncode == 0 else None


def resolve_base(repo, base):
    if base:
        if git(repo, 'rev-parse', '--verify', '--quiet', base+'^{commit}', check=False) is None:
            raise RepoError('base not found: '+base)
        return base
    remote = git(repo, 'rev-parse', '--abbrev-ref', 'origin/HEAD', check=False)
    if remote and remote.strip() != 'origin/HEAD':
        return remote.strip()
    for name in ('main', 'master'):
        if git(repo, 'rev-parse', '--verify', '--quiet', name+'^{commit}', check=False) is not None:
            return name
    raise RepoError('no base: pass --base (no origin/HEAD, main or master)')


# --- The diff ----------------------------------------------------------------------------------------------------------

def header_path(value):
    """A path from a ---/+++ line: git adds a tab after a name with a space; a quoted name stays quoted (shown as is)."""
    value = value.rstrip('\r').split('\t')[0]
    return value[2:] if value[:2] in ('a/', 'b/') else value


def parse_diff(text):
    """[{path, lines: [(kind, old, new, text)], binary}] from a unified diff; kind is '+', '-', ' ' or '@'.
    A hunk is read by the counts of its header, so a line that looks like a header inside it ('--- x', '+++ x') stays a line."""
    files, current, old, new, old_left, new_left = [], None, 0, 0, 0, 0
    for raw in text.split('\n'):
        line = raw.rstrip('\r')
        if current is not None and (old_left > 0 or new_left > 0):
            if line.startswith('\\'):
                continue  # \ No newline at end of file
            kind, body = (line[:1] or ' '), line[1:]
            if kind == '+':
                current['lines'].append(('+', None, new, body))
                new, new_left = new + 1, new_left - 1
            elif kind == '-':
                current['lines'].append(('-', old, None, body))
                old, old_left = old + 1, old_left - 1
            else:
                current['lines'].append((' ', old, new, body))
                old, new, old_left, new_left = old + 1, new + 1, old_left - 1, new_left - 1
            continue
        if line.startswith('diff --git '):
            current = {'path': None, 'lines': [], 'binary': False}
            files.append(current)
            parts = line[11:].split(' b/', 1)
            current['path'] = parts[1] if len(parts) == 2 else line[11:]
        elif current is None:
            continue
        elif line.startswith('+++ '):
            if line != '+++ /dev/null':
                current['path'] = header_path(line[4:])
        elif line.startswith('--- '):
            if current['path'] is None or line == '--- /dev/null':
                pass
        elif line.startswith('Binary files'):
            current['binary'] = True
        elif line.startswith('@@'):
            m = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if m:
                old, new = int(m.group(1)), int(m.group(3))
                old_left = int(m.group(2)) if m.group(2) is not None else 1
                new_left = int(m.group(4)) if m.group(4) is not None else 1
            current['lines'].append(('@', None, None, line))
    return files


def new_file(repo, rel):
    """A new untracked file, read only when it is a regular file: a link is shown as a link, never followed."""
    path = Path(repo)/rel
    try:
        info = os.lstat(path)
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode):
        return {'path': rel, 'lines': [], 'binary': False, 'note': 'symbolic link, not read'}
    if not stat.S_ISREG(info.st_mode):
        return None
    if info.st_size > MAX_NEW_FILE:
        return {'path': rel, 'lines': [], 'binary': False, 'note': 'new file of %d bytes, folded' % info.st_size}
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b'\0' in data[:8000]:
        return {'path': rel, 'lines': [], 'binary': True, 'note': 'binary file of %d bytes' % len(data), 'data': data}
    text = data.decode('utf-8', 'replace').replace('\r\n', '\n')
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return {'path': rel, 'lines': [('@', None, None, '@@ new file @@')] + [('+', None, i+1, line) for i, line in enumerate(lines)],
            'binary': False, 'data': data}


def artifact(rel):
    """A review guide or page of any change: never shown as part of the diff."""
    return rel.rsplit('/', 1)[-1] in ('review.html', 'review-guide.md')


def change_files(repo, merge_base, skip):
    text = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--no-color', '--src-prefix=a/', '--dst-prefix=b/', '-M', '--unified=3', merge_base)
    files = [f for f in parse_diff(text) if f['path'] not in skip and not artifact(f['path'])]
    for rel in filter(None, git(repo, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')):
        if rel not in skip and not artifact(rel):
            item = new_file(repo, rel)
            if item:
                files.append(item)
    return files, text


# --- The guide ---------------------------------------------------------------------------------------------------------

def guide_order(guide):
    """Paths in the order the guide cites them: Reading order, then Themes, then the other sections."""
    sections, name = {}, ''
    for line in guide.split('\n'):
        if line.startswith('## '):
            name = line[3:].strip().lower()
        sections.setdefault(name, []).append(line)
    ordered = []
    for key in ['reading order', 'themes'] + [k for k in sections if k not in ('reading order', 'themes')]:
        for line in sections.get(key, []):
            for m in re.finditer(r'(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.\w+)(?::\d+)?', line):
                if m.group(1) not in ordered:
                    ordered.append(m.group(1))
    return ordered


def inline(text):
    """Escaped text with `code` and file:line links; nothing from the guide is inserted unescaped."""
    out = []
    for i, part in enumerate(re.split(r'(`[^`]*`)', text)):
        if i % 2:
            out.append('<code>'+html.escape(part[1:-1])+'</code>')
            continue
        esc = html.escape(part)
        out.append(REF.sub(lambda m: '<a href="#'+line_id(m.group(1), m.group(2))+'">'+m.group(0)+'</a>', esc))
    return ''.join(out)


def render_guide(guide):
    out, in_code, in_list = [], False, None
    for line in guide.split('\n'):
        if line.startswith('```'):
            if in_list:
                out.append('</'+in_list+'>')
                in_list = None
            out.append('</pre>' if in_code else '<pre>')
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        heading = re.match(r'(#{1,4}) (.*)', line)
        item = re.match(r'\s*(?:[-*]|(\d+)\.) (.*)', line)
        if in_list and not item:
            out.append('</'+in_list+'>')
            in_list = None
        if heading:
            level, title = len(heading.group(1)), heading.group(2).strip()
            attr = ' class="section" data-section="'+html.escape(title, quote=True)+'"' if level >= 2 else ''
            out.append('<h%d%s>%s</h%d>' % (level, attr, inline(title), level))
        elif item:
            kind = 'ol' if item.group(1) else 'ul'
            if in_list != kind:
                if in_list:
                    out.append('</'+in_list+'>')
                out.append('<'+kind+'>')
                in_list = kind
            out.append('<li>'+inline(item.group(2))+'</li>')
        elif line.strip():
            out.append('<p>'+inline(line)+'</p>')
    if in_list:
        out.append('</'+in_list+'>')
    if in_code:
        out.append('</pre>')
    return '\n'.join(out)


# --- The page ----------------------------------------------------------------------------------------------------------

def line_id(path, line):
    return 'L-'+html.escape(path, quote=True)+'-'+str(line)


def render_file(item):
    path = item['path']
    if any(ord(ch) < 32 for ch in path):
        return '<section class="file" data-folded><h3>%s</h3><p class="folded">file name with control characters, not shown</p></section>' % html.escape(repr(path))
    attr = html.escape(path, quote=True)
    body = [row for row in item['lines'] if row[0] != '@']
    size = sum(len(row[3]) for row in body)
    if item.get('binary') or item.get('note') or len(body) > FOLD_LINES or size > MAX_NEW_FILE:
        why = item.get('note') or ('binary file' if item.get('binary') else '%d lines, %d characters of diff, folded' % (len(body), size))
        return '<section class="file" data-file="%s" data-folded><h3>%s</h3><p class="folded">%s</p></section>' % (attr, html.escape(path), why)
    rows = []
    for kind, old, new, text in item['lines']:
        if kind == '@':
            rows.append('<tr class="hunk"><td></td><td></td><td>%s</td></tr>' % html.escape(text))
            continue
        cls = {'+': 'add', '-': 'del', ' ': 'ctx'}[kind]
        number = new if new is not None else old
        ident = line_id(path, new) if new is not None else line_id(path, 'old%d' % old)
        label = str(new) if new is not None else '-%d' % old
        rows.append('<tr class="line %s" id="%s" data-path="%s" data-line="%s" tabindex="-1"><td class="num">%s</td>'
                    '<td class="sign">%s</td><td class="code">%s</td></tr>'
                    % (cls, ident, attr, label, number, kind if kind != ' ' else '', html.escape(text)))
    return '<section class="file" data-file="%s"><h3>%s</h3><table>%s</table></section>' % (attr, html.escape(path), ''.join(rows))


CSS = """
:root{color-scheme:light dark;--bg:#fff;--fg:#1f2328;--muted:#656d76;--add:#dafbe1;--del:#ffebe9;--hunk:#ddf4ff;--line:#d0d7de;--accent:#0969da;--note:#fff8c5}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8d96a0;--add:#033a16;--del:#4c1018;--hunk:#0c2d4a;--line:#30363d;--accent:#4493f8;--note:#3b2e00}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px 16px 96px}
.warning{border:1px solid var(--line);border-radius:6px;padding:8px 12px;color:var(--muted);font-size:13px}
.guide{border-bottom:1px solid var(--line);margin-bottom:24px}
.guide a,.guide code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}
.section{cursor:pointer}.section:hover{color:var(--accent)}
.file{border:1px solid var(--line);border-radius:6px;margin:16px 0;overflow:auto}
.file h3{margin:0;padding:8px 12px;font:600 13px ui-monospace,Menlo,Consolas,monospace;border-bottom:1px solid var(--line)}
table{border-collapse:collapse;width:100%;font:12.5px/1.45 ui-monospace,Menlo,Consolas,monospace}
td{padding:0 8px;white-space:pre-wrap;vertical-align:top}td.num{color:var(--muted);text-align:right;width:1%;user-select:none}
td.sign{width:1%;color:var(--muted)}.add{background:var(--add)}.del{background:var(--del)}.hunk td{background:var(--hunk);color:var(--muted)}
tr.line{cursor:pointer}tr.line:hover td.num,tr.current td.num{color:var(--accent);font-weight:700}
.note td{background:var(--note);font-family:system-ui,sans-serif;white-space:normal}
.folded{padding:8px 12px;color:var(--muted);margin:0}
textarea{width:100%;box-sizing:border-box;min-height:64px;font:inherit;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--bg);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;align-items:center;justify-content:space-between}
button{font:inherit;padding:6px 14px;border-radius:6px;border:1px solid var(--line);background:var(--accent);color:#fff;cursor:pointer}
button.plain{background:transparent;color:var(--fg)}
.panel{position:fixed;inset:10% 10% auto;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:16px;box-shadow:0 8px 32px #0004}
.panel textarea{min-height:240px}.hidden{display:none}.status{color:var(--muted);font-size:13px}
"""

LOGIC = """/* logic:start */
function oneLine(text) { return String(text).replace(/\\s*\\n\\s*/g, ' ').trim(); }
function formatComments(title, comments) {
  let out = '# Review comments: ' + title + '\\n';
  for (const c of comments) {
    const where = c.section ? '[' + oneLine(c.section) + ']' : oneLine(c.file) + ':' + oneLine(c.line);
    out += '- ' + where + ' \\u2014 ' + oneLine(c.text) + '\\n';
  }
  return out;
}
function draftKey(pagePath, digest) { return 'ai-kit-review:' + pagePath + ':' + digest; }
/* logic:end */"""

UI = """
const DATA = JSON.parse(document.getElementById('review-data').textContent);
const KEY = draftKey(location.pathname, DATA.digest);
let comments = [];
let storage = null;
try { localStorage.setItem(KEY + ':probe', '1'); localStorage.removeItem(KEY + ':probe'); storage = localStorage; } catch (e) { storage = null; }
const statusEl = document.getElementById('status');
if (!storage) { document.getElementById('nostore').classList.remove('hidden'); }
function save() { if (storage) { try { storage.setItem(KEY, JSON.stringify(comments)); } catch (e) {} } render(); }
function exists(c) {
  if (c && typeof c.text === 'string' && typeof c.section === 'string') return [...document.querySelectorAll('[data-section]')].some(e => e.dataset.section === c.section);
  if (c && typeof c.text === 'string' && typeof c.file === 'string' && /^-?\\d+$/.test(String(c.line))) return [...document.querySelectorAll('tr.line')].some(r => r.dataset.path === c.file && r.dataset.line === String(c.line));
  return false;
}
function load() {
  if (!storage) return;
  let saved = [];
  try { saved = JSON.parse(storage.getItem(KEY) || '[]'); } catch (e) { saved = []; }
  comments = Array.isArray(saved) ? saved.filter(exists).map(c => c.section ? {section: c.section, text: c.text} : {file: c.file, line: String(c.line), text: c.text}) : [];
}
function keyOf(c) { return c.section ? 's:' + c.section : 'l:' + c.file + ':' + c.line; }
function render() {
  document.querySelectorAll('tr.note').forEach(n => n.remove());
  document.querySelectorAll('.section-note').forEach(n => n.remove());
  for (const c of comments) {
    if (c.section) {
      const h = [...document.querySelectorAll('[data-section]')].find(e => e.dataset.section === c.section);
      if (h) { const p = document.createElement('p'); p.className = 'section-note note'; p.textContent = '\\u270e ' + c.text; h.after(p); }
    } else {
      const row = [...document.querySelectorAll('tr.line')].find(r => r.dataset.path === c.file && r.dataset.line === String(c.line));
      if (row) {
        const tr = document.createElement('tr'); tr.className = 'note';
        const td = document.createElement('td'); td.colSpan = 3; td.textContent = '\\u270e ' + c.text;
        tr.appendChild(td); row.after(tr);
      }
    }
  }
  statusEl.textContent = comments.length + (comments.length === 1 ? ' comment' : ' comments');
}
function edit(target) {
  const existing = comments.find(c => keyOf(c) === keyOf(target));
  const box = document.getElementById('editor');
  document.getElementById('editor-where').textContent = target.section ? '[' + target.section + ']' : target.file + ':' + target.line;
  const area = document.getElementById('editor-text');
  area.value = existing ? existing.text : '';
  box.classList.remove('hidden'); area.focus();
  box.dataset.target = JSON.stringify(target);
}
function closeEditor() { document.getElementById('editor').classList.add('hidden'); }
document.getElementById('editor-save').addEventListener('click', () => {
  const box = document.getElementById('editor'); const target = JSON.parse(box.dataset.target);
  const text = document.getElementById('editor-text').value.trim();
  comments = comments.filter(c => keyOf(c) !== keyOf(target));
  if (text) { comments.push(Object.assign(target, {text: text})); }
  closeEditor(); save();
});
document.getElementById('editor-delete').addEventListener('click', () => {
  const target = JSON.parse(document.getElementById('editor').dataset.target);
  comments = comments.filter(c => keyOf(c) !== keyOf(target)); closeEditor(); save();
});
document.getElementById('editor-cancel').addEventListener('click', closeEditor);
const rows = [...document.querySelectorAll('tr.line')];
let current = -1;
function focusRow(i) {
  if (!rows.length) return;
  current = Math.max(0, Math.min(rows.length - 1, i));
  rows.forEach(r => r.classList.remove('current'));
  rows[current].classList.add('current'); rows[current].scrollIntoView({block: 'center'});
}
rows.forEach((r, i) => r.addEventListener('click', () => { current = i; edit({file: r.dataset.path, line: r.dataset.line}); }));
document.querySelectorAll('[data-section]').forEach(h => h.addEventListener('click', () => edit({section: h.dataset.section})));
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'TEXTAREA') { if (e.key === 'Escape') closeEditor(); return; }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === 'j') focusRow(current + 1);
  else if (e.key === 'k') focusRow(current - 1);
  else if (e.key === 'c' && current >= 0) { e.preventDefault(); const r = rows[current]; edit({file: r.dataset.path, line: r.dataset.line}); }
  else if (e.key === 'Escape') { closeEditor(); document.getElementById('finish-panel').classList.add('hidden'); }
});
document.getElementById('finish').addEventListener('click', async () => {
  const shown = comments.filter(exists);
  const text = formatComments(DATA.title, shown);
  const panel = document.getElementById('finish-panel');
  const area = document.getElementById('finish-text');
  area.value = text; panel.classList.remove('hidden');
  let copied = false;
  try { await navigator.clipboard.writeText(text); copied = true; } catch (e) {
    try { area.focus(); area.select(); copied = document.execCommand('copy'); } catch (e2) { copied = false; }
  }
  document.getElementById('finish-status').textContent = shown.length + ' comments. ' + (copied
    ? 'Copied to the clipboard. Paste it to the agent, or download the file and give the agent its path.'
    : 'Copy the selected text, then paste it to the agent, or download the file and give the agent its path.');
  area.focus(); area.select();
});
document.getElementById('download').addEventListener('click', () => {
  const blob = new Blob([document.getElementById('finish-text').value], {type: 'text/markdown'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'review-comments.md';
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
});
document.getElementById('finish-close').addEventListener('click', () => document.getElementById('finish-panel').classList.add('hidden'));
load(); render();
"""


def sha256_source(block):
    return "'sha256-"+base64.b64encode(hashlib.sha256(block.encode('utf-8')).digest()).decode()+"'"


def build_page(title, guide, files, digest):
    script = LOGIC+'\n'+UI
    data = json.dumps({'title': title, 'digest': digest}).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    csp = "default-src 'none'; style-src %s; script-src %s; img-src data:; base-uri 'none'; form-action 'none'" % (
        sha256_source(CSS), sha256_source(script))
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta http-equiv="Content-Security-Policy" content="%s">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Review: %s</title>\n'
            '<style>%s</style>\n</head>\n<body>\n<main>\n'
            '<p class="warning">This page holds code from the repository: keep it on your machine, do not share it. '
            'Click a line or a section of the guide to comment; keys j and k move, c comments, Escape closes.</p>\n'
            '<p class="warning hidden" id="nostore">This browser does not keep data for local pages: your comments will be lost '
            'when you close it. Finish before closing.</p>\n'
            '<div class="guide">\n%s\n</div>\n%s\n</main>\n'
            '<div class="bar"><span class="status" id="status"></span><button id="finish">Finish</button></div>\n'
            '<div class="panel hidden" id="editor"><p><strong id="editor-where"></strong></p><textarea id="editor-text"></textarea>'
            '<p><button id="editor-save">Save</button> <button class="plain" id="editor-delete">Delete</button> '
            '<button class="plain" id="editor-cancel">Cancel</button></p></div>\n'
            '<div class="panel hidden" id="finish-panel"><p><strong>review-comments.md</strong></p><textarea id="finish-text" readonly></textarea>'
            '<p class="status" id="finish-status"></p><p><button id="download">Download</button> '
            '<button class="plain" id="finish-close">Close</button></p></div>\n'
            '<script type="application/json" id="review-data">%s</script>\n'
            '<script>%s</script>\n</body>\n</html>\n') % (
        csp, html.escape(title), CSS, render_guide(guide), '\n'.join(render_file(f) for f in files), data, script)


def write_page(repo, guide_path, base, out):
    if guide_path.is_symlink():
        raise RepoError('the guide is a symbolic link: refused')
    try:
        guide = guide_path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as error:
        raise RepoError('cannot read the guide: '+str(error))
    root = Path(git(repo, 'rev-parse', '--show-toplevel').strip()).resolve()
    if out.is_symlink():
        raise RepoError('the page path is a symbolic link: refused')
    skip = set()
    for path in (guide_path, out):
        try:
            skip.add(path.absolute().resolve().relative_to(root).as_posix())
        except ValueError:
            pass
    rel_out = next((p for p in skip if p.endswith(out.name)), None)
    if rel_out and git(root, 'ls-files', '--error-unmatch', '--', rel_out, check=False) is not None:
        raise RepoError('the page path is tracked by git: refused')
    merge_base = git(root, 'merge-base', resolve_base(root, base), 'HEAD').strip()
    files, diff_text = change_files(root, merge_base, skip)
    order = guide_order(guide)
    rank = {p: i for i, p in enumerate(order)}
    position = {id(f): i for i, f in enumerate(files)}
    files.sort(key=lambda f: (rank.get(f['path'], len(rank)), position[id(f)]))
    first = next((row[2:].strip() for row in guide.split('\n') if row.startswith('# ')), guide_path.parent.name)
    title = first.split(':', 1)[1].strip() if first.lower().startswith('review guide:') else first
    hasher = hashlib.sha256(diff_text.encode('utf-8'))
    for f in files:
        hasher.update(f['path'].encode('utf-8', 'replace'))
        hasher.update(f.get('data') or b'')
    page = build_page(title, guide, files, hasher.hexdigest()[:16])
    if len(page) > 5_000_000:
        print('review_html.py: the page is %d MB; large files are folded, the rest is shown' % (len(page) // 1_000_000), file=sys.stderr)
    # A temporary file of its own (created, never opened by a name someone could plant), readable by the person only:
    # the page holds the diff.
    descriptor, temp = tempfile.mkstemp(prefix='.'+out.name+'.', suffix='.tmp', dir=str(out.parent))
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(page)
        os.replace(temp, out)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog='review_html.py', description='Write review.html from a review guide and the diff.')
    parser.add_argument('--guide', required=True, help='the review-guide.md of the change')
    parser.add_argument('--base', help='the branch the work merges into (default: origin/HEAD, else main, else master)')
    parser.add_argument('--repo', default='.', help='a folder of the repository (default: the current folder)')
    parser.add_argument('--out', help='the page to write (default: review.html next to the guide)')
    args = parser.parse_args(argv)
    guide = Path(args.guide).absolute()
    out = Path(args.out).absolute() if args.out else guide.parent/'review.html'
    try:
        print(write_page(Path(args.repo).resolve(), guide, args.base, out))
    except (RepoError, OSError, subprocess.SubprocessError) as error:
        print('review_html.py: '+str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
