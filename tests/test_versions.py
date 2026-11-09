"""0.40: every skill and agent has its own version; changing one without raising its version fails the build."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from installer import cli, versions
from installer.core import ROOT


class LockTests(unittest.TestCase):
    def test_every_component_has_a_version_and_the_lock_is_current(self):
        # The message says what to do: raise the version in the catalog, then python3 scripts/versions.py --update.
        self.assertEqual(versions.problems(), [])
        self.assertEqual(versions.stale(), [], 'run python3 scripts/versions.py --update')

    def test_a_change_under_the_same_version_is_refused(self):
        lock = {'skills': {'tdd': {'version': '1.0.0', 'digest': 'old'}}, 'agents': {}}
        now = {'skills': {'tdd': {'version': '1.0.0', 'digest': 'new'}}, 'agents': {}}
        with mock.patch.object(versions, 'current', return_value=now):
            found = versions.problems(lock)
        self.assertEqual(len(found), 1)
        self.assertIn('skill tdd changed, still 1.0.0: raise its version', found[0])

    def test_a_raised_version_is_accepted_and_a_lower_one_refused(self):
        lock = {'skills': {'tdd': {'version': '1.2.0', 'digest': 'old'}}, 'agents': {}}
        with mock.patch.object(versions, 'current', return_value={'skills': {'tdd': {'version': '1.3.0', 'digest': 'new'}}, 'agents': {}}):
            self.assertEqual(versions.problems(lock), [])
        with mock.patch.object(versions, 'current', return_value={'skills': {'tdd': {'version': '1.1.0', 'digest': 'new'}}, 'agents': {}}):
            self.assertIn('lower than 1.2.0', versions.problems(lock)[0])

    def test_a_missing_or_malformed_version_is_refused(self):
        with mock.patch.object(versions, 'current', return_value={'skills': {'a': {'version': None, 'digest': 'x'}},
                                                                    'agents': {'b': {'version': 'v2', 'digest': 'y'}}}):
            found = versions.problems({})
        self.assertEqual(len(found), 2)
        self.assertTrue(all('not like 1.2.3' in line for line in found))

    def test_the_digest_ignores_line_endings(self):
        # A Windows checkout has CRLF: the same skill must give the same digest.
        with tempfile.TemporaryDirectory() as tmp:
            unix, windows = Path(tmp)/'unix', Path(tmp)/'windows'
            for folder, text in ((unix, b'---\nname: x\n---\nbody\n'), (windows, b'---\r\nname: x\r\n---\r\nbody\r\n')):
                (folder/'refs').mkdir(parents=True)
                (folder/'SKILL.md').write_bytes(text)
                (folder/'refs'/'a.md').write_bytes(b'ref\n')
            self.assertEqual(versions.content_digest(unix), versions.content_digest(windows))
            # The order does not depend on the system's comparison of paths (case-insensitive on Windows).
            (unix/'B.md').write_bytes(b'b\n'); (windows/'B.md').write_bytes(b'b\n')
            files = sorted(p.relative_to(unix).as_posix() for p in unix.rglob('*') if p.is_file())
            self.assertEqual(files, ['B.md', 'SKILL.md', 'refs/a.md'])
            self.assertEqual(versions.content_digest(unix), versions.content_digest(windows))
            (windows/'refs'/'a.md').write_bytes(b'changed\n')
            self.assertNotEqual(versions.content_digest(unix), versions.content_digest(windows))


class InstalledTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        patcher = mock.patch('shutil.which', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_kit(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return cli.apply('general', self.home, False, {'email': 'a@example.org', 'source': 'option'}, 'gemini')

    def state(self):
        return json.loads((self.home/'.ai-kit/state.json').read_text(encoding='utf-8'))

    def test_state_records_versions_and_a_reapply_says_what_changed(self):
        self.run_kit()
        recorded = self.state()['installed']['versions']
        self.assertEqual(recorded['skills']['tdd'], versions.catalog_versions()['skills']['tdd'])
        self.assertIn('verifier', recorded['agents'])
        state = self.state()
        state['installed']['versions']['skills']['tdd'] = '0.9.0'
        (self.home/'.ai-kit/state.json').write_text(json.dumps(state), encoding='utf-8')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.doctor_checks(self.home)
        self.assertIn('skill tdd 0.9.0 → '+recorded['skills']['tdd']+'; run ai-kit sync --offline', out.getvalue())
        notices = self.run_kit()
        self.assertTrue(any('Updated: skill tdd 0.9.0 → ' in n for n in notices))
        self.assertFalse(any('Updated:' in n for n in self.run_kit()))  # nothing to say the next time

    def test_a_friction_names_the_version_of_its_skill(self):
        self.run_kit()
        env = {**os.environ, 'HOME': str(self.home), 'USERPROFILE': str(self.home)}
        proc = subprocess.run([sys.executable, '-I', str(ROOT/'runtime/friction.py'), '--category', 'skill', '--command', 'grilling',
                               '--text', 'one recommended answer only'], capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        entry = json.loads((self.home/'.ai-kit/frictions.jsonl').read_text(encoding='utf-8').splitlines()[-1])
        self.assertEqual(entry['component'], 'skill grilling '+versions.catalog_versions()['skills']['grilling'])


if __name__ == '__main__':
    unittest.main()
