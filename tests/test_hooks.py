import contextlib, io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from installer.cli import apply, doctor
from installer.core import KitError, read_json, ROOT
H=ROOT/'runtime/hooks'
def run_hook(script,payload,env=None):
 proc=subprocess.run([sys.executable,'-I',str(H/script)],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',env={**os.environ,**(env or {})});return json.loads(proc.stdout or '{}')

class HookScriptTests(unittest.TestCase):
 def test_dbt_prod_denied(self):
  for cmd in ('dbt run --target prod','dbt build -t prd','cd x && dbt test --target=production','DBT_TARGET=prod dbt run',"dbt run --target 'prod'",'dbt run --target="prod"','dbt run -tprod','./dbt run -t prod','/usr/local/bin/dbt run --target prod','DBT run -t prod','dbt.exe run -t prod'):
   self.assertEqual(run_hook('dbt-prod-guard.py',{'tool_name':'run_shell_command','tool_input':{'command':cmd}}).get('decision'),'deny',cmd)
 def test_dbt_dev_allowed_and_non_dbt_ignored(self):
  for cmd in ('dbt test -t dev','dbt run','ls prod','python prod.py --target prod','dbt run -t prod-like','dbt run --target production_dev','mydbt run -t prod'):
   self.assertNotIn('decision',run_hook('dbt-prod-guard.py',{'tool_name':'run_shell_command','tool_input':{'command':cmd}}),cmd)
  self.assertEqual(run_hook('dbt-prod-guard.py',{'tool_name':'write_file','tool_input':{'file_path':'x'}}),{})
 def test_dbt_prod_allowed_with_env_and_custom_targets(self):
  self.assertNotIn('decision',run_hook('dbt-prod-guard.py',{'tool_name':'run_shell_command','tool_input':{'command':'dbt run -t prod'}},{'AI_KIT_ALLOW_PROD':'1'}))
  self.assertEqual(run_hook('dbt-prod-guard.py',{'tool_name':'run_shell_command','tool_input':{'command':'dbt run -t live'}},{'AI_KIT_PROD_TARGETS':'live,prod'}).get('decision'),'deny')
 def test_dbt_default_target_from_profiles(self):
  with tempfile.TemporaryDirectory() as tmp:
   (Path(tmp)/'profiles.yml').write_text('mon_projet:\n  target: prod\n  outputs:\n    prod: {type: bigquery}\n    dev: {type: bigquery}\n',encoding='utf-8')
   run=lambda cmd,env=None:run_hook('dbt-prod-guard.py',{'tool_name':'run_shell_command','cwd':tmp,'tool_input':{'command':cmd}},{'DBT_PROFILES_DIR':tmp,'HOME':tmp,**(env or {})})
   self.assertEqual(run('dbt run').get('decision'),'deny');self.assertIn('profiles.yml',run('dbt run')['reason'])
   self.assertNotIn('decision',run('dbt run -t dev'));self.assertNotIn('decision',run('dbt run',{'AI_KIT_ALLOW_PROD':'1'}))
   (Path(tmp)/'profiles.yml').write_text('mon_projet:\n  target: dev\n',encoding='utf-8');self.assertNotIn('decision',run('dbt run'))
 def test_protected_paths(self):
  with tempfile.TemporaryDirectory() as tmp:
   (Path(tmp)/'.gemini').mkdir();(Path(tmp)/'.gemini/protected-paths').write_text('# protégé\ntarget/**\ndbt_project.yml\n*.lock\n',encoding='utf-8')
   deny=lambda p,tool='write_file':run_hook('protected-paths.py',{'tool_name':tool,'cwd':tmp,'tool_input':{'file_path':p}}).get('decision')
   self.assertEqual(deny(tmp+'/target/run.sql'),'deny');self.assertEqual(deny('dbt_project.yml','replace'),'deny');self.assertEqual(deny('poetry.lock'),'deny')
   self.assertIsNone(deny('models/a.sql'));self.assertIsNone(deny('target/x','run_shell_command'))
   self.assertIsNone(deny('targets/x.sql'));self.assertIsNone(deny('target_new.sql'));self.assertEqual(deny('TARGET/x.sql'),'deny')
   self.assertIsNone(run_hook('protected-paths.py',{'tool_name':'write_file','cwd':tmp,'tool_input':{'file_path':'D:\\ailleurs\\x.sql'}}).get('decision'))
  with tempfile.TemporaryDirectory() as tmp:
   self.assertIsNone(run_hook('protected-paths.py',{'tool_name':'write_file','cwd':tmp,'tool_input':{'file_path':'target/x'}}).get('decision'))
 def test_protected_paths_from_repo_root_when_launched_in_subfolder(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'.git').mkdir();(root/'.gemini').mkdir();(root/'.gemini/protected-paths').write_text('target/**\nfinance/clotures/**\n',encoding='utf-8')
   (root/'finance/.gemini').mkdir(parents=True);(root/'finance/.gemini/protected-paths').write_text('seeds/**\n',encoding='utf-8')
   sub=str(root/'finance')
   deny=lambda p:run_hook('protected-paths.py',{'tool_name':'write_file','cwd':sub,'tool_input':{'file_path':p}}).get('decision')
   self.assertEqual(deny(str(root/'target/x.sql')),'deny');self.assertEqual(deny('clotures/2026.sql'),'deny');self.assertEqual(deny('seeds/a.csv'),'deny')
   self.assertIsNone(deny('models/marge.sql'));self.assertIsNone(deny(str(root/'marketing/seeds/a.csv')))
 def test_protected_paths_neutral_file_and_legacy_file_both_read(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'.git').mkdir();(root/'.ai-kit').mkdir();(root/'.ai-kit/protected-paths').write_text('target/**\n',encoding='utf-8')
   (root/'.gemini').mkdir();(root/'.gemini/protected-paths').write_text('*.lock\n',encoding='utf-8')
   deny=lambda p:run_hook('protected-paths.py',{'tool_name':'write_file','cwd':tmp,'tool_input':{'file_path':p}}).get('decision')
   self.assertEqual(deny('target/a.sql'),'deny');self.assertEqual(deny('poetry.lock'),'deny');self.assertIsNone(deny('models/a.sql'))
 def test_old_hook_location_migrated(self):
  import hashlib
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);(home/'.ai-toolkit').mkdir();(home/'.ai-toolkit/overrides.json').write_text(json.dumps({'hooks':{'dbt-prod-guard':True}}),encoding='utf-8')
   with contextlib.redirect_stdout(io.StringIO()):apply('data-analyst',home,False,None,'gemini')
   # Simuler une installation 0.16 : script à l'ancien emplacement, suivi par l'état.
   old=home/'.gemini/hooks/ai-kit/dbt-prod-guard.py';old.parent.mkdir(parents=True);old.write_bytes((H/'dbt-prod-guard.py').read_bytes())
   state=read_json(home/'.ai-toolkit/state.json');state['files']['.gemini/hooks/ai-kit/dbt-prod-guard.py']=hashlib.sha256(old.read_bytes()).hexdigest()
   (home/'.ai-toolkit/state.json').write_text(json.dumps(state),encoding='utf-8')
   with contextlib.redirect_stdout(io.StringIO()):apply('data-analyst',home,False,None,'gemini')
   self.assertFalse(old.exists());self.assertFalse((home/'.gemini/hooks/ai-kit').exists());self.assertTrue((home/'.ai-toolkit/hooks/dbt-prod-guard.py').is_file())
   command=read_json(home/'.gemini/settings.json')['hooks']['BeforeTool'][0]['hooks'][0]['command'];self.assertIn('.ai-toolkit',command)
 def test_malformed_input_never_breaks(self):
  for s in ('dbt-prod-guard.py','protected-paths.py'):
   proc=subprocess.run([sys.executable,'-I',str(H/s)],input='not json',capture_output=True,text=True);self.assertEqual(proc.returncode,0);self.assertEqual(proc.stdout.strip(),'{}')

class HookInstallTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst'):
  with contextlib.redirect_stdout(io.StringIO()):apply(role,self.home)
 def overrides(self,v):
  p=self.home/'.ai-toolkit/overrides.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v),encoding='utf-8')
 def settings(self):return read_json(self.home/'.gemini/settings.json')
 def test_disabled_by_default(self):
  self.run_kit();self.assertNotIn('hooks',self.settings());self.assertFalse((self.home/'.gemini/hooks').exists());self.assertEqual(read_json(self.home/'.ai-toolkit/state.json')['hooks'],{})
 def test_enable_then_disable(self):
  self.overrides({'hooks':{'dbt-prod-guard':True,'protected-paths':True}});self.run_kit()
  groups=self.settings()['hooks']['BeforeTool'];self.assertEqual(len(groups),2);names={g['hooks'][0]['name'] for g in groups};self.assertEqual(names,{'ai-kit-dbt-prod-guard','ai-kit-protected-paths'})
  self.assertEqual(groups[0]['matcher'],'run_shell_command');self.assertTrue((self.home/'.ai-toolkit/hooks/dbt-prod-guard.py').is_file());self.assertIn(str(self.home),groups[0]['hooks'][0]['command'])
  self.overrides({'hooks':{'dbt-prod-guard':True,'protected-paths':False}});self.run_kit()
  groups=self.settings()['hooks']['BeforeTool'];self.assertEqual(len(groups),1);self.assertFalse((self.home/'.ai-toolkit/hooks/protected-paths.py').exists())
  self.overrides({'hooks':{}});self.run_kit();self.assertNotIn('hooks',self.settings());self.assertFalse((self.home/'.gemini/hooks/ai-kit').exists())
 def test_user_hooks_preserved(self):
  s=self.home/'.gemini/settings.json';s.parent.mkdir(parents=True);s.write_text(json.dumps({'hooks':{'BeforeTool':[{'matcher':'*','hooks':[{'name':'mine','type':'command','command':'echo'}]}],'SessionStart':[{'hooks':[{'type':'command','command':'x'}]}]}}))
  self.overrides({'hooks':{'dbt-prod-guard':True}});self.run_kit();h=self.settings()['hooks'];self.assertEqual(h['BeforeTool'][0]['hooks'][0]['name'],'mine');self.assertEqual(len(h['BeforeTool']),2);self.assertIn('SessionStart',h)
  self.overrides({'hooks':{}});self.run_kit();h=self.settings()['hooks'];self.assertEqual(len(h['BeforeTool']),1);self.assertIn('SessionStart',h)
 def test_modified_kit_hook_blocks(self):
  self.overrides({'hooks':{'dbt-prod-guard':True}});self.run_kit();s=self.home/'.gemini/settings.json';v=read_json(s);v['hooks']['BeforeTool'][0]['matcher']='.*';s.write_text(json.dumps(v))
  with self.assertRaises(KitError):self.run_kit()
 def test_unknown_or_invalid(self):
  self.overrides({'hooks':{'nope':True}})
  with self.assertRaises(KitError):self.run_kit()
  self.overrides({'hooks':{'dbt-prod-guard':'yes'}})
  with self.assertRaises(KitError):self.run_kit()
 def test_doctor_reports(self):
  self.overrides({'hooks':{'dbt-prod-guard':True}});self.run_kit();out=io.StringIO()
  with contextlib.redirect_stdout(out):doctor(self.home)
  self.assertIn('[OK] Garde-fou actif : dbt-prod-guard',out.getvalue())
  self.overrides({'hooks':{}});self.run_kit();out=io.StringIO()
  with contextlib.redirect_stdout(out):doctor(self.home)
  self.assertIn('Aucun garde-fou activé',out.getvalue())
 def test_verifier_agent_has_shell_others_do_not(self):
  self.run_kit('data-developer');base=self.home/'.gemini/agents'
  v=(base/'ai-kit-verifier.md').read_text(encoding='utf-8');self.assertIn('run_shell_command',v.split('---')[1]);self.assertIn('max_turns: 15',v)
  for n in ('ai-kit-repo-investigator.md','ai-kit-code-reviewer.md'):self.assertNotIn('run_shell_command',(base/n).read_text(encoding='utf-8').split('---')[1])
if __name__=='__main__':unittest.main()
