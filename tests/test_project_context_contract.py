"""What init-project-context writes in a project matches what the kit reads there (ADR 0032): a repo's REVIEW.md adds to the
kit's review passes and never removes one, the git rule for local notes holds in a monorepo, and the AGENTS.md, plan.md and
intent.md templates carry what the commands read, without copying the kit's own rules."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT/'skills/internal/common/init-project-context'
CODE_REVIEW = ROOT/'skills/internal/common/code-review/SKILL.md'


def read(path):
    return Path(path).read_text(encoding='utf-8')


def review_passes():
    """The passes code-review runs: its bold bullets between the scope step and the dedicated security review."""
    text = read(CODE_REVIEW)
    block = text[text.index('Run them in sequence'):text.index('**A change at risk')]
    return re.findall(r'^- \*\*(\w+)\*\*:', block, re.M)


def headings(text):
    return re.findall(r'^#+ (.+)$', text, re.M)


class ProjectContextContractTests(unittest.TestCase):
    def test_review_template_adds_to_every_kit_pass(self):
        passes = review_passes()
        self.assertEqual(passes, ['Bugs', 'Security', 'Domain', 'Standards', 'Compliance', 'Tests'])
        template = read(SKILL/'templates/REVIEW.md')
        for name in passes:
            self.assertIn(name, template)
        self.assertIn('never removes a pass', template)
        self.assertIn('never lower a Security or Tests finding', template)
        for gone in ('Run four passes', 'Full mode'):
            self.assertNotIn(gone, template)
        standards = next(line for line in read(CODE_REVIEW).splitlines() if line.startswith('- **Standards**'))
        self.assertNotRegex(standards, r'\bwins?\b')
        self.assertIn('never removes a pass', standards)
        self.assertIn('never lower a Security or Tests finding', standards)
        self.assertIn('never removes a pass', read(ROOT/'commands/review.md'))

    @unittest.skipUnless(shutil.which('git'), 'git not installed')
    def test_gitignore_lines_cover_area_notes(self):
        lines = re.findall(r'`(\*\*/docs/sdlc/[^`]+)`', read(SKILL/'SKILL.md'))
        self.assertNotEqual(lines, [], 'the skill proposes no .gitignore line valid in an area')
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
            with open(repo/'.gitignore', 'w', encoding='utf-8', newline='\n') as f:  # no CRLF on Windows
                f.write('\n'.join(lines)+'\n')
            def ignored(rel):  # hermetic: the machine's global excludes do not count
                return subprocess.run(['git', '-c', 'core.excludesFile=', 'check-ignore', '-q', rel], cwd=repo).returncode == 0
            self.assertTrue(ignored('docs/sdlc/2026-01-01-x/intent.md'))
            self.assertTrue(ignored('apis/billing/docs/sdlc/2026-01-01-x/plan.md'))
            self.assertTrue(ignored('apis/billing/docs/sdlc/handoff-2026-01-01.md'))
            self.assertFalse(ignored('apis/billing/docs/sdlc/2026-01-01-x/spec.md'))

    def test_project_files_match_what_the_kit_reads(self):
        agents = read(SKILL/'templates/AGENTS.md')
        for title in ('Verifying your work', 'Report', 'Things the agent gets wrong', 'Where the rest lives'):
            self.assertIn(title, headings(agents))
        self.assertIn('| Stack | Changed | Full |', agents)
        for stack in ('PHP', 'Go', 'Scala'):
            self.assertRegex(agents, r'(?m)^\| '+stack+r'\b')
        for copy in ('Never commit', 'never weaken', 'docs/sdlc/'):
            self.assertNotIn(copy, agents, 'the kit context already carries it')

        plan = read(SKILL/'templates/plan.md')
        self.assertIn('Ceremony: quick | standard | full', plan)
        titles = headings(plan)
        self.assertLess(titles.index('Risks'), titles.index('Files that change'))

        self.assertEqual(titles, ['Plan: <title> (from spec.md or intent.md <date>)', 'Risks', 'Files that change', 'Order of work', 'Proof'])
        intent = headings(read(SKILL/'templates/intent.md'))
        self.assertEqual(intent.index('Risks'), intent.index('Constraints')+1)
        self.assertNotRegex(agents, r'\b(code-review|tdd|init-project-context|setup-workflow)\b', 'a kit skill named in a repo file')

        skill = read(SKILL/'SKILL.md')
        self.assertNotIn('only when the repo is used with Claude Code', skill)
        self.assertIn('references/monorepo.md', skill)
        self.assertIn('never name a personal skill or a kit skill in a repo file', skill)
        self.assertIn('first paragraph kept word for word', skill)
        self.assertIn('An existing `GEMINI.md` stays as it is', skill)

    def test_monorepo_layers_are_shown_before_writing(self):
        text = read(SKILL/'references/monorepo.md')
        for words in ('pnpm-workspace.yaml', 'go.work', 'CODEOWNERS', 'Skip dependency and generated folders',
                      'only when it differs', 'start with the map', 'ask; do not invent'):
            self.assertIn(words, text)
        self.assertRegex(text, r'`Extends [^`]+\. Overrides: [^`]+`')
        self.assertIn('Overrides: none.', text)

    def test_no_kit_text_has_the_agent_create_or_fill_a_claude_md(self):
        setup = read(ROOT/'skills/internal/common/setup-workflow/SKILL.md')
        self.assertIn('Never write the block into `CLAUDE.md`', setup)
        self.assertNotIn('If `CLAUDE.md` exists, edit it', setup)
        for path in (ROOT/'templates/kit-context.md', ROOT/'installer/adapters/claude.py'):
            text = read(path)
            self.assertIn('`@AGENTS.md` atop an existing one', text, path.name)
            self.assertNotIn('one line, `@AGENTS.md`', text, path.name)

    def test_the_skill_is_offered_where_its_files_are_missing(self):
        self.assertIn('without `REVIEW.md`: offer the init-project-context skill once', read(ROOT/'commands/review.md'))
        tdd = read(ROOT/'skills/internal/common/tdd/SKILL.md')
        self.assertIn('offer the init-project-context skill, never as a prerequisite', tdd)
        self.assertIn('or a parent it extends', tdd)


class KitDriftTests(unittest.TestCase):
    """Guards against the drift found on 2026-11-14: a level vocabulary, a cited file or a retired name that the rest of
    the kit no longer has."""
    AGENT_TEXTS = ('commands', 'skills', 'agents', 'templates')

    def test_artifact_templates_use_the_kit_levels(self):
        levels = re.findall(r'\*\*(quick|standard|full)\*\*', read(ROOT/'templates/kit-context.md'))
        self.assertEqual(levels, ['quick', 'standard', 'full'])
        self.assertIn('Ceremony: '+' | '.join(levels), read(SKILL/'templates/plan.md'))
        self.assertIn('Level: quick', read(ROOT/'commands/build.md'))
        self.assertIn('(quick, standard or full)', read(ROOT/'commands/ship.md'))
        old = [f'{path.relative_to(ROOT)}' for folder in ('commands', 'templates') for path in (ROOT/folder).rglob('*.md')
               if re.search(r'\btweak\b|large change', read(path))]
        old += [f'{path.relative_to(ROOT)}' for path in (SKILL/'templates').glob('*.md') if 'tweak' in read(path)]
        self.assertEqual(old, [])

    def test_files_a_skill_cites_exist(self):
        formats = {p.name for p in (ROOT/'skills').rglob('*-FORMAT.md')}
        missing, checked = [], 0
        for skill in (ROOT/'skills').rglob('SKILL.md'):
            text = read(skill)
            for rel in set(re.findall(r'(?<![\w/<.-])((?:templates|references)/[\w.-]+\.md)', text)):
                checked += 1
                if not (skill.parent/rel).is_file():
                    missing.append(f'{skill.parent.name}: {rel}')
            for name in set(re.findall(r'`([A-Z]+(?:-[A-Z]+)*-FORMAT\.md)`', text)):
                if name not in formats:
                    missing.append(f'{skill.parent.name}: {name}')
        self.assertGreater(checked, 10)
        self.assertEqual(missing, [])

    def test_no_agent_text_cites_a_retired_name(self):
        retired = ('init-workflow', 'Security scan', '.ai-kit/protected-paths')
        found = []
        for folder in self.AGENT_TEXTS:
            self.assertTrue((ROOT/folder).is_dir(), folder)
            for path in (ROOT/folder).rglob('*.md'):
                text = read(path)
                found += [f'{path.relative_to(ROOT)}: {name}' for name in retired if name in text]
        self.assertEqual(found, [])


if __name__ == '__main__':
    unittest.main()
