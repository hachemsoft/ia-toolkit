"""4.8.0: protected-paths refuses what a write tool writes to the configuration (an exact path) and the kit's commands that
change the installation; it no longer reads shell commands otherwise, on any system. What a command changes is reported by
the integrity check (spec docs/sdlc/2026-11-14-protected-paths-integrity-check, R1 R2 R3)."""
import json
import unittest

from test_guardrail_bypasses import Base


class WriteToolsOnly(Base):
    def setUp(self):
        super().setUp()
        self.clone = self.home/'apps'/'ai-toolkit'
        (self.clone/'.git'/'hooks').mkdir(parents=True)
        (self.clone/'scripts').mkdir()
        for launcher in ('bootstrap.sh', 'launcher.py'):
            (self.clone/'scripts'/launcher).write_text('', encoding='utf-8')
        (self.home/'.ai-kit').mkdir()
        (self.home/'.ai-kit'/'state.json').write_text(json.dumps({'kit_dir': str(self.clone), 'files': {}}), encoding='utf-8')
        self.repo = self.home/'repo'
        (self.repo/'.git').mkdir(parents=True)

    def write(self, path, content='x', cwd=None):
        cwd = str(cwd or self.repo)
        return self.decide({'tool_name': 'Write', 'tool_input': {'file_path': str(path), 'content': content}, 'cwd': cwd}, cwd)

    def shell(self, command, tool='Bash', cwd=None):
        cwd = str(cwd or self.repo)
        return self.decide({'tool_name': tool, 'tool_input': {'command': command}, 'cwd': cwd}, cwd)

    def test_r1_a_write_tool_still_cannot_write_the_configuration(self):
        refused = [self.home/'.claude'/'settings.json', self.home/'.ai-kit'/'hooks'/'protected-paths.py', self.home/'.ai-kit'/'aikit.toml',
                   self.clone/'.git'/'config', self.clone/'.git'/'hooks'/'pre-commit', self.repo/'.claude'/'settings.local.json']
        wrong = [str(p) for p in refused if self.write(p) != 'deny']
        wrong += ['.env'] if self.write(self.repo/'.env', 'AI_KIT_ALLOW_PROD=1\n') != 'deny' else []
        wrong += [str(p) for p in (self.home/'.claude'/'projects'/'p'/'memory'/'a.md', self.home/'.ai-kit'/'learning'/'t.md', self.repo/'notes.md')
                  if self.write(p) == 'deny']
        self.assertEqual(wrong, [])

    def test_r2_a_shell_command_runs_unless_it_is_a_kit_command_that_changes_the_installation(self):
        runs = ('echo x > ~/.claude/settings.json', 'rm ~/.ai-kit/hooks/protected-paths.py', 'cd ~/.claude && sed -i s/a/b/ settings.json',
                f'git config --file {self.clone}/.git/config remote.origin.url https://example.org/x.git',
                "grep hooks ~/.claude/settings.json | sed 's/a/b/'", 'echo AI_KIT_ALLOW_PROD=1 > .env', 'python3 ~/.ai-kit/hooks/protected-paths.py',
                'ai-kit status', 'ai-kit doctor')
        refused = ('ai-kit sync', 'ai-kit sync --offline', 'python3 -m ai_kit uninstall --yes', f'sh {self.clone}/scripts/bootstrap.sh',
                   'ai-kit doctor --live')
        wrong = [('should run', c) for c in runs if self.shell(c) == 'deny']
        wrong += [('should run', 'Remove-Item $HOME\\.ai-kit\\aikit.toml')] if self.shell('Remove-Item $HOME\\.ai-kit\\aikit.toml', 'PowerShell') == 'deny' else []
        wrong += [('should be refused', c) for c in refused if self.shell(c) != 'deny']
        self.assertEqual(wrong, [])

    def test_r3_a_repo_no_longer_declares_protected_paths(self):
        (self.repo/'.ai-kit').mkdir()
        (self.repo/'.ai-kit'/'protected-paths').write_text('*.lock\n', encoding='utf-8')
        answers = (self.write(self.repo/'poetry.lock'), self.write(self.repo/'.ai-kit'/'protected-paths'), self.shell('echo x > poetry.lock'))
        self.assertEqual(answers, (None, None, None))


if __name__ == '__main__':
    unittest.main()
