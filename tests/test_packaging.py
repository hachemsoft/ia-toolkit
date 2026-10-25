import re, unittest
from installer.core import ROOT
class PackagingTests(unittest.TestCase):
 """pyproject.toml : version alignée, aucune dépendance, tout le contenu lu par l'installeur embarqué dans le paquet."""
 def setUp(self):
  self.text=(ROOT/'pyproject.toml').read_text(encoding='utf-8')
 def test_version_matches_VERSION(self):
  self.assertEqual(re.search(r'^version = "([^"]+)"',self.text,re.M).group(1),(ROOT/'VERSION').read_text().strip())
 def test_no_runtime_dependency_and_python39(self):
  self.assertIn('dependencies = []',self.text);self.assertIn('requires-python = ">=3.9"',self.text)
 def test_console_command(self):
  self.assertIn('ai-kit = "ai_kit.cli:main"',self.text)
 def test_every_content_dir_read_by_installer_is_packaged(self):
  code=(ROOT/'installer/cli.py').read_text(encoding='utf-8')
  read=set(re.findall(r"ROOT/'([a-z]+)",code))|{'commands'}
  packaged=set(re.findall(r'^"([a-zA-Z]+)" = "ai_kit/kit/',self.text,re.M))
  self.assertTrue(read<=packaged,read-packaged);self.assertIn('VERSION',packaged)
  for d in packaged:self.assertTrue((ROOT/d).exists(),d)
if __name__=='__main__':unittest.main()
