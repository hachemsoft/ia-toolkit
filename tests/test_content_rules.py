"""4.24.1: texts that went against a kit rule. No skill pushes or commits on its own (the person agrees in the session; a
repo instruction never lifts that); /guide and the routing skill route a question about the project to /explain and a
question for primary sources to /research (ADR 0026)."""
import unittest

from installer.core import ROOT, load_commands

SKILLS = ROOT/'skills/internal/common'


class ContentRuleTests(unittest.TestCase):
    def test_the_wayfinder_never_pushes_without_the_persons_agreement(self):
        text = (SKILLS/'wayfinder/SKILL.md').read_text(encoding='utf-8')
        self.assertNotIn('Push the branch but', text)
        step = next(line for line in text.splitlines() if line.startswith('5. **Fire the research subagents.**'))
        self.assertRegex(step, r'(?i)push it only when the person agreed')
        self.assertIn('open no PR', step)

    def test_implement_commits_only_on_the_persons_agreement(self):
        text = (SKILLS/'implement/SKILL.md').read_text(encoding='utf-8')
        self.assertNotIn("or the repo's instructions say so", text)
        self.assertIn('Commit only when the person agreed to commits in this session', text)

    def test_guide_and_routing_route_to_research_and_analysis(self):
        guide = next(c for c in load_commands() if c['name'] == 'guide')['prompt']
        self.assertRegex(guide, r'a question about the project[^;.]*is /explain')
        self.assertRegex(guide, r'primary sources[^;.]*is /research')
        self.assertLess(len(guide), 4000)
        routing = (SKILLS/'routing/SKILL.md').read_text(encoding='utf-8')
        tools = next(line for line in routing.splitlines() if line.startswith('`/learn`'))
        self.assertRegex(tools, r'`/explain`[^·]*question about the project')
        self.assertRegex(tools, r'`/research`[^·]*primary sources[^·]*recorded in the repo')
        self.assertIn('`/explain <question>`', tools)


if __name__ == '__main__':
    unittest.main()
