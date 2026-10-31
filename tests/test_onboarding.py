"""What a person sees at the end of setup and at the top of doctor: what is ready, what is missing, the next step.
CLIs are simulated (shutil.which); no call to a model or an MCP server."""
import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from installer import cli
from installer.core import read_json

FALSE_SUCCESS = re.compile(r'(?i)\b(connected|authenticated|signed in|ready to use)\b')


def found(*names):
    """shutil.which that finds only these CLIs."""
    return lambda name, *a, **k: '/usr/local/bin/'+name if name in names else None


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def install(self, profile='data-analyst', target='all', overrides=None, org=None):
        if overrides is not None:
            (self.home/'.ai-kit').mkdir(parents=True, exist_ok=True)
            (self.home/'.ai-kit/overrides.json').write_text(json.dumps(overrides), encoding='utf-8')
        self.org = org or {}
        with mock.patch.object(cli, 'organization', return_value=self.org), contextlib.redirect_stdout(io.StringIO()):
            cli.apply(profile, self.home, False, {'email': 'a@example.org', 'source': 'test'}, target)
        return read_json(self.home/'.ai-kit/state.json')

    def summary(self, which, live=None, problems=()):
        out = io.StringIO()
        with mock.patch.object(cli.shutil, 'which', side_effect=which), mock.patch.object(cli, 'organization', return_value=self.org), \
             contextlib.redirect_stdout(out):
            cli.print_summary(self.home, read_json(self.home/'.ai-kit/state.json'), live, problems)
        return out.getvalue()

    def test_no_cli_available(self):
        self.install()
        out = self.summary(found())
        for label in ('Gemini CLI', 'Antigravity CLI', 'Codex CLI', 'Claude Code'):
            self.assertIn(label+': not found on this workstation; its configuration is prepared', out)
        self.assertIn('Next step: install Gemini CLI or Antigravity CLI or Codex CLI or Claude Code following your IT procedure', out)
        self.assertNotIn('start `', out)
        self.assertNotRegex(out, FALSE_SUCCESS)

    def test_one_cli_absent_does_not_hide_another(self):
        self.install(target='both')  # Gemini CLI and Antigravity CLI
        out = self.summary(found('gemini'))
        self.assertIn('Gemini CLI: found; connection not verified.', out)
        self.assertIn('Antigravity CLI: not found on this workstation', out)
        self.assertIn('start `gemini`', out)
        self.assertNotIn('start `agy`', out)
        self.assertNotIn('Codex', out)  # not targeted: not mentioned

    def test_cli_found_connection_not_verified_without_a_real_call(self):
        self.install(target='gemini')
        out = self.summary(found('gemini'))
        self.assertIn('connection not verified', out)
        self.assertNotIn('connection verified', out.replace('connection not verified', ''))
        self.assertNotRegex(out, FALSE_SUCCESS)

    def test_connection_verified_only_after_a_real_call(self):
        self.install(target='gemini')
        self.assertIn('Gemini CLI: found; connection verified: the model answered.', self.summary(found('gemini'), live={'gemini': 0}))
        failed = self.summary(found('gemini'), live={'gemini': 1})
        self.assertIn('the model did not answer', failed)
        self.assertIn('Next step: apply the fix shown above, then run doctor --live.', failed)

    def test_mcp_chosen_but_not_defined(self):
        self.install()
        out = self.summary(found('gemini'))
        self.assertIn('bigquery not provided by your organization yet; dbt not provided by your organization yet', out)
        self.assertIn('You can work on the SQL and dbt files of your repo with its usual tools', out)
        self.assertIn('needs a connection provided by your company', out)
        self.assertNotIn('MCP enabled', out)

    def test_mcp_turned_off_and_configured(self):
        org = {'defaults': {'mcp': {'bigquery': {'server': {'httpUrl': 'https://bq.example.org/mcp'}},
                                    'dbt': {'server': {'command': 'dbt-mcp'}}}}}
        self.install(overrides={'mcp': {'dbt': False}}, org=org)
        out = self.summary(found('gemini'))
        self.assertIn('bigquery configured; connection not verified', out)
        self.assertIn('dbt turned off (in your overrides.json or by your team)', out)
        self.assertNotRegex(out, FALSE_SUCCESS)

    def test_problems_come_first_in_the_next_step(self):
        self.install(target='gemini')
        out = self.summary(found('gemini'), problems=['.gemini/skills/x/SKILL.md'])
        self.assertIn('Failed checks, to fix (1): .gemini/skills/x/SKILL.md.', out)
        self.assertIn('Next step: fix the points above, then run doctor again.', out)


class SetupAndDoctorOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = self.temp.name

    def run_main(self, *args, which=found()):
        out = io.StringIO()
        with mock.patch.object(cli.shutil, 'which', side_effect=which), contextlib.redirect_stdout(out):
            code = cli.main(list(args)+['--home', self.home])
        return code, out.getvalue()

    def test_setup_ends_with_the_summary_and_keeps_its_exit_code(self):
        code, out = self.run_main('setup', '--profile', 'data-analyst', '--no-live', '--user', 'a@example.org', '--target', 'gemini')
        self.assertEqual(code, 0)
        self.assertLess(out.index('Kit configuration installed.'), out.index('Summary'))
        self.assertIn('Gemini CLI: not found on this workstation', out)
        self.assertIn('Next step: install Gemini CLI', out)
        self.assertNotIn('Open a project, start the CLI', out)  # no invitation to start a missing CLI
        self.assertNotRegex(out, FALSE_SUCCESS)

    def test_doctor_summary_before_details(self):
        self.run_main('setup', '--profile', 'data-analyst', '--no-live', '--user', 'a@example.org', '--target', 'gemini')
        code, out = self.run_main('doctor', which=found('gemini'))
        self.assertEqual(code, 0)
        self.assertLess(out.index('Summary'), out.index('Next step:'))
        self.assertLess(out.index('Next step:'), out.index('Details'))
        self.assertLess(out.index('Details'), out.index('[OK] Python 3.9 minimum'))
        self.assertEqual(out.count('[OK] Python 3.9 minimum'), 1)  # each check runs once

    def test_doctor_reports_a_problem_in_the_summary_and_exit_code(self):
        self.run_main('setup', '--profile', 'general', '--no-live', '--user', 'a@example.org', '--target', 'gemini')
        Path(self.home, '.gemini/00_KIT.md').write_text('edited', encoding='utf-8')
        code, out = self.run_main('doctor', which=found('gemini'))
        self.assertEqual(code, 1)
        self.assertIn('Failed checks, to fix (1): .gemini/00_KIT.md', out[:out.index('Details')])


class HomeWithSpacesTests(unittest.TestCase):
    def test_guardrail_reported_active_in_a_home_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)/'Home à'
            home.mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                cli.apply('general', home, False, {'email': 'a@example.org', 'source': 'test'}, 'gemini')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                cli.doctor(home)
            self.assertIn('[OK] Guardrail configured in settings.json: protected-paths', out.getvalue())


class AnalystReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def install(self, overrides=None):
        if overrides is not None:
            (self.home/'.ai-kit').mkdir(parents=True, exist_ok=True)
            (self.home/'.ai-kit/overrides.json').write_text(json.dumps(overrides), encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            cli.apply('data-analyst', self.home, False, {'email': 'a@example.org', 'source': 'test'}, 'gemini')
        return read_json(self.home/'.ai-kit/state.json')['installed']['commands']

    def test_review_in_the_data_analyst_profile_with_sql_and_dbt(self):
        self.assertIn('review', self.install())
        # The command stays neutral; the analyst's installed SQL and dbt playbooks carry the review checks.
        self.assertIn('"In the kit commands" section', (self.home/'.gemini/commands/review.toml').read_text(encoding='utf-8'))
        for skill, agent in (('sql-review', 'ai-kit-sql-reviewer'), ('dbt-model-change', 'ai-kit-dbt-reviewer')):
            text = (self.home/'.gemini/skills'/skill/'SKILL.md').read_text(encoding='utf-8')
            self.assertIn('`/review`', text)
            self.assertIn(agent, text)

    def test_personal_choice_kept(self):
        self.assertNotIn('review', self.install({'disabled_commands': ['review']}))
        self.assertFalse((self.home/'.gemini/commands/review.toml').exists())

    def test_no_duplicate_when_already_added(self):
        commands = self.install({'extra_commands': ['review']})
        self.assertEqual(commands.count('review'), 1)


if __name__ == '__main__':
    unittest.main()
