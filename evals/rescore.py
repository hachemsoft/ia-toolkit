"""Judges recorded answers again with the current criteria of their case, turn by turn, without a model.

After widening or narrowing a criterion, run it on the reports that judged that case: the earlier verdicts must stay, and
only the answers the change was meant for may move (AGENTS.md). Only the answer is judged again (the model's stdout of
each turn); file and git criteria (files_present, unchanged, file_regex) need the run's temporary copy, which is gone.

Usage: python3 evals/rescore.py [--cases evals/cases] [--only name] report.json [...]
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402  (evals/run.py: load_cases, check)

TURN = '=== turn '
STDERR = '\n--- stderr ---\n'


def turns_of(output):
    """[(turn number, answer)] of a recorded output: the runner marks each turn of a multi-turn case and appends stderr."""
    if not output.startswith(TURN):
        return [(1, output.split(STDERR, 1)[0])]
    found = []
    for chunk in output.split(TURN)[1:]:
        number, _, rest = chunk.partition(' ===\n')
        if number.isdigit():
            found.append((int(number), rest.split(STDERR, 1)[0]))
    return found


def expectation(case, number):
    turns = case.get('turns', [])
    if number == 1:
        return case['expect']
    return turns[number - 2]['expect'] if number - 2 < len(turns) else None


def main(argv=None):
    parser = argparse.ArgumentParser(description='Judge recorded answers again with the current criteria, without a model.')
    parser.add_argument('reports', nargs='+', type=Path)
    parser.add_argument('--cases', type=Path, default=Path(__file__).resolve().parent/'cases')
    parser.add_argument('--only')
    args = parser.parse_args(argv)
    cases = {case['name']: case for case in run.load_cases(args.cases)}
    for report in args.reports:
        data = json.loads(report.read_text(encoding='utf-8'))
        cli = data.get('meta', {}).get('cli', '?')
        for result in data.get('results', []):
            name = result.get('name')
            if args.only and name != args.only:
                continue
            case = cases.get(name)
            head = report.name + ' | ' + str(cli) + ' | ' + str(name) + ' | recorded ' + str(result.get('status'))
            if case is None:
                print(head + ' | no such case in ' + str(args.cases))
                continue
            print(head + ' (answers only, files not re-checked)')
            for number, answer in turns_of(result.get('output', '')):
                expect = expectation(case, number)
                if expect is None:
                    print('  turn ' + str(number) + ': no such turn in the case now')
                    continue
                failures = run.check(answer, expect)
                print('  turn ' + str(number) + ': ' + ('OK' if not failures else 'FAIL ' + ' ; '.join(failures)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
