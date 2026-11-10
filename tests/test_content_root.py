"""V2 slice 1 (ADR 0013): the engine root and the content root are distinct. The content (skills, agents, commands, practices,
profiles, organization.toml, the kit context template) can come from another tree, the way a Core source extracted at a tag
will; the engine's own files (hooks, scripts, schemas) still come from the engine."""
import contextlib
import io
from pathlib import Path
import shutil
import tempfile
import unittest

from installer.cli import apply
from installer.core import ROOT, KitError, content_from, content_root

CONTENT = ('skills', 'agents', 'commands', 'context', 'templates', 'aikit.toml')


class ContentRootTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base/'home'
        self.home.mkdir()
        self.source = self.base/'core'
        for name in CONTENT:
            (shutil.copytree if (ROOT/name).is_dir() else shutil.copy2)(ROOT/name, self.source/name)

    def test_the_default_content_root_is_the_engine_root(self):
        self.assertEqual(content_root(), ROOT)

    def test_content_comes_from_the_source_tree_and_engine_files_from_the_engine(self):
        skill = self.source/'skills/internal/common/tdd/SKILL.md'
        skill.write_text(skill.read_text(encoding='utf-8')+'\nMarker from the source tree.\n', encoding='utf-8')
        command = self.source/'commands/build.md'
        command.write_text(command.read_text(encoding='utf-8')+'\nMarker in the build command.\n', encoding='utf-8')
        with content_from(self.source), contextlib.redirect_stdout(io.StringIO()):
            apply(self.home, False, None, 'claude')
        self.assertEqual(content_root(), ROOT)  # restored after the block
        self.assertIn('Marker from the source tree.', (self.home/'.claude/skills/ai-kit-tdd/SKILL.md').read_text(encoding='utf-8'))
        self.assertIn('Marker in the build command.', (self.home/'.claude/commands/build.md').read_text(encoding='utf-8'))
        self.assertEqual((self.home/'.ai-kit/hooks/protected-paths.py').read_bytes(), (ROOT/'runtime/hooks/protected-paths.py').read_bytes())

    def test_a_skill_missing_from_the_source_is_not_read_from_the_engine(self):
        shutil.rmtree(self.source/'skills/internal/common/tdd')
        with content_from(self.source), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KitError) as caught:
                apply(self.home, False, None, 'claude')
        self.assertIn('requires tdd, which does not exist', str(caught.exception))  # 2.0 slice 3: refused by the requirement check


if __name__ == '__main__':
    unittest.main()
