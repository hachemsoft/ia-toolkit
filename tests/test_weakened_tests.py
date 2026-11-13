"""runtime/weakened_tests.py: the facts /review reads about tests deleted, moved, disabled or relaxed (spec
docs/sdlc/2026-11-13-spec-anchored-tests/spec.md, ADR 0027). Real temporary Git repositories, no model."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'runtime'/'weakened_tests.py'


def load_module():
    spec = importlib.util.spec_from_file_location('weakened_tests', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Repo:
    """A Git repository in a temporary folder: files committed on main, then changed."""

    def __init__(self, files):
        self.tmp = tempfile.mkdtemp()
        self.path = Path(self.tmp)
        self.git('init', '--quiet', '--initial-branch=main')
        self.write(files)
        self.commit('base')

    def git(self, *args):
        return subprocess.run(['git', '-c', 'user.name=T', '-c', 'user.email=t@example.org', '-c', 'commit.gpgsign=false', *args],
                              cwd=self.path, check=True, capture_output=True, text=True).stdout

    def write(self, files):
        for rel, text in files.items():
            target = self.path/rel
            if text is None:
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8')

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '--quiet', '--allow-empty', '-m', message)

    def run(self, *args):
        proc = subprocess.run([sys.executable, '-I', str(SCRIPT), '--repo', str(self.path), *args], capture_output=True, text=True, timeout=60)
        return proc.returncode, json.loads(proc.stdout)

    def facts(self, *args):
        code, out = self.run(*args)
        self.case.assertEqual(code, 0, out)
        self.case.assertIsNone(out['error'])
        return [(f['kind'], f['path'], f['test'], f['moved_to'], f['family']) for f in out['facts']]

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Base(unittest.TestCase):
    def repo(self, files):
        repo = Repo(files)
        repo.case = self
        self.addCleanup(repo.cleanup)
        return repo


class ScopeAndLevelOneTests(Base):
    def test_outside_a_repository_exits_2_with_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run([sys.executable, '-I', str(SCRIPT), '--repo', tmp], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 2)
        out = json.loads(proc.stdout)
        self.assertEqual(out['schema'], 1)
        self.assertTrue(out['error'])
        self.assertEqual(out['facts'], [])

    def test_nothing_changed_gives_no_fact(self):
        repo = self.repo({'src/export.py': 'x = 1\n', 'tests/test_export.py': 'def test_x():\n    assert True\n'})
        code, out = repo.run()
        self.assertEqual((code, out['facts'], out['error']), (0, [], None))
        self.assertEqual(set(out), {'schema', 'base', 'merge_base', 'error', 'facts', 'families_seen', 'files_unrecognized', 'files_unreadable', 'truncated'})

    def test_deleted_test_file_is_a_fact_and_a_deleted_source_file_is_not(self):
        repo = self.repo({'src/export.py': 'x = 1\n', 'tests/test_export.py': 'def test_x():\n    assert True\n'})
        repo.write({'src/export.py': None, 'tests/test_export.py': None})
        self.assertEqual(repo.facts(), [('test_file_deleted', 'tests/test_export.py', None, None, None)])

    def test_every_generic_test_folder_is_recognized(self):
        files = {d+'/check.txt': 'x\n' for d in ('test', 'tests', '__tests__', 'spec', 'app/test')}
        repo = self.repo(files)
        repo.write({p: None for p in files})
        self.assertEqual(sorted(f[1] for f in repo.facts()), sorted(files))

    def test_staged_unstaged_and_committed_deletions_are_all_seen(self):
        repo = self.repo({'tests/a.py': 'a\n', 'tests/b.py': 'b\n', 'tests/c.py': 'c\n'})
        repo.git('checkout', '--quiet', '-b', 'feature')
        repo.git('rm', '--quiet', 'tests/a.py')
        repo.commit('committed deletion')
        repo.git('rm', '--quiet', 'tests/b.py')  # staged
        repo.write({'tests/c.py': None})  # unstaged
        self.assertEqual([f[1] for f in repo.facts('--base', 'main')], ['tests/a.py', 'tests/b.py', 'tests/c.py'])

    def test_renamed_test_file_is_moved_not_deleted(self):
        repo = self.repo({'tests/test_a.py': 'def test_a():\n    assert 1 == 1\n' * 5})
        repo.git('mv', 'tests/test_a.py', 'tests/test_b.py')
        self.assertEqual(repo.facts(), [('test_moved', 'tests/test_a.py', None, 'tests/test_b.py', None)])

    def test_test_file_moved_without_git_is_moved_not_deleted(self):
        repo = self.repo({'tests/test_a.py': 'def test_a():\n    assert 1 == 1\n'})
        (repo.path/'tests/test_a.py').rename(repo.path/'tests/test_b.py')  # untracked new file, tracked file gone
        self.assertEqual(repo.facts(), [('test_moved', 'tests/test_a.py', None, 'tests/test_b.py', None)])

    def test_output_is_stable(self):
        repo = self.repo({'tests/a.py': 'a\n', 'tests/b.py': 'b\n'})
        repo.write({'tests/a.py': None, 'tests/b.py': None})
        self.assertEqual(repo.run(), repo.run())

    def test_unknown_base_exits_2(self):
        repo = self.repo({'a.txt': 'a\n'})
        code, out = repo.run('--base', 'no-such-branch')
        self.assertEqual(code, 2)
        self.assertIn('no-such-branch', out['error'])

    def test_read_only_git_and_no_write(self):
        repo = self.repo({'tests/a.py': 'a\n', 'models/x.sql': 'select 1\n'})
        repo.write({'tests/a.py': None})
        before = sorted((p.relative_to(repo.path).as_posix(), p.stat().st_mtime_ns) for p in repo.path.rglob('*') if '.git' not in p.parts)
        status = repo.git('status', '--porcelain')
        module = load_module()
        calls = []
        real = subprocess.run
        def spy(args, *a, **k):
            calls.append(args)
            return real(args, *a, **k)
        with mock.patch.object(module.subprocess, 'run', side_effect=spy), mock.patch('sys.stdout', new=open(os.devnull, 'w', encoding='utf-8')) as sink:
            module.main(['--repo', str(repo.path)])
            sink.close()
        subcommands = {next(w for w in c[1:] if not w.startswith('-') and '=' not in w and w != str(repo.path)) for c in calls}
        self.assertLessEqual(subcommands, {'rev-parse', 'merge-base', 'diff', 'show', 'ls-files'}, calls)
        self.assertTrue(all(c[0] == 'git' and 'core.hooksPath='+os.devnull in c for c in calls), calls)
        after = sorted((p.relative_to(repo.path).as_posix(), p.stat().st_mtime_ns) for p in repo.path.rglob('*') if '.git' not in p.parts)
        self.assertEqual((before, status), (after, repo.git('status', '--porcelain')))

    def test_many_facts_are_truncated(self):
        files = {'tests/t%03d.py' % i: 'x\n' for i in range(205)}
        repo = self.repo(files)
        repo.write({p: None for p in files})
        code, out = repo.run()
        self.assertEqual((code, len(out['facts']), out['truncated']), (0, 200, {'test_file_deleted': 205}))


DBT_PROJECT = "name: shop\nversion: '1.0'\nprofile: shop\n"
SCHEMA = """version: 2
models:
  - name: orders
    tests:
      - dbt_utils.expression_is_true:
          expression: "amount >= 0"
    columns:
      - name: order_id
        tests:
          - unique
          - not_null
      - name: amount
        data_tests:
          - not_null:
              config:
                severity: error
                error_if: ">0"
          - accepted_values:
              values: ['EUR', 'USD']
