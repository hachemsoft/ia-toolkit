"""What the agent reads stays consistent: proportionate ceremony, the test rule, commits only with agreement, one review
behaviour whose scope commands really see every kind of change, a generic welcome."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from installer.core import ROOT, load_commands, read_json
from installer.resolve import skill_catalog

CATALOG = skill_catalog(ROOT)
COMMANDS = {c['name']: c['prompt'] for c in load_commands()}


def skill_text(name):
    return (ROOT/CATALOG[name]['path']/'SKILL.md').read_text(encoding='utf-8')


class CeremonyTests(unittest.TestCase):
    def test_grilling_offers_options_and_stays_in_scope(self):
        # Frictions from a session: a single recommended answer to confirm, and a drift to hosting and access while framing.
        grilling = (ROOT/'skills/internal/common/grilling/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('at least two real options', grilling)
        self.assertIn('**Later**', grilling)
        spec = COMMANDS['spec']
        self.assertIn('all in one round', spec)
        self.assertIn('write the whole spec.md in the same turn', spec)
        self.assertIn('hosting, access, operations', spec)

    def test_levels_defined_once_and_used_by_the_commands(self):
        kit = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8')
        for level in ('**quick**', '**standard**', '**full**'):
            self.assertIn(level, kit)
        self.assertIn('a go-ahead already given stands', kit)
        for name in ('build', 'intent', 'guide'):
            self.assertRegex(COMMANDS[name], r'quick, standard or full', name)
        # The level is a fixed first line, written even when the agent is blocked: the workflow and the evals read it.
        self.assertIn('`Level: quick|standard|full`', kit)
        for name in ('build', 'intent'):
            self.assertIn('The first line of your reply is `Level: quick`', COMMANDS[name], name)
            self.assertIn('even if you then ask', COMMANDS[name], name)

    def test_resuming_reads_the_state_and_asks_again_for_a_stale_approval(self):
        # docs/sdlc/2026-11-21-loop-and-resume: paid runs of the resume cases (40-44) showed a new session that ignored the
        # other branches, did not name the plan it followed, restored a changed approved test on its own, or assumed an
        # approval that nothing recorded.
        kit = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8')
        self.assertIn('Resuming', kit, 'the kit context has no resume rule')
        rule = kit[kit.index('Resuming'):].split('\n', 1)[0]
        for words in ('`git status`', 'other branches', 'log', 'name the artifact and the step',
                      'changed since its approval', 'nothing records', 'ask again', 'never restore', 'not replayed'):
            self.assertIn(words, rule, words)

    def test_a_word_about_an_approval_in_another_tool_is_not_a_record(self):
        # Eval claude-to-codex-resumes-the-work (2026-11-22): told "I approved the test yesterday, in another tool", Codex
        # asked again twice and went on once without showing it; the person chose: the test is shown and confirmed again.
        kit = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8')
        self.assertIn('Resuming', kit)
        rule = kit[kit.index('Resuming'):].split('\n', 1)[0]
        self.assertIn('a word about another tool is not a record', rule)

    def test_resuming_asks_before_building_on_a_change_made_by_someone_else(self):
        # Paid runs of case 43 on agy (4.21.0, --sandbox): it named an uncommitted change outside the plan, then built on it
        # in the same turn and asked only afterwards.
        kit = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8')
        rule = kit[kit.index('Resuming'):].split('\n', 1)[0]
        for words in ('a change outside the plan you did not make', 'ask before building on it'):
            self.assertIn(words, rule, words)

    def test_build_says_a_one_line_contract_change_is_not_quick(self):
        # Codex classed get_order "raises KeyError -> returns None", "one line", as quick in 4.2.0, 4.5.0, 4.22.3 and 4.23.2
        # (eval small-contract-change-names-its-consequences): the level follows what a change can break, not its size.
        build = COMMANDS['build']
        self.assertIn("a function's return value, the type of error it raises or its parameters", build)
        self.assertIn('never quick, even on one line', build)
        # 2026-11-22: "what a function raises" made Codex class a message's new wording as standard (case 06): the wording
        # alone is no contract.
        self.assertIn("a message's wording alone does not", build)

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


class OwnershipTests(unittest.TestCase):
    """Operational ownership: the level follows the stakes, evidence is told apart from assumption, and a risky change
    says how a failure shows and how it is undone, without adding a step, a file or a technology to the core."""
    def template(self, name):
        return (ROOT/CATALOG['init-project-context']['path']/'templates'/name).read_text(encoding='utf-8')

    def test_level_follows_the_stakes_not_the_size(self):
        kit = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8')
        self.assertIn('not its size', kit)
        self.assertIn('shared contract', kit)
        self.assertIn('**quick** (local, obvious behaviour, no contract changed)', kit)
        self.assertIn('how a failure shows and how to undo or mitigate it', kit)

    def test_evidence_is_told_apart_from_assumption(self):
        kit = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8')
        line = next(row for row in kit.splitlines() if row.startswith('Evidence:'))
        for words in ('observed', 'assume', 'never call verified', 'unknown stays unknown'):
            self.assertIn(words, line)

    def test_full_plan_and_delivery_cover_detection_recovery_and_decisions(self):
        build = COMMANDS['build']
        full = build[build.index('Full:'):build.index('Step 2')]
        self.assertIn('how a failure would show and how to undo it', full)
        self.assertIn('how a failure would show', self.template('plan.md'))
        ship = COMMANDS['ship']
        for words in ('how to undo or mitigate', 'not verified', 'a human must decide'):
            self.assertIn(words, ship)
        self.assertIn('whether a failure would show and how it is undone', COMMANDS['review'])

    def test_recovery_never_blocks_a_change_where_it_does_not_apply(self):
        for text in ((ROOT/'templates/kit-context.md').read_text(encoding='utf-8'), COMMANDS['build'], COMMANDS['ship'], self.template('plan.md')):
            self.assertRegex(text, r'when (that|it) applies|"not applicable"|not applicable')
        quick = COMMANDS['build'][:COMMANDS['build'].index('Standard:')]
        self.assertNotRegex(quick, r'(?i)rollback|undo|mitigat')

    def test_assumptions_have_a_place_in_the_artifacts(self):
        for name in ('intent.md', 'spec.md'):
            self.assertIn('Assumption:', self.template(name), name)

    def test_the_core_names_no_technology(self):
        # The ownership rules are universal; methods of a domain stay in its playbook.
        kit = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8')
        added = [row for row in kit.splitlines() if row.startswith(('Evidence:', 'Reply to a change'))]
        self.assertEqual(len(added), 2)
        self.assertNotRegex('\n'.join(added), r'(?i)\b(dbt|sql|bigquery|terraform|kubernetes|helm|java|python|database)\b')
        ship = COMMANDS['ship']
        self.assertNotRegex(ship, r'(?i)\b(dbt|sql|bigquery|terraform|kubernetes|helm|java|python)\b')


if __name__ == '__main__':
    unittest.main()


class CoherenceTests(unittest.TestCase):
    """docs/sdlc/2026-11-21-loop-and-resume, increment 1: what the skills say agrees with their metadata and the commands."""

    TRACKER_SKILLS = ('implement-spec', 'to-tickets', 'to-spec', 'ticket-sorting', 'wayfinder')

    def test_no_skill_requires_a_tracker_to_continue(self):
        for name in self.TRACKER_SKILLS:
            body = skill_text(name).split('\n---\n', 1)[1]
            with self.subTest(skill=name):
                self.assertNotIn('tell the user to run `/setup-workflow`', body)
                self.assertIn('never require a tracker to continue', body)
                self.assertIn('local markdown', body)
        self.assertNotIn('requires `glab` or `gh`', skill_text('routing'))
        self.assertNotIn('Run once before first use', skill_text('setup-workflow'))
        self.assertNotIn('run before your first engineering flow', skill_text('workflow-guide'))

    def test_splitting_into_tickets_is_described_as_it_works(self):
        self.assertNotIn('/build or to-tickets does it', COMMANDS['spec'])
        self.assertNotIn('`/build` per ticket', skill_text('routing'))

    def test_implement_spec_asks_once_for_the_commits_before_its_subagents(self):
        # Its subagents commit and merge on branches: the kit context's rule (agreement to commits in this session) is said
        # where it is needed, once, before they start.
        body = skill_text('implement-spec')
        self.assertIn('Before any subagent starts, ask the person once for their agreement to the commits and merges', body)
        self.assertIn('push nothing, and open no PR, without their agreement', body)

    def test_the_retrospective_writes_where_retro_says(self):
        retro = skill_text('retrospective')
        self.assertNotIn('CODING_STANDARDS.md', retro)
        self.assertIn('REVIEW.md', retro)


class RetryLimitTests(unittest.TestCase):
    """docs/sdlc/2026-11-21-loop-and-resume, increment 2: the correction loop is bounded. Paid runs of the loop cases
    (45, 46, 31) showed no gap, so the rule stays as written; this test keeps it from being lost."""

    def test_build_and_diagnose_stop_after_three_different_fixes_of_the_same_check(self):
        for name in ('build', 'diagnose'):
            with self.subTest(command=name):
                self.assertRegex(COMMANDS[name], r'the same check still fails after three different fixes, stop')
                self.assertIn('the literal failing output', COMMANDS[name])


class PlaybookSectionTests(unittest.TestCase):
    """docs/sdlc/2026-11-21-loop-and-resume: a playbook's "In the kit commands" lines go only to commands that read them
    (ADR 0021, amended: /test reads it when AGENTS.md has no table of checks)."""

    def test_no_playbook_line_for_spec_or_guide_and_test_names_the_section(self):
        for path in sorted((ROOT/'skills/internal').glob('*/*/SKILL.md')):
            text = path.read_text(encoding='utf-8')
            if '## In the kit commands' not in text:
                continue
            section = text.split('## In the kit commands', 1)[1].split('\n## ', 1)[0]
            with self.subTest(playbook=path.parent.name):
                self.assertNotRegex(section, r'(?m)^- `/(spec|guide)`')
        self.assertIn('the "In the kit commands" section of the matching domain playbook for `/test`', COMMANDS['test'])
        dbt = skill_text('dbt-model-change')
        self.assertIn('- `/test`: when AGENTS.md has no "Verifying your work" table', dbt)
