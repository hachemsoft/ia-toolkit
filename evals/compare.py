"""Compares two eval reports of the same cases: one with the kit, one without it (run.py --baseline).

Usage: python3 evals/compare.py with-kit.json without-kit.json
No model call: it reads the two JSON files. Both runs must use the same CLI and model, or the comparison says nothing.
Exit code 2 if the reports cannot be compared.
"""
import json
import sys
from pathlib import Path


def load(path):
    report = json.loads(Path(path).read_text(encoding='utf-8'))
    return report.get('meta', {}), {r['name']: r['status'] for r in report.get('results', [])}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    (with_meta, with_kit), (base_meta, without) = load(argv[0]), load(argv[1])
    problems = []
    if with_meta.get('baseline') or not base_meta.get('baseline'):
        problems.append('the first report must be a run with the kit, the second a run with --baseline')
    for key in ('cli', 'model'):
        if with_meta.get(key) != base_meta.get(key):
            problems.append(key + ' differs: ' + str(with_meta.get(key)) + ' / ' + str(base_meta.get(key)))
    if problems:
        print('Not comparable: ' + '; '.join(problems) + '.', file=sys.stderr)
        return 2
    names = sorted(n for n in with_kit if n in without and 'ERROR' not in (with_kit[n], without[n]) and 'SKIP' not in (with_kit[n], without[n]))
    only_kit = [n for n in names if with_kit[n] == 'OK' and without[n] != 'OK']
    only_base = [n for n in names if with_kit[n] != 'OK' and without[n] == 'OK']
    both = sum(1 for n in names if with_kit[n] == without[n] == 'OK')
    print('| Case | With the kit | Without |')
    print('| --- | --- | --- |')
    for n in names:
        print('| ' + n + ' | ' + with_kit[n] + ' | ' + without[n] + ' |')
    print()
    print(str(len(names)) + ' cases compared (' + str(with_meta.get('cli')) + ', model ' + str(with_meta.get('model')) + ')'
          + ('; simulated, not a measure' if with_meta.get('simulated') or base_meta.get('simulated') else '') + ':')
    print('- passed only with the kit: ' + str(len(only_kit)) + (' (' + ', '.join(only_kit) + ')' if only_kit else ''))
    print('- passed only without it: ' + str(len(only_base)) + (' (' + ', '.join(only_base) + ')' if only_base else ''))
    print('- passed with both: ' + str(both))
    left = len([n for n in with_kit if n not in names])
    if left:
        print(str(left) + ' case(s) left out: an infrastructure error or a skip in one of the runs.')
    print('One run of each varies with the model: repeat both before concluding.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
