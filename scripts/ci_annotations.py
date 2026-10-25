"""Publishes each failing test as a GitHub Actions annotation (::error), readable without opening the logs.

Usage in CI, after `python -m unittest ... 2>&1 | tee test-output.txt`: python scripts/ci_annotations.py test-output.txt
"""
import re
import sys

SEPARATOR = re.compile(r'^(=+|-+)$')


def failures(text):
    """(title, detail) for each FAIL: or ERROR: block of the unittest output."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.match(r'^(FAIL|ERROR): ', line):
            continue
        detail = []
        for follow in lines[index+2:]:
            if SEPARATOR.match(follow) and detail:
                break
            detail.append(follow)
        yield line, '\n'.join(detail[-25:])


def escape(value):
    return value.replace('%', '%25').replace('\r', '').replace('\n', '%0A')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')  # Windows console in cp1252: tracebacks may contain non-ASCII characters
    with open(sys.argv[1], encoding='utf-8', errors='replace') as handle:
        output = handle.read()
    for title, detail in failures(output):
        print('::error title='+escape(title.replace(',', ' ').replace(':', ' '))+'::'+escape(detail))
