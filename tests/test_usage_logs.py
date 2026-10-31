"""usage on Codex and agy: kit skills read and ai-kit-* agents invoked, read from the CLIs' own session files
(shapes taken from Codex sessions/rollout-*.jsonl and agy 1.4.12 conversations/<id>.db)."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from installer.adapters import agy, codex

STATE = {'installed': {'skills': ['tdd', 'grilling']}}


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)

    def names(self, events, kind):
        return [e['name'] for e in events if e['kind'] == kind]


class CodexTests(Base):
    def test_skills_agents_and_errors_from_the_session_files(self):
        folder = self.home/'.codex/sessions/2099/01/01'
        folder.mkdir(parents=True)
        ts = '2099-01-01T10:00:00.000Z'
        lines = [{'timestamp': ts, 'type': 'session_meta', 'payload': {'id': 'abc'}},
                 {'timestamp': ts, 'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'name': 'exec',
                  'input': 'tools.exec_command({cmd:"cat /h/.codex/skills/ai-kit-tdd/SKILL.md; cat /h/.codex/skills/mine/SKILL.md"})'}},
                 {'timestamp': ts, 'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'spawn_agent',
                  'arguments': json.dumps({'agent_type': 'ai-kit-verifier', 'message': 'x'})}},
                 {'timestamp': ts, 'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'spawn_agent',
                  'arguments': json.dumps({'agent_type': 'explorer'})}},
                 {'timestamp': ts, 'type': 'event_msg', 'payload': {'type': 'error', 'message': 'x'}}, 'not json']
        (folder/'rollout-2099-01-01T10-00-00-abc.jsonl').write_text('\n'.join(x if isinstance(x, str) else json.dumps(x) for x in lines), encoding='utf-8')
        events = list(codex.session_events(self.home, STATE))
        self.assertEqual(self.names(events, 'skill'), ['tdd'])
        self.assertEqual(self.names(events, 'agent'), ['ai-kit-verifier'])
        self.assertEqual(len([e for e in events if e['kind'] == 'error']), 1)
        self.assertEqual({e['session'] for e in events}, {'codex:abc'})
        self.assertEqual(codex.OBSERVES, {'prompt', 'skill', 'agent', 'error'})


class AgyTests(Base):
    def conversation(self, name, payloads):
        folder = self.home/'.gemini/antigravity-cli/conversations'
        folder.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(folder/(name+'.db'))) as db:
            db.execute('create table steps (idx integer, step_type integer, step_payload blob)')
            db.executemany('insert into steps values (?, ?, ?)', [(i, 132, p) for i, p in enumerate(payloads)])
        db.close()

    def test_skills_read_and_agents_invoked(self):
        read = b'\x0a\x10call_1\x12\tread_file\x1a{"Path":"/h/.gemini/skills/grilling/SKILL.md"}\x22'
        invoke = b'\x12\x0finvoke_subagent\x1a{"Prompt":"look","Role":"Reader","TypeName":"ai-kit-repo-investigator"}2'
        listing = b'context: skills at /h/.gemini/skills/tdd/SKILL.md'  # named, not read
        self.conversation('c1', [read, invoke, read+invoke, listing])
        self.conversation('broken', [])
        (self.home/'.gemini/antigravity-cli/conversations/bad.db').write_bytes(b'not sqlite')
        events = list(agy.conversation_events(self.home, STATE))
        self.assertEqual(self.names(events, 'skill'), ['grilling'])
        self.assertEqual(self.names(events, 'agent'), ['ai-kit-repo-investigator'])
        self.assertEqual({e['session'] for e in events}, {'agy:c1'})
        self.assertEqual(agy.OBSERVES, {'prompt', 'skill', 'agent'})


if __name__ == '__main__':
    unittest.main()
