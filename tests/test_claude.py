"""Claude Code adapter: context imported by ~/.claude/CLAUDE.md, prefixed skills and their references, commands renamed
only on a collision with a personal skill or command, agents with native tools, guardrails beside the person's own hooks
in ~/.claude/settings.json, MCP servers in ~/.claude.json, removal, usage from the transcripts, guardrail payloads."""
import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from installer import cli
from installer.adapters import claude
from installer.core import ROOT, KitError, read_json

H = ROOT/'runtime/hooks'
PERSONAL_HOOK = {'hooks': [{'type': 'command', 'command': '/usr/local/bin/my-status'}]}


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        patcher = mock.patch('shutil.which', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def overrides(self, value):
        path = self.home/'.ai-kit/overrides.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def run_kit(self, target='claude', profile='general'):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            notices = cli.apply(profile, self.home, False, {'email': 'a@example.org', 'source': 'option'}, target)
        self.out = out.getvalue()
        return notices

    def read(self, rel):
        return (self.home/rel).read_text(encoding='utf-8')


class InstallTests(Base):
    def test_context_is_imported_never_copied_and_the_persons_text_stays(self):
        (self.home/'.claude').mkdir()
        (self.home/'.claude/CLAUDE.md').write_text('# My own instructions\nAlways answer in French.\n', encoding='utf-8')
        self.run_kit()
        text = self.read('.claude/CLAUDE.md')
        self.assertTrue(text.startswith(claude.CLAUDE_MD[0]))
        self.assertIn('Always answer in French.', text)
        for name in ('00_KIT.md', '10_COMPANY.md', '20_TEAM.md', '30_USER.md'):
            self.assertRegex(text, r'(?m)^@.*/'+name+'$')
        self.assertNotIn('Person:', text)  # 30_USER.md is imported, not copied
        self.assertIn('AGENTS.md', text)
        self.run_kit()  # idempotent
        self.assertEqual(self.read('.claude/CLAUDE.md'), text)

    def test_skills_are_prefixed_and_references_rewritten(self):
        self.run_kit()
        skills = self.home/'.claude/skills'
        self.assertTrue((skills/'ai-kit-tdd/SKILL.md').is_file())
        self.assertFalse((skills/'tdd').exists())
        implement = self.read('.claude/skills/ai-kit-implement/SKILL.md')
        self.assertIn('name: ai-kit-implement', implement)
        self.assertIn('"ai-kit-tdd"', implement)
        self.assertIn('"ai-kit-code-review"', implement)
        build = self.read('.claude/commands/build.md')
        self.assertIn('the ai-kit-implement skill', build)
        self.assertIn('$ARGUMENTS', build)
        self.assertNotIn('{{args}}', build)

    def test_no_unprefixed_skill_reference_is_left_in_backticks_or_quotes(self):
        self.run_kit()
        names = read_json(self.home/'.ai-kit/state.json')['installed']['skills']
        leftover = re.compile(r'(?<![\w/.-])(`|")(' + '|'.join(map(re.escape, names)) + r')(`|")')
        for path in list((self.home/'.claude/skills').rglob('*.md')) + list((self.home/'.claude/commands').glob('*.md')):
            self.assertIsNone(leftover.search(path.read_text(encoding='utf-8')), path)

    def test_custom_prefix_and_its_change(self):
        self.overrides({'skill_prefix': 'acme-'})
        self.run_kit()
        self.assertTrue((self.home/'.claude/skills/acme-tdd/SKILL.md').is_file())
        self.assertIn('`acme-`', self.read('.claude/CLAUDE.md'))
        self.overrides({'skill_prefix': 'kit-'})
        self.run_kit()
        self.assertFalse((self.home/'.claude/skills/acme-tdd').exists())
        self.assertTrue((self.home/'.claude/skills/kit-tdd/SKILL.md').is_file())

    def test_empty_prefix_refused_on_a_collision_and_invalid_prefix_refused(self):
        self.overrides({'skill_prefix': ''})
        with self.assertRaises(KitError) as caught:
            self.run_kit()  # code-review ships with Claude Code
        self.assertIn('code-review', str(caught.exception))
        self.assertFalse((self.home/'.claude/skills').exists())
        self.overrides({'skill_prefix': 'Bad Prefix!'})
        with self.assertRaises(KitError):
            self.run_kit()

    def test_command_renamed_only_on_a_collision_with_a_personal_skill(self):
        mine = self.home/'.claude/skills/review/SKILL.md'
        mine.parent.mkdir(parents=True)
        mine.write_text('---\nname: review\ndescription: my review\n---\nmine\n', encoding='utf-8')
        notices = self.run_kit()
        self.assertTrue((self.home/'.claude/commands/ai-kit-review.md').is_file())
        self.assertFalse((self.home/'.claude/commands/review.md').exists())
        self.assertTrue((self.home/'.claude/commands/build.md').is_file())
        self.assertEqual(mine.read_text(encoding='utf-8'), '---\nname: review\ndescription: my review\n---\nmine\n')
        self.assertIn('/review is /ai-kit-review', self.read('.claude/CLAUDE.md'))
        self.assertTrue(any('/review installed as /ai-kit-review' in n for n in notices))

    def test_agents_get_claude_tool_names(self):
        self.run_kit()
        verifier = self.read('.claude/agents/ai-kit-verifier.md')
        self.assertIn('tools: Read, Grep, Glob, Bash', verifier)
        self.assertIn('run only the commands', verifier)
        self.assertIn('tools: Read, Grep\n', self.read('.claude/agents/ai-kit-code-reviewer.md'))


class SettingsTests(Base):
    def test_guardrails_beside_personal_hooks_and_edits_detected(self):
        settings = self.home/'.claude/settings.json'
        settings.parent.mkdir()
        settings.write_text(json.dumps({'theme': 'dark', 'hooks': {'PreToolUse': [PERSONAL_HOOK], 'Stop': [PERSONAL_HOOK]}}), encoding='utf-8')
        self.overrides({'hooks': {'dbt-prod-guard': True}})
        self.run_kit()
        data = read_json(settings)
        self.assertEqual(data['theme'], 'dark')
        self.assertEqual(data['hooks']['Stop'], [PERSONAL_HOOK])
        groups = data['hooks']['PreToolUse']
        self.assertEqual(groups[0], PERSONAL_HOOK)
        self.assertEqual({g['matcher'] for g in groups[1:]}, {'Bash', 'Bash|Write|Edit|MultiEdit|NotebookEdit'})
        before = settings.read_bytes()
        self.run_kit()
        self.assertEqual(settings.read_bytes(), before)
        data['hooks']['PreToolUse'][1]['matcher'] = 'Write'
        settings.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(KitError):
            self.run_kit()

    def test_mcp_servers_in_claude_json_translated_and_the_rest_kept(self):
        state = self.home/'.claude.json'
        state.write_text(json.dumps({'numStartups': 3, 'mcpServers': {'mine': {'type': 'stdio', 'command': 'x'}}}), encoding='utf-8')
        self.overrides({'mcp': {'tool': {'server': {'command': 'npx', 'args': ['-y', 'tool'], 'env': {'TOKEN': '${TOOL_TOKEN}'}}},
                                'docs': {'server': {'httpUrl': 'https://docs.example.org/mcp', 'headers': {'X': '1'}}},
                                'events': {'server': {'url': 'https://events.example.org/sse'}}}})
        self.run_kit()
        data = read_json(state)
        self.assertEqual(data['numStartups'], 3)
        servers = data['mcpServers']
        self.assertEqual(servers['mine'], {'type': 'stdio', 'command': 'x'})
        self.assertEqual(servers['ai-kit-tool'], {'type': 'stdio', 'command': 'npx', 'args': ['-y', 'tool'], 'env': {'TOKEN': '${TOOL_TOKEN}'}})
        self.assertEqual(servers['ai-kit-docs'], {'type': 'http', 'url': 'https://docs.example.org/mcp', 'headers': {'X': '1'}})
        self.assertEqual(servers['ai-kit-events'], {'type': 'sse', 'url': 'https://events.example.org/sse'})
        self.overrides({'mcp': {'docs': {'server': {'httpUrl': 'https://docs.example.org/mcp', 'headers': {'X': '1'}}}}})
        self.run_kit()
        self.assertEqual(sorted(read_json(state)['mcpServers']), ['ai-kit-docs', 'mine'])

    def test_mcp_cwd_refused_and_no_file_created_without_servers(self):
        self.run_kit()
        self.assertFalse((self.home/'.claude.json').exists())
        self.overrides({'mcp': {'tool': {'server': {'command': 'tool', 'cwd': '/srv'}}}})
        with self.assertRaises(KitError) as caught:
            self.run_kit()
        self.assertIn('cwd', str(caught.exception))

    def test_mcp_entry_edited_by_hand_stops_the_update(self):
        self.overrides({'mcp': {'docs': {'server': {'httpUrl': 'https://docs.example.org/mcp'}}}})
        self.run_kit()
        state = self.home/'.claude.json'
        data = read_json(state)
        data['mcpServers']['ai-kit-docs']['url'] = 'https://elsewhere.example.org/mcp'
        state.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(KitError):
            self.run_kit()


class RemovalTests(Base):
    def test_removing_claude_leaves_only_the_persons_things(self):
        (self.home/'.claude').mkdir()
        (self.home/'.claude/CLAUDE.md').write_text('Mine.\n', encoding='utf-8')
        (self.home/'.claude/settings.json').write_text(json.dumps({'hooks': {'PreToolUse': [PERSONAL_HOOK]}}), encoding='utf-8')
        (self.home/'.claude.json').write_text(json.dumps({'mcpServers': {'mine': {'type': 'stdio', 'command': 'x'}}}), encoding='utf-8')
        self.overrides({'mcp': {'docs': {'server': {'httpUrl': 'https://docs.example.org/mcp'}}}})
        self.run_kit('claude')
        self.run_kit('gemini')
        self.assertEqual(self.read('.claude/CLAUDE.md'), 'Mine.\n')
        self.assertEqual(read_json(self.home/'.claude/settings.json'), {'hooks': {'PreToolUse': [PERSONAL_HOOK]}})
        self.assertEqual(read_json(self.home/'.claude.json'), {'mcpServers': {'mine': {'type': 'stdio', 'command': 'x'}}})
        self.assertEqual([p for p in (self.home/'.claude').rglob('*') if p.is_file() and 'ai-kit' in p.as_posix()], [])

    def test_uninstall_cleans_claude(self):
        self.run_kit('all')
        with contextlib.redirect_stdout(io.StringIO()):
            cli.uninstall(self.home)
        self.assertFalse((self.home/'.claude/CLAUDE.md').read_text(encoding='utf-8').strip())
        self.assertNotIn('hooks', read_json(self.home/'.claude/settings.json'))
        self.assertTrue((self.home/'.claude/skills').is_dir())  # the CLI's folders stay


class DoctorAndUsageTests(Base):
    def doctor(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.doctor_checks(self.home)
        return out.getvalue()

    def test_doctor_after_install(self):
        self.run_kit()
        out = self.doctor()
        self.assertIn('[OK] Kit block intact in ~/.claude/CLAUDE.md', out)
        self.assertIn('[OK] File imported by ~/.claude/CLAUDE.md present', out)
        self.assertIn('[OK] Guardrails configured in ~/.claude/settings.json', out)
        self.assertNotIn('[Check] Kit block', out)

    def test_usage_reads_the_transcripts_and_observes_skills(self):
        self.run_kit()
        folder = self.home/'.claude/projects/-repo'
        folder.mkdir(parents=True)
        now = '2099-01-01T10:00:00.000Z'
        lines = [{'type': 'user', 'sessionId': 's1', 'timestamp': now, 'message': {'role': 'user', 'content': '<command-message>review</command-message>\n<command-name>/review</command-name>\n<command-args>main</command-args>'}},
                 {'type': 'user', 'sessionId': 's1', 'timestamp': now, 'message': {'role': 'user', 'content': 'explain this module'}},
                 {'type': 'assistant', 'sessionId': 's1', 'timestamp': now, 'message': {'content': [
                     {'type': 'tool_use', 'name': 'Skill', 'input': {'skill': 'ai-kit-tdd'}},
                     {'type': 'tool_use', 'name': 'Agent', 'input': {'subagent_type': 'ai-kit-verifier', 'prompt': 'x'}}]}},
                 {'type': 'assistant', 'sessionId': 's1', 'timestamp': now, 'isApiErrorMessage': True, 'message': {'content': []}},
                 {'type': 'user', 'sessionId': 's1', 'timestamp': now, 'isMeta': True, 'message': {'content': 'meta'}},
                 'not json']
        (folder/'s1.jsonl').write_text('\n'.join(x if isinstance(x, str) else json.dumps(x) for x in lines), encoding='utf-8')
        events = list(claude.history(self.home, read_json(self.home/'.ai-kit/state.json')))
        self.assertEqual([e['text'] for e in events if e['kind'] == 'prompt'], ['/review main', 'explain this module'])
        self.assertEqual([e['name'] for e in events if e['kind'] == 'skill'], ['tdd'])
        self.assertEqual([e['name'] for e in events if e['kind'] == 'agent'], ['ai-kit-verifier'])
        self.assertEqual(len([e for e in events if e['kind'] == 'error']), 1)
        self.assertEqual(claude.OBSERVES, {'prompt', 'skill', 'agent', 'error'})


class GuardrailPayloadTests(unittest.TestCase):
    """The kit's scripts with the JSON Claude Code sends: tool_name and tool_input."""
    def run_hook(self, script, payload, home):
        proc = subprocess.run([sys.executable, '-I', str(H/script)], input=json.dumps(payload), capture_output=True, text=True,
                              encoding='utf-8', env={**os.environ, 'HOME': str(home), 'USERPROFILE': str(home)})
        return json.loads(proc.stdout or '{}')

    def denied(self, answer):
        return answer.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny'

    def test_claude_tool_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            base = {'hook_event_name': 'PreToolUse', 'cwd': str(home), 'session_id': 'x'}
            self.assertTrue(self.denied(self.run_hook('dbt-prod-guard.py', {**base, 'tool_name': 'Bash', 'tool_input': {'command': 'dbt run --target prod'}}, home)))
            self.assertFalse(self.denied(self.run_hook('dbt-prod-guard.py', {**base, 'tool_name': 'Bash', 'tool_input': {'command': 'dbt run --target dev'}}, home)))
            for tool, key in (('Write', 'file_path'), ('Edit', 'file_path'), ('MultiEdit', 'file_path'), ('NotebookEdit', 'notebook_path')):
                for target in ('.claude/settings.json', '.claude.json', '.ai-kit/overrides.json'):
                    answer = self.run_hook('protected-paths.py', {**base, 'tool_name': tool, 'tool_input': {key: str(home/target)}}, home)
                    self.assertTrue(self.denied(answer), tool+' '+target)
            answer = self.run_hook('protected-paths.py', {**base, 'tool_name': 'Write', 'tool_input': {'file_path': str(home/'notes.md')}}, home)
            self.assertFalse(self.denied(answer))
            answer = self.run_hook('protected-paths.py', {**base, 'tool_name': 'Bash', 'tool_input': {'command': 'echo x >> ~/.claude/settings.json'}}, home)
            self.assertTrue(self.denied(answer))


if __name__ == '__main__':
    unittest.main()
