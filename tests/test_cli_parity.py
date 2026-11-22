"""The four adapters treat the same situation the same way: paths under another home, shared files the integrity check
watches, a CLI missing from the PATH, kit names behind a prefix, logs with odd lines. Temporary homes only: no network,
no model, no real CLI."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from installer import cli, core, doctor, versions
from installer.adapters import agy, claude, codex, gemini
from installer.core import ROOT, read_json
from installer.interface import DoctorContext
from personal import write_personal  # noqa: E402
from presets import apply_as  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        patcher = mock.patch('shutil.which', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def core_servers(self, servers):
        org = {'defaults': {'mcp': {name: {'server': server} for name, server in servers.items()}}}
        for target in ('installer.settings.core_settings', 'installer.plan.core_settings', 'installer.cli.core_settings', 'installer.doctor.core_settings'):
            patcher = mock.patch(target, return_value=org)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_kit(self, target='all'):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            notices = apply_as('general', self.home, False, {'email': 'a@example.org', 'source': 'option'}, target)
        self.out = out.getvalue()
        return notices

    def state(self):
        return read_json(self.home/'.ai-kit/state.json')

    def read(self, rel):
        return (self.home/rel).read_text(encoding='utf-8')

    def write_json(self, rel, data):
        (self.home/rel).write_text(json.dumps(data), encoding='utf-8')

    def doctor_lines(self, adapter, state=None):
        lines, out = [], io.StringIO()
        ctx = DoctorContext(context_names=['00_KIT.md', '10_CORE.md'], load_commands=core.load_commands)
        with contextlib.redirect_stdout(out):
            adapter.doctor(self.home, state or self.state(), lambda ok, message: lines.append(('[OK] ' if ok else '[Fail] ')+message), ctx)
        return lines, out.getvalue()


class AgyTests(Base):
    def test_the_version_checked_is_the_one_the_tool_names_were_read_on(self):
        self.assertEqual(agy.VERIFIED, '1.5.14')

    def test_rules_name_the_context_of_the_home_the_kit_was_installed_in(self):
        self.run_kit('agy')
        rules = self.read(agy.AGY_PLUGIN+'/rules/AGENTS.md')
        self.assertIn('@[00_kit]('+(self.home/'.ai-kit/context/00_KIT.md').as_posix()+')', rules)
        self.assertNotIn('(~/', rules)

    def test_rules_name_the_context_from_the_tilde_in_the_persons_own_home(self):
        with mock.patch('pathlib.Path.home', return_value=self.home):
            self.run_kit('agy')
        self.assertIn('@[user](~/.ai-kit/context/USER.md)', self.read(agy.AGY_PLUGIN+'/rules/AGENTS.md'))

    def test_a_conversation_is_read_whatever_characters_its_folder_holds(self):
        # '?' cannot be in a file name on Windows; the space, '#' and '%41' are the ones a URI would misread everywhere.
        home = self.home/('a #b c %41' if os.name == 'nt' else 'a #b ?c %41')
        folder = home/'.gemini/antigravity-cli/conversations'
        folder.mkdir(parents=True)
        with contextlib.closing(sqlite3.connect(str(folder/'c1.db'))) as db:
            db.execute('create table steps (idx integer, step_type integer, step_payload blob)')
            db.execute('insert into steps values (?, ?, ?)', (0, 132, b'\x12\x0finvoke_subagent\x1a{"Prompt":"look","TypeName":"ai-kit-verifier"}2'))
            db.commit()
        events = list(agy.conversation_events(home, {'installed': {'skills': ['tdd']}}))
        self.assertEqual([e['name'] for e in events], ['ai-kit-verifier'])

    def test_a_conversation_another_process_holds_is_left_out_quickly(self):
        calls = []
        real = sqlite3.connect
        def connect(*args, **kwargs):
            calls.append(kwargs)
            return real(*args, **kwargs)
        folder = self.home/'.gemini/antigravity-cli/conversations'
        folder.mkdir(parents=True)
        real(str(folder/'c1.db')).close()
        with mock.patch('sqlite3.connect', side_effect=connect):
            list(agy.conversation_events(self.home, {}))
        self.assertLessEqual(calls[0].get('timeout', 5), 0.5)

    def test_doctor_says_when_whats_new_is_off_since_integrity_runs_through_it(self):
        write_personal(self.home, {'hooks': {'whats-new': False}})
        self.run_kit('agy')
        _, out = self.doctor_lines(agy)
        self.assertIn('[Check] Antigravity CLI: whats-new is off', out)
        self.assertIn('integrity', out)

    def test_doctor_says_nothing_about_it_when_whats_new_is_on(self):
        self.run_kit('agy')
        self.assertNotIn('whats-new is off', self.doctor_lines(agy)[1])

    def test_history_skips_lines_that_are_not_objects_and_reads_conversations_without_a_prompt_file(self):
        folder = self.home/'.gemini/antigravity-cli'
        (folder/'conversations').mkdir(parents=True)
        with contextlib.closing(sqlite3.connect(str(folder/'conversations/c1.db'))) as db:
            db.execute('create table steps (idx integer, step_type integer, step_payload blob)')
            db.execute('insert into steps values (?, ?, ?)', (0, 132, b'\x1a{"TypeName":"ai-kit-doubter"}2'))
            db.commit()
        self.assertEqual([e['name'] for e in agy.history(self.home, {})], ['ai-kit-doubter'])  # no history.jsonl
        (folder/'history.jsonl').write_text('null\n123\n"text"\n[1]\n'+json.dumps({'display': 'hello', 'timestamp': 1000, 'conversationId': 'c1'})+'\n', encoding='utf-8')
        events = list(agy.history(self.home, {}))
        self.assertEqual([e['kind'] for e in events], ['prompt', 'agent'])


class GeminiTests(Base):
    def test_a_layer_whose_name_holds_a_digit_is_retired_like_the_others(self):
        self.run_kit('gemini')
        state = self.state()
        layer = self.home/'.gemini/20_TEAM2.md'
        layer.write_text('# Team 2\n', encoding='utf-8')
        state['files']['.gemini/20_TEAM2.md'] = core.digest(layer.read_bytes())
        self.write_json('.ai-kit/state.json', state)
        settings = read_json(self.home/'.gemini/settings.json')
        settings['context']['fileName'].insert(2, '20_TEAM2.md')
        self.write_json('.gemini/settings.json', settings)
        self.run_kit('gemini')
        self.assertNotIn('20_TEAM2.md', read_json(self.home/'.gemini/settings.json')['context']['fileName'])

    def test_a_layer_taken_out_of_the_context_files_is_a_change(self):
        self.run_kit('gemini')
        self.assertEqual(gemini.changed_blocks(self.home, self.state()), [])
        settings = read_json(self.home/'.gemini/settings.json')
        settings['context']['fileName'].remove('10_CORE.md')
        self.write_json('.gemini/settings.json', settings)
        self.assertEqual(gemini.changed_blocks(self.home, self.state()), ['.gemini/settings.json'])

    def test_a_kit_server_removed_or_edited_is_a_change(self):
        self.core_servers({'docs': {'httpUrl': 'https://mcp.example.org/docs'}})
        write_personal(self.home, {'mcp': {'docs': True}})
        self.run_kit('gemini')
        self.assertEqual(gemini.changed_blocks(self.home, self.state()), [])
        settings = read_json(self.home/'.gemini/settings.json')
        settings['mcpServers']['ai-kit-docs']['httpUrl'] = 'https://elsewhere.example.org/docs'
        self.write_json('.gemini/settings.json', settings)
        self.assertEqual(gemini.changed_blocks(self.home, self.state()), ['.gemini/settings.json'])

    def test_hooks_switched_off_are_a_change(self):
        self.run_kit('gemini')
        for switches in ({'enabled': False}, {'disabled': ['ai-kit-protected-paths']}):
            settings = read_json(self.home/'.gemini/settings.json')
            settings['hooksConfig'] = switches
            self.write_json('.gemini/settings.json', settings)
            self.assertEqual(gemini.changed_blocks(self.home, self.state()), ['.gemini/settings.json'], switches)
        settings['hooksConfig'] = {'enabled': True, 'disabled': ['my-own-hook']}
        self.write_json('.gemini/settings.json', settings)
        self.assertEqual(gemini.changed_blocks(self.home, self.state()), [])

    def test_doctor_says_gemini_is_not_on_the_path_without_failing(self):
        self.run_kit('gemini')
        lines, out = self.doctor_lines(gemini)
        self.assertIn('[Info] Gemini CLI set up by the kit but not on the PATH.', out)
        self.assertEqual([line for line in lines if 'on the PATH' in line], [])

    def test_a_skill_activated_under_its_prefix_counts_for_the_kit_skill(self):
        self.run_kit('gemini')
        state = self.state()
        state['files']['.gemini/skills/ai-kit-tdd/SKILL.md'] = 'x'  # installed under the prefix: the person has a tdd of their own
        state['installed']['skills'] = sorted(set(state['installed']['skills']) | {'tdd'})
        chat = self.home/'.gemini/tmp/p/chats'
        chat.mkdir(parents=True)
        calls = [{'name': 'activate_skill', 'args': {'name': n}} for n in ('ai-kit-tdd', 'create-tdd')]
        (chat/'s.json').write_text(json.dumps({'messages': [{'type': 'gemini', 'timestamp': '2099-01-01T10:00:00Z', 'toolCalls': calls}]}), encoding='utf-8')
        self.assertEqual([e['name'] for e in gemini.history(self.home, state) if e['kind'] == 'skill'], ['tdd', 'create-tdd'])


class CodexTests(Base):
    BLOCK = codex.CODEX_MD[0]+'\n# from another machine\n'+codex.CODEX_MD[1]+'\n'

    def test_a_codex_the_kit_never_configured_is_left_alone(self):
        (self.home/'.codex').mkdir()
        (self.home/'.codex/AGENTS.md').write_text(self.BLOCK, encoding='utf-8')
        (self.home/'.codex/config.toml').write_text(codex.CODEX_TOML[0]+'\nmodel = "x"\n'+codex.CODEX_TOML[1]+'\n', encoding='utf-8')
        self.run_kit('claude')  # Codex is not a target and never was
        self.assertEqual(self.read('.codex/AGENTS.md'), self.BLOCK)
        self.assertIn('model = "x"', self.read('.codex/config.toml'))

    def test_doctor_reports_a_user_file_that_is_not_utf8_instead_of_stopping(self):
        self.run_kit('codex')
        (self.home/'.ai-kit/context/USER.md').write_bytes(b'caf\xe9\n')
        lines, _ = self.doctor_lines(codex)
        self.assertTrue(any(line.startswith('[Fail] Codex has the latest version of USER.md') and 'UTF-8' in line for line in lines), lines)

    def test_an_approval_of_the_integrity_hook_is_a_record_like_the_others(self):
        (self.home/'.codex').mkdir()
        (self.home/'.codex/config.toml').write_text('[hooks.state."/h/.codex/config.toml:post_tool_use:0:0"]\ntrusted_hash = "x"\n', encoding='utf-8')
        self.assertTrue(codex.hook_approval(self.home)[0])

    def test_hooks_after_a_tool_written_in_another_form_stop_the_installation(self):
        (self.home/'.codex').mkdir()
        (self.home/'.codex/config.toml').write_text('[hooks]\nPostToolUse = [{ matcher = ".*", hooks = [] }]\n', encoding='utf-8')
        with self.assertRaises(core.KitError) as raised:
            self.run_kit('codex')
        self.assertIn('hooks.PostToolUse', str(raised.exception))

    def test_a_command_skill_says_how_the_command_is_typed_in_codex(self):
        self.run_kit('all')
        text = self.read('.codex/skills/guide/SKILL.md')
        self.assertIn('Kit command $guide.', text)
        self.assertIn('types $guide', text)
        self.assertNotIn('/guide.', text.split('---')[1])
        self.assertIn('Kit command /guide.', self.read(agy.AGY_PLUGIN+'/skills/guide/SKILL.md'))

    def test_history_skips_lines_that_are_not_objects_and_reads_sessions_without_a_prompt_file(self):
        self.run_kit('codex')
        state = self.state()
        folder = self.home/'.codex/sessions/2099/01/01'
        folder.mkdir(parents=True)
        call = {'timestamp': '2099-01-01T10:00:00.000Z', 'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'spawn_agent', 'arguments': json.dumps({'agent_type': 'ai-kit-verifier'})}}
        (folder/'rollout-2099-01-01T10-00-00-abc.jsonl').write_text(json.dumps(call), encoding='utf-8')
        self.assertEqual([e['name'] for e in codex.history(self.home, state)], ['ai-kit-verifier'])  # no history.jsonl
        (self.home/'.codex/history.jsonl').write_text('null\n123\n[]\n'+json.dumps({'session_id': 's', 'ts': 1, 'text': '$guide'})+'\n', encoding='utf-8')
        self.assertEqual([e['kind'] for e in codex.history(self.home, state)], ['prompt', 'agent'])


class ClaudeTests(Base):
    def test_a_kit_server_removed_or_edited_in_claude_json_is_a_change(self):
        self.core_servers({'docs': {'httpUrl': 'https://mcp.example.org/docs'}})
        write_personal(self.home, {'mcp': {'docs': True}})
        self.run_kit('claude')
        self.assertEqual(claude.changed_blocks(self.home, self.state()), [])
        data = read_json(self.home/'.claude.json')
        data['mcpServers']['ai-kit-docs']['url'] = 'https://elsewhere.example.org/docs'
        data['numStartups'] = 12  # the rest of the file is Claude Code's
        self.write_json('.claude.json', data)
        self.assertEqual(claude.changed_blocks(self.home, self.state()), ['.claude.json'])
        del data['mcpServers']
        self.write_json('.claude.json', data)
        self.assertEqual(claude.changed_blocks(self.home, self.state()), ['.claude.json'])

    def test_claude_json_without_kit_servers_is_never_a_change(self):
        self.run_kit('claude')
        self.write_json('.claude.json', {'numStartups': 3})
        self.assertEqual(claude.changed_blocks(self.home, self.state()), [])

    def test_the_integrity_check_watches_claude_json(self):
        spec = importlib.util.spec_from_file_location('hook_integrity', ROOT/'runtime/hooks/integrity.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn('.claude.json', module.SHARED)
        self.core_servers({'docs': {'httpUrl': 'https://mcp.example.org/docs'}})
        write_personal(self.home, {'mcp': {'docs': True}})
        self.run_kit('claude')
        data = read_json(self.home/'.claude.json')
        data['mcpServers']['ai-kit-docs']['url'] = 'https://elsewhere.example.org/docs'
        self.write_json('.claude.json', data)
        changes, failed, _ = module.shared_changes(str(self.home), self.state(), {}, True)
        self.assertEqual(([name for name, _ in changes], failed), (['.claude.json'], []))

    def test_a_repo_skill_in_dot_claude_with_a_kit_name_is_found(self):
        self.assertIn('.claude/skills', doctor.REPO_SKILL_DIRS)
        repo = self.home/'repo'
        (repo/'.git').mkdir(parents=True)
        (repo/'.claude/skills/tdd').mkdir(parents=True)
        (repo/'.claude/skills/tdd/SKILL.md').write_text('---\nname: tdd\n---\n', encoding='utf-8')
        _, found = doctor.repo_skill_overrides({'installed': {'skills': ['tdd'], 'commands': []}}, repo)
        self.assertEqual(found, [('tdd', '.claude/skills/tdd')])

    def test_a_personal_skill_whose_name_ends_like_a_kit_skill_is_not_the_kit_skill(self):
        self.run_kit('claude')
        state = self.state()
        self.assertIn('mr', state['installed']['skills'])
        folder = self.home/'.claude/projects/-repo'
        folder.mkdir(parents=True)
        calls = [{'type': 'tool_use', 'name': 'Skill', 'input': {'skill': name}} for name in ('create-mr', 'ai-kit-mr', 'mr')]
        (folder/'s.jsonl').write_text(json.dumps({'type': 'assistant', 'timestamp': '2099-01-01T10:00:00Z', 'sessionId': 's', 'message': {'content': calls}}), encoding='utf-8')
        self.assertEqual([e['name'] for e in claude.history(self.home, state) if e['kind'] == 'skill'], ['create-mr', 'mr', 'mr'])


class KitNameTests(unittest.TestCase):
    def test_only_a_real_prefix_gives_the_kit_name(self):
        known = {'mr', 'code-review', 'review'}
        self.assertEqual(core.kit_name('ai-kit-mr', known), 'mr')
        self.assertEqual(core.kit_name('create-mr', known), 'create-mr')
        self.assertEqual(core.kit_name('ai-kit-code-review', known), 'code-review')
        self.assertEqual(core.kit_name('kit-mr', known), 'kit-mr')
        self.assertEqual(core.kit_name('kit-mr', known, ('kit-',)), 'mr')
        self.assertEqual(core.kit_name('mr', known), 'mr')

    def test_the_prefixes_in_use_are_read_from_what_the_kit_installed(self):
        state = {'installed': {'skills': ['mr', 'code-review', 'review'], 'commands': ['guide']},
                 'files': {'.claude/skills/kit-code-review/SKILL.md': 'x', '.gemini/skills/review/SKILL.md': 'x', '.codex/skills/code-review/SKILL.md': 'x',
                           '.claude/commands/kit-guide.md': 'x', '.gemini/commands/guide.toml': 'x', '.claude/agents/ai-kit-verifier.md': 'x'}}
        self.assertEqual(sorted(core.kit_prefixes(state)), ['ai-kit-', 'kit-'])

    def test_a_skill_file_read_under_the_persons_prefix_counts(self):
        self.assertEqual(core.skills_read('cat /h/.codex/skills/kit-mr/SKILL.md /h/.codex/skills/create-mr/SKILL.md', {'mr'}, ('kit-',)), ['mr'])


class UsageTests(Base):
    def usage(self, events, commands=('diagnose', 'build'), files=None):
        (self.home/'.ai-kit').mkdir(exist_ok=True)
        self.write_json('.ai-kit/state.json', {'version': '0', 'targets': ['claude'], 'files': files or {'.claude/commands/ai-kit-diagnose.md': 'x'},
                                               'installed': {'skills': ['tdd'], 'commands': list(commands), 'agents': []}})
        out = io.StringIO()
        with mock.patch.object(cli.ADAPTERS[0], 'history', return_value=events), contextlib.redirect_stdout(out):
            cli.usage(self.home, as_json=self.home/'r.json')
        return read_json(self.home/'r.json')

    def test_a_command_typed_under_its_new_name_counts_for_the_kit_command(self):
        report = self.usage([{'kind': 'prompt', 'text': '/ai-kit-diagnose the export', 'session': 'a', 'ts': 9e12},
                             {'kind': 'prompt', 'text': '/pre-build something else entirely', 'session': 'b', 'ts': 9e12}])
        self.assertEqual(report['commands'], {'diagnose': 1})
        self.assertEqual(report['unknown_commands'], {'pre-build': 1})
        self.assertEqual(report['sessions_with_the_kit'], 1)

    def test_the_frictions_fixed_are_read_from_the_changelog_of_the_content_in_use(self):
        content = self.home/'content'
        content.mkdir()
        for name in ('skills', 'agents', 'commands'):
            (content/name).mkdir()
        (self.home/'.ai-kit').mkdir()
        entry = {'ts': '2099-01-01T10:00:00Z', 'text': 'a friction', 'category': 'other'}
        entry['id'] = core.friction_id(entry['ts'], entry['text'])
        (self.home/'.ai-kit/frictions.jsonl').write_text(json.dumps(entry)+'\n', encoding='utf-8')
        (content/'CHANGELOG.md').write_text('## 9.9.9 (2099-01-02)\n\n- Fixed (frictions: '+entry['id']+').\n', encoding='utf-8')
        from installer import usage
        with core.content_from(content):
            _, fixed = usage.read_frictions(self.home, 0)
        self.assertEqual(fixed, {entry['id']: '9.9.9'})


class VersionsTests(unittest.TestCase):
    def test_versions_are_read_from_the_content_in_use(self):
        with tempfile.TemporaryDirectory() as folder:
            content = Path(folder)
            skill = content/'skills/internal/common/alpha'
            skill.mkdir(parents=True)
            (skill/'SKILL.md').write_text('---\nname: alpha\ndescription: An example. Use when asked.\nmetadata:\n  aikit-version: 1.2.3\n  aikit-category: tool\n---\n\nBody.\n', encoding='utf-8')
            (content/'agents').mkdir()
            with core.content_from(content):
                now = versions.current()
                self.assertEqual(versions.lock_path(), content/'versions.lock.json')
            self.assertEqual(list(now['skills']), ['alpha'])
            self.assertEqual(now['skills']['alpha']['version'], '1.2.3')
        self.assertEqual(versions.lock_path(), ROOT/'versions.lock.json')


class McpReportTests(Base):
    def test_a_server_it_refuses_is_not_said_configured(self):
        self.core_servers({'docs': {'httpUrl': 'https://mcp.example.org/docs'}, 'wiki': {'httpUrl': 'https://wiki.example.org/mcp'}})
        write_personal(self.home, {'mcp': {'docs': True, 'wiki': True}})
        (self.home/'.ai-kit').mkdir(exist_ok=True)
        with mock.patch('installer.doctor.load_managed', return_value={'mcp': {'denied': ['docs']}}):
            lines = doctor.mcp_report(self.home, {})
        text = ' '.join(lines)
        self.assertIn('wiki configured', text)
        self.assertNotIn('docs, wiki configured', text)
        self.assertIn('docs not installed', text)

    def test_a_local_server_from_a_team_that_nobody_approved_is_not_said_configured(self):
        team = {'mcp': {'files': {'server': {'command': 'node', 'args': ['server.js']}, 'enabled': True, 'team': True}}}
        self.core_servers({})
        (self.home/'.ai-kit').mkdir(exist_ok=True)
        with mock.patch('installer.doctor.load_managed', return_value=None), mock.patch('installer.doctor.team_settings', return_value=team):
            waiting = ' '.join(doctor.mcp_report(self.home, {'team': 'data'}))
            identity = __import__('installer.config', fromlist=['server_identity']).server_identity(team['mcp']['files']['server'])
            approved = ' '.join(doctor.mcp_report(self.home, {'team': 'data', 'mcp_approvals': [identity]}))
        self.assertIn('files not installed', waiting)
        self.assertIn('files configured', approved)


if __name__ == '__main__':
    unittest.main()
