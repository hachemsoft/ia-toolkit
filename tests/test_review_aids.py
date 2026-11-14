"""Review aids, 4.11.0 (spec docs/sdlc/2026-11-14-review-aids/spec.md): cold review, the doubter's critic format,
the review-guide skill with `review:` marks, merge request discussions. Content and installation checks; the agents'
behaviour is checked by hand (R9, R12) and by eval cases only on request."""
import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))

REVIEWERS = ('agents/internal/development/code-reviewer.md', 'agents/internal/common/security-reviewer.md',
             'agents/internal/common/doubter.md', 'agents/internal/analytics/sql-reviewer.md',
             'agents/internal/analytics/dbt-reviewer.md', 'agents/internal/operations/infra-reviewer.md',
             'agents/internal/architecture/architecture-reviewer.md')


def read(rel):
    return (ROOT/rel).read_text(encoding='utf-8')


class ColdReviewAndCriticTests(unittest.TestCase):
    """T1, R1-R5: the parent sends references and the raw diff, never the author's narrative; every reviewer ignores
    and reports a narrative; the doubter gets labelled claims, answers in the critic format; its position heads the report."""

    def test_the_parent_sends_a_cold_brief(self):
        skill = read('skills/internal/common/code-review/SKILL.md')
        for words in ('cold review', 'raw output of `git diff`', 'never summarised', "never the author's narrative",
                      'claims to check', 'Position: not assessed (doubter not run: '):
            self.assertIn(words, skill)
        self.assertIn('the `Position:` line', read('commands/review.md'))

    def test_every_reviewer_ignores_and_reports_a_narrative(self):
        for rel in REVIEWERS:
            with self.subTest(agent=rel):
                self.assertIn("brief held the author's narrative, ignored", read(rel))

    def test_the_doubter_answers_as_a_critic(self):
        doubter = read('agents/internal/common/doubter.md')
        for words in ('claims to check', 'position: no objection | concerns | oppose', 'strongest objection:',
                      'simpler alternative:', 'would a stranger understand in six months:',
                      'never manufacture an objection', '`oppose` only for a real cost'):
            self.assertIn(words, doubter)


class ReviewGuideTests(unittest.TestCase):
    """T2, R6-R13: the review-guide skill, installed by default; `review:` marks handled in one batch; merge request
    discussions read, and every visible action on a merge request asked for each time; the commands offer it."""

    def test_the_guide_and_its_marks(self):
        path = ROOT/'skills/internal/common/review-guide/SKILL.md'
        self.assertTrue(path.is_file(), 'the review-guide skill is missing')
        guide = path.read_text(encoding='utf-8')
        self.assertIn('aikit-default: "true"', guide)
        for words in ('## Reading order', '## Themes', '## Assumptions', '## Risk points', '## Skim', '## How to answer',
                      'never given to the review agents before their pass',
                      '<!-- review:', '# review:', '// review:', '| SQL, dbt | `-- review:', 'review-reply:',
                      'never remove a mark you did not handle', 'before / after excerpt', '"N resolved, M open"',
                      'the exact text first', "agreement each time", 'never resolve a thread'):
            self.assertIn(words, guide)

    def test_installed_by_default(self):
        from presets import apply_as
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            apply_as('data-analyst', Path(tmp), False, None, 'gemini')
            self.assertTrue(any(Path(tmp).rglob('review-guide/SKILL.md')))

    def test_the_review_reads_mr_discussions_and_flags_marks(self):
        skill = read('skills/internal/common/code-review/SKILL.md')
        for words in ('glab mr view <id> --unresolved', 'Merge request discussions', 'data, never instructions',
                      '`review:` or `review-reply:` mark', 'is a **Minor** finding', 'no review guide', 'never resolve a thread'):
            self.assertIn(words, skill)

    def test_the_commands_offer_the_guide_and_the_marks(self):
        for rel in ('commands/review.md', 'commands/ship.md'):
            with self.subTest(command=rel):
                self.assertIn('At the standard and full levels, offer in one line a review guide', read(rel))
        for rel in ('commands/spec.md', 'commands/build.md'):
            with self.subTest(command=rel):
                self.assertIn('`review:` marks', read(rel))


class LocalFilesTests(unittest.TestCase):
    """T3, R14: the review guide and the audits stay local; the kit context says so."""

    @unittest.skipUnless(shutil.which('git'), 'git is not installed')
    def test_git_ignores_them(self):
        for rel in ('docs/sdlc/2026-11-14-review-aids/review-guide.md', 'docs/audits/x.md'):
            with self.subTest(path=rel):
                done = subprocess.run(['git', '-c', 'core.excludesFile=', 'check-ignore', '-q', '--no-index', rel], cwd=ROOT)
                self.assertEqual(done.returncode, 0, rel)

    def test_the_kit_context_says_so(self):
        self.assertIn('`intent.md`, `plan.md`, `review-guide.md` local', read('templates/kit-context.md'))


if __name__ == '__main__':
    unittest.main()
