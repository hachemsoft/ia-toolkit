import re, unittest
from installer.core import ROOT
class PackagingTests(unittest.TestCase):
 """pyproject.toml: aligned version, pinned runtime dependencies, all content read by the installer shipped in the package."""
 def setUp(self):
  self.text=(ROOT/'pyproject.toml').read_text(encoding='utf-8')
 def test_version_matches_VERSION(self):
  self.assertEqual(re.search(r'^version = "([^"]+)"',self.text,re.M).group(1),(ROOT/'VERSION').read_text(encoding='utf-8').strip())
 def test_runtime_dependencies_pinned_within_their_ranges_and_python39(self):
  # 0.34: the interface uses rich and questionary; every pin in packaging/runtime.txt is a pure-Python wheel supporting 3.11 (2.0.0 raised the minimum from 3.9, D4).
  self.assertIn('requires-python = ">=3.11"',self.text)
  declared=re.search(r'^dependencies = \[(.*)\]$',self.text,re.M).group(1)
  self.assertIn('"rich>=',declared);self.assertIn('"questionary>=',declared)
  pins=dict(line.split('==') for line in (ROOT/'packaging/runtime.txt').read_text(encoding='utf-8').splitlines() if '==' in line and not line.startswith('#'))
  for name in ('rich','questionary','prompt_toolkit','markdown-it-py','pygments','mdurl','wcwidth'):self.assertIn(name,pins)
  self.assertEqual(int(pins['rich'].split('.')[0]) in range(13,16),True);self.assertTrue(pins['questionary'].startswith('2.'))
 def test_console_command(self):
  self.assertIn('ai-kit = "ai_kit.cli:main"',self.text)
 def test_the_package_holds_the_engine_and_never_the_content(self):
  # 2.2: what the engine reads from ROOT is packaged; the content (read from content_root()) travels as the Core bundle.
  code=''.join(f.read_text(encoding='utf-8') for f in (ROOT/'installer').rglob('*.py'))
  read=set(re.findall(r"ROOT ?/ ?'([A-Za-z][\w.-]*)",code))-{'.git','versions.lock.json','tests','docs'}
  packaged=set(re.findall(r'^"([\w.-]+)" = "ai_kit/kit/',self.text,re.M))
  self.assertTrue(read<=packaged,read-packaged);self.assertIn('VERSION',packaged)
  self.assertFalse(packaged&{'skills','agents','commands','practices','profiles','organization.toml','aikit.toml'})
  for d in packaged:self.assertTrue((ROOT/d).exists(),d)
if __name__=='__main__':unittest.main()
