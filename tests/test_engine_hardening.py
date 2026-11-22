"""MCP server definitions the validation let through or refused by mistake, and engine behaviours that cost a retry or wrote
when they should not: a Team's parallel agents default, the USER.md copy of a CLI when the file is refused, a renamed
skill inside another program's command, the verifier's opening, doctor and release checks without the network, a dry
run that writes nothing, the launcher's reinstall, and bounds on what a source may hold. No network, no model."""
import contextlib
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from installer import cli, config, doctor, sources, validate
from installer.core import ROOT, KitError, rename_references
from installer.settings import validate_server

sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'tests'))
import launcher  # noqa: E402
import test_git_sources  # noqa: E402
import test_targets_and_context  # noqa: E402

SECRET = 'ghp_'+'a1B2'*9


def refused(server):
    try:
        validate_server(server)
    except KitError as exc:
        return str(exc)
    return ''


class McpServerTests(unittest.TestCase):
    def test_a_header_made_of_a_standard_scheme_and_a_variable_is_accepted(self):
        for value in ('Bearer ${API_TOKEN}', 'bearer ${API_TOKEN}', 'Basic ${CREDENTIALS}', 'Token ${T}', '${API_TOKEN}'):
            self.assertEqual(refused({'httpUrl': 'https://mcp.example.org/mcp', 'headers': {'Authorization': value}}), '', value)
        for value in ('Bearer abcdefghijklmnop', 'Bearer ${API_TOKEN} and-more', 'Bearer '+SECRET, 'Custom ${API_TOKEN}'):
            self.assertIn('looks secret', refused({'httpUrl': 'https://mcp.example.org/mcp', 'headers': {'Authorization': value}}), value)

    def test_a_shell_an_inline_script_or_a_wrapper_is_refused_whatever_its_spelling(self):
        for server in ({'command': 'node', 'args': ['-e', 'require("child_process").exec("x")']},
                       {'command': 'node.exe', 'args': ['--eval', 'x']},
                       {'command': 'python3', 'args': ['-c', 'import os']},
                       {'command': 'deno', 'args': ['eval', 'x']},
                       {'command': 'env', 'args': ['bash', '-c', 'x']},
                       {'command': '/usr/bin/env', 'args': ['FOO=1', 'tracker-mcp']},
                       {'command': 'Bash.EXE', 'args': ['server.sh']},
                       {'command': 'tool', 'args': ['-COMMAND', 'x']},
                       {'command': 'tool', 'args': ['-command', 'x']},
                       {'command': 'tool', 'args': ['/C', 'x']},
                       {'command': 'tool', 'args': ['-EncodedCommand', 'x']}):
            self.assertIn('name the program itself', refused(server), server)
        for server in ({'command': 'node', 'args': ['server.js', '--port', '3000']}, {'command': 'tracker-mcp', 'args': ['--config', 'c.toml']},
                       {'command': 'python3', 'args': ['-m', 'tracker_mcp']}):
            self.assertEqual(refused(server), '', server)

    def test_cwd_is_a_text(self):
        self.assertIn('cwd', refused({'command': 'tracker-mcp', 'cwd': 3}))
        self.assertIn('cwd', refused({'command': 'tracker-mcp', 'cwd': ['a']}))
        self.assertEqual(refused({'command': 'tracker-mcp', 'cwd': '~/work'}), '')

    def test_a_windows_launcher_script_is_the_same_fetch_and_run_launcher(self):
        for command in ('npx.cmd', 'uvx.exe', 'pnpx.cmd', 'bunx.exe', 'pipx.exe', r'C:\Program Files\nodejs\NPX.CMD', 'npx'):
            self.assertTrue(config.unpinned_launcher({'command': command, 'args': ['some-server']}), command)
        self.assertFalse(config.unpinned_launcher({'command': 'npx.cmd', 'args': ['-y', 'some-server@1.2.3']}))
        self.assertFalse(config.unpinned_launcher({'command': 'tracker-mcp.exe', 'args': []}))

    def test_a_denied_entry_matches_without_case_and_stops_at_the_end_of_the_host(self):
        server = {'httpUrl': 'https://mcp.example.org/mcp'}
        for entry, expected in (('https://mcp.example.org', True), ('https://MCP.Example.org', True), ('https://mcp.example.org/mcp', True),
                                ('https://mcp.example.org/', True), ('https://mcp.example', False), ('https://mcp.example.org/mc', False),
                                ('https://mcp.example.org.evil.test', False)):
            self.assertEqual(config.denied_match('docs', server, [entry]), expected, entry)
        self.assertTrue(config.denied_match('docs', {'httpUrl': 'https://mcp.example.org:8443/mcp'}, ['https://mcp.example.org']))
        for command, entry in ((r'C:\Tools\NPX.CMD', 'npx'), ('/usr/local/bin/Tracker', 'tracker'), ('npx', 'NPX'), ('npx.exe', 'npx.exe')):
            self.assertTrue(config.denied_match('x', {'command': command}, [entry]), (command, entry))
        self.assertFalse(config.denied_match('x', {'command': 'npx-wrapper'}, ['npx']))
        self.assertTrue(config.denied_match('docs', server, ['docs']))

    def test_validate_reads_the_servers_of_a_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'aikit.toml').write_text('schema = 1\nname = "data"\nkind = "team"\nmin_engine = "2.0.0"\n', encoding='utf-8')
            (root/'mcp').mkdir()
            servers = root/'mcp'/'servers.toml'
            for text, expected in (
                    ('[servers.docs]\nhttpUrl = "http://mcp.example.org/mcp"\n', 'mcp/servers.toml: docs: Remote MCP: HTTPS URL expected.'),
                    ('[servers.tracker]\ncommand = "bash"\nargs = ["run.sh"]\n', 'mcp/servers.toml: tracker: MCP: bash runs a shell'),
                    ('[servers.tracker]\ncommand = "npx.cmd"\nargs = ["tracker-mcp"]\n', 'mcp/servers.toml: tracker: its launcher fetches a package without an exact version'),
                    ('[servers.docs]\nhttpUrl = "https://mcp.example.org/mcp"\nenabled = "yes"\n', 'mcp/servers.toml: docs: enabled must be true or false'),
                    ('servers = 3\n', 'mcp/servers.toml: one table per server'),
                    ('[servers.docs\n', 'mcp/servers.toml')):
                servers.write_text(text, encoding='utf-8')
                found = validate.problems(root, '99.0.0')
                self.assertTrue(any(expected in line for line in found), (text, found))
            servers.write_text('[servers.docs]\nhttpUrl = "https://mcp.example.org/mcp"\n[servers.docs.headers]\nAuthorization = "Bearer ${DOCS_TOKEN}"\n', encoding='utf-8')
            self.assertEqual(validate.problems(root, '99.0.0'), [])


