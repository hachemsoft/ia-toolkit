import contextlib, io, json, tempfile, unittest
from pathlib import Path
from installer.resolve import skill_catalog
from installer.core import KitError, read_json, START, ROOT
from unittest import mock
from personal import write_personal  # noqa: E402
from presets import apply_as  # noqa: E402
class InstallationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='kit space é ');self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst',dry=False):
  with contextlib.redirect_stdout(io.StringIO()):apply_as(role,self.home,dry)
 def path(self,p):return self.home/p
 def write(self,p,text):
  f=self.path(p);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text,encoding='utf-8');return f
 def overrides(self,v):write_personal(self.home,v)
 def core_servers(self,servers):
  # The Core's MCP servers (mcp/servers.toml), turned on by the person in aikit.toml.
  patcher=mock.patch('installer.plan.core_settings',return_value={'defaults':{'mcp':{n:{'server':s} for n,s in servers.items()}}});patcher.start();self.addCleanup(patcher.stop)
 def test_idempotence(self):
  self.run_kit();before={str(p):p.read_bytes() for p in self.home.rglob('*') if p.is_file()};self.run_kit();self.assertEqual(before,{str(p):p.read_bytes() for p in self.home.rglob('*') if p.is_file()})
 def test_existing_settings_and_context(self):
  self.write('.gemini/settings.json','{"theme":"custom","skills":{"enabled":false}}');p=self.write('.gemini/GEMINI.md','My instructions\n');self.run_kit();self.assertEqual(p.read_text(encoding='utf-8'),'My instructions\n');self.assertNotIn(START,p.read_text(encoding='utf-8'));u=self.path('.gemini/USER.md');self.assertTrue(u.exists());u.write_text('English',encoding='utf-8');self.run_kit();self.assertEqual(u.read_text(encoding='utf-8'),'English');self.assertFalse(read_json(self.path('.gemini/settings.json'))['skills']['enabled'])
 def test_switch(self):
  # the resources of a role are personal lines; taking python-js-change off the person's list removes it.
  self.run_kit('data-developer');note=self.write('.gemini/skills/python-js-change/notes.txt','personal');self.overrides({});self.run_kit();self.assertTrue(note.exists());self.assertFalse((note.parent/'SKILL.md').exists());self.assertTrue(self.path('.gemini/skills/sql-review/SKILL.md').exists())
 def test_modified_skill_blocks(self):
  self.run_kit();self.write('.gemini/skills/sql-review/SKILL.md','personal')
  with self.assertRaises(KitError):self.run_kit('data-developer')
 def test_existing_skill_kept_and_the_kits_renamed(self):
  # 0.36: one of the person's skills with a kit skill's name is kept; the kit's is installed with the prefix.
  self.write('.gemini/skills/sql-review/SKILL.md','third-party')
  self.run_kit()
  self.assertEqual(self.path('.gemini/skills/sql-review/SKILL.md').read_text(encoding='utf-8'),'third-party')
  self.assertIn('name: ai-kit-sql-review',self.path('.gemini/skills/ai-kit-sql-review/SKILL.md').read_text(encoding='utf-8'))
 def test_dry_run(self):
  self.run_kit(dry=True);self.assertEqual(list(self.home.iterdir()),[])
 def test_invalid_json(self):
  self.write('.gemini/settings.json','{broken')
  with self.assertRaises(KitError):self.run_kit()
  self.assertFalse(self.path('.ai-kit').exists())
 def test_mcp_add_remove(self):
  self.core_servers({'dbt':{'command':'dbt-mcp'}});self.overrides({'mcp':{'dbt':True}});self.run_kit();self.assertIn('ai-kit-dbt',read_json(self.path('.gemini/settings.json'))['mcpServers']);self.overrides({});self.run_kit();self.assertEqual(read_json(self.path('.gemini/settings.json'))['mcpServers'],{})
 def test_external_mcp_preserved(self):
  self.write('.gemini/settings.json','{"mcpServers":{"existing":{"command":"x"}}}');self.run_kit();self.assertIn('existing',read_json(self.path('.gemini/settings.json'))['mcpServers'])
 def test_mcp_conflict(self):
  self.core_servers({'dbt':{'command':'dbt-mcp'}});self.overrides({'mcp':{'dbt':True}});self.run_kit();p=self.path('.gemini/settings.json');v=read_json(p);v['mcpServers']['ai-kit-dbt']['command']='custom';p.write_text(json.dumps(v),encoding='utf-8')
  with self.assertRaises(KitError):self.run_kit()
 def test_backup(self):
  self.write('.gemini/settings.json','{}');self.run_kit();backups=list(self.path('.ai-kit/backups').glob('*/.gemini/settings.json'));self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_text(encoding='utf-8'),'{}')
 def test_unknown_skill(self):
  self.overrides({'extra_skills':['unknown']})
  with self.assertRaises(KitError):self.run_kit()
 def test_mcp_trust(self):
  self.core_servers({'dbt':{'command':'x','trust':True}});self.overrides({'mcp':{'dbt':True}})
  with self.assertRaises(KitError):self.run_kit()
 def test_skill_frontmatter(self):
  for name,e in skill_catalog(ROOT).items():
   if 'replaced_by' in e:continue
   text=(ROOT/e['path']/'SKILL.md').read_text(encoding='utf-8');self.assertTrue(text.startswith('---\nname: '+name+'\ndescription: '),name);self.assertIn('\n---\n',text);self.assertLess(len(text.encode('utf-8')),20000,name)
 @unittest.skipIf(__import__('os').name=='nt','Symlinks not guaranteed on Windows')
 def test_symlink_refused(self):
  self.path('.gemini').symlink_to(self.home/'outside',target_is_directory=True)
  with self.assertRaises(KitError):self.run_kit()
if __name__=='__main__':unittest.main()
