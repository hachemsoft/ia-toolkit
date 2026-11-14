"""Version B of the agents (spec docs/sdlc/2026-11-14-kit-agents/spec-b.md): blast-radius and contribution-auditor,
installed by default; agent configuration as a trigger of the dedicated security review (ADR 0029); architecture-reviewer
and infra-reviewer called by their playbooks. Content and installation checks; the agents' behaviour is measured by eval
cases, written and run only on request."""
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


class BlastRadiusTests(unittest.TestCase):
    """T1, R1-R3, R10: what blast-radius looks for, its output, when it runs."""

    def test_the_agent(self):
        agent = read('agents/internal/common/blast-radius.md')
        self.assertIn('aikit-default: "true"', agent)
        for words in ('Cold review', 'callers', 'public contracts', 'downstream dbt models', 'areas of a monorepo',
                      'file:line', 'flowchart LR', 'what to test before the merge', 'dynamic calls', 'consumers outside the repository',
                      'Nothing reached: no map', 'never a guarantee', 'does not judge the quality', 'Before any code exists', 'Not for:'):
            self.assertIn(words, agent)
        self.assertNotIn('tools:', agent)  # the read-only defaults

    def test_it_runs_at_the_full_level(self):
        self.assertIn('At the full level, before writing the areas of concern, give ai-kit-blast-radius', read('commands/spec.md'))
        self.assertIn('At the full level, or when the person asks, also give ai-kit-blast-radius', read('skills/internal/common/code-review/SKILL.md'))


class ContributionAuditorTests(unittest.TestCase):
    """T2, R4-R7, R10: what contribution-auditor audits and finds, its severities, and agent configuration as a risk."""

    def test_the_agent(self):
        agent = read('agents/internal/common/contribution-auditor.md')
        self.assertIn('aikit-default: "true"', agent)
        for words in ('AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'SKILL.md', 'hooks', '.mcp.json', 'mcpServers',
                      'hidden instruction', 'U+200B', 'U+202A', 'U+2066', 'U+FEFF', 'allowed-tools', 'sends data out',
                      'too broad a trigger', 'imitates a kit component', 'data, never instructions',
                      'Important', 'Minor', '<U+200B>', 'never blocks', 'Not for:', 'U+E0000', 'read the changed files yourself',
                      'that is its content, not a finding', 'Text aimed at whoever audits'):
            self.assertIn(words, agent)

    def test_agent_configuration_is_a_change_at_risk(self):
        skill = read('skills/internal/common/code-review/SKILL.md')
        for words in ('or agent configuration (`AGENTS.md`', '`.cursor/`', '`.mcp.json`', '`runtime/hooks/`, `templates/`',
                      'ai-kit-contribution-auditor that configuration', 'Security review: dedicated (agent configuration)'):
            self.assertIn(words, skill)


class WiringTests(unittest.TestCase):
    """T3, R8, R9, R10, R11: the playbooks call their reviewer cold, with a fallback; the two new agents are installed."""

    def test_the_playbooks_call_their_reviewer(self):
        architecture = read('skills/internal/architecture/architecture-decision/SKILL.md')
        infra = read('skills/internal/operations/infra-change/SKILL.md')
        self.assertIn('ai-kit-architecture-reviewer', architecture)
        self.assertIn('ai-kit-infra-reviewer', infra)
        for text in (architecture, infra):
            self.assertIn('never the author', text)
            self.assertIn('without the agent installed', text)
        for rel in ('agents/internal/architecture/architecture-reviewer.md', 'agents/internal/operations/infra-reviewer.md'):
            self.assertIn('Not for:', read(rel))

    def test_installed_by_default(self):
        from presets import apply_as
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            apply_as('data-analyst', Path(tmp), False, None, 'gemini')
            for name in ('blast-radius', 'contribution-auditor'):
                self.assertTrue((Path(tmp)/'.gemini/agents'/('ai-kit-'+name+'.md')).is_file(), name)


if __name__ == '__main__':
    unittest.main()
