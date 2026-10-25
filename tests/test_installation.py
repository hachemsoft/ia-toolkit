import contextlib, io, json, tempfile, unittest
from pathlib import Path
from installer.cli import apply
from installer.core import KitError, read_json, START, ROOT
class InstallationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='kit espace é ');self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst',dry=False):
  with contextlib.redirect_stdout(io.StringIO()):apply(role,self.home,dry)
 def path(self,p):return self.home/p
 def write(self,p,text):
  f=self.path(p);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text,encoding='utf-8');return f
 def overrides(self,v):self.write('.ai-toolkit/overrides.json',json.dumps(v))
 def test_idempotence(self):
  self.run_kit();before={str(p):p.read_bytes() for p in self.home.rglob('*') if p.is_file()};self.run_kit();self.assertEqual(before,{str(p):p.read_bytes() for p in self.home.rglob('*') if p.is_file()})
 def test_existing_settings_and_context(self):
  self.write('.gemini/settings.json','{"theme":"custom","skills":{"enabled":false}}');p=self.write('.gemini/GEMINI.md','Mes instructions\n');self.run_kit();self.assertEqual(p.read_text(),'Mes instructions\n');self.assertNotIn(START,p.read_text());u=self.path('.gemini/30_USER.md');self.assertTrue(u.exists());u.write_text('Anglais');self.run_kit();self.assertEqual(u.read_text(),'Anglais');self.assertFalse(read_json(self.path('.gemini/settings.json'))['skills']['enabled'])
 def test_switch(self):
  self.run_kit('data-developer');note=self.write('.gemini/skills/python-js-change/notes.txt','personnel');self.run_kit();self.assertTrue(note.exists());self.assertFalse((note.parent/'SKILL.md').exists());self.assertTrue(self.path('.gemini/skills/sql-review/SKILL.md').exists())
 def test_modified_skill_blocks(self):
  self.run_kit();self.write('.gemini/skills/sql-review/SKILL.md','personnel')
  with self.assertRaises(KitError):self.run_kit('data-developer')
  self.assertEqual(read_json(self.path('.ai-toolkit/state.json'))['profile'],'data-analyst')
 def test_existing_skill_blocks(self):
  self.write('.gemini/skills/sql-review/SKILL.md','tiers')
  with self.assertRaises(KitError):self.run_kit()
  self.assertFalse(self.path('.gemini/settings.json').exists())
 def test_dry_run(self):
  self.run_kit(dry=True);self.assertEqual(list(self.home.iterdir()),[])
 def test_invalid_json(self):
  self.write('.gemini/settings.json','{broken')
  with self.assertRaises(KitError):self.run_kit()
  self.assertFalse(self.path('.ai-toolkit').exists())
 def test_mcp_add_remove(self):
  self.overrides({'mcp':{'dbt':{'enabled':True,'server':{'command':'dbt-mcp'}}}});self.run_kit();self.assertIn('ai-kit-dbt',read_json(self.path('.gemini/settings.json'))['mcpServers']);self.overrides({'mcp':{}});self.run_kit();self.assertEqual(read_json(self.path('.gemini/settings.json'))['mcpServers'],{})
 def test_external_mcp_preserved(self):
  self.write('.gemini/settings.json','{"mcpServers":{"existing":{"command":"x"}}}');self.run_kit();self.assertIn('existing',read_json(self.path('.gemini/settings.json'))['mcpServers'])
 def test_mcp_conflict(self):
  self.overrides({'mcp':{'dbt':{'enabled':True,'server':{'command':'dbt-mcp'}}}});self.run_kit();p=self.path('.gemini/settings.json');v=read_json(p);v['mcpServers']['ai-kit-dbt']['command']='custom';p.write_text(json.dumps(v))
  with self.assertRaises(KitError):self.run_kit()
 def test_malformed_context(self):
  self.write('.gemini/GEMINI.md',START)
  with self.assertRaises(KitError):self.run_kit()
 def test_backup(self):
  self.write('.gemini/settings.json','{}');self.run_kit();backups=list(self.path('.ai-toolkit/backups').glob('*/.gemini/settings.json'));self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_text(),'{}')
 def test_unknown_skill(self):
  self.overrides({'extra_skills':['unknown']})
  with self.assertRaises(KitError):self.run_kit()
 def test_mcp_trust(self):
  self.overrides({'mcp':{'dbt':{'enabled':True,'server':{'command':'x','trust':True}}}})
  with self.assertRaises(KitError):self.run_kit()
 def test_skill_frontmatter(self):
  for name,e in read_json(ROOT/'skills/catalog.json').items():
   if 'replaced_by' in e:continue
   text=(ROOT/e['path']/'SKILL.md').read_text(encoding='utf-8');self.assertTrue(text.startswith('---\nname: '+name+'\ndescription: '),name);self.assertIn('\n---\n',text);self.assertLess(len(text.encode('utf-8')),20000,name)
 @unittest.skipIf(__import__('os').name=='nt','Symlinks non garantis sous Windows')
 def test_symlink_refused(self):
  self.path('.gemini').symlink_to(self.home/'outside',target_is_directory=True)
  with self.assertRaises(KitError):self.run_kit()
if __name__=='__main__':unittest.main()