class TeamDefaultsTests(unittest.TestCase):
    def manifest(self, line):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        (Path(temp.name)/'aikit.toml').write_text('schema = 1\nname = "data"\nkind = "team"\nmin_engine = "2.0.0"\n[defaults]\n'+line+'\n', encoding='utf-8')
        return Path(temp.name)

    def test_a_team_sets_parallel_agents(self):
        self.assertIs(config.check_source(self.manifest('parallel_agents = true\nextra_skills = ["tdd"]'), '99.0.0')['defaults']['parallel_agents'], True)
        for line in ('parallel_agents = "yes"', 'parallel_agents = ["a"]', 'extra_skills = true', 'unknown = true'):
            with self.assertRaises(KitError, msg=line):
                config.check_source(self.manifest(line), '99.0.0')


class RefusedUserFileTests(test_targets_and_context.Base):
    def test_every_cli_keeps_its_last_copy_and_the_person_is_told_once(self):
        self.run_kit('all')
        user = self.home/'.ai-kit/context/USER.md'
        user.write_text('Valid preference\n', encoding='utf-8')
        self.run_kit('all')
        copy = self.home/'.gemini/USER.md'
        self.assertEqual(copy.read_text(encoding='utf-8'), 'Valid preference\n')
        user.write_text('Valid preference\n'+SECRET+'\n', encoding='utf-8')
        notices = self.run_kit('all')
        self.assertTrue(copy.exists(), 'the copy Gemini reads was removed')
        self.assertEqual(copy.read_text(encoding='utf-8'), 'Valid preference\n')
        self.assertIn('.gemini/USER.md', self.state()['files'])
        self.assertIn('Valid preference', (self.home/'.codex/AGENTS.md').read_text(encoding='utf-8'))
        told = [n for n in notices if 'USER.md' in n and 'not copied' in n]
        self.assertEqual(len(told), 1, notices)
        self.assertTrue(told[0].startswith('[Check] '))
        self.assertNotIn(SECRET, ''.join(notices)+self.out)
        self.run_kit('all')  # a second run changes nothing more
        self.assertEqual(copy.read_text(encoding='utf-8'), 'Valid preference\n')
        user.write_text('Fixed preference\n', encoding='utf-8')
        self.assertEqual([n for n in self.run_kit('all') if 'not copied' in n], [])
        self.assertEqual(copy.read_text(encoding='utf-8'), 'Fixed preference\n')


