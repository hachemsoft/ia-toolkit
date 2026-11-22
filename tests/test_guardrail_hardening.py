"""Guardrails: forms of a command or of a write the two scripts let through (quoted Windows paths, a sourced launcher, a
backslash in a program's name, a .cmd launcher, a zero byte cap, HEAD pushed by force, terragrunt run-all, kubectl -nprod,
a multi-edit of a .env), and commands refused or let through by mistake (a sentence that only mentions dbt, a profiles.yml
the script could not read). No network, no model."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from installer.core import ROOT

HOOKS = ROOT/'runtime'/'hooks'


def load(name):
    spec = importlib.util.spec_from_file_location('guard_'+name.replace('-', '_'), HOOKS/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Home(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()/'home'
        self.repo = self.home/'work'/'repo'
        (self.repo/'.git').mkdir(parents=True)
        (self.repo/'.git'/'HEAD').write_text('ref: refs/heads/main\n', encoding='utf-8')
        (self.home/'.ai-kit').mkdir()
        (self.home/'.ai-kit'/'state.json').write_text('{}', encoding='utf-8')
        env = {k: v for k, v in os.environ.items() if not k.startswith(('AI_KIT_', 'DBT_', 'TF_', 'KUBECONFIG'))}
        patcher = mock.patch.dict(os.environ, {**env, 'HOME': str(self.home), 'USERPROFILE': str(self.home)}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)


class ProtectedPathsTests(Home):
    def setUp(self):
        super().setUp()
        self.guard = load('protected-paths')

    def shell(self, command):
        return self.guard.decide({'tool_name': 'run_shell_command', 'tool_input': {'command': command}, 'cwd': str(self.repo)})

    def write(self, tool, args):
        return self.guard.decide({'tool_name': tool, 'tool_input': args, 'cwd': str(self.repo)})

    def test_the_kit_command_is_seen_behind_a_quoted_path_with_spaces(self):
        for command in (r'"C:\Program Files\Python311\python.exe" -m ai_kit sync',
                        r"& 'C:\Program Files\Python311\python.exe' -m ai_kit uninstall --yes",
                        '"/opt/my tools/python3" -m ai_kit rollback',
                        r'"C:\Users\me\AppData\Local\Programs\AI Kit\ai-kit.cmd" sync'):
            self.assertIn('changes the installation', self.shell(command) or '', command)
        for command in ('bash -c "ai-kit sync"', "sh -lc 'ai-kit rollback'", 'ai-kit sync', 'python3 -m ai_kit init'):  # as before
            self.assertIn('changes the installation', self.shell(command) or '', command)
        for command in ('"C:\\Program Files\\Python311\\python.exe" -m ai_kit status', 'echo "ai-kit sync"', 'ai-kit doctor'):
            self.assertIsNone(self.shell(command), command)

    def test_a_launcher_read_into_the_current_shell_installs_too(self):
        kit = self.home/'kit folder'/'scripts'
        kit.mkdir(parents=True)
        for name in ('bootstrap.sh', 'launcher.py'):
            (kit/name).write_text('', encoding='utf-8')
        for command in ('source "'+str(kit)+'/bootstrap.sh"', '. "'+str(kit)+'/bootstrap.sh"', 'cd "'+str(kit)+'" && . ./bootstrap.sh sync',
                        'sh "'+str(kit)+'/bootstrap.sh"'):
            self.assertIn('changes the installation', self.shell(command) or '', command)
        other = self.repo/'scripts'
        other.mkdir()
        (other/'bootstrap.sh').write_text('', encoding='utf-8')  # another project's bootstrap.sh is not the kit's launcher
        self.assertIsNone(self.shell('. scripts/bootstrap.sh'))
        self.assertIsNone(self.shell('source .venv/bin/activate'))

    def test_more_configuration_files_are_protected(self):
        for path in ('.codex/AGENTS.override.md', '.ai-kit/engine.lock'):
            self.assertIn('configuration', self.write('write_file', {'file_path': str(self.home/path), 'content': 'x'}) or '', path)

    def test_a_path_written_with_a_tilde_or_a_windows_long_path_prefix_is_the_same_file(self):
        self.assertIn('configuration', self.write('write_file', {'file_path': '~/.ai-kit/aikit.toml', 'content': 'x'}) or '')
        self.assertIn('configuration', self.write('Write', {'file_path': '~/.claude/settings.json', 'content': '{}'}) or '')
        for prefix in ('\\\\?\\', '//?/'):
            self.assertIn('configuration', self.write('write_file', {'file_path': prefix+str(self.home/'.ai-kit'/'aikit.toml'), 'content': 'x'}) or '', prefix)
        self.assertIsNone(self.write('write_file', {'file_path': '~/notes.md', 'content': 'x'}))

    def test_a_dotenv_cannot_set_the_kit_variables_through_any_write_tool(self):
        env = str(self.repo/'.env')
        blocked = (
            ('write_file', {'file_path': env, 'content': 'AI_KIT_ALLOW_PROD=1\n'}),
            ('MultiEdit', {'file_path': env, 'edits': [{'old_string': 'A=1', 'new_string': 'A=1\nAI_KIT_ALLOW_PROD=1'}]}),
            ('MultiEdit', {'file_path': env, 'edits': [{'old_string': 'A=1', 'new_string': 'B=2'}, {'old_string': 'C=3', 'new_string': 'export DBT_TARGET=prod'}]}),
            ('multi_replace_file_content', {'TargetFile': env, 'ReplacementChunks': [{'TargetContent': 'A=1', 'ReplacementContent': 'A=1\nAI_KIT_ALLOW_PROD=1'}]}),
            ('apply_patch', {'input': '*** Begin Patch\n*** Update File: '+env+'\n@@\n A=1\n+AI_KIT_ALLOW_PROD=1\n*** End Patch\n'}),
            ('apply_patch', {'command': ['apply_patch', '*** Begin Patch\n*** Add File: '+env+'\n+AI_KIT_PROD_TARGETS=none\n*** End Patch\n']}),
        )
        for tool, args in blocked:
            self.assertIn('.env', self.write(tool, args) or '', (tool, args))
        allowed = (
            ('MultiEdit', {'file_path': env, 'edits': [{'old_string': 'AI_KIT_ALLOW_PROD=1', 'new_string': 'A=1'}]}),  # removing it is fine
            ('apply_patch', {'input': '*** Begin Patch\n*** Update File: '+env+'\n@@\n-AI_KIT_ALLOW_PROD=1\n+A=1\n*** End Patch\n'}),
            ('multi_replace_file_content', {'TargetFile': env, 'ReplacementChunks': [{'TargetContent': 'DBT_TARGET=prod', 'ReplacementContent': 'A=2'}]}),
        )
        for tool, args in allowed:
            self.assertIsNone(self.write(tool, args), (tool, args))


class ShellGuardTests(Home):
    def setUp(self):
        super().setUp()
        self.guard = load('shell-guard')

    def payload(self):
        return {'tool_name': 'run_shell_command', 'cwd': str(self.repo)}

    def refused(self, rule, command):
        answer = getattr(self.guard, rule)(command, self.payload())
        return json.dumps(answer) if answer and 'systemMessage' not in answer else ''

    def test_a_backslash_in_a_program_name_hides_nothing(self):
        self.assertIn('reset --hard', self.refused('git_guard', r'g\it reset --hard'))
        self.assertIn('bq query', self.refused('bq_cost_guard', r'b\q query "select 1"'))
        self.assertIn('reset --hard', self.refused('git_guard', r'C:\tools\git.exe reset --hard'))  # a Windows path, as before
        self.assertIn('reset --hard', self.refused('git_guard', r'tools\git.exe reset --hard'))

    def test_a_windows_launcher_script_is_the_program(self):
        for command in ('bq.cmd query "select 1"', r'C:\sdk\bin\bq.cmd query "select 1"', 'bq.bat query "select 1"'):
            self.assertIn('bq query', self.refused('bq_cost_guard', command), command)
        self.assertIn('reset --hard', self.refused('git_guard', 'git.cmd reset --hard'))

    def test_a_byte_cap_must_be_a_number_above_zero(self):
        for command in ('bq query --maximum_bytes_billed 0 "select 1"', 'bq query --maximum_bytes_billed=0 "select 1"',
                        'bq query --maximum_bytes_billed "select 1"', 'bq query --maximum_bytes_billed -1 "select 1"'):
            self.assertIn('bq query', self.refused('bq_cost_guard', command), command)
        for command in ('bq query --maximum_bytes_billed=1000000 "select 1"', 'bq query --maximum_bytes_billed 1000000 "select 1"',
                        'bq query --dry_run "select 1"'):
            self.assertEqual(self.refused('bq_cost_guard', command), '', command)

    def test_a_forced_push_of_head_or_of_every_branch_is_refused_on_a_main_branch(self):
        for command in ('git push --force origin HEAD', 'git push -f origin HEAD', 'git push --force-with-lease origin HEAD',
                        'git push origin +HEAD', 'git push --force origin @', 'git push --force origin HEAD:main',
                        'git push --force-with-lease --all', 'git push --force-with-lease --mirror origin', 'git push --force --all'):
            self.assertIn('git push', self.refused('git_guard', command), command)
        (self.repo/'.git'/'HEAD').write_text('ref: refs/heads/my-branch\n', encoding='utf-8')
        for command in ('git push --force-with-lease origin HEAD', 'git push --force origin HEAD', 'git push origin HEAD', 'git push --all'):
            self.assertEqual(self.refused('git_guard', command), '', command)

    def test_terragrunt_run_all_and_a_glued_kubectl_namespace_are_read(self):
        prod = self.repo/'envs'/'prod'
        prod.mkdir(parents=True)
        payload = {'tool_name': 'run_shell_command', 'cwd': str(prod)}
        for command in ('terragrunt run-all apply', 'terragrunt run-all destroy --terragrunt-non-interactive', 'terragrunt run --all apply',
                        'terragrunt run -- apply', 'terragrunt apply'):
            answer = self.guard.infra_prod_guard(command, payload)
            self.assertIn('on production', json.dumps(answer or {}), command)
        self.assertIsNone(self.guard.infra_prod_guard('terragrunt run-all plan', payload))
        for command in ('kubectl -nprod delete pod x', 'kubectl delete pod x -nprod', 'kubectl -n=prod delete pod x', 'kubectl -n prod delete pod x'):
            self.assertIn('on production', self.refused('infra_prod_guard', command), command)
        self.assertEqual(self.refused('infra_prod_guard', 'kubectl -ndev delete pod x --context dev'), '')

    def test_a_sentence_that_only_mentions_dbt_is_not_a_dbt_command(self):
        for command in ('echo "dbt run --target prod"', 'git commit -m "docs: dbt run --target prod is refused"', 'grep -r "dbt run --target prod" docs',
                        "printf '%s\\n' 'dbt build -t prod'"):
            self.assertIsNone(self.guard.dbt_prod_guard(command, self.payload()), command)
        for command in ('dbt run --target prod', 'echo "dbt run --target prod" | sh', 'sh -c "dbt run --target prod"', 'uv run dbt build -t prod',
                        'cd models && dbt run --target=prod', 'python -c "from dbt.cli.main import dbtRunner; dbtRunner().invoke([\'run\', \'--target\', \'prod\'])"',
                        'echo start; d\'\'bt run --target pr\\od', 'poetry run dbt run --target prod', 'echo $(dbt run --target prod)'):
            self.assertIn('production target', json.dumps(self.guard.dbt_prod_guard(command, self.payload()) or {}), command)

    def test_a_profiles_file_the_script_cannot_read_fully_never_lets_production_through(self):
        profiles = self.home/'my profiles'
        profiles.mkdir()
        for text, command, expected in (
                ('jaffle:\n  target:   \n  outputs: {}\n', 'dbt run', None),                         # an empty target: nothing to refuse, no crash
                ('jaffle:\n  target: # set by CI\n  outputs: {}\n', 'dbt run', None),
                ('one:\n  target: # none\ntwo:\n  target: prod\n', 'dbt run', 'prod'),                # the unreadable line does not hide the next one
                ('jaffle:\n  target: prod  # default\n', 'dbt run --profiles-dir "'+str(profiles)+'"', 'prod'),  # a quoted folder with a space
                ('jaffle:\n  target: prod\n', "dbt run --profiles-dir='"+str(profiles)+"'", 'prod')):
            (profiles/'profiles.yml').write_text(text, encoding='utf-8')
            (self.repo/'profiles.yml').write_text(text if '--profiles-dir' not in command else 'x:\n  target: dev\n', encoding='utf-8')
            answer = self.guard.dbt_prod_guard(command, self.payload())  # an exception here would let the command through
            if expected:
                self.assertIn('production target', json.dumps(answer or {}), (text, command))
            else:
                self.assertIsNone(answer, (text, command))
        hit = self.guard.default_target_hit(r'dbt run --profiles-dir C:\Users\me\profiles', ['prod'], self.payload())  # a Windows folder: no crash
        self.assertIsNone(hit)

    def test_the_script_still_answers_through_its_command_line(self):
        payload = {'tool_name': 'run_shell_command', 'tool_input': {'command': r'g\it reset --hard'}, 'cwd': str(self.repo)}
        proc = subprocess.run([sys.executable, '-I', str(HOOKS/'shell-guard.py'), 'git-guard', 'bq-cost-guard'], input=json.dumps(payload),
                              capture_output=True, text=True, encoding='utf-8', env=dict(os.environ), timeout=30)
        self.assertEqual(json.loads(proc.stdout).get('decision'), 'deny')


if __name__ == '__main__':
    unittest.main()
