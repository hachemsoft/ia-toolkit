"""ADR 0028: test-first where a person looks at the test. Quick: no test written first, the existing checks prove it.
Standard and full: a failing acceptance test, shown with why it fails and approved by the person before any code; then
the implementation is free (the red-green loop of the tdd skill is optional), the test is kept, nothing is committed red."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT/rel).read_text(encoding='utf-8')


class AcceptanceFirstTests(unittest.TestCase):
    def test_kit_context_states_it_per_level(self):
        kit = read('templates/kit-context.md')
        self.assertIn('**standard** (small feature, a few files): short alignment, then a failing acceptance test approved before code.', kit)
        self.assertIn('run the check that covers it', kit)  # quick: no test written first
        self.assertIn('a go-ahead already given stands, not for an unseen test', kit)
        self.assertIn('risks first: how a failure shows', kit)
        self.assertIn('acceptance before code, then as standard', kit)  # full: risks first, then the standard step
        self.assertLess(len(kit), 3800)

    def test_build_shows_the_failing_test_and_waits(self):
        build = read('commands/build.md')
        for words in ('acceptance test', 'why it fails', 'wait for the person', 'acceptance criteria of spec.md',
                      'Quick: no test written first', 'free', 'never commit while it fails'):
            self.assertIn(words, build)
        for words in ('except for the acceptance tests of step 2', 'at most three', 'not on an import or compile error',
                      'do not stop for the tests', 'no test runner', 'needs no new test',
                      'an empty stub in a new file', 'a test-config change', 'no other existing file changes before approval',
                      'for an irreversible operation the backup or way back'):
            self.assertIn(words, build)
        self.assertNotIn('red test first', build)

    def test_playbooks_and_test_follow_the_levels(self):
        for rel in ('skills/internal/development/code-change/SKILL.md',):
            self.assertIn('quick: the existing checks', read(rel))
        self.assertIn('At standard and full levels, no change to the model', read('skills/internal/analytics/dbt-model-change/SKILL.md'))
        self.assertIn('The acceptance to show and get approved before the change is read-only evidence', read('skills/internal/operations/infra-change/SKILL.md'))
        self.assertIn("wait for the person's approval before the code, as /build does", read('commands/test.md'))
        self.assertIn('three at most', read('skills/internal/common/tdd/SKILL.md'))

    def test_tdd_skill_names_the_contract_and_the_optional_loop(self):
        tdd = read('skills/internal/common/tdd/SKILL.md')
        self.assertIn('## In the kit', tdd)
        self.assertIn('acceptance test the person approved is the contract', tdd)
        self.assertIn('optional', tdd)

    def test_dbt_playbook_shows_the_failing_test_first(self):
        self.assertIn('show it failing to the person and wait for their approval', read('skills/internal/analytics/dbt-model-change/SKILL.md'))

    def test_docs_follow(self):
        self.assertIn('a failing acceptance test approved before code', read('docs/commands.md'))
        self.assertTrue((ROOT/'docs/adr/0028-test-first-where-a-person-looks-at-the-test.md').is_file())


if __name__ == '__main__':
    unittest.main()
