"""What the Core's texts say stays true to the kit's own rules and decisions: the Research workflow of ADR 0026, the
proof /build falls back to, the level of a shared contract, steering files and secrets the agent never touches, and
no word left from the profiles of version 1. Text only: no model."""
from pathlib import Path
import unittest

from installer.core import load_commands
from installer.frontmatter import parse

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {c['name']: c['prompt'] for c in load_commands()}


def skill(name):
    path = next((ROOT/'skills').rglob(name+'/SKILL.md'))
    return parse(path.read_text(encoding='utf-8'))[1]


class ResearchWorkflowTests(unittest.TestCase):
    """ADR 0026: frame the question and the criteria, search primary sources, compare options, challenge, recommend one
    option and one ruled-out alternative, recorded in the repo."""
    STEPS = (('criteria',), ('primary sources',), ('compare', 'options'), ('challenge', 'counter-example', 'assumptions that change the result'),
             ('ai-kit-doubter',), ('recommend', 'ruled-out alternative'))

    def test_the_skill_follows_the_five_steps_in_order(self):
        text = skill('investigation').lower()
        places = []
        for words in self.STEPS:
            for word in words:
                self.assertIn(word, text, word)
            places.append(text.index(words[0]))
        self.assertEqual(places, sorted(places), 'the steps come in the order of ADR 0026')
        self.assertIn('when it is installed', text)  # the doubter is optional: the challenge is done inline without it
        self.assertIn('markdown file', text)

    def test_the_command_names_the_steps_for_a_cli_without_the_skill(self):
        command = COMMANDS['research']
        for words in self.STEPS:
            for word in words:
                self.assertIn(word, command, word)
        self.assertIn('docs/research/<slug>.md', command)
        self.assertLess(len(command), 4000)


class BuildProofFallbackTests(unittest.TestCase):
    def test_build_names_the_proof_script_when_the_verifier_is_missing(self):
        build = COMMANDS['build']
        self.assertIn('ai-kit-verifier agent when available', build)
        self.assertIn('~/.ai-kit/bin/prove_test.py', build)
        self.assertIn('passes without the code', build)
        self.assertLess(len(build), 4189, 'lighter than before the script was named (4188 characters)')


class LevelOfASharedContractTests(unittest.TestCase):
    def test_guide_sends_a_shared_contract_to_full_as_the_kit_context_does(self):
        kit = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8')
        self.assertIn('production, a shared contract, a data model, irreversible or personal data', kit)
        guide = COMMANDS['guide']
        standard = guide[guide.index('a standard change'):guide.index('a full change')]
        full = guide[guide.index('a full change'):guide.index('reviewing changes')]
        self.assertNotIn('contract', standard.replace('no contract changed', ''))
        self.assertNotIn('an API', standard)
        for words in ('a shared contract', 'a data model', 'irreversible or personal data', 'production'):
            self.assertIn(words, full)

    def test_the_routing_skill_says_the_same(self):
        row = next(line for line in skill('routing').splitlines() if line.startswith('| Production'))
        for words in ('shared contract', 'data model', 'irreversible', 'personal data'):
            self.assertIn(words, row)


class NeverTouchedByTheAgentTests(unittest.TestCase):
    def test_the_retrospective_never_edits_a_global_steering_file(self):
        retro = skill('retrospective')
        self.assertIn('never edit it yourself', retro)
        self.assertIn('say what to change', retro)
        self.assertNotIn("in the repo OR the user's global scope", retro)

    def test_manual_steps_reads_the_example_file_never_the_env_file(self):
        steps = skill('manual-steps')
        self.assertNotIn('For setup: `.env`,', steps)
        self.assertIn('`.env.example`', steps)
        self.assertIn('never open `.env`', steps)


class NoWordFromVersionOneTests(unittest.TestCase):
    def test_no_profile_no_analyst_and_ticket_sorting_under_its_name(self):
        found = []
        for folder in ('skills', 'commands', 'agents', 'templates', 'context'):
            for path in sorted((ROOT/folder).rglob('*.md')):
                text = path.read_text(encoding='utf-8')
                found += [path.relative_to(ROOT).as_posix()+': '+words for words in ('in this profile', 'for an analyst', '`triage`') if words in text]
        self.assertEqual(found, [])

    def test_setup_workflow_names_the_skill_that_sorts_tickets(self):
        text = skill('setup-workflow')
        self.assertIn('`ticket-sorting`', text)
        self.assertIn('`needs-triage`', text)  # the label keeps its name


if __name__ == '__main__':
    unittest.main()


class DocumentedFiguresTests(unittest.TestCase):
    """The figures and lists the pages give are the repository's own."""

    def read(self, rel):
        return (ROOT/rel).read_text(encoding='utf-8')

    def test_the_readme_counts_the_commands_and_the_eval_cases_that_exist(self):
        from installer.settings import core_selection
        readme = self.read('README.md')
        default = len(core_selection()['commands'])
        self.assertIn(str(default)+' by default', readme)
        self.assertIn(str(len(COMMANDS) - default)+' optional |', readme)
        self.assertIn(str(len(list((ROOT/'evals/cases').glob('*.json'))))+' cases;', readme)

    def test_every_command_has_its_row_in_the_commands_page(self):
        page = self.read('docs/commands.md')
        self.assertEqual([name for name in sorted(COMMANDS) if '| `/'+name+'` |' not in page], [])

    def test_the_budgets_the_pages_give_are_the_ones_the_tests_hold(self):
        for rel in ('docs/extending.md', 'docs/architecture.md'):
            page = self.read(rel)
            self.assertIn('4,300', page, rel)
            self.assertNotIn('3,800 characters', page.replace('raised to 3,800', ''), rel)
        self.assertIn('4,200 for `/build`', self.read('docs/extending.md'))
        self.assertLess(len(self.read('templates/kit-context.md')), 4300)

    def test_the_sources_page_names_the_playbooks_that_exist(self):
        line = next(text for text in self.read('docs/sources.md').splitlines() if text.startswith('The domain playbooks'))
        self.assertNotIn('Java', line)
        self.assertIn('code change', line)
        self.assertTrue(next((ROOT/'skills').rglob('code-change/SKILL.md')).is_file())

    def test_the_review_and_compliance_pages_say_what_the_test_check_reads(self):
        for rel in ('docs/review.md', 'docs/compliance.md'):
            page = self.read(rel)
            self.assertIn('inside a file, dbt only', page, rel)
            self.assertIn('for every language', page, rel)

    def test_the_agy_page_names_the_version_checked_and_no_link_to_a_home_file(self):
        from installer.adapters import agy
        self.assertIn('agy '+agy.VERIFIED, self.read('docs/cli/agy.md'))
        self.assertNotIn('](~/', self.read('docs/cli/agy.md'))

    def test_the_pinned_dependencies_carry_no_note_about_a_python_the_kit_no_longer_supports(self):
        self.assertNotIn('before Python 3.11', self.read('packaging/runtime.txt'))

    def test_the_integrity_check_counts_the_files_it_watches(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('hook_integrity_doc', ROOT/'runtime/hooks/integrity.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(len(module.SHARED), 6)
        self.assertIn('the six files it shares', module.__doc__)
