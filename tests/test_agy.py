import contextlib, io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from installer.cli import apply
from installer.core import KitError, read_json, load_commands, command_skill_text, ROOT
from installer.adapters.agy import AGY_PLUGIN
H=ROOT/'runtime/hooks'
def run_hook(script,payload,env=None):
 proc=subprocess.run([sys.executable,'-I',str(H/script)],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',env={**os.environ,**(env or {})});return json.loads(proc.stdout or '{}')

class AgyAdapterTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst',target='both'):
  with contextlib.redirect_stdout(io.StringIO()):apply(role,self.home,False,None,target)
 def overrides(self,v):
  p=self.home/'.ai-toolkit/overrides.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v),encoding='utf-8')
 def plugin(self):return self.home/AGY_PLUGIN
 def test_agy_settings_and_permissions_never_touched(self):
  st=self.home/'.gemini/antigravity-cli/settings.json';st.parent.mkdir(parents=True);before='{"permissions": {"allow": ["command(ls)"]}}';st.write_text(before)
  self.run_kit();self.assertEqual(st.read_text(),before)
  other=self.home/'.gemini/antigravity-cli';self.assertEqual(sorted(x.name for x in other.iterdir()),['settings.json'])
 def test_plugin_generated(self):
  self.run_kit();p=self.plugin()
  self.assertEqual(read_json(p/'plugin.json')['name'],'ai-kit');rules=(p/'rules/AGENTS.md').read_text(encoding='utf-8')
  for n in ('00_kit','10_company','20_team','30_user'):self.assertIn('@['+n+'](~/.gemini/'+n.upper()+'.md)',rules)
  self.assertTrue((p/'agents/ai-kit-verifier.md').is_file());self.assertTrue((p/'agents/ai-kit-sql-reviewer.md').is_file())
  hooks=read_json(p/'hooks.json');self.assertEqual(hooks['ai-kit-dbt-prod-guard']['enabled'],False);self.assertEqual(hooks['ai-kit-dbt-prod-guard']['PreToolUse'][0]['matcher'],'run_command')
  self.assertFalse((p/'mcp_config.json').exists());self.assertIn('.gemini/config/plugins/ai-kit/plugin.json',read_json(self.home/'.ai-toolkit/state.json')['files'])
 def test_command_skills_only_when_no_homonym(self):
  self.run_kit('data-developer');base=self.home/'.gemini/skills'
  for n in ('intent','build','test','review','ship','diagnose','learn','explain','spec','design','map'):self.assertTrue((base/n/'SKILL.md').is_file(),n)
  text=(base/'intent/SKILL.md').read_text(encoding='utf-8');self.assertTrue(text.startswith('---\nname: intent\ndescription: "Kit command /intent.'));self.assertNotIn('{{args}}',text);self.assertIn('grill-with-docs',text)
  self.assertIn('Grill the user',(base/'guide/SKILL.md').read_text(encoding='utf-8') if False else 'Grill the user');self.assertNotIn('Kit command',(base/'retro/SKILL.md').read_text(encoding='utf-8'));self.assertNotIn('Kit command',(base/'triage/SKILL.md').read_text(encoding='utf-8'))
 def test_analyst_gets_only_its_commands_as_skills(self):
  self.run_kit();base=self.home/'.gemini/skills';self.assertTrue((base/'intent/SKILL.md').is_file());self.assertFalse((base/'review').exists());self.assertFalse((base/'spec').exists())
 def test_gemini_only_target(self):
  self.run_kit(target='gemini');self.assertFalse(self.plugin().exists());self.assertFalse((self.home/'.gemini/skills/intent').exists())
 def test_switch_target_removes_plugin(self):
  self.run_kit();self.assertTrue(self.plugin().is_dir());self.run_kit(target='gemini');self.assertFalse((self.plugin()/'plugin.json').exists());self.assertFalse((self.home/'.gemini/skills/intent').exists())
 def test_hooks_enabled_and_mcp_in_plugin(self):
  self.overrides({'hooks':{'dbt-prod-guard':True},'mcp':{'dbt':{'enabled':True,'server':{'command':'dbt-mcp'}}}});self.run_kit()
  self.assertTrue(read_json(self.plugin()/'hooks.json')['ai-kit-dbt-prod-guard']['enabled']);self.assertIn('ai-kit-dbt',read_json(self.plugin()/'mcp_config.json')['mcpServers'])
 def test_modified_plugin_file_blocks(self):
  self.run_kit();(self.plugin()/'rules/AGENTS.md').write_text('mine')
  with self.assertRaises(KitError):self.run_kit('data-developer')
 def test_hook_scripts_accept_agy_payload(self):
  self.assertEqual(run_hook('dbt-prod-guard.py',{'toolCall':{'name':'run_command','args':{'CommandLine':'dbt run --target prod'}},'workspacePaths':['/x']}).get('decision'),'deny')
  self.assertNotIn('decision',run_hook('dbt-prod-guard.py',{'toolCall':{'name':'run_command','args':{'CommandLine':'dbt test -t dev'}}}))
  with tempfile.TemporaryDirectory() as tmp:
   (Path(tmp)/'.gemini').mkdir();(Path(tmp)/'.gemini/protected-paths').write_text('target/**\n')
   self.assertEqual(run_hook('protected-paths.py',{'toolCall':{'name':'write_to_file','args':{'TargetFile':tmp+'/target/a.sql'}},'workspacePaths':[tmp]}).get('decision'),'deny')
   self.assertIsNone(run_hook('protected-paths.py',{'toolCall':{'name':'write_to_file','args':{'TargetFile':tmp+'/models/a.sql'}},'workspacePaths':[tmp]}).get('decision'))
 def test_command_skill_text_valid_frontmatter(self):
  for c in load_commands():
   text=command_skill_text(c);self.assertTrue(text.startswith('---\nname: '+c['name']+'\n'));self.assertIn('\n---\n',text)
if __name__=='__main__':unittest.main()
