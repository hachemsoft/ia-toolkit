import contextlib, io, json, tempfile, unittest
from pathlib import Path
from installer.cli import apply, doctor, resolve_skills, command_lines, playbook_lines
from installer.core import KitError, read_json, ROOT
FAKE={'a':{'path':'x','requires':['b']},'b':{'path':'x'},'c':{'path':'x','stage':'ship'},'old':{'replaced_by':['a','c']}}
class SkillCatalogTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst'):
  out=io.StringIO()
  with contextlib.redirect_stdout(out):apply(role,self.home)
  return out.getvalue()
 def overrides(self,v):
  p=self.home/'.ai-kit/overrides.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v),encoding='utf-8')
 def test_requires_resolved_transitively(self):
  self.assertEqual(resolve_skills({'skills':['a']},{},FAKE,log=lambda m:None),['a','b'])
 def test_disabled_dependency_refused(self):
  with self.assertRaises(KitError):resolve_skills({'skills':['a']},{'disabled_skills':['b']},FAKE,log=lambda m:None)
 def test_disabled_root_skipped(self):
  self.assertEqual(resolve_skills({'skills':['a','c']},{'disabled_skills':['a']},FAKE,log=lambda m:None),['c'])
 def test_replaced_substituted_and_logged(self):
  logs=[];self.assertEqual(resolve_skills({'skills':['old']},{},FAKE,log=logs.append),['a','b','c']);self.assertIn('Skill replaced: old → a, c',logs)
 def test_unknown_refused(self):
  with self.assertRaises(KitError):resolve_skills({'skills':['zz']},{},FAKE,log=lambda m:None)
 def test_command_and_playbook_lines(self):
  cmds=[{'name':'intent','category':'workflow','description':'Plan'},{'name':'learn','category':'tool','description':'Learn'}]
  self.assertEqual(command_lines(cmds),'### Steps\n- /intent — Plan\n### Tools\n- /learn — Learn');self.assertEqual(command_lines([]),'- No command installed.')
  cat={'a':{'category':'domain','description':'A'},'b':{'category':'tool','description':'B'}};self.assertEqual(playbook_lines(['a','b'],cat),'- a : A')
 def test_real_catalog_consistent(self):
  catalog=read_json(ROOT/'skills/catalog.json')
  for name,e in catalog.items():
   if 'replaced_by' in e:
    for r in e['replaced_by']:self.assertIn(r,catalog);self.assertNotIn('replaced_by',catalog[r])
    continue
   self.assertTrue((ROOT/e['path']/'SKILL.md').is_file(),name)
   for r in e.get('requires',[]):self.assertIn(r,catalog)
   if e.get('origin')=='upstream':self.assertTrue((ROOT/e['license']).is_file(),name)
  for pid in ('data-analyst','data-developer'):
   for s in read_json(ROOT/'profiles'/(pid+'.json'))['skills']:self.assertIn(s,catalog);self.assertNotIn('replaced_by',catalog[s],s)
 def test_legacy_override_still_installs(self):
  self.overrides({'extra_skills':['clarify-request'],'disabled_skills':['debug-systematically']});out=self.run_kit()
  self.assertIn('Skill replaced: clarify-request → grilling',out);self.assertTrue((self.home/'.gemini/skills/grilling/SKILL.md').exists());self.assertFalse((self.home/'.gemini/skills/clarify-request').exists())
 def test_legacy_installed_skill_removed_on_update(self):
  self.run_kit();old=self.home/'.gemini/skills/clarify-request/SKILL.md';old.parent.mkdir();old.write_text('old',encoding='utf-8')
  sp=self.home/'.ai-kit/state.json';st=read_json(sp);st['files']['.gemini/skills/clarify-request/SKILL.md']=__import__('installer.cli',fromlist=['digest']).digest(b'old');sp.write_text(json.dumps(st),encoding='utf-8')
  self.run_kit();self.assertFalse(old.exists());self.assertFalse(old.parent.exists());self.assertTrue((self.home/'.gemini/skills').is_dir())
 def test_kit_layer_lists_commands_and_playbooks(self):
  self.run_kit();text=(self.home/'.gemini/00_KIT.md').read_text(encoding='utf-8')
  for s in ('- /intent — ','- /ship — ','- /learn — ','- sql-review : '):self.assertIn(s,text)
  self.assertNotIn('{commands}',text);self.assertNotIn('{playbooks}',text);self.assertNotIn('/design',text);self.assertNotIn('/review',text);self.assertNotIn('grilling',text)
  self.run_kit('data-developer');text=(self.home/'.gemini/00_KIT.md').read_text(encoding='utf-8');self.assertIn('- /design — ',text);self.assertIn('- /triage — ',text);self.assertIn('- /review — ',text);self.assertNotIn('/ask',text);self.assertIn('- python-js-change : ',text)
 def test_upstream_files_copied_without_codex_metadata(self):
  self.run_kit('data-developer');base=self.home/'.gemini/skills'
  self.assertTrue((base/'tdd/mocking.md').exists());self.assertTrue((base/'domain-modeling/ADR-FORMAT.md').exists());self.assertFalse((base/'tdd/agents').exists())
  self.assertIn('MR body',(base/'mr/SKILL.md').read_text(encoding='utf-8'))
 def test_doctor_lists_needs_agents_when_disabled(self):
  self.overrides({'extra_skills':['research']});self.run_kit('data-developer');s=self.home/'.gemini/settings.json';v=read_json(s);v['experimental']={'enableAgents':False};s.write_text(json.dumps(v),encoding='utf-8')
  out=io.StringIO()
  with contextlib.redirect_stdout(out):doctor(self.home)
  self.assertIn('degraded without them: research',out.getvalue())
if __name__=='__main__':unittest.main()