class RenamedReferencesTests(unittest.TestCase):
    def test_a_word_of_another_programs_command_is_not_a_skill(self):
        mapping = {'mr': 'ai-kit-mr', 'research': 'ai-kit-research', 'tdd': 'ai-kit-tdd'}
        for text in ('Open it with `glab mr create --fill`.', 'Run `glab mr` then `gh pr create`.', 'See `docs/research` and `uv run tdd-tool`.',
                     'A plain mr in a sentence, and research too.', '`git log --grep mr`'):
            self.assertEqual(rename_references(text, mapping), text)
        for text, expected in (('Use `mr`.', 'Use `ai-kit-mr`.'), ('the mr skill', 'the ai-kit-mr skill'), ('Type /mr now', 'Type /ai-kit-mr now'),
                               ('the Skill tool with "research"', 'the Skill tool with "ai-kit-research"'), ('`/tdd`', '`/ai-kit-tdd`'),
                               ('$tdd', '$ai-kit-tdd'), ('the `tdd` skill', 'the `ai-kit-tdd` skill')):
            self.assertEqual(rename_references(text, mapping), expected)


class VerifierOpeningTests(unittest.TestCase):
    def test_the_opening_does_not_forbid_what_the_verifier_is_told_to_run(self):
        text = cli.agent_instruction({'tools': ['read_file', 'run_shell_command']})
        self.assertNotIn('Modify no file;', text)  # ADR 0033: the proof script swaps files for a moment
        self.assertIn('yourself', text)
        self.assertIn('run only the commands your instructions below allow', text)
        self.assertIn('modify no file and run no command', cli.agent_instruction({'tools': ['read_file']}))


class DoctorWithoutNetworkTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)

    def tracker(self, live):
        lines, calls = [], []
        def run_timed(command, *args, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)
        state = {'friction_tracker': {'kind': 'gitlab', 'project': 'tools/ai-kit', 'host': None, 'labels': [], 'sources': ['agent']}}
        with mock.patch.object(doctor.shutil, 'which', return_value='/usr/bin/glab'), mock.patch.object(doctor, 'run_timed', side_effect=run_timed), \
                contextlib.redirect_stdout(io.StringIO()):
            doctor.tracker_checks(self.home, state, lambda ok, message: lines.append((ok, message)), live=live)
        return lines, calls

    def test_the_tracker_sign_in_is_asked_only_by_a_live_doctor(self):
        lines, calls = self.tracker(live=False)
        self.assertEqual(calls, [])  # `glab auth status` calls the host
        self.assertTrue(lines[0][0])
        self.assertIn('doctor --live', lines[0][1])
        lines, calls = self.tracker(live=True)
        self.assertEqual([c[1:] for c in calls], [['auth', 'status']])
        self.assertIn('signed in', lines[0][1])

    def test_the_release_check_changes_nothing_in_the_kit_folder(self):
        folder = self.home/'kit'
        (folder/'.git').mkdir(parents=True)
        (folder/'VERSION').write_text('1.0.0\n', encoding='utf-8')
        calls = []
        def run(command, *args, **kwargs):
            calls.append(command)
            listing = 'aaa\trefs/tags/v1.0.0\nbbb\trefs/tags/v1.2.0\nccc\trefs/tags/v1.10.0\nddd\trefs/tags/not-a-version\n'
            return subprocess.CompletedProcess(command, 0, stdout=listing if 'ls-remote' in command else '', stderr='')
        out = io.StringIO()
        with mock.patch.object(doctor, 'source_folder', return_value=folder), mock.patch.object(doctor.shutil, 'which', return_value='/usr/bin/git'), \
                mock.patch.object(doctor.subprocess, 'run', side_effect=run), contextlib.redirect_stdout(out):
            doctor.release_check()
        self.assertIn('AI Kit 1.10.0 is published', out.getvalue())
        self.assertTrue(calls)
        for command in calls:
            self.assertNotIn('fetch', command)  # a fetch writes the clone and runs what its configuration names
            self.assertNotIn('pull', command)
        self.assertTrue(any('ls-remote' in c for c in calls))


