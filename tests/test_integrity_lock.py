"""IT can lock the integrity check (spec docs/sdlc/2026-11-15-integrity-lockable/spec.md, 4.17.0): managed.toml
[hooks] locked = ["integrity"] keeps integrity and whats-new on whatever aikit.toml says, and ai-kit managed-settings writes
them in the policy files of Claude Code, Gemini CLI and Codex. Without that lock, nothing changes."""
import contextlib
import io
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from installer import cli, config, managed
from installer.managed import managed_settings
from personal import write_personal

LOCKED = 'managed_schema = 1\n[hooks]\nlocked = ["integrity"]\n'


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.managed = self.root/'managed.toml'
        trusted = mock.patch('installer.config.ownership_problem', return_value=None)
        trusted.start()
        self.addCleanup(trusted.stop)

    def generate(self, imposed=None, hooks_only=False):
        out = self.root/('out-%d' % len(list(self.root.glob('out-*'))))
        if imposed is not None:
            self.managed.write_text(imposed, encoding='utf-8')
        try:
            with mock.patch.object(managed, 'core_settings', return_value={}), contextlib.redirect_stdout(io.StringIO()):
                managed_settings(out, hooks_only, False, managed_file=self.managed)
        except config.ManagedConfigError as error:
            self.fail('managed.toml refused: '+str(error))
        return out


class DefaultUnchangedTests(Base):
    """T1, R0: without a lock, the policy files carry no integrity, whats-new, after-tool or session-start hook."""

    def test_policy_files_without_a_lock(self):
        out = self.generate()
        claude = json.loads((out/'claude-code/managed-settings.json').read_text(encoding='utf-8'))
        self.assertEqual(set(claude['hooks']), {'PreToolUse'})
        gemini = json.loads((out/'gemini-cli/settings.json').read_text(encoding='utf-8'))
        self.assertEqual(set(gemini['hooks']), {'BeforeTool'})
        codex = tomllib.loads((out/'codex/requirements.toml').read_text(encoding='utf-8'))
        self.assertNotIn('hooks', codex)
        self.assertNotIn('features', codex)
        readme = (out/'README.txt').read_text(encoding='utf-8')
        self.assertNotIn('integrity', readme.split('agy')[0] if 'agy' in readme else readme)


class LockTests(Base):
    """T2, R1, R2, R7b: what IT may lock, and the installation keeping both hooks on."""

    def names(self):
        from installer import core
        self.assertTrue(hasattr(core, 'is_lockable'), 'installer.core has no is_lockable')
        manifest = core.read_json(core.ROOT/'runtime/hooks/hooks.json')['hooks']
        return [n for n, spec in manifest.items() if core.is_lockable(spec)]

    def test_validation(self):
        names = self.names()
        self.assertIn('integrity', names)
        self.assertNotIn('whats-new', names)
        self.managed.write_text(LOCKED, encoding='utf-8')
        self.assertEqual(config.load_managed(self.managed, names)['hooks']['locked'], ['integrity'])
        for bad, words in (('locked = ["whats-new"]', 'follows integrity'), ('whats-new = true', 'follows integrity'),
                           ('locked = ["integrity"]\nintegrity = false', 'hooks.locked contains integrity')):
            self.managed.write_text('managed_schema = 1\n[hooks]\n'+bad+'\n', encoding='utf-8')
            with self.assertRaises(config.ManagedConfigError) as raised:
                config.load_managed(self.managed, names)
            self.assertIn(words, str(raised.exception))
        self.managed.write_text('managed_schema = 1\n[hooks]\nintegrity = false\n', encoding='utf-8')
        self.assertIs(config.load_managed(self.managed, names)['hooks']['integrity'], False)  # off for everyone, not locked

    def test_every_caller_accepts_the_lock(self):
        # 4.17.0 review: bootstrap (ZIP install), sync and init called load_managed without names and refused any [hooks]
        self.managed.write_text(LOCKED, encoding='utf-8')
        self.assertEqual(config.load_managed(self.managed)['hooks']['locked'], ['integrity'])

    def test_the_installation_keeps_both_hooks(self):
        home = self.root/'home'
        home.mkdir()
        write_personal(home, {'hooks': {'integrity': False, 'whats-new': False}})
        self.managed.write_text(LOCKED, encoding='utf-8')
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                cli.apply(home, False, None, 'claude', managed_file=self.managed)
        except config.ManagedConfigError as error:
            self.fail('managed.toml refused: '+str(error))
        state = json.loads((home/'.ai-kit/state.json').read_text(encoding='utf-8'))
        self.assertIn('integrity', state['hooks'])
        self.assertIn('whats-new', state['hooks'])
        self.assertIn('[Info] Hook integrity stays on', output.getvalue())
        self.assertIn('[Info] Hook whats-new stays on', output.getvalue())

    def test_status_does_not_flag_the_lock(self):
        from installer import status
        self.managed.write_text(LOCKED, encoding='utf-8')
        home = self.root/'home2'
        home.mkdir()
        text = io.StringIO()
        with mock.patch.object(config, 'managed_path', return_value=self.managed), contextlib.redirect_stdout(text):
            status.status(home)
        self.assertNotIn('[Check]', text.getvalue())
        self.assertIn('integrity', text.getvalue())


