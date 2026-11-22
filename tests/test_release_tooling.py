"""The tools around a release: the evaluation runner's reading of a CLI's output, the options the kit relies on in each
CLI, the GitLab pipeline, what the release ZIP ships. Stand-in CLIs and temporary folders only: no model, no network."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT/rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evals_run = load('evals_run_tooling', 'evals/run.py')
drift = load('cli_drift_tooling', 'scripts/cli_drift.py')
build_release = load('build_release_tooling', 'scripts/build_release.py')


class ApiErrorTests(unittest.TestCase):
    def test_an_answer_that_quotes_a_status_is_not_an_api_error(self):
        answer = 'The endpoint returns `status: 200` on success and status: 503 when the pool is empty.\n--- stderr ---\n'
        self.assertIsNone(evals_run.api_error(0, answer))

    def test_a_status_on_the_error_stream_or_a_failed_run_is_one(self):
        self.assertIn('API 429', evals_run.api_error(0, 'partial\n--- stderr ---\nApiError status: 429 quota'))
        self.assertIn('API 503', evals_run.api_error(1, 'status: 503\n--- stderr ---\n'))

    def test_a_success_status_is_never_an_api_error(self):
        self.assertIsNone(evals_run.api_error(1, 'request done, status: 200\n--- stderr ---\nsomething else failed'))


class ClaudeWritableCaseTests(unittest.TestCase):
    def test_the_verifier_may_run_the_proof_script(self):
        command = evals_run.cli_command('claude', 'claude', {'prompt': '/build x', 'sandbox': 'workspace-write'}, 60, None, 'default')
        allowed = command[command.index('--allowedTools') + 1:]
        allowed = allowed[:next((i for i, a in enumerate(allowed) if a.startswith('--')), len(allowed))]
        self.assertIn('Bash(python3 ~/.ai-kit/bin/prove_test.py:*)', allowed)
        self.assertEqual([a for a in allowed if not re.fullmatch(r'Bash\((python3? -m pytest|git|python3? ~/\.ai-kit/bin/prove_test\.py):\*\)', a)], [])
        plain = evals_run.cli_command('claude', 'claude', {'prompt': '/build x'}, 60, None, 'default')
        self.assertFalse([a for a in plain if 'prove_test' in a], plain)  # a read-only case proves nothing


GOOD = {'claude': '-p, --print  --model <m> --disallowedTools --allowedTools --permission-mode <mode> -c, --continue',
        'codex': '--skip-git-repo-check --ephemeral --color --sandbox <mode> -m, --model --last',
        'agy': '--print --print-timeout --sandbox --model  plugin validate <dir>',
        'gemini': '--approval-mode --policy --skip-trust --prompt -m, --model'}


@unittest.skipIf(sys.platform == 'win32', 'stand-ins are shell scripts')
class DriftTests(unittest.TestCase):
    def stand_in(self, folder, name, version='0.0.1', help_text=None, script=None):
        path = Path(folder)/name
        help_text = GOOD[name] if help_text is None else help_text
        path.write_text(script or '#!/bin/sh\nif [ "$1" = "--version" ]; then echo "' + version + '"; else echo "' + help_text + '"; fi\n', encoding='utf-8')
        path.chmod(0o755)

    def run_drift(self, folder):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {'PATH': folder + os.pathsep + '/bin' + os.pathsep + '/usr/bin'}), contextlib.redirect_stdout(out), \
                mock.patch.object(drift.shutil, 'which', side_effect=lambda name: str(Path(folder)/name) if (Path(folder)/name).exists() else None):
            code = drift.main([])
        return code, out.getvalue()

    def test_every_cli_with_every_option_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in GOOD:
                self.stand_in(folder, name)
            code, out = self.run_drift(folder)
        self.assertEqual((code, out.count('[OK]')), (0, 4), out)

    def test_the_options_the_evals_and_doctor_use_are_checked(self):
        for name, option in (('claude', '--allowedTools'), ('claude', '--permission-mode'), ('claude', '--continue'), ('codex', '--last'),
                             ('agy', '--sandbox'), ('agy', 'validate'), ('codex', '--sandbox')):
            with tempfile.TemporaryDirectory() as folder:
                self.stand_in(folder, name, help_text=' '.join(w for w in GOOD[name].split() if w not in (option, '-c,')))
                code, out = self.run_drift(folder)
            self.assertEqual(code, 1, (name, option, out))
            self.assertIn(option, out)

    def test_a_help_that_fails_is_a_problem_even_when_it_prints_the_options(self):
        with tempfile.TemporaryDirectory() as folder:
            self.stand_in(folder, 'claude', script='#!/bin/sh\nif [ "$1" = "--version" ]; then echo 1.0.0; exit 0; fi\necho "' + GOOD['claude'] + '"\nexit 3\n')
            code, out = self.run_drift(folder)
        self.assertEqual(code, 1, out)
        self.assertIn('[Broken] Claude Code', out)
        self.assertIn('exit code 3', out)

    def test_a_version_call_that_fails_is_a_problem(self):
        with tempfile.TemporaryDirectory() as folder:
            self.stand_in(folder, 'codex', script='#!/bin/sh\nif [ "$1" = "--version" ]; then echo "cannot start" >&2; exit 2; fi\necho "' + GOOD['codex'] + '"\n')
            code, out = self.run_drift(folder)
        self.assertEqual(code, 1, out)
        self.assertIn('[Broken] Codex CLI', out)
        self.assertIn('--version', out)

    def test_a_version_that_cannot_be_read_from_a_working_cli_is_only_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            self.stand_in(folder, 'gemini', version='nightly')
            code, out = self.run_drift(folder)
        self.assertEqual(code, 0, out)
        self.assertIn('[Check] Gemini CLI: version unreadable', out)


class GitLabPipelineTests(unittest.TestCase):
    def job(self, name):
        text = (ROOT/'.gitlab-ci.yml').read_text(encoding='utf-8')
        match = re.search(r'^' + re.escape(name) + r':\n((?:[ \t#].*\n|\n)+)', text, re.M)
        self.assertIsNotNone(match, name + ' missing from .gitlab-ci.yml')
        return match.group(1)

    def test_the_zip_is_installed_offline_before_it_is_published(self):
        job = self.job('release-zip-test')
        self.assertRegex(job, r'needs:\s*\[\s*release-zip\s*\]')
        self.assertIn('AI_KIT_RELEASE_ZIP', job)
        self.assertIn('test_enterprise_install.py', job)
        self.assertRegex(job, r'PIP_INDEX_URL:\s*"?http://127\.0\.0\.1:9/simple')  # no package index reachable
        self.assertRegex(job, r'PYTHON: \["3\.11", "3\.14"\]')
        self.assertRegex(self.job('publish-release'), r'needs:\s*\[[^\]]*release-zip-test')


class ReleaseContentTests(unittest.TestCase):
    def test_the_change_folders_stay_out_of_the_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            source, payload = Path(folder)/'source', Path(folder)/'payload'
            for rel in build_release.SHIPPED:
                path = source/rel
                if rel == 'docs':
                    for name in ('hooks.md', 'cli/agy.md', 'sdlc/2026-01-01-a-change/spec.md', 'decisions/0001-x.md'):
                        (path/name).parent.mkdir(parents=True, exist_ok=True)
                        (path/name).write_text('x', encoding='utf-8')
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('x', encoding='utf-8')
            build_release.ship(source, payload)
            shipped = sorted(p.relative_to(payload).as_posix() for p in payload.rglob('*') if p.is_file())
        self.assertIn('docs/hooks.md', shipped)
        self.assertIn('docs/decisions/0001-x.md', shipped)
        self.assertIn('Installer.cmd', shipped)
        self.assertEqual([name for name in shipped if name.startswith('docs/sdlc')], [])

    def test_no_shipped_page_links_to_a_change_folder(self):
        import subprocess
        names = subprocess.run(['git', '-C', str(ROOT), 'ls-files', 'README.md', 'docs'], capture_output=True, text=True).stdout.split()
        broken = []
        for name in names:
            if name.startswith('docs/sdlc/') or not name.endswith('.md'):
                continue
            text = (ROOT/name).read_text(encoding='utf-8')
            broken += [name + ': ' + target for target in re.findall(r'\]\(([^)#\s]*sdlc/[^)\s]*)\)', text)]
        self.assertEqual(broken, [])


if __name__ == '__main__':
    unittest.main()