def tree(folder):
    return {p.relative_to(folder).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
            for p in sorted(Path(folder).rglob('*'))}


class DryRunTests(test_git_sources.Base):
    def test_a_dry_run_of_sync_writes_nothing_at_all(self):
        self.run_action('sync')
        self.release('v1.1.0', 'Marker v1.1.0.', push=True)
        before = tree(self.home)
        out = self.run_action('sync', dry_run=True)
        self.assertIn('v1.1.0', out)  # the preview still says what would come
        self.assertEqual({k: v for k, v in tree(self.home).items() if before.get(k, '') != v}, {})
        self.assertEqual(sorted(set(before) - set(tree(self.home))), [])

    def test_a_first_dry_run_creates_no_folder(self):
        before = tree(self.home)
        self.run_action('sync', dry_run=True)
        self.assertEqual(tree(self.home), before)


class SourceBoundsTests(test_git_sources.Base):
    def extract(self):
        entry = self.lock_after_sync()
        dest = self.base/('out-'+str(len(list(self.base.glob('out-*')))))
        dest.mkdir()
        return sources.extract(self.kit, sources.cache_dir(self.kit, self.url), entry['commit'], dest), dest

    def lock_after_sync(self):
        if not (self.kit/'lock.toml').exists():
            self.run_action('sync')
        return self.lock()['sources']['core']

    def test_a_source_with_too_many_or_too_large_files_is_refused_before_it_is_read(self):
        digest, dest = self.extract()
        self.assertEqual(digest, test_git_sources.tree_digest(dest))  # as before, within the bounds
        for name, value, word in (('MAX_FILES', 3, 'files'), ('MAX_FILE_BYTES', 10, 'larger'), ('MAX_TOTAL_BYTES', 1000, 'in all')):
            with mock.patch.object(sources, name, value), mock.patch.object(sources, 'git', wraps=sources.git) as git:
                with self.assertRaises(sources.SourceError) as caught:
                    self.extract()
            self.assertEqual(caught.exception.kind, 'invalid', name)
            self.assertIn(word, str(caught.exception), name)
            self.assertFalse(any('cat-file' in call.args[0] for call in git.call_args_list), name)  # refused from the listing

    def test_a_large_source_is_read_in_several_batches(self):
        with mock.patch.object(sources, 'BATCH_BYTES', 20000), mock.patch.object(sources, 'git', wraps=sources.git) as git:
            digest, dest = self.extract()
        self.assertEqual(digest, test_git_sources.tree_digest(dest))
        self.assertGreater(sum('cat-file' in call.args[0] for call in git.call_args_list), 1)


class LauncherReinstallTests(unittest.TestCase):
    def test_the_kit_is_never_removed_before_its_new_version_is_installed(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)/'runtime'
            (runtime/'venv').mkdir(parents=True)
            python = runtime/'venv'/'python'
            python.write_text('', encoding='utf-8')
            commands = []
            def run(command, *args, **kwargs):
                commands.append([str(c) for c in command])
                return subprocess.CompletedProcess(command, 0, stdout='', stderr='')
            with mock.patch.object(launcher, 'runs', return_value=True), mock.patch.object(launcher, 'environment_python', return_value=python), \
                    mock.patch.object(launcher, 'installed_version', return_value='x'), mock.patch.object(launcher, 'say'), \
                    mock.patch.object(launcher.subprocess, 'run', side_effect=run):
                launcher.ensure_runtime(runtime, 'clone')
            self.assertTrue(any('install' in c for c in commands), commands)
            self.assertFalse(any('uninstall' in c for c in commands), commands)  # a failed install would leave no kit at all


class SkillNamesTests(unittest.TestCase):
    def test_a_skill_named_for_the_skill_tool_exists(self):
        from installer.resolve import skill_catalog
        catalog = skill_catalog(ROOT)
        import re
        for skill, entry in catalog.items():
            if 'path' not in entry:
                continue
            for path in (ROOT/entry['path']).rglob('*.md'):
                for line in path.read_text(encoding='utf-8').splitlines():
                    if 'Skill tool' not in line:
                        continue
                    for name in re.findall(r'"([a-z][a-z0-9-]+)"', line):
                        self.assertIn(name, catalog, path.relative_to(ROOT).as_posix()+': the Skill tool is called with a name that is no skill')


if __name__ == '__main__':
    unittest.main()
