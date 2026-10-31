"""What the agent reads stays consistent: proportionate ceremony, the test rule, commits only with agreement, one review
behaviour whose scope commands really see every kind of change, a generic welcome."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from installer.core import ROOT, load_commands, read_json

CATALOG = read_json(ROOT/'skills/catalog.json')
COMMANDS = {c['name']: c['prompt'] for c in load_commands()}


def skill_text(name):
    return (ROOT/CATALOG[name]['path']/'SKILL.md').read_text(encoding='utf-8')


class CeremonyTests(unittest.TestCase):
    def test_levels_defined_once_and_used_by_the_commands(self):
        kit = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8')
        for level in ('**quick**', '**standard**', '**full**'):
            self.assertIn(level, kit)
        self.assertIn('a go-ahead already given stands', kit)
        for name in ('build', 'intent', 'guide'):
            self.assertRegex(COMMANDS[name], r'quick, standard or full', name)

    def test_a_quick_change_needs_no_plan_and_no_new_acceptance(self):
        build = COMMANDS['build']
        self.assertIn('Quick: no plan file', build)
        self.assertNotIn('a small tweak needs no artifact', build)
        # The plan and the acceptance are for the full level only.
        full = build[build.index('Full:'):build.index('Step 2')]
        self.assertIn('plan.md', full)
        self.assertIn('accepts the plan', full)
        self.assertNotIn('accepts the plan', build[:build.index('Full:')])


class TestRuleTests(unittest.TestCase):
    def test_no_absolute_never_touch_the_tests_rule(self):
        places = [ROOT/'templates/kit-context.md', ROOT/'commands/test.md', ROOT/CATALOG['init-project-context']['path']/'templates/AGENTS.md']
        for path in places:
            text = path.read_text(encoding='utf-8')
            self.assertNotRegex(text, r'(?i)never the tests?\b|fix code, never tests', path.name)
        self.assertIn('to hide a regression', COMMANDS['test'])
        self.assertIn('contract', COMMANDS['test'])


class CommitTests(unittest.TestCase):
    def test_no_unconditional_commit(self):
        self.assertNotIn('Commit your work to the current branch.', skill_text('implement'))
        self.assertIn('agreed to commits', skill_text('implement'))
        for name in ('prototype', 'manual-steps'):
            for line in skill_text(name).splitlines():
                if re.search(r'\bcommit it\b', line):
                    self.assertIn('agreement', line, name)

    def test_upstream_adaptations_are_recorded(self):
        lock = read_json(ROOT/'skills/upstream.lock.json')
        for name in ('code-review', 'implement'):
            self.assertIn(name, lock['local_adaptations'])
        self.assertIn('not recorded', lock['note'])  # the original commit is not invented


class ReviewTests(unittest.TestCase):
    def test_one_review_behaviour(self):
        review, skill = COMMANDS['review'], skill_text('code-review')
        self.assertIn('Activate the code-review skill', review)
        for severity in ('Important', 'Minor', 'Nit'):
            self.assertIn(severity, review)
            self.assertIn('**'+severity+'**', skill)
        for word in ('staged', 'unstaged', 'new files'):
            self.assertIn(word, review)
            self.assertIn(word, skill)
        for text in (review, skill):
            self.assertIn('nothing to review', text)
            self.assertNotIn('setup-workflow', text)
        self.assertIn('Never ask for a spec or a tracker', skill)


@unittest.skipUnless(shutil.which('git'), 'git required')
class ReviewScopeCommandTests(unittest.TestCase):
    """The scope commands written in the code-review skill, run on a real repository: they see a commit of the branch,
    a staged change, an unstaged change and a new file; nothing is left out because it is not committed."""
    def git(self, *args):
        return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.org', *args], cwd=self.repo, check=True,
                              capture_output=True, text=True, encoding='utf-8').stdout

    def scope_commands(self):
        block = re.search(r'```sh\n(.*?)```', skill_text('code-review'), re.S).group(1)
        return [line.split('#')[0].strip() for line in block.splitlines() if line.split('#')[0].strip()]

    def test_every_kind_of_change_is_in_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.repo = Path(tmp)
            self.git('init', '--quiet', '--initial-branch=main')
            for name in ('committed.py', 'staged.py', 'unstaged.py'):
                (self.repo/name).write_text('x = 1\n', encoding='utf-8')
            self.git('add', '-A')
            self.git('commit', '--quiet', '-m', 'base')
            self.git('checkout', '--quiet', '-b', 'feature')
            (self.repo/'committed.py').write_text('x = 2  # committed\n', encoding='utf-8')
            self.git('commit', '--quiet', '-am', 'feature work')
            (self.repo/'staged.py').write_text('x = 3  # staged\n', encoding='utf-8')
            self.git('add', 'staged.py')
            (self.repo/'unstaged.py').write_text('x = 4  # unstaged\n', encoding='utf-8')
            (self.repo/'new_file.py').write_text('y = 5\n', encoding='utf-8')
            seen = ''
            base = self.git('merge-base', 'main', 'HEAD').strip()
            for command in self.scope_commands():
                parts = command.replace('<base>', 'main').replace('<merge-base>', base).split()
                if parts[:3] == ['git', 'rev-parse', '--abbrev-ref']:
                    continue  # needs a remote; the base is given here
                seen += self.git(*parts[1:])
            for marker in ('# committed', '# staged', '# unstaged', 'new_file.py', 'feature work'):
                self.assertIn(marker, seen)


class WelcomeTests(unittest.TestCase):
    def test_four_everyday_uses_first_and_no_domain_in_the_shared_router(self):
        routing = skill_text('routing')
        start = routing.index('## Start here')
        self.assertLess(start, routing.index('## Ceremony level'))
        for use in ('Understand a repo', 'Change a behaviour', 'Diagnose a problem', 'Review changes'):
            self.assertIn(use, routing)
        self.assertNotRegex(routing, r'(?i)\b(dbt|bigquery|sql)\b')
        self.assertIn('no ticket tracker', routing)
        self.assertIn('plain sentence', routing)

    def test_project_context_is_one_grouped_proposal(self):
        text = skill_text('init-project-context')
        self.assertIn('one grouped proposal', text)
        self.assertNotIn('For each file, show the full content and wait for confirmation', text)
        self.assertIn('never as a prerequisite', text)


if __name__ == '__main__':
    unittest.main()
