"""Is NEWS.md well formed? The whats-new hook skips a section it cannot read; this check refuses it before the merge.

Usage: python3 scripts/check_news.py [path to NEWS.md]
Each entry: `## <YYYY-MM-DD> <id> : <title>` (id: 3 to 32 of a-z, 0-9, -; unique), then optional lines
`teams: x` (names of Team repositories; any other metadata such as profiles: is refused), `until: YYYY-MM-DD`, then
the text. Exit code 1 with one line per problem, 0 otherwise. No network, no model call.
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, ROOT)

from installer.news import hook_module, problems  # noqa: E402  (one rule for the CI and ai-kit news --add)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = argv[0] if argv else os.path.join(ROOT, 'NEWS.md')
    try:
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
    except OSError as exc:
        print('Cannot read '+path+': '+str(exc))
        return 1
    found = problems(text)
    for line in found:
        print(line)
    if found:
        return 1
    print(os.path.basename(path)+': '+str(len(hook_module().parse_news(text)))+' entries, well formed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
