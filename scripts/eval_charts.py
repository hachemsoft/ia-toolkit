"""Draws the eval charts of the README from evals/results/*.json: SVG files in docs/img/, one light and one dark each.

Usage: python3 scripts/eval_charts.py [evals/results/2026-11-01.json]
No dependency, no model call: it reads the results file and writes three charts, each in two themes.
"""
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
THEMES = {
    'light': {'surface': '#fcfcfb', 'text': '#0b0b0b', 'muted': '#52514e', 'grid': '#e4e3df', 'kit': '#2a78d6', 'nokit': '#eb6834'},
    'dark': {'surface': '#1a1a19', 'text': '#f0efec', 'muted': '#c3c2b7', 'grid': '#3a3a37', 'kit': '#3987e5', 'nokit': '#d95926'},
}
FONT = "font-family='-apple-system, Segoe UI, Helvetica, Arial, sans-serif'"
CASES = [('fuzzy-request-aligns-first', 'Asks the deciding question before SQL'),
         ('secret-kept-out-of-code', 'Keeps an API key out of the code'),
         ('red-suite-keeps-its-test', 'Keeps a failing test, raises the contract')]


def version(v):
    return tuple(int(x) for x in v.split('.'))


def svg(width, height, theme, title, body):
    t = THEMES[theme]
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}' role='img' {FONT}>"
            f"<title>{escape(title)}</title><rect width='{width}' height='{height}' rx='8' fill='{t['surface']}'/>" + body + '</svg>\n')


def text(x, y, value, fill, size=13, anchor='start', weight='400'):
    return f"<text x='{x}' y='{y}' font-size='{size}' fill='{fill}' text-anchor='{anchor}' font-weight='{weight}'>{escape(value)}</text>"


def legend(x, y, t):
    return (f"<rect x='{x}' y='{y - 9}' width='10' height='10' rx='2' fill='{t['kit']}'/>" + text(x + 16, y, 'With the kit', t['muted'], 12)
            + f"<rect x='{x + 110}' y='{y - 9}' width='10' height='10' rx='2' fill='{t['nokit']}'/>" + text(x + 126, y, 'Without the kit', t['muted'], 12))


def bars(runs, theme):
    """Per case: share of runs that pass, with the current kit (0.45.4 or later, where the framing rule exists) and without."""
    t = THEMES[theme]
    width, left, plot = 720, 290, 330
    rows = []
    for case, label in CASES:
        def count(kit_side):
            picked = [r for r in runs if r['case'] == case and r['status'] != 'ERROR'
                      and (r['kit'] is None if not kit_side else r['kit'] and version(r['kit']) >= (0, 45, 4))]
            return sum(r['status'] == 'OK' for r in picked), len(picked)
        rows.append((label, count(True), count(False)))
    body = text(24, 34, 'Plain-words tasks: with and without the kit', t['text'], 16, weight='600')
    body += text(24, 54, 'Claude Code 2.1.316 and Codex CLI 0.164.0, kit 0.45.4+, 2 runs per CLI and side, 1 Nov 2026', t['muted'], 12)
    body += legend(24, 80, t)
    y = 110
    for x in (0, 0.5, 1):
        gx = left + plot * x
        body += f"<line x1='{gx}' y1='{y - 8}' x2='{gx}' y2='{y + len(rows) * 62 - 14}' stroke='{t['grid']}' stroke-width='1'/>"
        body += text(gx, y + len(rows) * 62, f'{int(x * 100)} %', t['muted'], 11, 'middle')
    for label, (k_ok, k_n), (n_ok, n_n) in rows:
        body += text(24, y + 16, label, t['text'], 13)
        for i, (ok, n, color) in enumerate(((k_ok, k_n, t['kit']), (n_ok, n_n, t['nokit']))):
            by = y + i * 22
            w = max(plot * ok / n, 0) if n else 0
            if w:
                body += f"<rect x='{left}' y='{by}' width='{w:.1f}' height='18' rx='4' fill='{color}'/>"
            else:
                body += f"<rect x='{left}' y='{by}' width='3' height='18' rx='1.5' fill='{color}'/>"
            body += text(left + max(w, 3) + 8, by + 13, f'{ok}/{n}', t['text'], 12, weight='600')
        y += 62
    return svg(width, y + 34, theme, 'Plain-words tasks passed with and without the kit', body)


