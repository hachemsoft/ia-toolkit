"""The integrity hook runs after every tool call: what it loads when nothing moved, and an alert that survives a kit
folder it cannot write to. Temporary homes only: no network, no model."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from installer.core import ROOT

HOOKS = ROOT/'runtime'/'hooks'
HEAVY = ('hashlib', 'tempfile', 'pathlib', 'shutil', 'random', 'bz2', 'lzma')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_hook(name):
    spec = importlib.util.spec_from_file_location('hook_'+name.replace('-', '_'), HOOKS/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Installed(unittest.TestCase):
    """A home where the kit installed the check itself and one file, from a clone whose .git/config is recorded."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        self.kit = self.home/'.ai-kit'
        self.hook = self.kit/'hooks'/'integrity.py'
        self.other = self.kit/'hooks'/'shell-guard.py'
        self.clone = self.home/'apps'/'ai-toolkit'
        for path, data in ((self.hook, (HOOKS/'integrity.py').read_bytes()), (self.other, b'print(1)\n'), (self.clone/'.git'/'config', b'[core]\n')):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        files = {p.relative_to(self.home).as_posix(): sha(p.read_bytes()) for p in (self.hook, self.other)}
        self.state = {'version': '9.9.9', 'files': files, 'blocks': {}, 'targets': [], 'kit_dir': str(self.clone), 'kit_git': {}}
        (self.kit/'state.json').write_text(json.dumps(self.state), encoding='utf-8')

    def imported(self, payload):
        """(modules the installed hook loaded, its answer) for one call, read from Python's own import log."""
        env = {**os.environ, 'HOME': str(self.home), 'USERPROFILE': str(self.home)}
        proc = subprocess.run([sys.executable, '-I', '-X', 'importtime', str(self.hook)], input=json.dumps(payload), capture_output=True,
                              text=True, encoding='utf-8', env=env, timeout=30)
        names = {line.rsplit('|', 1)[1].strip() for line in proc.stderr.splitlines() if line.startswith('import time:') and '|' in line}
        return names, json.loads(proc.stdout or '{}')


class NothingMoved(Installed):
    def test_a_call_that_finds_nothing_loads_none_of_the_heavy_modules(self):
        bash = {'hook_event_name': 'PostToolUse', 'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}
        self.imported(bash)  # the first call records the stamps
        for payload in (bash, {'hook_event_name': 'PostToolUse', 'tool_name': 'Read', 'tool_input': {'file_path': 'a'}}):
            names, answer = self.imported(payload)
            self.assertEqual(answer, {})
            self.assertIn('json', names)  # the import log was read
            self.assertEqual(sorted(n for n in names if n.split('.')[0].lstrip('_') in HEAVY), [], payload['tool_name'])

    def test_a_change_is_still_reported_after_the_quiet_calls(self):
        bash = {'hook_event_name': 'PostToolUse', 'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}
        self.imported(bash)
        self.imported(bash)
        self.other.write_bytes(b'print(2)\n')
        _, answer = self.imported(bash)
        self.assertIn('.ai-kit/hooks/shell-guard.py', answer.get('systemMessage', ''))
        (self.clone/'.git'/'config').write_text('[remote "origin"]\n\turl = https://example.org/x.git\n', encoding='utf-8')
        _, answer = self.imported(bash)
        self.assertIn('git settings changed', answer.get('systemMessage', ''))


class KitFolderNotWritable(Installed):
    """The marker cannot be written (a kit folder that is read-only or gone): the alert is still given."""

    def refused(self):
        return mock.patch('tempfile.mkstemp', side_effect=PermissionError(13, 'read-only'))

    def test_write_marker_never_raises(self):
        module = load_hook('integrity')
        with self.refused():
            module.write_marker(str(self.kit/'integrity.json'), {'a': 1})
        self.assertFalse((self.kit/'integrity.json').exists())
        module.write_marker(str(self.home/'absent'/'integrity.json'), {'a': 1})  # a folder that is gone

    def test_a_state_that_cannot_be_read_is_still_announced(self):
        module = load_hook('integrity')
        (self.kit/'state.json').write_text('{not json', encoding='utf-8')
        with self.refused(), mock.patch.object(module, '__file__', str(self.hook)):
            agent, person = module.checked(str(self.home))
        self.assertIn('could not check', agent)
        self.assertIn('ai-kit doctor', person)

    def test_a_change_is_still_announced(self):
        module = load_hook('integrity')
        self.other.write_bytes(b'print(2)\n')
        with self.refused(), mock.patch.object(module, '__file__', str(self.hook)):
            agent, person = module.checked(str(self.home))
        self.assertIn('.ai-kit/hooks/shell-guard.py', person)


if __name__ == '__main__':
    unittest.main()
