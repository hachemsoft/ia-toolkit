"""4.7.1: protected-paths no longer refuses shell commands that only read (spec docs/sdlc/2026-11-14-protected-paths-false-refusals,
R1 to R3): a cd into a configuration folder followed by reads, a cd into a subfolder that holds no protected file, and the
message of a git commit. Each refused command below is a write that must stay refused."""
import unittest

from test_guardrail_bypasses import Base


class ReadsAreNotRefused(Base):
    def assert_answers(self, allowed, refused, tool='Bash'):
        wrong = [('should pass', c) for c in allowed if self.shell(c, tool) == 'deny']
        wrong += [('should be refused', c) for c in refused if self.shell(c, tool) != 'deny']
        self.assertEqual(wrong, [])

    def test_r1_cd_into_a_subfolder_with_no_protected_file_is_an_ordinary_folder(self):
        self.assert_answers(
            allowed=('cd ~/.claude/projects/p/memory && cat a.md',
                     'cd ~/.claude/projects/p/memory && echo x >> MEMORY.md',
                     'cd ~/.claude/projects/p/memory && ls ..'),
            refused=('cd ~/.claude/projects/p && echo x > ../../settings.json',
                     'cd ~/.claude/projects/p && rm ../../settings.json'))

    def test_r2_cd_into_a_configuration_folder_then_only_reads(self):
        self.assert_answers(
            allowed=('cd ~/.claude', 'cd ~/.claude && ls', "cd ~/.claude && find . -name '*.md'", 'cd ~/.ai-kit && cat aikit.toml'),
            refused=('cd ~/.claude && rm settings.json', 'cd ~/.claude && sed -i s/a/b/ settings.json',
                     'cd ~/.ai-kit && echo x > aikit.toml', 'cd ~/.claude && cp x settings.json', 'cd ~/.claude && rm *.json',
                     'cd ~/.claude || rm -rf x', 'cd ~/.claude/agents && rm ai-kit-reviewer.md', 'pushd ~/.ai-kit && touch aikit.toml'))
        self.assert_answers(
            allowed=('Set-Location $HOME\\.claude; Get-ChildItem',),
            refused=('Set-Location $HOME\\.claude; Remove-Item settings.json',), tool='PowerShell')

    def test_r3_the_message_of_a_git_commit_is_not_a_path(self):
        self.assert_answers(
            allowed=('git commit -m "docs: explain .ai-kit/protected-paths"',
                     'git commit -m "a; b ~/.claude/settings.json"',
                     "git commit -m 'x' -m 'cite .claude/settings.json'",
                     'git commit --message="cite .claude/settings.json"'),
            refused=('git commit -m "$(rm ~/.claude/settings.json)"',
                     'git commit -m "`rm ~/.claude/settings.json`"',
                     'git commit -m x && rm ~/.claude/settings.json',
                     'git commit -F ~/.claude/settings.json && echo x > ~/.claude/settings.json'))


class ACdAfterACdIntoAConfigurationFolder(Base):
    """Found while writing 4.7.1: after a cd into an ordinary subfolder, a second cd (.., -, a variable) can lead back to a
    protected file; it is judged as a cd into the folder root."""
    def test_a_second_cd_keeps_the_writes_refused(self):
        for command in ('cd ~/.claude/projects/p && cd ../.. && rm settings.json', 'cd ~/.claude/projects/p; cd -; rm settings.json',
                        'cd ~/.claude/projects/p && cd "$OLDPWD" && echo x > settings.json'):
            self.assertEqual(self.shell(command), 'deny', command)
        self.assertNotEqual(self.shell('cd ~/.claude/projects/p && cd ../q && cat a.md'), 'deny')

    def test_found_in_review_a_climbing_target_an_option_after_it_and_the_starting_folder(self):
        for command in ('cd ~/.claude/projects/p/../.. && rm settings.json', 'cd ~/.claude/projects/../agents && rm ai-kit-x.md'):
            self.assertEqual(self.shell(command), 'deny', command)
        self.assertEqual(self.shell('Set-Location $HOME\\.claude -PassThru; Remove-Item settings.json', 'PowerShell'), 'deny')
        # A CLI that keeps the folder of a previous cd starts the next call there: it is judged as a cd into that folder.
        (self.home/'.claude').mkdir()
        start = {'cwd': str(self.home/'.claude')}
        self.assertEqual(self.decide({'tool_name': 'Bash', 'tool_input': {'command': 'rm settings.json'}, **start}), 'deny')
        self.assertNotEqual(self.decide({'tool_name': 'Bash', 'tool_input': {'command': 'cat settings.json'}, **start}), 'deny')


if __name__ == '__main__':
    unittest.main()
