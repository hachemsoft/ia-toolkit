"""4.7.1: a guardrail that lets an agy tool call through answers {"decision": "ask"}, never "allow". agy's "allow"
approves the call without its permission prompt (seen with agy 1.5.8: in `agy -p`, a `touch` outside the person's
permission rules ran); "ask" hands the call to agy's own permission flow, as if no hook had answered."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HOOKS = Path(__file__).resolve().parents[1]/'runtime'/'hooks'
RULES = ('dbt-prod-guard', 'git-guard', 'bq-cost-guard', 'infra-prod-guard')


class AgyDecidesItsOwnPermissions(unittest.TestCase):
    def answer(self, script, rules, payload, env=None):
        home = tempfile.mkdtemp()
        proc = subprocess.run([sys.executable, '-I', str(HOOKS/script), *rules], input=json.dumps(payload), capture_output=True, text=True,
                              encoding='utf-8', env={**os.environ, 'HOME': home, 'USERPROFILE': home, **(env or {})})
        return json.loads(proc.stdout or '{}')

    def test_a_call_let_through_is_handed_back_to_agy(self):
        work = tempfile.mkdtemp()
        payloads = ({'toolCall': {'name': 'run_command', 'args': {'CommandLine': 'touch notes.md'}}, 'workspacePaths': [work]},
                    {'toolCall': {'name': 'write_to_file', 'args': {'TargetFile': work + '/notes.md'}}, 'workspacePaths': [work]},
                    {'toolCall': {'name': 'read_file', 'args': {'Path': work + '/notes.md'}}, 'workspacePaths': [work]})
        for payload in payloads:
            self.assertEqual(self.answer('protected-paths.py', [], payload), {'decision': 'ask'}, payload)
            self.assertEqual(self.answer('shell-guard.py', list(RULES), payload), {'decision': 'ask'}, payload)
        self.assertEqual(self.answer('shell-guard.py', [], payloads[0]), {'decision': 'ask'})
        # A note the guardrail adds keeps its text and hands the decision back too.
        noted = self.answer('shell-guard.py', ['dbt-prod-guard'], {'toolCall': {'name': 'run_command', 'args': {'CommandLine': 'dbt run --target prod'}},
                                                                  'workspacePaths': [work]}, {'AI_KIT_ALLOW_PROD': '1'})
        self.assertEqual(noted['decision'], 'ask')
        self.assertIn('allowed by AI_KIT_ALLOW_PROD=1', noted['systemMessage'])
        # A refusal stays a refusal.
        refused = self.answer('shell-guard.py', ['git-guard'], {'toolCall': {'name': 'run_command', 'args': {'CommandLine': 'git reset --hard'}}})
        self.assertEqual(refused['decision'], 'deny')


if __name__ == '__main__':
    unittest.main()
