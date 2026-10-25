import contextlib, io, json, tempfile, unittest
from pathlib import Path
from installer.cli import apply, doctor
from installer.core import KitError, read_json, digest, START, END, ROOT
class ContextLayerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst',user=None):
  with contextlib.redirect_stdout(io.StringIO()):apply(role,self.home,False,user)
 def path(self,p):return self.home/p
 def write(self,p,text):
  f=self.path(p);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text,encoding='utf-8');return f
 def test_fresh_install_layers(self):
  self.run_kit()
  for name in ('00_KIT.md','10_COMPANY.md','20_TEAM.md','30_USER.md'):self.assertTrue(self.path('.gemini/'+name).is_file(),name)
  self.assertIn('Profil : data-analyst',self.path('.gemini/00_KIT.md').read_text())
  self.assertIn('Pratiques d’équipe',self.path('.gemini/20_TEAM.md').read_text())
  state=read_json(self.path('.ai-toolkit/state.json'));self.assertEqual(state['schema_version'],2);self.assertNotIn('context_hash',state)
  self.assertIn('.gemini/00_KIT.md',state['files']);self.assertNotIn('.gemini/30_USER.md',state['files'])
  self.assertFalse(self.path('.gemini/GEMINI.md').exists());self.assertFalse(self.path('.ai-toolkit/preferences.md').exists())
 def test_user_layer_never_rewritten(self):
  self.run_kit();u=self.path('.gemini/30_USER.md');u.write_text('Personnel');self.run_kit('data-developer');self.assertEqual(u.read_text(),'Personnel')
  doctor_out=io.StringIO()
  with contextlib.redirect_stdout(doctor_out):code=doctor(self.home)
  self.assertEqual(code,0,doctor_out.getvalue());self.assertIn('[OK] Contexte personnel présent',doctor_out.getvalue())
 def test_modified_kit_layer_blocks(self):
  self.run_kit();self.write('.gemini/10_COMPANY.md','modifié')
  with self.assertRaises(KitError):self.run_kit('data-developer')
  self.assertEqual(read_json(self.path('.ai-toolkit/state.json'))['profile'],'data-analyst')
 def test_existing_unmanaged_layer_blocks(self):
  self.write('.gemini/00_KIT.md','tiers')
  with self.assertRaises(KitError):self.run_kit()
  self.assertFalse(self.path('.ai-toolkit/state.json').exists())
 def legacy_state(self,block_text):
  block=START+'\n'+block_text+'\n'+END
  self.write('.gemini/GEMINI.md','Mes notes\n\n'+block+'\n')
  self.write('.ai-toolkit/preferences.md','# Mes préférences\n- Anglais\n')
  self.write('.ai-toolkit/state.json',json.dumps({'schema_version':1,'version':'0.0.4','profile':'data-analyst','files':{},'context_hash':digest(block.encode()),'mcp':{}}))
 def test_migration_from_legacy_block(self):
  self.legacy_state('ancien bloc');self.run_kit()
  self.assertEqual(self.path('.gemini/GEMINI.md').read_text(),'Mes notes\n')
  self.assertEqual(self.path('.gemini/30_USER.md').read_text(),'# Mes préférences\n- Anglais\n')
  self.assertFalse(self.path('.ai-toolkit/preferences.md').exists());self.assertTrue(self.path('.ai-toolkit/preferences.md.migrated').exists())
  self.assertEqual(read_json(self.path('.ai-toolkit/state.json'))['schema_version'],2)
  self.run_kit();self.assertEqual(self.path('.gemini/GEMINI.md').read_text(),'Mes notes\n')
 def test_migration_removes_empty_gemini_md(self):
  block=START+'\nbloc\n'+END;self.write('.gemini/GEMINI.md',block+'\n')
  self.write('.ai-toolkit/state.json',json.dumps({'schema_version':1,'version':'0.0.4','profile':'data-analyst','files':{},'context_hash':digest(block.encode()),'mcp':{}}))
  self.run_kit();self.assertFalse(self.path('.gemini/GEMINI.md').exists())
 def test_migration_refused_when_block_modified(self):
  self.legacy_state('ancien bloc');g=self.path('.gemini/GEMINI.md');g.write_text(g.read_text().replace('ancien bloc','bloc édité'))
  with self.assertRaises(KitError):self.run_kit()
  self.assertFalse(self.path('.gemini/00_KIT.md').exists());self.assertTrue(self.path('.ai-toolkit/preferences.md').exists())
 def test_obsolete_managed_layer_removed(self):
  self.run_kit();old=self.write('.gemini/15_OLD.md','ancienne couche');state_path=self.path('.ai-toolkit/state.json');state=read_json(state_path)
  state['files']['.gemini/15_OLD.md']=digest(old.read_bytes());state_path.write_text(json.dumps(state))
  self.run_kit();self.assertFalse(old.exists())
 def test_state_never_deletes_user_layer(self):
  self.run_kit();state_path=self.path('.ai-toolkit/state.json');state=read_json(state_path)
  state['files']['.gemini/30_USER.md']=digest(self.path('.gemini/30_USER.md').read_bytes());state_path.write_text(json.dumps(state))
  with self.assertRaises(KitError):self.run_kit()
  self.assertTrue(self.path('.gemini/30_USER.md').exists())
 def test_doctor_detects_missing_layer_and_legacy_block(self):
  self.run_kit();self.path('.gemini/10_COMPANY.md').unlink();self.write('.gemini/GEMINI.md',START+'\nx\n'+END+'\n')
  out=io.StringIO()
  with contextlib.redirect_stdout(out):code=doctor(self.home)
  self.assertEqual(code,1);self.assertIn('[À vérifier] .gemini/10_COMPANY.md',out.getvalue());self.assertIn('[À vérifier] Aucun bloc hérité',out.getvalue())
 def test_doctor_ok_after_install(self):
  self.run_kit();out=io.StringIO()
  with contextlib.redirect_stdout(out):doctor(self.home)
  text=out.getvalue();self.assertIn('[OK] context.fileName contient',text);self.assertNotIn('[À vérifier] .gemini/',text)
 def test_kit_template_has_priority_rules(self):
  text=(ROOT/'templates/kit-context.md').read_text(encoding='utf-8');self.assertIn('30_USER.md',text);self.assertIn('AGENTS.md',text);self.assertIn('CLAUDE.md',text);self.assertIn('extra_commands',text);self.assertIn('{frictions}',text);self.assertLess(len(text),3700)
if __name__=='__main__':unittest.main()
