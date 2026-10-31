import contextlib, io, json, tempfile, unittest
from pathlib import Path
from installer.cli import apply
from installer.core import KitError
class ExtraCommandsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def overrides(self,v):
  p=self.home/'.ai-kit/overrides.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v),encoding='utf-8')
 def run_kit(self,role='data-analyst',target='gemini'):
  with contextlib.redirect_stdout(io.StringIO()):apply(role,self.home,False,None,target)
 def test_extra_command_installs_command_and_its_skills(self):
  self.overrides({'extra_commands':['spec','explain']});self.run_kit()
  for c in ('spec','explain','intent'):self.assertTrue((self.home/'.gemini/commands'/(c+'.toml')).exists(),c)
  for s in ('to-spec','zoom-out','wait-what'):self.assertTrue((self.home/'.gemini/skills'/s/'SKILL.md').exists(),s)
  self.assertIn('/spec',(self.home/'.gemini/00_KIT.md').read_text(encoding='utf-8'))
 def test_disabled_command_removed_for_developer(self):
  self.overrides({'disabled_commands':['retro']});self.run_kit('data-developer')
  self.assertFalse((self.home/'.gemini/commands/retro.toml').exists());self.assertTrue((self.home/'.gemini/commands/review.toml').exists())
 def test_unknown_command_refused(self):
  self.overrides({'extra_commands':['nope']})
  with self.assertRaises(KitError):self.run_kit()
 def test_removing_extra_command_cleans_up(self):
  self.overrides({'extra_commands':['spec']});self.run_kit();self.overrides({});self.run_kit()
  self.assertFalse((self.home/'.gemini/commands/spec.toml').exists());self.assertFalse((self.home/'.gemini/skills/to-spec').exists())
 def test_prune_keeps_structural_dirs(self):
  self.run_kit('data-analyst','both');self.run_kit('data-analyst','gemini')
  self.assertTrue((self.home/'.gemini/config').is_dir());self.assertFalse((self.home/'.gemini/config/plugins/ai-kit').exists())
 def test_no_env_file_written_for_authentication(self):
  # 0.36: authentication belongs to the CLI; a "vertex" key writes nothing.
  self.overrides({'vertex':{'project':'demo-project-01'}});self.run_kit();self.assertFalse((self.home/'.gemini/.env').exists())
if __name__=='__main__':unittest.main()
