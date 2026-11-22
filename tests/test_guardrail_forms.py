"""4.24.1: forms the guardrails did not read. A Windows path to a program (.venv\\Scripts\\dbt.exe), a redirection that holds
an & (2>&1, &>), a variable written in lower case (Windows reads it without case), ~/.claude/settings.local.json, a quoted
path with spaces inside bash -c, a launcher path with capitals on a case-sensitive system, git push --mirror, git switch
--force, terragrunt --working-dir; and Installer.cmd takes a Python that crashes for no Python."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from installer.core import ROOT
import test_guardrail_bypasses
import test_shell_guard

run, denied = test_shell_guard.run, test_shell_guard.denied
PATHS = ROOT/'runtime'/'hooks'/'protected-paths.py'


class ShellGuardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        self.env = {'HOME': str(self.home), 'USERPROFILE': str(self.home)}

    def refused(self, rule, command, **more):
        return denied(run([rule], command, cwd=str(self.home), env={**self.env, **more}))

    def passes(self, rule, command):
        return run([rule], command, cwd=str(self.home), env=self.env) == {}

    def test_dbt_by_a_windows_path_or_a_launcher_script(self):
        for command in ('.venv\\Scripts\\dbt.exe run --target prod', 'C:\\tools\\dbt\\dbt.cmd run --target prod', 'dbt.bat build -t prod',
                        '.venv\\Scripts\\dbt run --target=production', '& "C:\\Program Files\\dbt\\dbt.exe" run --target prd',
                        'd\\bt run --target pr\\od'):  # a POSIX shell drops these backslashes: still read
            self.assertTrue(self.refused('dbt-prod-guard', command), command)
        for command in ('.venv\\Scripts\\dbt.exe run --target dev', 'C:\\tools\\dbt.cmd run --target dev', 'type C:\\notes\\dbt.txt', 'echo .venv\\Scripts\\dbt.exe run --target prod'):
            self.assertTrue(self.passes('dbt-prod-guard', command), command)

    def test_a_redirection_is_not_the_end_of_a_command(self):
        for command in ('git reset 2>&1 --hard', 'git reset &>/dev/null --hard', 'git clean 2>&1 -fd', 'git push 2>&1 --force origin main',
                        'git reset >&2 --hard', 'git reset 2>&1 --hard | tee log', 'git reset |& tee log --hard; git reset --hard'):
            self.assertTrue(self.refused('git-guard', command), command)
        for command in ('git status 2>&1', 'git log 2>&1 | head', 'git reset 2>&1 --soft HEAD~1'):
            self.assertTrue(self.passes('git-guard', command), command)
        for command in ('bq query 2>&1 --dry_run "SELECT 1"', 'bq query &> out.txt --dry_run "SELECT 1"', 'bq query 2>&1 --maximum_bytes_billed=1000000 "SELECT 1"',
                        'bq query --dry_run "SELECT 1" 2>&1 | tee out.txt'):
            self.assertTrue(self.passes('bq-cost-guard', command), command)
        for command in ('bq query 2>&1 "SELECT 1"', 'bq query "SELECT 1" 2>&1'):
            self.assertTrue(self.refused('bq-cost-guard', command), command)
        self.assertTrue(self.refused('infra-prod-guard', 'terraform apply 2>&1 -var-file=prod.tfvars'))

    def test_git_commands_that_discard_or_overwrite(self):
        for command in ('git push --mirror', 'git push --mirror origin', 'git push origin --mirror', 'git switch -f main', 'git switch --force main',
                        'git switch --discard-changes main', 'git -C repo switch -f other'):
            self.assertTrue(self.refused('git-guard', command), command)
        for command in ('git switch main', 'git switch -c feature', 'git switch -', 'git push origin feature', 'git commit -m "git push --mirror"'):
            self.assertTrue(self.passes('git-guard', command), command)

    def test_terragrunt_working_dir_names_the_folder(self):
        for command in ('terragrunt apply --working-dir envs/prod', 'terragrunt --working-dir envs/prod apply', 'terragrunt --terragrunt-working-dir envs/prod apply',
                        'terragrunt destroy --terragrunt-working-dir=live/production', 'terragrunt apply --working-dir=envs/prd -auto-approve'):
            self.assertTrue(self.refused('infra-prod-guard', command), command)
        for command in ('terragrunt apply --working-dir envs/dev', 'terragrunt --working-dir envs/prod plan', 'terragrunt --terragrunt-working-dir envs/dev apply'):
            self.assertTrue(self.passes('infra-prod-guard', command), command)

    def test_the_permission_from_an_env_file_is_refused_whatever_its_case(self):
        (self.home/'.env').write_text('ai_kit_allow_prod=1\n', encoding='utf-8')
        answer = run(['dbt-prod-guard'], 'dbt run --target prod', cwd=str(self.home), env={**self.env, 'AI_KIT_ALLOW_PROD': '1'})
        self.assertTrue(denied(answer))
        self.assertIn('a file the agent can write', answer['reason'])


class ProtectedPathsTests(test_guardrail_bypasses.Base):
    def write(self, path, content='x'):
        return self.decide({'tool_name': 'Write', 'tool_input': {'file_path': str(path), 'content': content}})

    def test_a_kit_command_with_a_redirection_is_still_the_kit_command(self):
        for command in ('ai-kit 2>&1 sync', 'ai-kit sync 2>&1', 'ai-kit &> out.txt sync', 'ai-kit 2>&1 uninstall --yes', 'ai-kit >&2 rollback',
                        'ai-kit 2>&1 team use data', 'ai-kit doctor 2>&1 --live', 'python -m ai_kit 2>&1 init', 'ai-kit 2>&1 sync | tee log'):
            self.assertEqual(self.shell(command), 'deny', command)
        for command in ('ai-kit 2>&1 status', 'ai-kit doctor 2>&1 | tee log', 'ai-kit --version 2>&1', 'echo done 2>&1 & echo sync'):
            self.assertIsNone(self.shell(command), command)

    def test_a_quoted_kit_path_with_spaces_inside_a_shell_text(self):
        for command in ('bash -c \'"/opt/my tools/ai-kit" sync\'', "bash -c \"'/opt/my tools/ai-kit' rollback\"", 'sh -c \'"/Users/me/My Kit/ai-kit" uninstall --yes\''):
            self.assertEqual(self.shell(command), 'deny', command)
        self.assertIsNone(self.shell('bash -c \'"/opt/my tools/ai-kit" status\''))

    def test_the_powershell_call_operator_does_not_hide_the_kit_command(self):
        for command in ('pwsh -Command "& \'C:\\Program Files\\AI Kit\\ai-kit.exe\' sync"', "powershell -Command \"& 'C:\\Tools\\ai-kit.exe' uninstall --yes\"",
                        '& "C:\\Program Files\\AI Kit\\ai-kit.exe" sync', "& 'C:\\Tools\\ai-kit.exe' rollback", 'powershell.exe -NoProfile -Command "& ai-kit sync"',
                        'cd C:\\x; & "C:\\Tools\\ai-kit.exe" team use data', 'pwsh -c "& { & \'C:\\Tools\\ai-kit.exe\' sync }"', '& ai-kit sync'):
            self.assertEqual(self.shell(command), 'deny', command)
        for command in ('pwsh -Command "& \'C:\\Program Files\\AI Kit\\ai-kit.exe\' status"', '& "C:\\Tools\\ai-kit.exe" doctor', 'sleep 1 & echo sync',
                        'echo "a & b" sync', '& "C:\\Tools\\other.exe" sync'):
            self.assertIsNone(self.shell(command), command)

    def test_the_local_settings_of_claude_code_in_the_home_folder(self):
        (self.home/'.claude').mkdir()
        project = self.home/'project'  # a session started elsewhere: the file is protected as the home folder's, not as a repo's
        project.mkdir()
        def write(name):
            return self.decide({'tool_name': 'Write', 'tool_input': {'file_path': str(self.home/'.claude'/name), 'content': '{"disableAllHooks": true}'}}, cwd=str(project))
        self.assertEqual(write('settings.local.json'), 'deny')
        self.assertIsNone(write('notes.md'))

    def test_a_kit_variable_in_an_env_file_whatever_its_case(self):
        for content in ('ai_kit_allow_prod=1\n', 'export Ai_Kit_Prod_Targets=none\n', 'x=1\ndbt_target=prod\n'):
            self.assertEqual(self.write(self.home/'project'/'.env', content), 'deny', content)
        self.assertIsNone(self.write(self.home/'project'/'.env', 'API_URL=https://example.org\n'))

    def test_a_launcher_path_keeps_its_case(self):
        """On a case-sensitive system (Linux) the launcher is looked for where it was written, capitals included."""
        scripts = self.home.resolve()/'Kit'/'scripts'
        scripts.mkdir(parents=True)
        for name in ('bootstrap.sh', 'launcher.py'):
            (scripts/name).write_text('', encoding='utf-8')
        spec = importlib.util.spec_from_file_location('ai_kit_protected_paths', PATHS)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        real_isfile = os.path.isfile  # pathlib calls os.path.isfile itself (Python 3.15): the stand-in must not call itself

        def exact_case(path):  # os.path.isfile as a case-sensitive file system answers
            path = Path(path)
            for part in (path, *path.parents):
                if part.parent != part and (not part.parent.is_dir() or part.name not in os.listdir(part.parent)):
                    return False
            return real_isfile(path)
        kit = scripts.parent.as_posix()
        with mock.patch.object(module.os.path, 'isfile', exact_case), mock.patch.dict(os.environ, {'HOME': str(self.home), 'USERPROFILE': str(self.home)}):
            for command in ('sh '+kit+'/scripts/bootstrap.sh', 'cd '+kit+' && sh scripts/bootstrap.sh', 'python3 '+kit+'/scripts/launcher.py',
                            'bash -c "sh '+kit+'/scripts/bootstrap.sh"'):
                self.assertIsNotNone(module.kit_command_reason(command, str(self.home)), command)
            self.assertIsNone(module.kit_command_reason('sh '+kit+'/scripts/bootstrap.sh status', str(self.home)))
            self.assertIsNone(module.kit_command_reason('sh '+self.home.as_posix()+'/other/bootstrap.sh', str(self.home)))


class InstallerCmdTests(unittest.TestCase):
    def test_only_exit_code_zero_is_a_python_that_runs(self):
        text = (ROOT/'Installer.cmd').read_text(encoding='utf-8')
        self.assertIn('if %ERRORLEVEL% EQU 0 (', text)
        self.assertNotIn('if not errorlevel 1', text)  # true for a negative code: a Python that crashed (0xC0000135) was accepted

    @unittest.skipUnless(os.name == 'nt', 'Installer.cmd runs on Windows')
    def test_a_python_that_answers_a_negative_code_is_not_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            # A stand-in for a python.exe that crashes at start: the :try_python routine of Installer.cmd, run on a command
            # that answers the code of a missing DLL.
            lines = (ROOT/'Installer.cmd').read_text(encoding='utf-8').splitlines()
            routine = lines[lines.index(':try_python'):]
            routine[1:3] = ['cmd /c exit /b -1073741515']  # in place of the where test and the version probe
            script = folder/'probe.cmd'
            script.write_text('\r\n'.join(['@echo off', 'set "KIT_PY="', 'set "KIT_FOUND="', 'call :try_python crashed', 'echo PY=[%KIT_PY%] FOUND=[%KIT_FOUND%]',
                                           'exit /b 0', *routine])+'\r\n', encoding='utf-8')
            out = subprocess.run(['cmd.exe', '/c', str(script)], capture_output=True, text=True, timeout=60).stdout
        self.assertIn('PY=[] FOUND=[blocked]', out)


if __name__ == '__main__':
    unittest.main()
