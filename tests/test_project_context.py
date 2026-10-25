import contextlib, io, tempfile, unittest
from pathlib import Path
from installer.cli import apply
from installer.core import read_json, ROOT
class ProjectContextTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role):
  with contextlib.redirect_stdout(io.StringIO()):apply(role,self.home)
 def test_installed_for_both_profiles_with_dependencies(self):
  for role in ('data-analyst','data-developer'):
   self.run_kit(role);base=self.home/'.gemini/skills'
   self.assertTrue((base/'init-project-context/SKILL.md').is_file());self.assertTrue((base/'init-project-context/templates/AGENTS.md').is_file());self.assertTrue((base/'init-project-context/templates/GLOSSARY.md').is_file())
   self.assertTrue((base/'writing-for-agents/SKILL.md').is_file());self.assertTrue((base/'domain-modeling/SKILL.md').is_file())
 def test_templates_follow_upstream_formats(self):
  g=(ROOT/'skills/internal/common/init-project-context/templates/GLOSSARY.md').read_text(encoding='utf-8')
  self.assertIn('## Language',g);self.assertIn('**Grain**:',g);self.assertIn('_Avoid_:',g)
  a=(ROOT/'skills/internal/common/init-project-context/templates/AGENTS.md').read_text(encoding='utf-8')
  self.assertLess(a.count('\n'),60);self.assertIn('GLOSSARY.md',a);self.assertIn('docs/adr/',a)
 def test_skill_requires_declared(self):
  e=read_json(ROOT/'skills/catalog.json')['init-project-context'];self.assertEqual(sorted(e['requires']),['domain-modeling','writing-for-agents'])
 def test_kit_writes_only_under_gemini_and_kit_dirs(self):
  self.run_kit('data-developer');written={p.relative_to(self.home).parts[0] for p in self.home.rglob('*') if p.is_file()};self.assertTrue(written<={'.gemini','.ai-toolkit','.codex'},written)
  outside=[p for p in self.home.rglob('*') if p.name in ('AGENTS.md','GLOSSARY.md') and '.gemini/skills' not in p.as_posix() and '.gemini/config/plugins/ai-kit' not in p.as_posix() and '.codex/skills' not in p.as_posix() and p.relative_to(self.home).as_posix()!='.codex/AGENTS.md'];self.assertEqual(outside,[])
if __name__=='__main__':unittest.main()
