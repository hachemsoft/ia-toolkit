import contextlib, io, json, tempfile, unittest
from pathlib import Path
from installer.cli import apply, doctor, selected_commands
from installer.core import load_commands, KitError, read_json, ROOT
class CommandTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst'):
  with contextlib.redirect_stdout(io.StringIO()):apply(role,self.home)
 def overrides(self,v):
  p=self.home/'.ai-toolkit/overrides.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v),encoding='utf-8')
 def cmd(self,name):return self.home/'.gemini/commands'/(name+'.toml')
 def test_manifest_consistent(self):
  catalog=read_json(ROOT/'skills/catalog.json');names=set()
  for c in load_commands():
   self.assertIn(c['category'],('workflow','tool'));self.assertNotIn(c['name'],names);names.add(c['name'])
   for s in c['skills']:self.assertIn(s,catalog,c['name']);self.assertNotIn('replaced_by',catalog[s])
   self.assertIn('{{args}}',c['prompt'],c['name']);self.assertTrue(c['description']);self.assertLess(len(c['prompt']),4000,c['name'])
   if c['category']=='workflow':self.assertIn('stage',c)
  for c in load_commands():
   for s in c['skills']:self.assertIn(c['skills'][0],catalog)
  builtin={'plan','init','help','memory','skills','commands','agents','mcp','clear','compress','chat','tools','settings','stats','quit','auth','about','bug','copy','directory','docs','editor','extensions','hooks','ide','model','permissions','policies','privacy','restore','resume','rewind','setup-github','shells','terminal-setup','theme','upgrade','vim'}
  self.assertFalse(names&builtin,names&builtin)
 def test_catalog_categories_and_tiers(self):
  catalog=read_json(ROOT/'skills/catalog.json')
  core=set()
  for k,v in catalog.items():
   if 'replaced_by' in v:continue
   self.assertIn(v['category'],('workflow','tool','domain','reference','setup'),k);self.assertIn(v['tier'],('core','optional','profile'),k)
   if v['tier']=='core':core.add(k)
  for pid in ('data-analyst','data-developer'):
   skills=set(read_json(ROOT/'profiles'/(pid+'.json'))['skills']);(self.assertTrue(core<=skills,pid) if pid=='data-developer' else None);self.assertFalse({k for k in skills if catalog[k]['tier']=='optional' and catalog[k]['category']=='reference'}-{'codebase-design'})
 def test_commands_installed_per_profile(self):
  self.run_kit();self.assertTrue(self.cmd('intent').exists());self.assertTrue(self.cmd('learn').exists());self.assertFalse(self.cmd('ask').exists());self.assertFalse(self.cmd('review').exists());self.assertFalse(self.cmd('spec').exists());self.assertFalse(self.cmd('design').exists());self.assertFalse(self.cmd('triage').exists())
  self.assertEqual(sorted(p.stem for p in (self.home/'.gemini/commands').glob('*.toml')),['build','diagnose','friction','guide','intent','learn','ship','test'])
  self.assertIn('.gemini/commands/intent.toml',read_json(self.home/'.ai-toolkit/state.json')['files'])
  self.run_kit('data-developer');self.assertTrue(self.cmd('design').exists());self.assertTrue(self.cmd('triage').exists());self.assertTrue(self.cmd('review').exists());self.assertFalse(self.cmd('ask').exists())
 def test_command_removed_when_skill_disabled(self):
  self.run_kit();self.assertTrue(self.cmd('learn').exists());self.overrides({'disabled_skills':['teach']});self.run_kit();self.assertFalse(self.cmd('learn').exists());self.assertTrue(self.cmd('intent').exists())
 def test_personal_command_conflict_blocks(self):
  p=self.cmd('intent');p.parent.mkdir(parents=True);p.write_text('prompt = "mine"\n')
  with self.assertRaises(KitError):self.run_kit()
  self.assertEqual(p.read_text(),'prompt = "mine"\n');self.assertFalse((self.home/'.ai-toolkit/state.json').exists())
 def test_modified_command_blocks(self):
  self.run_kit();self.cmd('ship').write_text('prompt = "edited"\n')
  with self.assertRaises(KitError):self.run_kit('data-developer')
 def test_selected_commands_requires_all_skills(self):
  m=[{'name':'x','category':'tool','skills':['a','b']},{'name':'y','category':'tool','skills':['a']},{'name':'z','category':'tool','skills':['a']}]
  self.assertEqual([c['name'] for c in selected_commands(['a'],m)],['y','z']);self.assertEqual([c['name'] for c in selected_commands(['a'],m,['z'])],['z'])
 def test_doctor_reports_commands_and_weight(self):
  self.run_kit();out=io.StringIO()
  with contextlib.redirect_stdout(out):code=doctor(self.home)
  text=out.getvalue();self.assertEqual(code,0,text);self.assertIn('[OK] Commande /intent : skills présents',text);self.assertIn('descriptions de skills injectées',text);self.assertIn('[OK] .gemini/commands/intent.toml',text)
  (self.home/'.gemini/skills/teach/SKILL.md').unlink();sp=self.home/'.ai-toolkit/state.json';st=read_json(sp);del st['files']['.gemini/skills/teach/SKILL.md'];sp.write_text(json.dumps(st))
  out=io.StringIO()
  with contextlib.redirect_stdout(out):doctor(self.home)
  self.assertIn('[À vérifier] Commande /learn : skills présents (manque teach)',out.getvalue())
 def test_doctor_detects_agents_alias_shadowing(self):
  self.run_kit();(self.home/'.agents/skills/tdd').mkdir(parents=True);(self.home/'.agents/skills/tdd/SKILL.md').write_text('---\nname: tdd\ndescription: mine\n---\n')
  out=io.StringIO()
  with contextlib.redirect_stdout(out):code=doctor(self.home)
  self.assertEqual(code,1);self.assertIn('[À vérifier] Aucun skill du kit masqué par une copie dans ~/.agents/skills (masqués : tdd)',out.getvalue())
 def test_templates_installed_with_init_skill(self):
  self.run_kit();base=self.home/'.gemini/skills/init-project-context/templates'
  for n in ('intent.md','spec.md','plan.md','REVIEW.md','AGENTS.md','GLOSSARY.md'):self.assertTrue((base/n).is_file(),n)
  self.assertIn('## Verifying your work',(base/'AGENTS.md').read_text(encoding='utf-8'));self.assertIn('## Passes',(base/'REVIEW.md').read_text(encoding='utf-8'))
if __name__=='__main__':unittest.main()