def framing(runs, theme):
    """The fuzzy-request case, run by run: no kit, then each kit version. 0.45.4 added one rule to the kit context."""
    t = THEMES[theme]
    columns = [None, '0.45.3', '0.45.4', '0.45.5']
    headers = ['No kit', 'Kit 0.45.3', 'Kit 0.45.4', 'Kit 0.45.5']
    clis = ['Claude Code 2.1.316', 'Codex CLI 0.164.0']
    width, left, col = 720, 200, 125
    body = text(24, 34, 'Asks the deciding question before writing SQL', t['text'], 16, weight='600')
    body += text(24, 54, "Case fuzzy-request-aligns-first: one mark per run. Kit 0.45.4 added one rule to the kit's context.", t['muted'], 12)
    for i, h in enumerate(headers):
        body += text(left + i * col + col / 2, 88, h, t['muted'], 12, 'middle', '600')
    body += f"<line x1='{left + col}' y1='72' x2='{left + col}' y2='{100 + len(clis) * 44}' stroke='{t['grid']}' stroke-width='1'/>"
    y = 114
    for cli in clis:
        body += text(24, y + 5, cli, t['text'], 13)
        for i, kit in enumerate(columns):
            picked = [r for r in runs if r['case'] == 'fuzzy-request-aligns-first' and r['cli'] == cli and r['kit'] == kit and r['status'] != 'ERROR']
            cx = left + i * col + col / 2 - (len(picked) - 1) * 13
            if not picked:
                body += text(left + i * col + col / 2, y + 5, 'not run', t['muted'], 11, 'middle')
            for j, r in enumerate(picked):
                x = cx + j * 26
                if r['status'] == 'OK':
                    body += f"<circle cx='{x}' cy='{y}' r='9' fill='{t['kit']}'/><path d='M{x - 4} {y} l3 3 l5 -6' stroke='{t['surface']}' stroke-width='2' fill='none' stroke-linecap='round'/>"
                else:
                    body += f"<circle cx='{x}' cy='{y}' r='8' fill='none' stroke='{t['nokit']}' stroke-width='2'/><path d='M{x - 3.5} {y - 3.5} l7 7 M{x + 3.5} {y - 3.5} l-7 7' stroke='{t['nokit']}' stroke-width='2' stroke-linecap='round'/>"
        y += 44
    body += f"<circle cx='30' cy='{y + 6}' r='6' fill='{t['kit']}'/>" + text(42, y + 10, 'asked first', t['muted'], 12)
    body += f"<circle cx='140' cy='{y + 6}' r='5.5' fill='none' stroke='{t['nokit']}' stroke-width='2'/>" + text(152, y + 10, 'wrote SQL without asking', t['muted'], 12)
    return svg(width, y + 34, theme, 'Framing a fuzzy request, run by run', body)


def audit(scores, theme):
    """The audit's eight axes, out of 5: 0.40 and 0.45.8."""
    t = THEMES[theme]
    before, after = scores['0.40'], scores['0.45.8']
    axes = sorted(after, key=lambda a: (-after[a], a))
    width, left, plot = 720, 200, 420
    body = text(24, 34, 'Audit scores, out of 5', t['text'], 16, weight='600')
    body += text(24, 54, f"Average {sum(before.values()) / 8:.1f} in 0.40, {sum(after.values()) / 8:.1f} in 0.45.8", t['muted'], 12)
    body += (f"<circle cx='30' cy='76' r='5' fill='{t['nokit']}'/>" + text(42, 80, '0.40', t['muted'], 12)
             + f"<circle cx='90' cy='76' r='5' fill='{t['kit']}'/>" + text(102, 80, '0.45.8', t['muted'], 12))
    y = 108
    for s in range(6):
        gx = left + plot * s / 5
        body += f"<line x1='{gx}' y1='{y - 12}' x2='{gx}' y2='{y + len(axes) * 30 - 18}' stroke='{t['grid']}' stroke-width='1'/>"
        body += text(gx, y + len(axes) * 30, str(s), t['muted'], 11, 'middle')
    for axis in axes:
        b, a = left + plot * before[axis] / 5, left + plot * after[axis] / 5
        body += text(24, y + 4, axis, t['text'], 13)
        body += f"<line x1='{b}' y1='{y}' x2='{a}' y2='{y}' stroke='{t['muted']}' stroke-width='2'/>"
        if a != b:
            body += f"<circle cx='{b}' cy='{y}' r='6' fill='{t['nokit']}' stroke='{t['surface']}' stroke-width='2'/>"
        body += f"<circle cx='{a}' cy='{y}' r='6' fill='{t['kit']}' stroke='{t['surface']}' stroke-width='2'/>"
        label = f"{after[axis]:g}".replace('.', ',') if False else f"{after[axis]:g}"
        body += text(a + 12, y + 4, label, t['text'], 12, weight='600')
        y += 30
    return svg(width, y + 30, theme, 'Audit scores out of 5, 0.40 and 0.45.8', body)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    # The charts read the latest results file that carries the with/without comparison and the audit scores.
    charted = [p for p in sorted((ROOT / 'evals' / 'results').glob('*.json')) if 'audit' in json.loads(p.read_text(encoding='utf-8'))]
    source = Path(argv[0]) if argv else charted[-1]
    data = json.loads(source.read_text(encoding='utf-8'))
    out = ROOT / 'docs' / 'img'
    out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (out / f'evals-with-without-{theme}.svg').write_text(bars(data['runs'], theme), encoding='utf-8')
        (out / f'evals-framing-{theme}.svg').write_text(framing(data['runs'], theme), encoding='utf-8')
        (out / f'audit-scores-{theme}.svg').write_text(audit(data['audit'], theme), encoding='utf-8')
    print('Charts written to', out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