"""


class DbtTests(Base):
    def dbt(self, extra=None):
        return self.repo({'dbt_project.yml': DBT_PROJECT, 'models/schema.yml': SCHEMA, 'models/orders.sql': 'select 1\n',
                          'tests/assert_positive.sql': 'select * from x where amount < 0\n', **(extra or {})})

    def changed(self, old, new, repo=None):
        repo = repo or self.dbt()
        assert old in SCHEMA, old
        repo.write({'models/schema.yml': SCHEMA.replace(old, new)})
        return repo.facts()

    def test_singular_test_deleted_is_a_dbt_fact(self):
        repo = self.dbt()
        repo.write({'tests/assert_positive.sql': None})
        self.assertEqual(repo.facts(), [('test_file_deleted', 'tests/assert_positive.sql', None, None, 'dbt')])

    def test_generic_test_removed(self):
        facts = self.changed('          - unique\n          - not_null\n', '          - unique\n')
        self.assertEqual(facts, [('test_removed', 'models/schema.yml', 'orders.order_id.not_null', None, 'dbt')])

    def test_model_level_test_removed(self):
        facts = self.changed('    tests:\n      - dbt_utils.expression_is_true:\n          expression: "amount >= 0"\n', '')
        self.assertEqual(facts, [('test_removed', 'models/schema.yml', 'orders.dbt_utils.expression_is_true', None, 'dbt')])

    def test_severity_lowered(self):
        self.assertEqual([f[0] for f in self.changed('severity: error', 'severity: warn')], ['severity_lowered'])

    def test_threshold_relaxed_and_tightened(self):
        self.assertEqual([f[0] for f in self.changed('error_if: ">0"', 'error_if: ">100"')], ['threshold_relaxed'])
        repo = self.dbt()
        repo.write({'models/schema.yml': SCHEMA.replace('error_if: ">0"', 'error_if: ">100"')})
        repo.commit('relaxed')
        repo.write({'models/schema.yml': SCHEMA})
        self.assertEqual(repo.facts('--base', 'HEAD'), [])

    def test_disabled(self):
        facts = self.changed('                severity: error\n', '                severity: error\n                enabled: false\n')
        self.assertEqual([(f[0], f[2]) for f in facts], [('test_disabled', 'orders.amount.not_null')])

    def test_changed_arguments_are_left_to_the_review(self):
        facts = self.changed("values: ['EUR', 'USD']", "values: ['EUR', 'USD', 'GBP']")
        self.assertEqual([(f[0], f[2]) for f in facts], [('assertion_changed', 'orders.amount.accepted_values')])

    def test_inline_config_is_read(self):
        repo = self.dbt()
        repo.write({'models/schema.yml': SCHEMA.replace('          - not_null\n', '          - not_null: {config: {severity: warn}}\n')})
        self.assertEqual([(f[0], f[2]) for f in repo.facts()], [('severity_lowered', 'orders.order_id.not_null')])

    def test_test_moved_to_another_yaml_file(self):
        repo = self.dbt()
        repo.write({'models/schema.yml': SCHEMA.replace('          - not_null\n', '', 1),
                    'models/more.yml': 'version: 2\nmodels:\n  - name: orders\n    columns:\n      - name: order_id\n        tests:\n          - not_null\n'})
        self.assertEqual(repo.facts(), [('test_moved', 'models/schema.yml', 'orders.order_id.not_null', 'models/more.yml', 'dbt')])

    def test_deleted_yaml_file_removes_its_tests(self):
        repo = self.dbt({'models/other.yml': 'version: 2\nmodels:\n  - name: customers\n    columns:\n      - name: id\n        tests: [unique, not_null]\n'})
        repo.write({'models/other.yml': None})
        self.assertEqual([f[2] for f in repo.facts()], ['customers.id.not_null', 'customers.id.unique'])

    def test_project_wide_severity_lowered(self):
        repo = self.dbt()
        repo.write({'dbt_project.yml': DBT_PROJECT + 'data_tests:\n  shop:\n    +severity: warn\n'})
        self.assertEqual([(f[0], f[1]) for f in repo.facts()], [('severity_lowered', 'dbt_project.yml')])

    def test_project_wide_tests_disabled(self):
        repo = self.dbt()
        repo.write({'dbt_project.yml': DBT_PROJECT + 'tests:\n  +enabled: false\n'})
        self.assertEqual([(f[0], f[1]) for f in repo.facts()], [('test_disabled', 'dbt_project.yml')])

    def test_unreadable_yaml_gives_no_fact(self):
        repo = self.dbt()
        repo.write({'models/schema.yml': SCHEMA.replace('version: 2', 'version: 2\nanchors: &base\n  a: 1') + 'x: *base\n'})
        self.assertEqual(repo.facts(), [])

    def test_dbt_project_in_a_subfolder(self):
        repo = self.repo({'analytics/dbt_project.yml': DBT_PROJECT, 'analytics/models/schema.yml': SCHEMA})
        repo.write({'analytics/models/schema.yml': SCHEMA.replace('          - not_null\n', '', 1)})
        self.assertEqual(repo.facts(), [('test_removed', 'analytics/models/schema.yml', 'orders.order_id.not_null', None, 'dbt')])

    def test_yaml_outside_a_dbt_project_is_ignored(self):
        repo = self.repo({'config/schema.yml': SCHEMA})
        repo.write({'config/schema.yml': None})
        self.assertEqual(repo.facts(), [])


class ReviewFindingsTests(Base):
    """Cases from the review of slice 1: no silent loss, no false fact on a legitimate refactoring."""

    def dbt(self, extra=None):
        return self.repo({'dbt_project.yml': DBT_PROJECT, 'models/schema.yml': SCHEMA, **(extra or {})})

    def drop_not_null(self, repo):
        repo.write({'models/schema.yml': SCHEMA.replace('          - not_null\n', '', 1)})

    def test_ci_yaml_at_the_root_is_not_a_properties_file(self):
        repo = self.dbt({'.gitlab-ci.yml': '.defaults: &defaults\n  image: x\njob:\n  <<: *defaults\n',
                         '.github/workflows/ci.yml': 'jobs:\n  build:\n    name: Build\n    tests: [unit, e2e]\n'})
        repo.write({'.gitlab-ci.yml': '.defaults: &defaults\n  image: y\njob:\n  <<: *defaults\n',
                    '.github/workflows/ci.yml': 'jobs:\n  build:\n    name: Build\n    tests: [unit]\n'})
        self.drop_not_null(repo)
        self.assertEqual([f[0] for f in repo.facts()], ['test_removed'])

    def test_one_unreadable_file_does_not_hide_the_others(self):
        repo = self.dbt({'models/other.yml': 'version: 2\nmodels:\n  - name: c\n    columns:\n      - name: id\n        tests: [unique]\n'})
        repo.write({'models/other.yml': 'version: 2\nx: &a\n  b: 1\n'})
        self.drop_not_null(repo)
        code, out = repo.run()
        self.assertEqual([f['kind'] for f in out['facts']], ['test_removed'])
        self.assertEqual(out['files_unreadable'], ['models/other.yml'])

    def test_quoted_stars_and_ampersands_and_multi_line_scalars_are_read(self):
        text = SCHEMA.replace('    columns:\n', '    description: "Total *before* tax & fees"\n    columns:\n', 1)
        text = text.replace('      - name: order_id\n', '      - name: order_id\n        description: a long text\n          that goes on\n', 1)
        text = text.replace('                severity: error\n', '                severity: error\n                where: "amount != 0"\n', 1)
        repo = self.repo({'dbt_project.yml': DBT_PROJECT, 'models/schema.yml': text})
        repo.write({'models/schema.yml': text.replace('          - not_null\n', '', 1)})
        code, out = repo.run()
        self.assertEqual(([f['kind'] for f in out['facts']], out['files_unreadable']), (['test_removed'], []))

    def test_multi_line_flow_mapping_is_read(self):
        text = SCHEMA.replace('    columns:\n', '    meta: {owner: finance,\n      pii: false}\n    columns:\n', 1)
        repo = self.repo({'dbt_project.yml': DBT_PROJECT, 'models/schema.yml': text})
        repo.write({'models/schema.yml': text.replace('          - not_null\n', '', 1)})
        code, out = repo.run()
        self.assertEqual((code, [f['kind'] for f in out['facts']]), (0, ['test_removed']))

    def test_unterminated_flow_is_unreadable_not_a_crash(self):
        repo = self.dbt()
        repo.write({'models/schema.yml': SCHEMA + 'meta: {owner: finance,\n'})
        code, out = repo.run()
        self.assertEqual((code, out['facts'], out['files_unreadable']), (0, [], ['models/schema.yml']))

    def test_renamed_model_moves_its_tests(self):
        repo = self.dbt()
        repo.write({'models/schema.yml': SCHEMA.replace('  - name: orders\n', '  - name: fct_orders\n')})
        kinds = {f[0] for f in repo.facts()}
        self.assertEqual(kinds, {'test_moved'})

    def test_naming_a_test_moves_it(self):
        repo = self.dbt()
        repo.write({'models/schema.yml': SCHEMA.replace('          - unique\n', '          - name: uq_order_id\n            test_name: unique\n', 1)})
        self.assertEqual([f[0] for f in repo.facts()], ['test_moved'])

    def test_test_file_moved_and_edited_without_git_is_moved(self):
        body = ''.join('def test_%d():\n    assert %d == %d\n' % (i, i, i) for i in range(8))
        repo = self.repo({'tests/test_a.py': body})
        (repo.path/'tests/test_a.py').unlink()
        repo.write({'tests/test_b.py': body + 'def test_new():\n    assert True\n'})
        self.assertEqual([f[0] for f in repo.facts()], ['test_moved'])

    def test_test_file_moved_with_windows_line_endings_is_moved(self):
        body = 'def test_a():\n    assert 1 == 1\n' * 4
        repo = self.repo({'tests/test_a.py': body})
        (repo.path/'tests/test_a.py').unlink()
        (repo.path/'tests/test_b.py').write_bytes(body.replace('\n', '\r\n').encode('utf-8'))
        self.assertEqual([f[0] for f in repo.facts()], ['test_moved'])

    def test_nested_dbt_projects_give_each_fact_once(self):
        repo = self.repo({'dbt_project.yml': DBT_PROJECT, 'integration_tests/dbt_project.yml': DBT_PROJECT,
                          'integration_tests/models/schema.yml': SCHEMA})
        repo.write({'integration_tests/models/schema.yml': SCHEMA.replace('          - not_null\n', '', 1)})
        self.assertEqual(len(repo.facts()), 1)

    def test_new_project_and_inherited_severity_are_not_lowered(self):
        repo = self.repo({'a.txt': 'a\n'})
        repo.write({'dbt_project.yml': DBT_PROJECT + 'data_tests:\n  +severity: warn\n'})
        self.assertEqual(repo.facts(), [])
        repo = self.repo({'dbt_project.yml': DBT_PROJECT + 'data_tests:\n  +severity: warn\n'})
        repo.write({'dbt_project.yml': DBT_PROJECT + 'data_tests:\n  +severity: warn\n  shop:\n    +severity: warn\n'})
        self.assertEqual(repo.facts(), [])

    def test_quoted_false_disables(self):
        facts = DbtTests.changed(self, '                severity: error\n', '                severity: error\n                enabled: "false"\n')
        self.assertEqual([f[0] for f in facts], ['test_disabled'])

    def test_custom_test_and_model_paths(self):
        project = DBT_PROJECT + "model-paths: ['transform']\ntest-paths: ['checks']\n"
        repo = self.repo({'dbt_project.yml': project, 'transform/schema.yml': SCHEMA, 'checks/assert_x.sql': 'select 1\n'})
        repo.write({'transform/schema.yml': SCHEMA.replace('          - not_null\n', '', 1), 'checks/assert_x.sql': None})
        self.assertEqual(sorted((f[0], f[4]) for f in repo.facts()), [('test_file_deleted', 'dbt'), ('test_removed', 'dbt')])

    def test_sorted_by_file_then_line(self):
        repo = self.dbt()
        repo.write({'models/schema.yml': SCHEMA.replace('severity: error', 'severity: warn').replace('          - not_null\n', '', 1)})
        code, out = repo.run()
        lines = [f['line'] for f in out['facts']]
        self.assertEqual(lines, sorted(lines))

    def test_families_seen_and_truncated_without_facts(self):
        repo = self.dbt()
        repo.write({'models/orders.sql': 'select 2\n'})
        code, out = repo.run()
        self.assertEqual((out['families_seen'], out['truncated']), (['dbt'], None))

    def test_modified_test_files_without_family_rules_are_counted(self):
        repo = self.repo({'tests/a.py': 'a\n', 'tests/b.py': 'b\n'})
        repo.write({'tests/a.py': 'a2\n'})
        repo.git('add', 'tests/a.py')
        repo.write({'tests/b.py': 'b2\n', 'tests/c.py': 'c\n'})
        code, out = repo.run()
        self.assertEqual((out['facts'], out['files_unrecognized']), ([], 3))

    def test_the_index_is_left_alone(self):
        repo = self.repo({'tests/a.py': 'a\n'})
        repo.write({'tests/a.py': None})
        index = repo.path/'.git'/'index'
        before = (index.read_bytes(), index.stat().st_mtime_ns)
        repo.run()
        self.assertEqual(before, (index.read_bytes(), index.stat().st_mtime_ns))


class ReviewTextTests(unittest.TestCase):
    """The review runs the script and judges its facts (spec, requirements 11 and 12)."""

    def test_the_skill_runs_the_script_and_judges_its_facts(self):
        skill = (ROOT/'skills/internal/common/code-review/SKILL.md').read_text(encoding='utf-8')
        for needed in ('python3 ~/.ai-kit/bin/weakened_tests.py', 'py -3', '**Tests**', 'Important', 'commit message',
                       'not checked', 'intended test change'):
            self.assertIn(needed, skill)

    def test_the_command_lists_the_tests_pass(self):
        self.assertIn('Tests (', (ROOT/'commands/review.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
