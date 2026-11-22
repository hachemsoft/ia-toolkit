"""4.24.1: the Claude Code adapter compares the kit's part of ~/.claude/settings.json and ~/.claude.json by what it holds,
not by the order of its keys (Claude Code rewrites both files); doctor reports a kit MCP server changed in ~/.claude.json;
an agent that declares no tool never gets an empty tools line (which gives it every tool of the session), and an agent that
may write is not told to only read."""
import contextlib
import io
import json
import unittest

from installer import cli
from installer.adapters import claude
from installer.core import KitError, read_json
import test_claude


def reordered(value):
    """The same JSON value with the keys of every object in reverse order."""
    if isinstance(value, dict):
        return {key: reordered(value[key]) for key in reversed(list(value))}
    return [reordered(v) for v in value] if isinstance(value, list) else value


class KeyOrderTests(test_claude.Base):
    def install_with_a_server(self):
        self.core_servers({'tool': {'command': 'npx', 'args': ['-y', 'tool@1.0.0'], 'env': {'TOKEN': '${TOOL_TOKEN}'}},
                           'docs': {'httpUrl': 'https://docs.example.org/mcp', 'headers': {'X': '1'}}})
        self.overrides({'mcp': {'tool': True, 'docs': True}, 'hooks': {'dbt-prod-guard': True}})
        self.run_kit()

    def rewrite(self, rel):
        path = self.home/rel
        data = reordered(read_json(path))
        path.write_text(json.dumps(data), encoding='utf-8')
        return data

    def state(self):
        return read_json(self.home/'.ai-kit/state.json')

    def test_keys_reordered_by_claude_code_are_not_a_change(self):
        self.install_with_a_server()
        self.assertEqual(claude.changed_blocks(self.home, self.state()), [])
        settings, servers = self.rewrite('.claude/settings.json'), self.rewrite('.claude.json')
        self.assertEqual(claude.changed_blocks(self.home, self.state()), [])  # the integrity check and doctor
        self.run_kit()  # sync is not blocked by "edited by hand"
        self.assertEqual(read_json(self.home/'.claude.json')['mcpServers'], servers['mcpServers'])
        self.assertEqual(read_json(self.home/'.claude/settings.json')['hooks'], settings['hooks'])
        self.assertEqual(claude.changed_blocks(self.home, self.state()), [])

    def test_a_changed_value_is_still_a_change(self):
        self.install_with_a_server()
        data = self.rewrite('.claude.json')
        data['mcpServers']['ai-kit-docs']['url'] = 'https://elsewhere.example.org/mcp'
        (self.home/'.claude.json').write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(claude.changed_blocks(self.home, self.state()), ['.claude.json'])
        with self.assertRaises(KitError):
            self.run_kit()

    def test_doctor_reports_a_kit_mcp_server_changed_in_claude_json(self):
        self.install_with_a_server()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.doctor(self.home)
        self.assertIn('[OK] MCP servers in ~/.claude.json', out.getvalue())
        data = read_json(self.home/'.claude.json')
        data['mcpServers']['ai-kit-tool']['args'] = ['-y', 'another-package']
        (self.home/'.claude.json').write_text(json.dumps(data), encoding='utf-8')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.doctor(self.home)
        self.assertNotIn('[OK] MCP servers in ~/.claude.json', out.getvalue())
        self.assertIn('MCP servers in ~/.claude.json', out.getvalue())
        self.assertIn('changed', out.getvalue())
        self.assertEqual(code, 1)


class AgentToolsTests(unittest.TestCase):
    DEFAULTS = {'tools': ['read_file', 'grep_search']}

    def header(self, definition):
        text = claude.agent_text('ai-kit-x', {'description': 'An agent.', **definition}, self.DEFAULTS, 'Body.')
        return text.split('---')[1]

    def test_an_agent_without_tools_never_gets_an_empty_tools_line(self):
        self.assertIn('tools: Read, Grep\n', self.header({'tools': []}))  # no tool declared: the defaults, read and search
        self.assertIn('tools: Read, Grep\n', self.header({}))
        self.assertIn('tools: Read, Bash\n', self.header({'tools': ['read_file', 'run_shell_command']}))
        with self.assertRaises(KitError):  # nothing to give: refused, never an empty line (Claude Code reads it as every tool)
            claude.agent_text('ai-kit-x', {'description': 'An agent.', 'tools': []}, {'tools': []}, 'Body.')
        for definition in ({'tools': []}, {}, {'tools': ['read_file']}):
            self.assertNotRegex(self.header(definition), r'tools:\s*\n')

    def test_an_agent_that_may_write_is_not_told_to_only_read(self):
        read_only = cli.agent_instruction({'tools': ['read_file', 'grep_search']})
        self.assertIn('Read and search only: modify no file and run no command.', read_only)
        self.assertIn('Read and search only', cli.agent_instruction({'tools': []}))
        shell = cli.agent_instruction({'tools': ['read_file', 'run_shell_command']})
        self.assertIn('run only the commands your instructions below allow', shell)
        for tools in (['read_file', 'write_file'], ['replace'], ['read_file', 'write_file', 'run_shell_command']):
            text = cli.agent_instruction({'tools': tools})
            self.assertNotIn('Read and search only', text, tools)
            self.assertNotIn('Modify no file', text, tools)
            self.assertIn('only the files your instructions below name', text, tools)
        self.assertIn('run no command', cli.agent_instruction({'tools': ['write_file']}))
        self.assertNotIn('run no command', cli.agent_instruction({'tools': ['write_file', 'run_shell_command']}))


if __name__ == '__main__':
    unittest.main()
