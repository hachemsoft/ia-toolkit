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
 def test_hook_output_is_utf8_whatever_the_console(self):
  # Windows console (cp1252): the refusal must arrive as UTF-8, which is what the CLIs read.
  for script,payload in (('dbt-prod-guard.py',{'toolCall':{'name':'run_command','args':{'CommandLine':'dbt run --target prod'}}}),('dbt-prod-guard.py',{'hook_event_name':'PreToolUse','tool_name':'shell','tool_input':{'command':['bash','-lc','dbt run -t prod']}})):
   # Without -I, so that PYTHONIOENCODING simulates the Windows console.
   proc=subprocess.run([sys.executable,str(H/script)],input=json.dumps(payload).encode('utf-8'),capture_output=True,env={**os.environ,'PYTHONIOENCODING':'cp1252'})
   text=proc.stdout.decode('utf-8');self.assertIn('Blocked by the kit',text,proc.stderr)
 def test_dbt_guard_closes_audit_bypasses(self):
  # Contournements relevés par l'audit de sécurité : sh -c, cible connue seulement à l'exécution.
  for cmd in ('sh -c "dbt run --target prod"',"bash -lc 'dbt build -t prd'",'T=prod; dbt run --target $T','dbt run --target ${TARGET:-prod}','dbt run --target pr""od',"dbt run --target 'p'rod",'dbt run --target $(echo prod)','dbt run --target `echo prod`','DBT_TARGET=$X dbt run'):
   self.assertEqual(run_hook('dbt-prod-guard.py',{'tool_name':'run_shell_command','tool_input':{'command':cmd}}).get('decision'),'deny',cmd)
  for cmd in ('dbt run --threads 4 --target dev','dbt run --target "dev"','dbt run --select tag:$TAG --target dev','python prod.py --target $X','echo $HOME && dbt test -t dev'):
   self.assertNotIn('decision',run_hook('dbt-prod-guard.py',{'tool_name':'run_shell_command','tool_input':{'command':cmd}}),cmd)
 def test_dbt_allow_ignored_when_set_in_env_file(self):
  with tempfile.TemporaryDirectory() as tmp:
   payload={'tool_name':'run_shell_command','tool_input':{'command':'dbt run --target prod'},'cwd':tmp}
   self.assertNotIn('decision',run_hook('dbt-prod-guard.py',payload,{'AI_KIT_ALLOW_PROD':'1'}))
   Path(tmp,'.env').write_text('AI_KIT_ALLOW_PROD=1\n',encoding='utf-8')
   self.assertEqual(run_hook('dbt-prod-guard.py',payload,{'AI_KIT_ALLOW_PROD':'1'}).get('decision'),'deny')
 def test_protected_paths_symlink_and_config(self):
  # Audit : un lien vers un dossier protégé, et la configuration du kit et des CLI, protégée même sans motif du repo.
  with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as fake_home:
   t=Path(tmp);(t/'.git').mkdir();(t/'.ai-kit').mkdir();(t/'.ai-kit/protected-paths').write_text('target/**\n',encoding='utf-8');(t/'target').mkdir()
   env={'HOME':fake_home,'USERPROFILE':fake_home}
   def decide(path):
    return run_hook('protected-paths.py',{'tool_name':'write_file','tool_input':{'file_path':path},'cwd':tmp},env).get('decision')
   try:(t/'link').symlink_to(t/'target',target_is_directory=True)
   except (OSError,NotImplementedError):pass
   if (t/'link').exists():self.assertEqual(decide('link/a.sql'),'deny')
   self.assertEqual(decide('.ai-kit/protected-paths'),'deny')
   for rel in ('.gemini/settings.json','.gemini/.env','.ai-kit/overrides.json','.ai-kit/hooks/dbt-prod-guard.py','.codex/config.toml','.gemini/config/plugins/ai-kit/hooks.json',
               '.gemini/00_KIT.md','.gemini/10_COMPANY.md','.gemini/20_TEAM.md','.gemini/20_DATA_PLATFORM.md','.ai-kit/context/00_KIT.md'):
    self.assertEqual(decide(str(Path(fake_home)/rel)),'deny',rel)
   for rel in ('.ai-kit/learn/topic/progress.md','.gemini/30_USER.md','notes.md'):
    self.assertIsNone(decide(str(Path(fake_home)/rel)),rel)
   self.assertIsNone(decide('models/a.sql'))
 def test_shell_writes_to_configuration_blocked(self):
  # The agent cannot overwrite overrides.json or the CLI settings through simple shell commands; reading stays allowed.
  for cmd in ('echo "{}" > ~/.ai-kit/overrides.json',"sed -i 's/true/false/' ~/.ai-kit/overrides.json",'tee ~/.gemini/settings.json < x','rm ~/.ai-kit/hooks/dbt-prod-guard.py','cp new.toml ~/.codex/config.toml','Set-Content $HOME\\.ai-kit\\overrides.json "{}"','mv x .ai-kit/protected-paths'):
   self.assertEqual(run_hook('protected-paths.py',{'tool_name':'run_shell_command','tool_input':{'command':cmd}}).get('decision'),'deny',cmd)
  for cmd in ('cat ~/.ai-kit/overrides.json','grep hooks ~/.gemini/settings.json','echo hi > notes.txt','rm -rf build/','sed -n 1,5p ~/.gemini/settings.json'):
   self.assertNotIn('decision',run_hook('protected-paths.py',{'tool_name':'run_shell_command','tool_input':{'command':cmd}}),cmd)
  # Judged per simple command: a write and a protected path in two different commands, or a protected path quoted in the
  # data of a heredoc given to another language, are not a write to the configuration.
  for cmd in ('cat ~/.ai-kit/overrides.json; sed -i s/a/b/ notes.md','grep x ~/.gemini/settings.json && rm -rf build/',
              "python3 - <<'EOF'\ndoc = 'sed -i s/a/b/ ~/.ai-kit/overrides.json, or echo x > .ai-kit/protected-paths'\nEOF",
              'cat <<EOF > notes.md\nnever run: rm ~/.ai-kit/hooks/dbt-prod-guard.py\nEOF'):
   self.assertNotIn('decision',run_hook('protected-paths.py',{'tool_name':'Bash','tool_input':{'command':cmd}}),cmd)
  # Still blocked: a write in the same simple command, through a pipe, a continued line, or a heredoc a shell runs.
  for cmd in ('echo x | tee ~/.ai-kit/overrides.json','cd ~ && sed -i s/a/b/ .ai-kit/overrides.json',"sed -i 's/a/b/' \\\n  ~/.ai-kit/overrides.json",
              'echo x &> ~/.ai-kit/overrides.json','bash <<EOF\nsed -i s/a/b/ ~/.ai-kit/overrides.json\nEOF',
              'sudo sh <<EOF\nrm ~/.ai-kit/hooks/dbt-prod-guard.py\nEOF','cat > ~/.ai-kit/overrides.json <<EOF\n{}\nEOF'):
   self.assertEqual(run_hook('protected-paths.py',{'tool_name':'Bash','tool_input':{'command':cmd}}).get('decision'),'deny',cmd)
  r=run_hook('protected-paths.py',{'hook_event_name':'PreToolUse','tool_name':'shell','tool_input':{'command':['bash','-lc','echo x > ~/.ai-kit/overrides.json']}})
  self.assertEqual(r['hookSpecificOutput']['permissionDecision'],'deny')
 def test_dbt_dev_allowed_and_non_dbt_ignored(self):
  for cmd in ('dbt test -t dev','dbt run','ls prod','python prod.py --target prod','dbt run -t prod-like','dbt run --target production_dev','mydbt run -t prod'):
   self.assertNotIn('decision',run_hook('dbt-prod-guard.py',{'tool_name':'run_shell_command','tool_input':{'command':cmd}}),cmd)
  self.assertEqual(run_hook('dbt-prod-guard.py',{'tool_name':'write_file','tool_input':{'file_path':'x'}}),{})
 def test_dbt_prod_allowed_with_env_and_custom_targets(self):
  self.assertNotIn('decision',run_hook('dbt-prod-guard.py',{'tool_name':'run_shell_command','tool_input':{'command':'dbt run -t prod'}},{'AI_KIT_ALLOW_PROD':'1'}))
  self.assertEqual(run_hook('dbt-prod-guard.py',{'tool_name':'run_shell_command','tool_input':{'command':'dbt run -t live'}},{'AI_KIT_PROD_TARGETS':'live,prod'}).get('decision'),'deny')
 def test_dbt_default_target_from_profiles(self):
  with tempfile.TemporaryDirectory() as tmp:
   (Path(tmp)/'profiles.yml').write_text('my_project:\n  target: prod\n  outputs:\n    prod: {type: bigquery}\n    dev: {type: bigquery}\n',encoding='utf-8')
   run=lambda cmd,env=None:run_hook('dbt-prod-guard.py',{'tool_name':'run_shell_command','cwd':tmp,'tool_input':{'command':cmd}},{'DBT_PROFILES_DIR':tmp,'HOME':tmp,**(env or {})})
   self.assertEqual(run('dbt run').get('decision'),'deny');self.assertIn('profiles.yml',run('dbt run')['reason'])
   self.assertNotIn('decision',run('dbt run -t dev'));self.assertNotIn('decision',run('dbt run',{'AI_KIT_ALLOW_PROD':'1'}))
   (Path(tmp)/'profiles.yml').write_text('my_project:\n  target: dev\n',encoding='utf-8');self.assertNotIn('decision',run('dbt run'))
 def test_protected_paths(self):
  with tempfile.TemporaryDirectory() as tmp:
   (Path(tmp)/'.gemini').mkdir();(Path(tmp)/'.gemini/protected-paths').write_text('# protected\ntarget/**\ndbt_project.yml\n*.lock\n',encoding='utf-8')
   deny=lambda p,tool='write_file':run_hook('protected-paths.py',{'tool_name':tool,'cwd':tmp,'tool_input':{'file_path':p}}).get('decision')
   self.assertEqual(deny(tmp+'/target/run.sql'),'deny');self.assertEqual(deny('dbt_project.yml','replace'),'deny');self.assertEqual(deny('poetry.lock'),'deny')
   self.assertIsNone(deny('models/a.sql'));self.assertIsNone(deny('target/x','run_shell_command'))
   self.assertIsNone(deny('targets/x.sql'));self.assertIsNone(deny('target_new.sql'));self.assertEqual(deny('TARGET/x.sql'),'deny')
   self.assertIsNone(run_hook('protected-paths.py',{'tool_name':'write_file','cwd':tmp,'tool_input':{'file_path':'D:\\elsewhere\\x.sql'}}).get('decision'))
  with tempfile.TemporaryDirectory() as tmp:
   self.assertIsNone(run_hook('protected-paths.py',{'tool_name':'write_file','cwd':tmp,'tool_input':{'file_path':'target/x'}}).get('decision'))
 def test_protected_paths_from_repo_root_when_launched_in_subfolder(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'.git').mkdir();(root/'.gemini').mkdir();(root/'.gemini/protected-paths').write_text('target/**\nfinance/closing/**\n',encoding='utf-8')
   (root/'finance/.gemini').mkdir(parents=True);(root/'finance/.gemini/protected-paths').write_text('seeds/**\n',encoding='utf-8')
   sub=str(root/'finance')
   deny=lambda p:run_hook('protected-paths.py',{'tool_name':'write_file','cwd':sub,'tool_input':{'file_path':p}}).get('decision')
   self.assertEqual(deny(str(root/'target/x.sql')),'deny');self.assertEqual(deny('closing/2026.sql'),'deny');self.assertEqual(deny('seeds/a.csv'),'deny')
   self.assertIsNone(deny('models/margin.sql'));self.assertIsNone(deny(str(root/'marketing/seeds/a.csv')))
 def test_protected_paths_neutral_file_and_legacy_file_both_read(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'.git').mkdir();(root/'.ai-kit').mkdir();(root/'.ai-kit/protected-paths').write_text('target/**\n',encoding='utf-8')
   (root/'.gemini').mkdir();(root/'.gemini/protected-paths').write_text('*.lock\n',encoding='utf-8')
   deny=lambda p:run_hook('protected-paths.py',{'tool_name':'write_file','cwd':tmp,'tool_input':{'file_path':p}}).get('decision')
   self.assertEqual(deny('target/a.sql'),'deny');self.assertEqual(deny('poetry.lock'),'deny');self.assertIsNone(deny('models/a.sql'))
 def test_old_hook_location_migrated(self):
  import hashlib
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);(home/'.ai-kit').mkdir();(home/'.ai-kit/overrides.json').write_text(json.dumps({'hooks':{'dbt-prod-guard':True}}),encoding='utf-8')
   with contextlib.redirect_stdout(io.StringIO()):apply('data-analyst',home,False,None,'gemini')
   # Simulate a 0.16 installation: script at the old location, tracked by the state.
   old=home/'.gemini/hooks/ai-kit/dbt-prod-guard.py';old.parent.mkdir(parents=True);old.write_bytes((H/'dbt-prod-guard.py').read_bytes())
   state=read_json(home/'.ai-kit/state.json');state['files']['.gemini/hooks/ai-kit/dbt-prod-guard.py']=hashlib.sha256(old.read_bytes()).hexdigest()
   (home/'.ai-kit/state.json').write_text(json.dumps(state),encoding='utf-8')
   with contextlib.redirect_stdout(io.StringIO()):apply('data-analyst',home,False,None,'gemini')
   self.assertFalse(old.exists());self.assertFalse((home/'.gemini/hooks/ai-kit').exists());self.assertTrue((home/'.ai-kit/hooks/dbt-prod-guard.py').is_file())
   command=read_json(home/'.gemini/settings.json')['hooks']['BeforeTool'][0]['hooks'][0]['command'];self.assertIn('.ai-kit',command)
 def test_malformed_input_never_breaks(self):
  for s in ('dbt-prod-guard.py','protected-paths.py'):
   proc=subprocess.run([sys.executable,'-I',str(H/s)],input='not json',capture_output=True,text=True);self.assertEqual(proc.returncode,0);self.assertEqual(proc.stdout.strip(),'{}')

class HookInstallTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst'):
  with contextlib.redirect_stdout(io.StringIO()):apply(role,self.home)
 def overrides(self,v):
  p=self.home/'.ai-kit/overrides.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v),encoding='utf-8')
 def settings(self):return read_json(self.home/'.gemini/settings.json')
 def doctor_text(self):
  out=io.StringIO()
  with contextlib.redirect_stdout(out):doctor(self.home)
  return out.getvalue()
 def test_doctor_proves_guardrails_block(self):
  # Audit : un garde-fou déclaré doit être prouvé, pas seulement présent.
  self.overrides({'hooks':{'dbt-prod-guard':True,'protected-paths':True}});self.run_kit()
  text=self.doctor_text()
  self.assertIn('[OK] Guardrail dbt-prod-guard: synthetic test, the script blocks a known case when run',text);self.assertIn('[OK] Guardrail protected-paths: synthetic test, the script blocks a known case when run',text)
 def test_doctor_flags_missing_interpreter(self):
  self.overrides({'hooks':{'dbt-prod-guard':True}});self.run_kit()
  sp=self.home/'.ai-kit/state.json';st=read_json(sp)
  hook=st['hooks']['dbt-prod-guard']['group']['hooks'][0];hook['command']=hook['command'].replace(sys.executable,str(self.home/'gone'/'python'))
  sp.write_text(json.dumps(st),encoding='utf-8')
  self.assertIn('[Check] Guardrail dbt-prod-guard: Python not found',self.doctor_text())
 def test_doctor_flags_unapproved_codex_guardrails(self):
  self.overrides({'hooks':{'dbt-prod-guard':True}})
  with contextlib.redirect_stdout(io.StringIO()):apply('data-analyst',self.home,False,None,'all')
  self.assertIn('[Check] Codex: kit guardrails approved in Codex (not yet',self.doctor_text())
  cfg=self.home/'.codex/config.toml'
  for i in range(2):cfg.write_text(cfg.read_text(encoding='utf-8')+'\n[hooks.state."'+str(cfg).replace('\\','/')+':pre_tool_use:'+str(i)+':0"]\ntrusted_hash = "sha256:00"\n',encoding='utf-8')  # dbt-prod-guard + protected-paths (on by default)
  # 0.34: approval records cannot be tied to the kit's guardrails (unknown hash, shared indexes): never reported as OK.
  text=self.doctor_text();self.assertNotIn('[OK] Codex: kit guardrails approved',text);self.assertIn('approval not verifiable automatically',text)
 def test_defaults_protect_configuration_only(self):
  # protected-paths is on by default (configuration of the kit and CLIs); dbt-prod-guard stays opt-in.
  self.run_kit();self.assertEqual(sorted(read_json(self.home/'.ai-kit/state.json')['hooks']),['protected-paths'])
  self.assertEqual([g['hooks'][0]['name'] for g in self.settings()['hooks']['BeforeTool']],['ai-kit-protected-paths'])
  self.overrides({'hooks':{'protected-paths':False}});self.run_kit();self.assertNotIn('hooks',self.settings());self.assertEqual(read_json(self.home/'.ai-kit/state.json')['hooks'],{})
 def test_enable_then_disable(self):
  self.overrides({'hooks':{'dbt-prod-guard':True,'protected-paths':True}});self.run_kit()
  groups=self.settings()['hooks']['BeforeTool'];self.assertEqual(len(groups),2);names={g['hooks'][0]['name'] for g in groups};self.assertEqual(names,{'ai-kit-dbt-prod-guard','ai-kit-protected-paths'})
  self.assertEqual({g['hooks'][0]['name']:g['matcher'] for g in groups}['ai-kit-dbt-prod-guard'],'run_shell_command');groups=[g for g in groups if g['hooks'][0]['name']=='ai-kit-dbt-prod-guard'];self.assertTrue((self.home/'.ai-kit/hooks/dbt-prod-guard.py').is_file());self.assertIn(str(self.home.resolve()),groups[0]['hooks'][0]['command'])  # Windows: the temporary folder has a short name (RUNNER~1)
  self.overrides({'hooks':{'dbt-prod-guard':True,'protected-paths':False}});self.run_kit()
  groups=self.settings()['hooks']['BeforeTool'];self.assertEqual(len(groups),1);self.assertFalse((self.home/'.ai-kit/hooks/protected-paths.py').exists())
  self.overrides({'hooks':{'protected-paths':False}});self.run_kit();self.assertNotIn('hooks',self.settings());self.assertFalse((self.home/'.gemini/hooks/ai-kit').exists())
 def test_user_hooks_preserved(self):
  s=self.home/'.gemini/settings.json';s.parent.mkdir(parents=True);s.write_text(json.dumps({'hooks':{'BeforeTool':[{'matcher':'*','hooks':[{'name':'mine','type':'command','command':'echo'}]}],'SessionStart':[{'hooks':[{'type':'command','command':'x'}]}]}}),encoding='utf-8')
  self.overrides({'hooks':{'dbt-prod-guard':True,'protected-paths':False}});self.run_kit();h=self.settings()['hooks'];self.assertEqual(h['BeforeTool'][0]['hooks'][0]['name'],'mine');self.assertEqual(len(h['BeforeTool']),2);self.assertIn('SessionStart',h)
  self.overrides({'hooks':{'protected-paths':False}});self.run_kit();h=self.settings()['hooks'];self.assertEqual(len(h['BeforeTool']),1);self.assertIn('SessionStart',h)
 def test_modified_kit_hook_blocks(self):
  self.overrides({'hooks':{'dbt-prod-guard':True}});self.run_kit();s=self.home/'.gemini/settings.json';v=read_json(s);v['hooks']['BeforeTool'][0]['matcher']='.*';s.write_text(json.dumps(v),encoding='utf-8')
  with self.assertRaises(KitError):self.run_kit()
 def test_unknown_or_invalid(self):
  self.overrides({'hooks':{'nope':True}})
  with self.assertRaises(KitError):self.run_kit()
  self.overrides({'hooks':{'dbt-prod-guard':'yes'}})
  with self.assertRaises(KitError):self.run_kit()
 def test_doctor_reports(self):
  self.overrides({'hooks':{'dbt-prod-guard':True}});self.run_kit();out=io.StringIO()
  with contextlib.redirect_stdout(out):doctor(self.home)
  self.assertIn('[OK] Guardrail configured in settings.json: dbt-prod-guard',out.getvalue())
  self.overrides({'hooks':{'protected-paths':False}});self.run_kit();out=io.StringIO()
  with contextlib.redirect_stdout(out):doctor(self.home)
  self.assertIn('No guardrail enabled',out.getvalue())
 def test_verifier_agent_has_shell_others_do_not(self):
  self.run_kit('data-developer');base=self.home/'.gemini/agents'
  v=(base/'ai-kit-verifier.md').read_text(encoding='utf-8');self.assertIn('run_shell_command',v.split('---')[1]);self.assertIn('max_turns: 15',v)
  for n in ('ai-kit-repo-investigator.md','ai-kit-code-reviewer.md'):self.assertNotIn('run_shell_command',(base/n).read_text(encoding='utf-8').split('---')[1])
if __name__=='__main__':unittest.main()
