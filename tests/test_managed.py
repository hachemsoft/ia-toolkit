import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from installer import managed
from installer.core import KitError
from installer.managed import managed_settings
from installer.toml_files import parse_toml


class ManagedSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)/'out'

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self, org=None, hooks_only=False, mcp_only=False):
        with mock.patch.object(managed, 'organization', return_value=org or {}), contextlib.redirect_stdout(io.StringIO()):
            return managed_settings(self.out, hooks_only, mcp_only)

    def test_default_guardrails_and_denied_paths_for_claude(self):
        self.run_it()
        settings = json.loads((self.out/'claude-code/managed-settings.json').read_text(encoding='utf-8'))
        commands = [h['command'] for g in settings['hooks']['PreToolUse'] for h in g['hooks']]
        self.assertEqual(len(commands), 1)
        self.assertIn('protected-paths.py', commands[0])
        self.assertIn('Bash|PowerShell', settings['hooks']['PreToolUse'][0]['matcher'])
        deny = settings['permissions']['deny']
        self.assertIn('Edit(~/.ai-kit/overrides.toml)', deny)
        self.assertFalse(any('30_USER' in d or 'learning' in d for d in deny), '/me and /learn must keep writing')
        self.assertNotIn('allowManagedHooksOnly', settings)

    def test_managed_toml_feeds_the_native_files(self):
        # V2 slice 6: IT's managed.toml locks a guardrail and refuses an MCP server in the files it deploys, too.
        imposed = Path(self.tmp.name)/'managed.toml'
        imposed.write_text('managed_schema = 1\n[hooks]\nlocked = ["dbt-prod-guard"]\n[mcp]\ndenied = ["db"]\n', encoding='utf-8')
        org = {'defaults': {'mcp': {'db': {'server': {'command': 'uvx', 'args': ['db']}}, 'docs': {'server': {'httpUrl': 'https://docs.example.org/mcp'}}}}}
        with mock.patch.object(managed, 'organization', return_value=org), mock.patch('installer.config.ownership_problem', return_value=None), \
                contextlib.redirect_stdout(io.StringIO()):
            managed_settings(self.out, False, True, managed_file=imposed)
        settings = json.loads((self.out/'claude-code/managed-settings.json').read_text(encoding='utf-8'))
        commands = ' '.join(h['command'] for g in settings['hooks']['PreToolUse'] for h in g['hooks'])
        self.assertIn('dbt-prod-guard', commands)
        self.assertEqual(settings['allowedMcpServers'], [{'serverUrl': 'https://docs.example.org/mcp'}])  # db refused by IT

    def test_locked_guardrails_and_hooks_only(self):
        self.run_it({'locked_hooks': ['protected-paths', 'dbt-prod-guard']}, hooks_only=True)
        claude = json.loads((self.out/'claude-code/managed-settings.json').read_text(encoding='utf-8'))
        self.assertTrue(claude['allowManagedHooksOnly'])
        self.assertEqual(len(claude['hooks']['PreToolUse']), 2)
        gemini = json.loads((self.out/'gemini-cli/settings.json').read_text(encoding='utf-8'))
        self.assertEqual(sorted(h['name'] for g in gemini['hooks']['BeforeTool'] for h in g['hooks']), ['ai-kit-dbt-prod-guard', 'ai-kit-protected-paths'])
        codex = parse_toml((self.out/'codex/requirements.toml').read_text(encoding='utf-8'))
        self.assertNotIn('danger-full-access', codex['allowed_sandbox_modes'])
        self.assertNotIn('never', codex['allowed_approval_policies'])
        self.assertIn('dbt-prod-guard', (self.out/'README.txt').read_text(encoding='utf-8'))

    def test_unknown_guardrail_and_non_empty_folder_refused(self):
        with self.assertRaises(KitError):
            self.run_it({'locked_hooks': ['nope']})
        with self.assertRaises(KitError):
            self.run_it({'locked_hooks': ['whats-new']})  # a hook that is not a guardrail is nothing IT locks
        self.out.mkdir(exist_ok=True)
        (self.out/'x').write_text('keep', encoding='utf-8')
        with self.assertRaises(KitError):
            self.run_it()
        self.assertEqual((self.out/'x').read_text(encoding='utf-8'), 'keep')

    ORG = {'defaults': {'mcp': {'docs': {'server': {'httpUrl': 'https://docs-mcp.example.org/mcp'}},
                                'github': {'server': {'command': 'docker', 'args': ['run', '-i', '--rm', 'ghcr.io/github/github-mcp-server:1.2.3']}}}},
           'teams': {'payments': {'mcp': {'ledger': {'server': {'url': 'https://ledger.example.org/sse'}}}}}}

    def test_no_mcp_lock_by_default(self):
        self.run_it(self.ORG)
        claude = json.loads((self.out/'claude-code/managed-settings.json').read_text(encoding='utf-8'))
        for key in ('allowedMcpServers', 'allowManagedMcpServersOnly'):
            self.assertNotIn(key, claude)
        self.assertNotIn('mcp_servers', parse_toml((self.out/'codex/requirements.toml').read_text(encoding='utf-8')))

    def test_mcp_allowlist_from_the_servers_the_organization_defines(self):
        self.run_it(self.ORG, mcp_only=True)
        claude = json.loads((self.out/'claude-code/managed-settings.json').read_text(encoding='utf-8'))
        self.assertTrue(claude['allowManagedMcpServersOnly'])
        self.assertCountEqual(claude['allowedMcpServers'], [
            {'serverUrl': 'https://docs-mcp.example.org/mcp'},
            {'serverCommand': ['docker', 'run', '-i', '--rm', 'ghcr.io/github/github-mcp-server:1.2.3']},
            {'serverUrl': 'https://ledger.example.org/sse'}])
        codex = parse_toml((self.out/'codex/requirements.toml').read_text(encoding='utf-8'))['mcp_servers']
        self.assertEqual(sorted(codex), ['ai-kit-docs', 'ai-kit-github', 'ai-kit-ledger'])  # the names the kit installs
        self.assertEqual(codex['ai-kit-docs']['identity'], {'url': 'https://docs-mcp.example.org/mcp'})
        command = codex['ai-kit-github']['identity']['command']
        self.assertEqual(command['executable'], 'docker')
        self.assertEqual([a['value'] for a in command['args']], ['run', '-i', '--rm', 'ghcr.io/github/github-mcp-server:1.2.3'])
        self.assertEqual({a['match'] for a in command['args']}, {'exact'})
        readme = (self.out/'README.txt').read_text(encoding='utf-8')
        self.assertIn('allowManagedMcpServersOnly', readme)
        self.assertIn('Gemini CLI', readme)
        self.assertNotIn('mcp', json.loads((self.out/'gemini-cli/settings.json').read_text(encoding='utf-8')))

    def test_mcp_lock_without_any_server_blocks_them_all(self):
        self.run_it({}, mcp_only=True)
        claude = json.loads((self.out/'claude-code/managed-settings.json').read_text(encoding='utf-8'))
        self.assertEqual(claude['allowedMcpServers'], [])
        self.assertEqual(parse_toml((self.out/'codex/requirements.toml').read_text(encoding='utf-8'))['mcp_servers'], {})


if __name__ == '__main__':
    unittest.main()
