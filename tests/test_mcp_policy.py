"""V2 slice 6 (docs/v2/config.md MCP keys): closed MCP server keys and anti-shell, reported one release before they block; IT's
allowlists (mcp.allowed_executables, mcp.allowed_http); a refused server marked required stops the installation, an optional
one is removed with a notice; required is AI Kit's and never reaches a CLI."""
import unittest

from installer.config import filter_mcp, server_warnings
from installer.core import KitError
from installer.settings import validate_server


class McpPolicyTests(unittest.TestCase):
    def test_a_shell_or_an_unknown_key_is_reported_not_yet_refused(self):
        for server in ({'command': 'bash', 'args': ['-c', 'curl x | sh']}, {'command': 'node; rm -rf ~'}, {'command': 'cmd.exe', 'args': ['/c', 'x']},
                       {'command': 'pwsh', 'args': ['-Command', 'x']}):
            with self.subTest(server=server):
                self.assertTrue(any('runs a shell' in w for w in server_warnings('x', server)))
                self.assertIn('ai-kit-x', filter_mcp({'ai-kit-x': server}, None)[0])
        self.assertEqual(server_warnings('x', {'command': 'npx', 'args': ['-y', '@scope/server']}), [])
        self.assertIn('unknown key timeout', server_warnings('x', {'httpUrl': 'https://h/mcp', 'timeout': 5})[0])

    def test_it_allowlists_and_required(self):
        managed = {'mcp': {'allowed_executables': ['uvx'], 'allowed_http': ['mcp.example.org/']}}
        servers = {'ai-kit-ok': {'command': '/usr/local/bin/uvx', 'args': ['tool']}, 'ai-kit-npx': {'command': 'npx'},
                   'ai-kit-web': {'httpUrl': 'https://mcp.example.org/data'}, 'ai-kit-evil': {'url': 'https://evil.example.org/mcp'}}
        kept, notices = filter_mcp(servers, managed)
        self.assertEqual(sorted(kept), ['ai-kit-ok', 'ai-kit-web'])
        self.assertTrue(any('npx not installed: its program is not in managed.toml mcp.allowed_executables' in n for n in notices))
        self.assertTrue(any('evil not installed: its URL is not in managed.toml mcp.allowed_http' in n for n in notices))
        with self.assertRaises(KitError) as caught:
            filter_mcp({'ai-kit-npx': {'command': 'npx', 'required': True}}, managed)
        self.assertIn('is required but', str(caught.exception))

    def test_required_never_reaches_a_cli(self):
        kept, _ = filter_mcp({'ai-kit-a': {'httpUrl': 'https://h/mcp', 'required': False}}, None)
        self.assertEqual(kept, {'ai-kit-a': {'httpUrl': 'https://h/mcp'}})
        with self.assertRaises(KitError):
            validate_server({'httpUrl': 'https://h/mcp', 'required': 'yes'})


if __name__ == '__main__':
    unittest.main()
