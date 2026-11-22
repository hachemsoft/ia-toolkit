"""The kit's helper scripts on the cases they missed: a friction lock left by a process that died, what a friction never
keeps, a proof that sets the approved test aside, a warehouse command behind a runner, test files next to the code and
dbt's own tests. Temporary folders and real temporary Git repositories: no network, no model."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))
from test_prove_test import Repo as ProofRepo  # noqa: E402
from test_weakened_tests import Base as WeakenedBase, DBT_PROJECT  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location('helper_'+name, ROOT/'runtime'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


friction = load('friction')
prove_test = load('prove_test')
OLD = {'ts': '2000-01-01T00:00:00Z', 'text': 'an old friction', 'category': 'other'}
NEW = {'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'text': 'a recent friction', 'category': 'other'}


class FrictionLockTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        (self.home/'.ai-kit').mkdir()
        self.file = self.home/'.ai-kit/frictions.jsonl'
        self.file.write_text(json.dumps(OLD)+'\n'+json.dumps(NEW)+'\n', encoding='utf-8')
        self.lock = Path(str(self.file)+'.lock')

    def kept(self):
        return [json.loads(line)['text'] for line in self.file.read_text(encoding='utf-8').splitlines()]

    def test_a_lock_left_by_a_process_that_died_no_longer_stops_the_purge(self):
        self.lock.write_text('', encoding='utf-8')
        long_ago = time.time() - 3600
        os.utime(self.lock, (long_ago, long_ago))
        self.assertEqual(friction.housekeep(str(self.home))['purged'], 1)
        self.assertEqual(self.kept(), ['a recent friction'])
        self.assertFalse(self.lock.exists())

    def test_a_lock_another_process_just_took_is_respected(self):
        self.lock.write_text('', encoding='utf-8')
        self.assertEqual(friction.housekeep(str(self.home))['purged'], 0)
        self.assertEqual(len(self.kept()), 2)
        self.assertTrue(self.lock.exists())


class FrictionWordsTests(unittest.TestCase):
    def test_what_is_left_to_send_names_the_command_the_person_runs(self):
        entries = [{'id': 'a1', 'text': 'x'}, {'id': 'b2', 'text': 'y'}]
        with mock.patch.object(friction, 'tracker', return_value={'kind': 'gitlab'}), mock.patch.object(friction, 'unsent', return_value=entries), \
                mock.patch.object(friction, 'send', return_value=('failed', 'glab not signed in')):
            lines = friction.sync('/nowhere')
        self.assertIn('ai-kit friction --publish', lines[-1])
        self.assertNotIn('--sync', ' '.join(lines))

    def test_temporary_cloud_keys_and_gitlab_runner_and_deploy_tokens_are_never_kept(self):
        for secret in ('ASIA' + 'Y34FZKBOKMUTVV7A', 'glrt-' + 'x9Kd72mPqLw8ZtR4vN1c', 'gldt-' + 'x9Kd72mPqLw8ZtR4vN1c'):
            self.assertNotIn(secret, friction.redact('the job printed ' + secret + ' in its log'), secret[:5])

    def test_a_windows_home_written_with_forward_slashes_names_nobody(self):
        for text in ('C:/Users/jdupont/repo/app.py', 'c:/users/jdupont/repo', r'D:\Users\jdupont\repo'):
            shown = friction.redact('failed in ' + text)
            self.assertNotIn('jdupont', shown, text)
            self.assertIn('~', shown)


class ProofFileTests(unittest.TestCase):
    def test_conftest_is_a_test_file(self):
        self.assertTrue(prove_test.is_test_path('conftest.py'))
        self.assertTrue(prove_test.is_test_path('pkg/conftest.py'))
        self.assertFalse(prove_test.is_test_path('pkg/config.py'))

    @unittest.skipUnless(shutil.which('git'), 'git is not installed')
    def test_code_renamed_into_the_approved_test_keeps_the_test_during_the_proof(self):
        body = ''.join('def check_%d(value):\n    return value == %d\n\n\n' % (i, i) for i in range(12))
        repo = ProofRepo({'checks.py': body, 'calc.py': 'def add(a, b):\n    return a - b\n'})
        self.addCleanup(repo.cleanup)
        repo.git('mv', 'checks.py', 'test_checks.py')  # git sees a rename: the file barely changes
        repo.write({'test_checks.py': body + 'assert check_1(1)\n', 'calc.py': 'def add(a, b):\n    return a + b\n'})
        before = repo.state()
        seen = repo.path/'seen.txt'
        probe = ('import os, pathlib; pathlib.Path(%r).write_text(",".join(n for n in ("test_checks.py", "checks.py") if os.path.exists(n)), encoding="utf-8")' % str(seen))
        code, out = repo.run('prove', '--test', 'test_checks.py', '--keep', 'seen.txt', '--', sys.executable, '-c', probe)
        self.assertEqual(code, 0, out)
        self.assertEqual(seen.read_text(encoding='utf-8'), 'test_checks.py,checks.py', out)  # the test stayed; the code it came from is back
        self.assertNotIn('test_checks.py', out['swapped'])
        seen.unlink()
        self.assertEqual(repo.state(), before)


class WarehouseGuardTests(unittest.TestCase):
    def resolve(self, *command, **env):
        with mock.patch.object(prove_test.shutil, 'which', side_effect=lambda name: '/bin/' + name), mock.patch.dict(os.environ, env):
            return prove_test.resolve_command(list(command))

    def refused(self, *command, **env):
        with self.assertRaises(prove_test.Unsupported) as raised:
            self.resolve(*command, **env)
        return str(raised.exception)

    def test_a_warehouse_command_behind_a_runner_needs_its_target_too(self):
        for command in (('uv', 'run', 'dbt', 'build'), ('poetry', 'run', 'dbt', 'test', '-s', 'orders'), ('uv', 'run', '--with', 'x', 'dbt', 'build'),
                        ('python', '-m', 'dbt', 'build'), ('uvx', 'dbt', 'build')):
            self.assertIn('--target', self.refused(*command), command)

    def test_a_production_target_is_never_run(self):
        for command in (('dbt', 'build', '--target', 'prod'), ('dbt', 'build', '--target=production'), ('uv', 'run', 'dbt', 'test', '--target', 'PRD'),
                        ('poetry', 'run', 'dbt', 'build', '--target', 'prod')):
            self.assertIn('production', self.refused(*command), command)
        self.assertIn('production', self.refused('dbt', 'build', '--target', 'live', AI_KIT_PROD_TARGETS='live, main'))

    def test_a_development_target_and_other_commands_run(self):
        self.assertEqual(self.resolve('dbt', 'build', '--target', 'dev'), ['/bin/dbt', 'build', '--target', 'dev'])
        self.assertEqual(self.resolve('uv', 'run', 'dbt', 'build', '--target', 'ci')[0], '/bin/uv')
        for command in (('uv', 'run', 'pytest', 'tests', '-k', 'dbt'), ('python', '-m', 'pytest', 'tests/dbt'), ('pytest', '--target', 'prod')):
            self.assertEqual(self.resolve(*command)[1:], list(command[1:]), command)


UNIT = """unit_tests:
  - name: test_amount_is_positive
    model: orders
    given:
      - input: ref('raw_orders')
        rows:
          - {order_id: 1, amount: 10}
    expect:
      rows:
        - {order_id: 1, amount: 10}
  - name: test_currency
    model: orders
    given:
      - input: ref('raw_orders')
        rows:
          - {order_id: 1, currency: EUR}
    expect:
      rows:
        - {order_id: 1, currency: EUR}
