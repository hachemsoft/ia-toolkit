import contextlib, io, json, tempfile, unittest
from pathlib import Path
from installer.cli import apply, doctor
from installer.core import KitError, read_json, digest, ROOT
from v1_profiles import apply_as  # noqa: E402
class ContextLayerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst',user=None):
  with contextlib.redirect_stdout(io.StringIO()):apply_as(role,self.home,False,user)
 def path(self,p):return self.home/p
 def write(self,p,text):
  f=self.path(p);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text,encoding='utf-8');return f
 def test_fresh_install_layers(self):
  self.run_kit()
  for name in ('00_KIT.md','10_COMPANY.md','20_TEAM.md','USER.md'):
   self.assertTrue(self.path('.ai-kit/context/'+name).is_file(),name);self.assertTrue(self.path('.gemini/'+name).is_file(),name)  # the file, Gemini's copy
  self.assertNotIn('Profile:',self.path('.gemini/00_KIT.md').read_text(encoding='utf-8'))  # 2.2: no profiles in the context
  self.assertIn('Team practices',self.path('.gemini/20_TEAM.md').read_text(encoding='utf-8'))
  state=read_json(self.path('.ai-kit/state.json'));self.assertEqual(state['schema_version'],2);self.assertNotIn('context_hash',state)
  self.assertIn('.gemini/00_KIT.md',state['files']);self.assertIn('.gemini/USER.md',state['files']);self.assertNotIn('.ai-kit/context/USER.md',state['files'])
  self.assertFalse(self.path('.gemini/GEMINI.md').exists())
 def test_user_layer_never_rewritten(self):
  self.run_kit();u=self.path('.gemini/USER.md');u.write_text('Personal',encoding='utf-8');self.run_kit('data-developer');self.assertEqual(u.read_text(encoding='utf-8'),'Personal')
  doctor_out=io.StringIO()
  with contextlib.redirect_stdout(doctor_out):doctor(self.home)
  self.assertEqual([line for line in doctor_out.getvalue().splitlines() if line.startswith('[Check]') and 'PATH' not in line and 'approved in Codex' not in line],[],doctor_out.getvalue());self.assertIn('[OK] Personal context present',doctor_out.getvalue())
 def test_modified_kit_layer_restored(self):
  # Rule layers edited by hand no longer block update: they are restored (see RuleLayerRestoreTests).
  self.run_kit();official=self.path('.gemini/10_COMPANY.md').read_text(encoding='utf-8');self.write('.gemini/10_COMPANY.md','modified')
  self.run_kit('data-developer')
  self.assertEqual(self.path('.gemini/10_COMPANY.md').read_text(encoding='utf-8'),official)
  self.assertEqual(read_json(self.path('.ai-kit/state.json'))['profile'],'core')  # 2.2: no profiles
 def test_existing_unmanaged_layer_blocks(self):
  self.write('.gemini/00_KIT.md','third-party')
  with self.assertRaises(KitError):self.run_kit()
  self.assertFalse(self.path('.ai-kit/state.json').exists())
 def test_obsolete_managed_layer_removed(self):
  self.run_kit();old=self.write('.gemini/15_OLD.md','old layer');state_path=self.path('.ai-kit/state.json');state=read_json(state_path)
  state['files']['.gemini/15_OLD.md']=digest(old.read_bytes());state_path.write_text(json.dumps(state),encoding='utf-8')
  self.run_kit();self.assertFalse(old.exists())
 def test_state_never_deletes_user_layer(self):
  self.run_kit();state_path=self.path('.ai-kit/state.json');state=read_json(state_path)
  state['files']['.ai-kit/context/USER.md']=digest(self.path('.ai-kit/context/USER.md').read_bytes());state_path.write_text(json.dumps(state),encoding='utf-8')
  with self.assertRaises(KitError):self.run_kit()
  self.assertTrue(self.path('.ai-kit/context/USER.md').exists())
 def test_doctor_detects_missing_layer(self):
  self.run_kit();self.path('.gemini/10_COMPANY.md').unlink()
  out=io.StringIO()
  with contextlib.redirect_stdout(out):code=doctor(self.home)
  self.assertEqual(code,1);self.assertIn('[Check] .gemini/10_COMPANY.md',out.getvalue())
 def test_doctor_ok_after_install(self):
  self.run_kit();out=io.StringIO()
  with contextlib.redirect_stdout(out):doctor(self.home)
  text=out.getvalue();self.assertIn('[OK] context.fileName contains',text);self.assertNotIn('[Check] .gemini/',text)
 def test_kit_template_has_priority_rules(self):
  text=(ROOT/'templates/kit-context.md').read_text(encoding='utf-8');self.assertIn('USER.md',text);self.assertIn('AGENTS.md',text);self.assertIn('CLAUDE.md',text);self.assertIn('extra_commands',text);self.assertIn('{frictions}',text);self.assertLess(len(text),3800)
if __name__=='__main__':unittest.main()


class RuleLayerRestoreTests(unittest.TestCase):
    """The rule layers (00, 10, 20) edited by hand are restored by update, the edited copy kept; anything else still stops update."""
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def run_kit(self):
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            apply('general', self.home, False, {'email': 'a@example.org', 'source': 'test'}, 'gemini')
        return out.getvalue()

    def test_hand_edited_rule_layer_restored_with_backup(self):
        self.run_kit()
        kit_file = self.home/'.gemini/00_KIT.md'
        official = kit_file.read_text(encoding='utf-8')
        kit_file.write_text(official.replace('never production without an explicit instruction', 'production is fine'), encoding='utf-8')
        out = self.run_kit()
        self.assertEqual(kit_file.read_text(encoding='utf-8'), official)
        self.assertIn('00_KIT.md was modified by hand: restored', out)
        copies = list((self.home/'.ai-kit/backups').glob('*/.gemini/00_KIT.md'))
        self.assertTrue(any('production is fine' in c.read_text(encoding='utf-8') for c in copies))

    def test_personal_context_never_restored(self):
        self.run_kit()
        user_file = self.home/'.gemini/USER.md'
        user_file.write_text('# Mine\n', encoding='utf-8')
        self.run_kit()
        self.assertEqual(user_file.read_text(encoding='utf-8'), '# Mine\n')

    def test_other_managed_file_edited_still_stops_update(self):
        self.run_kit()
        skill = next((self.home/'.gemini/skills').glob('*/SKILL.md'))
        skill.write_text('edited\n', encoding='utf-8')
        with self.assertRaises(KitError):
            self.run_kit()
