"""No orphan function or class in the engine and the hooks: every one defined in installer/, runtime/ or scripts/ is named
by some Python code of the repo (a call, an attribute, or a string, for the hooks and modes looked up by name).
2026-11-22: 4.24.1 replaced the last calls of shell_words and command_words in protected-paths.py and left both
functions behind; ruff finds unused imports and variables, never an unused function. Read only: it parses the files."""
import ast
from collections import Counter
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKED = ('installer', 'runtime', 'scripts')
READERS = CHECKED + ('evals', 'tests')
# Named by a framework, not by the code: the entry point, unittest's hooks, ast visitors.
BY_CONVENTION = re.compile(r'^(main|__\w+__|visit_\w+|setUp\w*|tearDown\w*)$')


def python_files(folders):
    for folder in folders:
        for path in sorted((ROOT/folder).rglob('*.py')):
            if '__pycache__' not in path.parts and 'fixtures' not in path.parts:
                yield path


def names_used(paths):
    """Every identifier the code reads: names, attributes, imported names, and the words of its strings. A docstring is
    prose, not a use: a function named only in one is still an orphan (this file's own docstring names two)."""
    used = Counter()
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8'), str(path))
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body
                      and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if id(node) in docstrings:
                continue
            if isinstance(node, ast.Name):
                used[node.id] += 1
            elif isinstance(node, ast.Attribute):
                used[node.attr] += 1
            elif isinstance(node, ast.ImportFrom):
                used.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                used.update(re.findall(r'[A-Za-z_]\w*', node.value))
    return used


def orphans():
    used = names_used(python_files(READERS))
    found = []
    for path in python_files(CHECKED):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'), str(path))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not BY_CONVENTION.match(node.name) \
                    and used[node.name] == 0:
                found.append(str(path.relative_to(ROOT)) + ':' + str(node.lineno) + ' ' + node.name)
    return found


class OrphanTests(unittest.TestCase):
    def test_every_function_of_the_engine_and_the_hooks_is_used(self):
        self.assertEqual(orphans(), [], 'defined but named by no code: remove it, or call it')

    def test_the_check_sees_an_orphan(self):
        source = 'def used():\n    return 1\n\ndef left_behind():\n    return used()\n'
        source = '"""left_behind is named here, in prose only."""\n' + source
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp)/'module.py'
            module.write_text(source, encoding='utf-8')
            used = names_used([module])
        self.assertEqual([name for name in ('used', 'left_behind') if used[name] == 0], ['left_behind'])


if __name__ == '__main__':
    unittest.main()
