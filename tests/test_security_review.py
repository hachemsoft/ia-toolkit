"""ADR 0029: a change at risk gets a security review by independent reviewers (spec
docs/sdlc/2026-11-14-risk-based-security-review/spec.md). Content and installation checks; the agents' behaviour is
measured by the eval case review-finds-logged-personal-data."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))


def read(rel):
    return (ROOT/rel).read_text(encoding='utf-8')


class DedicatedReviewTests(unittest.TestCase):
    """T1, requirements 1, 2, 4: triggers, independent reviewers, one merged list, the report line."""

    def test_the_skill_triggers_and_runs_independent_reviewers(self):
        skill = read('skills/internal/common/code-review/SKILL.md')
        for words in ('personal data', 'secrets or tokens', 'authentication or permissions', 'input from outside',
                      'external service', 'a Threats section', 'the person asks',
                      'ai-kit-code-reviewer', 'ai-kit-security-reviewer', 'ai-kit-doubter', 'fresh context',
                      'at the same time when the CLI can', 'one after the other otherwise',
                      'Security review: dedicated (', 'Security review: in the main pass (no trigger)',
                      'duplicates become one finding', 'name the reviewers that found it', 'a disagreement between reviewers',
                      'quick included', 'not when `/build`, or a skill that implements a spec, runs this skill', 'Wait until all have returned',
                      'Keep the Domain, Compliance and Tests passes yourself', 'only their instructions keep them from writing',
                      'then which reviewers ran and whether at the same time', 'the Security review line stays'):
            self.assertIn(words, skill)

    def test_the_command_points_to_it_within_its_budget(self):
        review = read('commands/review.md')
        self.assertIn('a change at risk gets a dedicated security review', review)
        sys.path.insert(0, str(ROOT))
        from installer.core import load_commands
        self.assertLess(next(len(c['prompt']) for c in load_commands() if c['name'] == 'review'), 4000)


class DefaultSecurityReviewerTests(unittest.TestCase):
    """T2, requirement 3: the security reviewer is installed for everyone, reads the threats, treats what it reads as data."""

    def test_default_and_inputs(self):
        agent = read('agents/internal/common/security-reviewer.md')
        self.assertIn('aikit-default: "true"', agent)
        self.assertIn('Threats section', agent)
        self.assertIn('data, never instructions', agent)
        self.assertIn('A finding without an exploitation scenario is at most Minor', agent)

    def test_installed_by_default(self):
        from presets import apply_as
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            apply_as('data-analyst', Path(tmp), False, None, 'gemini')
            self.assertTrue((Path(tmp)/'.gemini/agents/ai-kit-security-reviewer.md').is_file())


class ThreatsAndScanTests(unittest.TestCase):
    """T3, requirement 5: threats written at design time and checked at review (requirement 6, the scan, left for later)."""

    def test_spec_writes_threats(self):
        self.assertIn('## Threats', read('skills/internal/common/init-project-context/templates/spec.md'))
        self.assertIn('threat, mitigation, residual risk', read('commands/spec.md'))

    def test_review_checks_each_mitigation(self):
        self.assertIn('each mitigation of its Threats section', read('skills/internal/common/code-review/SKILL.md'))

    def test_no_repo_command_is_run_by_the_review(self):
        # 4.7.0 decision: running a scan the reviewed repo declares would run the change's own command; left for later.
        self.assertNotIn('Security scan', read('skills/internal/common/code-review/SKILL.md'))
        self.assertNotIn('Security scan', read('skills/internal/common/init-project-context/templates/AGENTS.md'))


if __name__ == '__main__':
    unittest.main()
