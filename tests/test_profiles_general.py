import contextlib, io, json, tempfile, unittest
from pathlib import Path
from installer.cli import apply, profile_ids
from installer.core import read_json
from installer.adapters.gemini import merge_context_filenames
class GeneralProfileTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role):
  with contextlib.redirect_stdout(io.StringIO()):apply(role,self.home,False,None,'gemini')
 def test_profiles_listed(self):
  self.assertEqual(profile_ids(),['data-analyst','data-developer','general'])
 def test_general_has_workflow_without_domain_playbooks(self):
  self.run_kit('general')
  for c in ('intent','spec','build','test','review','ship','diagnose','learn','explain','retro','guide'):self.assertTrue((self.home/'.gemini/commands'/(c+'.toml')).exists(),c)
  for s in ('sql-review','dbt-model-change','kpi-definition','python-js-change'):self.assertFalse((self.home/'.gemini/skills'/s).exists(),s)
  kit=(self.home/'.gemini/00_KIT.md').read_text(encoding='utf-8');self.assertIn('Aucun playbook',kit);self.assertTrue((self.home/'.gemini/20_TEAM.md').exists())
 def test_renamed_layer_is_retired_from_settings(self):
  # Une installation antérieure gérait 20_DATA.md : après update, le fichier et son nom disparaissent, 20_TEAM.md les remplace.
  self.run_kit('data-analyst');state=read_json(self.home/'.ai-toolkit/state.json')
  old=self.home/'.gemini/20_DATA.md';old.write_text('ancien',encoding='utf-8');import hashlib;state['files']['.gemini/20_DATA.md']=hashlib.sha256(b'ancien').hexdigest()
  (self.home/'.ai-toolkit/state.json').write_text(json.dumps(state),encoding='utf-8')
  settings=read_json(self.home/'.gemini/settings.json');settings['context']['fileName'].insert(2,'20_DATA.md');(self.home/'.gemini/settings.json').write_text(json.dumps(settings),encoding='utf-8')
  self.run_kit('data-analyst');names=read_json(self.home/'.gemini/settings.json')['context']['fileName']
  self.assertFalse(old.exists());self.assertNotIn('20_DATA.md',names);self.assertIn('20_TEAM.md',names)
 def test_merge_retired(self):
  s={'context':{'fileName':['00_KIT.md','20_DATA.md','MINE.md']}};merge_context_filenames(s,['00_KIT.md','20_TEAM.md'],['20_DATA.md','00_KIT.md'])
  self.assertEqual(s['context']['fileName'],['00_KIT.md','20_TEAM.md','30_USER.md','GEMINI.md','AGENTS.md','MINE.md'])
if __name__=='__main__':unittest.main()