"""


@unittest.skipUnless(shutil.which('git'), 'git is not installed')
class WeakenedTestsNextToTheCode(WeakenedBase):
    def test_a_deleted_test_file_next_to_the_code_is_a_fact(self):
        files = {'pkg/calc.go': 'package pkg\n', 'pkg/calc_test.go': 'package pkg\nfunc TestAdd(t *testing.T) {}\n',
                 'web/price.ts': 'export const a = 1\n', 'web/price.test.ts': 'test("a", () => {})\n', 'web/cart.test.tsx': 'test("b", () => {})\n',
                 'app/test_export.py': 'def test_x():\n    assert True\n', 'app/export.py': 'x = 1\n'}
        repo = self.repo(files)
        repo.write({name: None for name in ('pkg/calc_test.go', 'web/price.test.ts', 'web/cart.test.tsx', 'app/test_export.py', 'app/export.py')})
        self.assertEqual(sorted(f[:2] for f in repo.facts()), [('test_file_deleted', 'app/test_export.py'), ('test_file_deleted', 'pkg/calc_test.go'),
                                                               ('test_file_deleted', 'web/cart.test.tsx'), ('test_file_deleted', 'web/price.test.ts')])

    def dbt(self, extra=None):
        return self.repo({'dbt_project.yml': DBT_PROJECT, 'models/orders.sql': 'select 1\n', 'models/unit.yml': UNIT,
                          'tests/assert_positive.sql': 'select * from x where amount < 0\n', **(extra or {})})

    def test_a_singular_dbt_test_whose_query_changed_is_left_to_the_review(self):
        repo = self.dbt()
        repo.write({'tests/assert_positive.sql': 'select * from x where amount < -1000\n'})
        self.assertEqual(repo.facts(), [('assertion_changed', 'tests/assert_positive.sql', 'assert_positive', None, 'dbt')])

    def test_a_singular_dbt_test_reformatted_is_not_a_fact(self):
        repo = self.dbt()
        repo.write({'tests/assert_positive.sql': 'select *\nfrom x\nwhere amount < 0\n'})
        self.assertEqual(repo.facts(), [])

    def test_a_dbt_unit_test_removed_is_a_fact(self):
        repo = self.dbt()
        repo.write({'models/unit.yml': UNIT[:UNIT.index('  - name: test_currency')]})
        self.assertEqual(repo.facts(), [('test_removed', 'models/unit.yml', 'unit_tests.orders.test_currency', None, 'dbt')])

    def test_a_dbt_unit_test_whose_expectation_changed_is_left_to_the_review(self):
        repo = self.dbt()
        repo.write({'models/unit.yml': UNIT.replace('- {order_id: 1, amount: 10}\n  - name: test_currency', '- {order_id: 1, amount: 0}\n  - name: test_currency')})
        self.assertEqual(repo.facts(), [('assertion_changed', 'models/unit.yml', 'unit_tests.orders.test_amount_is_positive', None, 'dbt')])

    def test_a_dbt_unit_test_turned_off_is_a_fact(self):
        repo = self.dbt()
        repo.write({'models/unit.yml': UNIT.replace('    model: orders\n    given:\n      - input: ref(\'raw_orders\')\n        rows:\n          - {order_id: 1, currency: EUR}',
                                                     '    model: orders\n    config:\n      enabled: false\n    given:\n      - input: ref(\'raw_orders\')\n        rows:\n          - {order_id: 1, currency: EUR}')})
        facts = repo.facts()
        self.assertEqual([f[1:3] for f in facts], [('models/unit.yml', 'unit_tests.orders.test_currency')], facts)
        self.assertIn('disabled', facts[0][0])


if __name__ == '__main__':
    unittest.main()