class PolicyFilesTests(Base):
    """T3, R3-R6: the policy files with integrity locked."""

    def test_claude_code(self):
        for rel, windows in (('claude-code/managed-settings.json', False), ('windows/claude-code/managed-settings.json', True)):
            out = self.generate(LOCKED, hooks_only=True)
            claude = json.loads((out/rel).read_text(encoding='utf-8'))
            post = claude['hooks']['PostToolUse']
            self.assertEqual(len(post), 1)
            self.assertNotIn('matcher', post[0])  # every tool
            self.assertIn('integrity.py', post[0]['hooks'][0]['command'])
            self.assertIn('whats-new.py', claude['hooks']['SessionStart'][0]['hooks'][0]['command'])
            self.assertTrue(claude['allowManagedHooksOnly'])
            guard = claude['hooks']['PreToolUse'][0]['hooks'][0]
            self.assertEqual(post[0]['hooks'][0].get('shell'), guard.get('shell'))  # PowerShell on Windows, like the guardrails
            if windows:
                self.assertEqual(post[0]['hooks'][0]['shell'], 'powershell')

    def test_gemini_cli(self):
        out = self.generate(LOCKED)
        gemini = json.loads((out/'gemini-cli/settings.json').read_text(encoding='utf-8'))
        self.assertIn('integrity.py', gemini['hooks']['AfterTool'][0]['hooks'][0]['command'])
        self.assertNotIn('matcher', gemini['hooks']['AfterTool'][0])
        self.assertIn('whats-new.py', gemini['hooks']['SessionStart'][0]['hooks'][0]['command'])
        windows = json.loads((out/'windows/gemini-cli/settings.json').read_text(encoding='utf-8'))
        self.assertNotIn('hooks', windows)

    def test_codex(self):
        out = self.generate(LOCKED)
        codex = tomllib.loads((out/'codex/requirements.toml').read_text(encoding='utf-8'))
        self.assertIs(codex['features']['hooks'], True)
        post = codex['hooks']['PostToolUse']
        self.assertIn(post[0].get('matcher', '*'), ('', '*'))  # every tool: Codex maps "" and "*" to All (hooks/src/engine/matcher.rs)
        handler = post[0]['hooks'][0]
        self.assertEqual(handler['type'], 'command')
        self.assertIn('integrity.py', handler['command'])
        self.assertIn('integrity.py', handler['command_windows'])
        # Codex runs hooks through cmd.exe /C on Windows (openai/codex hooks/src/engine/command_runner.rs): cmd syntax, not PowerShell
        self.assertIn('%USERPROFILE%', handler['command_windows'])
        self.assertNotIn('$HOME', handler['command_windows'])
        self.assertFalse(handler['command_windows'].lstrip().startswith('&'))
        self.assertIn('whats-new.py', codex['hooks']['SessionStart'][0]['hooks'][0]['command'])
        self.assertEqual(codex['allowed_sandbox_modes'], ['read-only', 'workspace-write'])  # what was there stays

    def test_codex_with_the_mcp_lock(self):
        # 4.17.0 review: an empty MCP lock wrote a bare key after the hook tables, where TOML attaches it to the last table
        self.managed.write_text(LOCKED, encoding='utf-8')
        out = self.root/'out-mcp'
        with mock.patch.object(managed, 'core_settings', return_value={}), contextlib.redirect_stdout(io.StringIO()):
            managed_settings(out, False, True, managed_file=self.managed)
        codex = tomllib.loads((out/'codex/requirements.toml').read_text(encoding='utf-8'))
        self.assertEqual(codex['mcp_servers'], {})
        self.assertNotIn('mcp_servers', codex['hooks']['SessionStart'][0]['hooks'][0])

    def test_the_readme(self):
        readme = (self.generate(LOCKED)/'README.txt').read_text(encoding='utf-8')
        for words in ('integrity', 'whats-new', 'reports a change, it does not block', 'agy'):
            self.assertIn(words, readme)


if __name__ == '__main__':
    unittest.main()
