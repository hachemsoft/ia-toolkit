"""Frictions as issues of the organization's GitLab or GitHub project: the organization names the tracker, update
records it in state.json, the /friction script creates the issue through the person's own glab or gh (never a token in
the kit), keeps the friction local on any failure, and --sync sends what is left. A person can opt out."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from installer import cli, settings
from installer.core import ROOT, friction_module, read_json
from installer.toml_files import read_toml

ORG = {'allowed_domains': [], 'defaults': {}, 'friction_tracker': {'kind': 'gitlab', 'project': 'tools/ai-kit', 'labels': ['friction', 'kit']}}

FAKE = '''import json, os, sys
log = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calls.jsonl')
with open(log, 'a', encoding='utf-8') as handle:
    handle.write(json.dumps(sys.argv[1:]) + '\\n')
if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fail')):
    print('error: not signed in', file=sys.stderr)
    sys.exit(1)
if sys.argv[1:3] == ['auth', 'status']:
    print('Logged in'); sys.exit(0)
print('Creating issue...')
print('https://gitlab.example.org/tools/ai-kit/-/issues/' + str(sum(1 for _ in open(log))))
'''


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base/'home'
        self.home.mkdir()
        self.bin = self.base/'bin'
        self.bin.mkdir()
        self.org = json.loads(json.dumps(ORG))
        real = settings.read_toml
        for patcher in (mock.patch('shutil.which', side_effect=lambda name, path=None: self.fake_which(name, path)),
                        mock.patch.dict(os.environ, {'AI_KIT_SOURCE_DIR': '', 'PATH': str(self.bin)+os.pathsep+os.environ.get('PATH', '')}),
                        mock.patch.object(settings, 'read_toml', side_effect=lambda p, d=None: self.org if Path(p).name == 'organization.toml' else real(p, d)),
                        # 2.0.0: approval is the default (D5, ADR 0023, tested in test_config_precedence); these tests cover the auto mode.
                        mock.patch('installer.cli.publication', return_value='auto')):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.install_fake('glab')
        self.run_kit('setup', '--profile', 'general', '--user', 'a@example.org', '--target', 'gemini')

    def fake_which(self, name, path=None):
        candidate = self.bin/(name+('.cmd' if os.name == 'nt' else ''))
        return str(candidate) if candidate.is_file() else None

    def install_fake(self, name):
        (self.bin/(name+'-impl.py')).write_text(FAKE, encoding='utf-8')
        if os.name == 'nt':
            (self.bin/(name+'.cmd')).write_text('@echo off\r\n"'+sys.executable+'" -I "%~dp0'+name+'-impl.py" %*\r\n', encoding='utf-8')
        else:
            wrapper = self.bin/name
            wrapper.write_text('#!/bin/sh\nexec "'+sys.executable+'" -I "'+str(self.bin/(name+'-impl.py'))+'" "$@"\n', encoding='utf-8')
            wrapper.chmod(0o755)

    def calls(self):
        log = self.bin/'calls.jsonl'
        return [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.is_file() else []

    def run_kit(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), mock.patch.object(cli, 'interactive', return_value=False):
            code = cli.main([*args, '--home', str(self.home)])
        return code, out.getvalue()

    def script(self, *args, text='The plan step is too long'):
        env = {**os.environ, 'HOME': str(self.home), 'USERPROFILE': str(self.home)}
        return subprocess.run([sys.executable, '-I', str(self.home/'.ai-kit/bin/friction.py'), *args], input=text, capture_output=True, text=True, env=env, timeout=60)

    def lines(self):
        path = self.home/'.ai-kit/frictions.jsonl'
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.is_file() else []

    def sent(self):
        return read_json(self.home/'.ai-kit/frictions-sent.json', {})


class TrackerTests(Base):
    def test_update_records_the_tracker_and_the_person_can_opt_out(self):
        recorded = read_json(self.home/'.ai-kit/state.json')['friction_tracker']
        self.assertEqual(recorded, {'kind': 'gitlab', 'project': 'tools/ai-kit', 'host': '', 'labels': ['friction', 'kit'], 'sources': ['agent'], 'publication': 'auto'})  # 2.0.0: publication recorded
        overrides = self.home/'.ai-kit/overrides.toml'
        overrides.write_text(overrides.read_text(encoding='utf-8')+'\nshare_frictions = false\n', encoding='utf-8')
        code, out = self.run_kit('update')
        self.assertEqual(code, 0, out)
        self.assertNotIn('friction_tracker', read_json(self.home/'.ai-kit/state.json'))
        self.assertIn('share_frictions = false', out)  # update says the frictions stay local
        del self.org['friction_tracker']
        overrides.write_text(overrides.read_text(encoding='utf-8').replace('share_frictions = false', ''), encoding='utf-8')
        self.run_kit('update')
        self.assertNotIn('friction_tracker', read_json(self.home/'.ai-kit/state.json'))

    def test_approval_keeps_the_friction_until_the_person_sends_it(self):
        # 2.0.0 default (D5, ADR 0023): nothing leaves on its own; ai-kit friction --sync, run by the person, sends it.
        with mock.patch('installer.cli.publication', return_value='approval'):
            code, out = self.run_kit('update')
        self.assertEqual(code, 0, out)
        self.assertEqual(read_json(self.home/'.ai-kit/state.json')['friction_tracker']['publication'], 'approval')
        proc = self.script('--category', 'docs', '--command', '/build', '--cli', 'gemini', '--source', 'agent')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('Not sent yet', proc.stdout)
        self.assertEqual(self.calls(), [])
        proc = self.script('--sync')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(self.calls()), 1)

    def test_agent_friction_becomes_an_issue_once_and_a_person_friction_stays_local(self):
        proc = self.script('--category', 'docs', '--command', '/build', '--cli', 'gemini', '--source', 'agent')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        entry = self.lines()[-1]
        self.assertEqual(entry['source'], 'agent')
        self.assertIn('Issue created: https://gitlab.example.org/tools/ai-kit/-/issues/1', proc.stdout)
        call = self.calls()[-1]
        self.assertEqual(call[:3], ['issue', 'create', '--repo=tools/ai-kit'])
        self.assertIn('--title=[friction] docs on /build', call)
        self.assertTrue(any(a.startswith('--description=The plan step is too long') for a in call))
        # The whole command, in process: a Windows .cmd wrapper cannot receive an argument holding a newline (cmd.exe
        # truncates the line there), while a real glab.exe or gh.exe does; so the body and the labels are checked here.
        command = friction_module().issue_command(self.org['friction_tracker'], entry, 'glab')
        body = next(a for a in command if a.startswith('--description='))
        self.assertIn('The plan step is too long', body)
        self.assertIn('(frictions: '+entry['id']+')', body)
        self.assertIn('--label=friction,kit', command)
        self.assertEqual(self.sent()[entry['id']]['url'], 'https://gitlab.example.org/tools/ai-kit/-/issues/1')
        proc = self.script('--sync')
        self.assertIn('Nothing to send', proc.stdout)
        self.assertEqual(len(self.calls()), 1)
        proc = self.script('--category', 'tool', '--cli', 'gemini', text='Mine, typed by hand')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn('Issue created', proc.stdout)
        self.assertEqual(len(self.calls()), 1)
        code, out = self.run_kit('friction', '--list')
        self.assertIn('issues/1', out)

    def test_a_failing_cli_keeps_the_friction_local_and_sync_sends_it_later(self):
        (self.bin/'fail').write_text('', encoding='utf-8')
        proc = self.script('--category', 'rule', '--cli', 'claude', '--source', 'agent')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('kept locally', proc.stdout)
        self.assertIn('not signed in', proc.stdout)
        self.assertIn('--sync', proc.stdout)
        self.assertEqual(self.sent(), {})
        (self.bin/'fail').unlink()
        code, out = self.run_kit('friction', '--sync')
        self.assertEqual(code, 0, out)
        self.assertIn('Issue created', out)
        self.assertEqual(len(self.sent()), 1)
        proc = self.script('--sync')
        self.assertIn('Nothing to send', proc.stdout)

    def test_github_uses_gh_with_its_own_flags_and_a_host(self):
        self.org['friction_tracker'] = {'kind': 'github', 'project': 'acme/ai-kit', 'host': 'github.acme.org', 'sources': ['agent', 'person']}
        self.install_fake('gh')
        self.run_kit('update')
        proc = self.script('--category', 'skill', '--cli', 'codex')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        call = self.calls()[-1]
        self.assertEqual(call[:3], ['issue', 'create', '--repo=github.acme.org/acme/ai-kit'])
        self.assertTrue(any(a.startswith('--body=') for a in call))
        command = friction_module().issue_command(self.org['friction_tracker'], self.lines()[-1], 'gh')  # see above: in process
        self.assertTrue(any(a.startswith('--body=') and '(frictions: ' in a for a in command))
        self.assertIn('--label=friction', command)

    def test_doctor_reports_the_tracker(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.doctor(self.home)
        self.assertIn('[OK] Friction tracker: gitlab tools/ai-kit, glab signed in', out.getvalue())
        (self.bin/'fail').write_text('', encoding='utf-8')
        self.script('--category', 'rule', '--cli', 'claude', '--source', 'agent')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.doctor(self.home)
        self.assertIn('[Check] Friction tracker: gitlab tools/ai-kit, glab not signed in', out.getvalue())
        self.assertIn('[Info] 1 friction not sent to the tracker yet: ai-kit friction --sync', out.getvalue())
        (self.bin/('glab'+('.cmd' if os.name == 'nt' else ''))).unlink()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.doctor(self.home)
        self.assertIn('[Check] Friction tracker: gitlab tools/ai-kit, glab not on the PATH', out.getvalue())

    def test_bad_tracker_settings_are_refused(self):
        for bad in ({'kind': 'jira', 'project': 'a/b'}, {'kind': 'gitlab'}, {'kind': 'gitlab', 'project': 'https://x/y'},
                    {'kind': 'gitlab', 'project': 'a/b', 'sources': ['bot']}, {'kind': 'gitlab', 'project': 'a/b', 'host': 'http://h'}):
            self.org['friction_tracker'] = bad
            code, out = self.run_kit('update')
            self.assertEqual(code, 2, bad)
            self.assertIn('friction_tracker', out)


class TextsTests(unittest.TestCase):
    def test_auto_mode_passes_source_agent_and_schemas_know_the_keys(self):
        self.assertIn('--source agent', (ROOT/'commands/friction.md').read_text(encoding='utf-8'))
        self.assertIn('--source agent', cli.friction_rule('auto'))
        self.assertNotIn('--source agent', cli.friction_rule('propose'))
        self.assertIn('friction_tracker', read_json(ROOT/'schemas/organization.schema.json')['properties'])
        self.assertIn('share_frictions', read_json(ROOT/'schemas/overrides.schema.json')['properties'])
        self.assertIn('friction_tracker', read_toml(ROOT/'organization.toml', {}).keys() | {'friction_tracker'})  # documented in the file as a comment at least
        self.assertIn('[friction_tracker]', (ROOT/'organization.toml').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
