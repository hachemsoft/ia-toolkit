"""A repo's protected paths (.ai-kit/protected-paths) in shell commands: a command that names a protected file and changes
or deletes it is refused; a command that reads it, or a tool that regenerates it without naming it, runs."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from installer.core import ROOT

HOOK = ROOT/'runtime/hooks/protected-paths.py'

# Changes or deletes a protected file it names: refused.
REFUSED = (
    'echo x > poetry.lock', 'echo x >> poetry.lock', 'echo x >poetry.lock', 'cat a.txt | tee poetry.lock', 'tee -a target/run.log < a.txt',
    "sed -i 's/a/b/' poetry.lock", "sed -i.bak -e 's/a/b/' poetry.lock", "perl -pi -e 's/a/b/' poetry.lock",
    'rm poetry.lock', 'rm -rf target', 'rm -f target/a.sql', 'rmdir target', 'unlink poetry.lock',
    'mv poetry.lock poetry.old', 'mv new.lock poetry.lock', 'cp new.lock poetry.lock', 'cp -r build target',
    'truncate -s 0 poetry.lock', 'touch target/a.sql', 'chmod +w poetry.lock', 'ln -sf other.lock poetry.lock',
    'git checkout -- poetry.lock', 'git restore poetry.lock', 'git rm poetry.lock', 'git checkout main -- target/a.sql',
    'cd . && rm poetry.lock', 'ls ; echo x > ./poetry.lock', 'sudo rm poetry.lock', 'sh -c "rm poetry.lock"',
    'find . -name a.sql | xargs rm target/a.sql', 'rm "poetry.lock"', 'rm models/legacy/old.sql', 'rm MODELS/Legacy/old.sql',
    'rm {root}/poetry.lock', 'echo x > {root}/target/a.sql',
    'Remove-Item poetry.lock', 'Set-Content poetry.lock "x"', 'del poetry.lock',
)

# Reads a protected file, changes another file, regenerates the file without naming it, or only speaks of it: runs.
ALLOWED = (
    'cat poetry.lock', 'grep requests poetry.lock', 'head -5 poetry.lock', 'ls target', 'ls -la target/', 'wc -l poetry.lock',
    'diff poetry.lock other.lock', 'git diff poetry.lock', 'git log -- poetry.lock', 'git status', 'git add poetry.lock',
    'cp poetry.lock /tmp/copy.lock', 'cat poetry.lock > summary.txt', 'grep x poetry.lock | tee out.txt', 'sed -n 1,5p poetry.lock',
    "sed 's/a/b/' poetry.lock", 'find target -name "*.sql"',
    'poetry lock', 'poetry add requests', 'npm install', 'dbt run', 'dbt build --select my_model', 'terraform init',
    'rm targets/a.sql', 'rm other.txt', 'echo x > notes.md', 'mv a.txt b.txt', 'rm -rf build',
    'echo "do not rm poetry.lock"', 'git commit -m "rm poetry.lock explained"', "python3 - <<'EOF'\nprint('rm poetry.lock')\nEOF",
    'cat <<EOF > notes.md\nrm poetry.lock\nEOF',
)


def shell_payloads(command, cwd):
    """The same shell command as each of the four CLIs sends it to the hook."""
    return {
        'gemini': {'tool_name': 'run_shell_command', 'tool_input': {'command': command}, 'cwd': cwd},
        'agy': {'toolCall': {'name': 'run_command', 'args': {'CommandLine': command}}, 'workspacePaths': [cwd]},
        'codex': {'hook_event_name': 'PreToolUse', 'tool_name': 'shell', 'tool_input': {'command': ['bash', '-lc', command]}, 'cwd': cwd},
        'claude': {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': cwd},
    }


class RepoPathsInShellTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve()
        (self.repo/'.git').mkdir()
        (self.repo/'.ai-kit').mkdir()
        (self.repo/'.ai-kit/protected-paths').write_text('# generated or frozen\ntarget/**\nmodels/legacy/**\n*.lock\n', encoding='utf-8')
        (self.repo/'target').mkdir()

    def answer(self, payload):
        proc = subprocess.run([sys.executable, '-I', str(HOOK)], input=json.dumps(payload), capture_output=True, text=True,
                              encoding='utf-8', env={**os.environ, 'AI_KIT_PROBE': '1'})
        return json.loads(proc.stdout or '{}')

    def refused(self, payload):
        out = self.answer(payload)
        return out.get('decision') == 'deny' or out.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny'

    def gemini(self, command):
        return shell_payloads(command.replace('{root}', str(self.repo)), str(self.repo))['gemini']

    def test_a_command_that_changes_or_deletes_a_protected_file_is_refused(self):
        for command in REFUSED:
            self.assertTrue(self.refused(self.gemini(command)), command)
        reason = self.answer(self.gemini('rm poetry.lock'))['reason']
        for words in ('poetry.lock', '*.lock', '.ai-kit/protected-paths', 'person'):
            self.assertIn(words, reason)  # says which file, which pattern, where it is declared, and what to do instead

    def test_reading_it_or_regenerating_it_with_its_tool_runs(self):
        for command in ALLOWED:
            self.assertFalse(self.refused(self.gemini(command)), command)
        (self.repo/'.ai-kit/protected-paths').unlink()  # a repo that declares nothing: nothing changes
        for command in REFUSED[:12]:
            self.assertFalse(self.refused(self.gemini(command)), command)

    def test_the_four_clis_and_a_subfolder(self):
        for cli, payload in shell_payloads('rm poetry.lock', str(self.repo)).items():
            self.assertTrue(self.refused(payload), cli)
        for cli, payload in shell_payloads('cat poetry.lock', str(self.repo)).items():
            self.assertFalse(self.refused(payload), cli)
        self.assertEqual(self.answer(shell_payloads('cat poetry.lock', str(self.repo))['agy']), {'decision': 'ask'})
        sub = self.repo/'models'
        sub.mkdir()
        # Started from a subfolder: paths are read from that folder, patterns from the repo root.
        self.assertTrue(self.refused(shell_payloads('rm ../poetry.lock', str(sub))['gemini']))
        self.assertTrue(self.refused(shell_payloads('rm legacy/old.sql', str(sub))['gemini']))
        self.assertFalse(self.refused(shell_payloads('rm staging/new.sql', str(sub))['gemini']))


if __name__ == '__main__':
    unittest.main()
