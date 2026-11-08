"""V2 slice 6 (docs/v2/config.md MCP keys): closed MCP server keys and anti-shell, reported one release before they block; IT's
allowlists (mcp.allowed_executables, mcp.allowed_http); a refused server marked required stops the installation, an optional
one is removed with a notice; required is AI Kit's and never reaches a CLI."""
import unittest

from installer.config import filter_mcp, server_identity, server_warnings
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

    def test_it_lists_exact_identities_and_required(self):
        ok, npx = {'command': '/usr/local/bin/uvx', 'args': ['tool==1.2.0']}, {'command': 'npx', 'args': ['-y', 'pkg']}
        web, evil = {'httpUrl': 'https://mcp.example.org/data'}, {'url': 'https://evil.example.org/mcp'}
        managed = {'mcp': {'allowed_stdio': [server_identity(ok)], 'allowed_http': [server_identity(web)]}}
        kept, notices = filter_mcp({'ai-kit-ok': ok, 'ai-kit-npx': npx, 'ai-kit-web': web, 'ai-kit-evil': evil}, managed)
        self.assertEqual(sorted(kept), ['ai-kit-ok', 'ai-kit-web'])
        self.assertTrue(any('npx not installed: its identity sha256:' in n and 'mcp.allowed_stdio' in n for n in notices))
        # A changed argument is another identity; a rename is the same one.
        self.assertNotEqual(server_identity(ok), server_identity({**ok, 'args': ['tool==1.3.0']}))
        self.assertIn('ai-kit-renamed', filter_mcp({'ai-kit-renamed': dict(ok)}, managed)[0])
        with self.assertRaises(KitError) as caught:
            filter_mcp({'ai-kit-npx': {**npx, 'required': True}}, managed)
        self.assertIn('is required but', str(caught.exception))

    def test_denied_by_name_url_prefix_or_executable(self):
        servers = {'ai-kit-a': {'command': 'uvx', 'args': ['a']}, 'ai-kit-b': {'httpUrl': 'https://legacy.example.org/mcp/b'},
                   'ai-kit-c': {'command': '/opt/tools/dbtool'}, 'ai-kit-d': {'httpUrl': 'https://ok.example.org/mcp'}}
        kept, _ = filter_mcp(servers, {'mcp': {'denied': ['a', 'https://legacy.example.org/', 'dbtool']}})
        self.assertEqual(list(kept), ['ai-kit-d'])

    def test_required_never_reaches_a_cli(self):
        kept, _ = filter_mcp({'ai-kit-a': {'httpUrl': 'https://h/mcp', 'required': False}}, None)
        self.assertEqual(kept, {'ai-kit-a': {'httpUrl': 'https://h/mcp'}})
        with self.assertRaises(KitError):
            validate_server({'httpUrl': 'https://h/mcp', 'required': 'yes'})


if __name__ == '__main__':
    unittest.main()
