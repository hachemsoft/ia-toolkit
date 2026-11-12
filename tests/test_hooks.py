import contextlib, io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from installer.cli import doctor
from installer.core import KitError, read_json, ROOT
from personal import write_personal  # noqa: E402
from presets import apply_as  # noqa: E402
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
   for rel in ('.gemini/settings.json','.gemini/.env','.ai-kit/aikit.toml','.ai-kit/hooks/dbt-prod-guard.py','.codex/config.toml','.gemini/config/plugins/ai-kit/hooks.json',
               '.gemini/00_KIT.md','.gemini/10_COMPANY.md','.gemini/20_TEAM.md','.gemini/20_DATA_PLATFORM.md','.ai-kit/context/00_KIT.md'):
    self.assertEqual(decide(str(Path(fake_home)/rel)),'deny',rel)
   for rel in ('.ai-kit/learn/topic/progress.md','.gemini/USER.md','notes.md'):
    self.assertIsNone(decide(str(Path(fake_home)/rel)),rel)
   self.assertIsNone(decide('models/a.sql'))
 def test_shell_writes_to_configuration_blocked(self):
  # The agent cannot overwrite aikit.toml or the CLI settings through simple shell commands; reading stays allowed.
  for cmd in ('echo "{}" > ~/.ai-kit/aikit.toml',"sed -i 's/true/false/' ~/.ai-kit/aikit.toml",'tee ~/.gemini/settings.json < x','rm ~/.ai-kit/hooks/dbt-prod-guard.py','cp new.toml ~/.codex/config.toml','Set-Content $HOME\\.ai-kit\\aikit.toml "{}"','mv x .ai-kit/protected-paths'):
   self.assertEqual(run_hook('protected-paths.py',{'tool_name':'run_shell_command','tool_input':{'command':cmd}}).get('decision'),'deny',cmd)
  for cmd in ('cat ~/.ai-kit/aikit.toml','grep hooks ~/.gemini/settings.json','echo hi > notes.txt','rm -rf build/','head -n 5 ~/.gemini/settings.json'):
   self.assertNotIn('decision',run_hook('protected-paths.py',{'tool_name':'run_shell_command','tool_input':{'command':cmd}}),cmd)
  # Judged per simple command: a write and a protected path in two different commands, or a protected path quoted in the
  # data of a heredoc given to another language, are not a write to the configuration.
  for cmd in ('cat ~/.ai-kit/aikit.toml; sed -i s/a/b/ notes.md','grep x ~/.gemini/settings.json && rm -rf build/',
              "python3 - <<'EOF'\ndoc = 'sed -i s/a/b/ ~/.ai-kit/aikit.toml, or echo x > .ai-kit/protected-paths'\nEOF",
              'cat <<EOF > notes.md\nnever run: rm ~/.ai-kit/hooks/dbt-prod-guard.py\nEOF'):
   self.assertNotIn('decision',run_hook('protected-paths.py',{'tool_name':'Bash','tool_input':{'command':cmd}}),cmd)
  # A word inside a path is not a command: install.json, a folder named rm-old, a file named tee.log.
  for cmd in ('cat ~/.ai-kit/runtime/install.json','ls ~/.ai-kit/bin/rm-old ~/.gemini/settings.json','head ~/.ai-kit/hooks/tee.log'):
   self.assertNotIn('decision',run_hook('protected-paths.py',{'tool_name':'Bash','tool_input':{'command':cmd}}),cmd)
  # Where the shell runs it, it is one: after sudo, xargs, find -exec, bash -c, a subshell; the path anywhere in the pipeline.
  for cmd in ('sudo rm ~/.ai-kit/hooks/dbt-prod-guard.py',"bash -c 'rm ~/.ai-kit/hooks/dbt-prod-guard.py'",'echo ~/.ai-kit/hooks/x.py | xargs rm',
              'find ~/.ai-kit/hooks -name "*.py" -exec rm {} +','(cd ~ && cp x .ai-kit/aikit.toml)','FORCE=1 /bin/rm -f ~/.ai-kit/state.json',
              'pwsh -Command "Remove-Item $HOME/.ai-kit/aikit.toml"',"sudo -n sed -i 's/a/b/' ~/.ai-kit/aikit.toml"):
   self.assertEqual(run_hook('protected-paths.py',{'tool_name':'Bash','tool_input':{'command':cmd}}).get('decision'),'deny',cmd)
  # Still blocked: a write in the same simple command, through a pipe, a continued line, or a heredoc a shell runs.
  for cmd in ('echo x | tee ~/.ai-kit/aikit.toml','cd ~ && sed -i s/a/b/ .ai-kit/aikit.toml',"sed -i 's/a/b/' \\\n  ~/.ai-kit/aikit.toml",
              'echo x &> ~/.ai-kit/aikit.toml','bash <<EOF\nsed -i s/a/b/ ~/.ai-kit/aikit.toml\nEOF',
              'sudo sh <<EOF\nrm ~/.ai-kit/hooks/dbt-prod-guard.py\nEOF','cat > ~/.ai-kit/aikit.toml <<EOF\n{}\nEOF'):
   self.assertEqual(run_hook('protected-paths.py',{'tool_name':'Bash','tool_input':{'command':cmd}}).get('decision'),'deny',cmd)
  r=run_hook('protected-paths.py',{'hook_event_name':'PreToolUse','tool_name':'shell','tool_input':{'command':['bash','-lc','echo x > ~/.ai-kit/aikit.toml']}})
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
   (Path(tmp)/'.ai-kit').mkdir();(Path(tmp)/'.ai-kit/protected-paths').write_text('# protected\ntarget/**\ndbt_project.yml\n*.lock\n',encoding='utf-8')
   deny=lambda p,tool='write_file':run_hook('protected-paths.py',{'tool_name':tool,'cwd':tmp,'tool_input':{'file_path':p}}).get('decision')
   self.assertEqual(deny(tmp+'/target/run.sql'),'deny');self.assertEqual(deny('dbt_project.yml','replace'),'deny');self.assertEqual(deny('poetry.lock'),'deny')
   self.assertIsNone(deny('models/a.sql'));self.assertIsNone(deny('target/x','run_shell_command'))
   self.assertIsNone(deny('targets/x.sql'));self.assertIsNone(deny('target_new.sql'));self.assertEqual(deny('TARGET/x.sql'),'deny')
   self.assertIsNone(run_hook('protected-paths.py',{'tool_name':'write_file','cwd':tmp,'tool_input':{'file_path':'D:\\elsewhere\\x.sql'}}).get('decision'))
  with tempfile.TemporaryDirectory() as tmp:
   self.assertIsNone(run_hook('protected-paths.py',{'tool_name':'write_file','cwd':tmp,'tool_input':{'file_path':'target/x'}}).get('decision'))
 def test_protected_paths_from_repo_root_when_launched_in_subfolder(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'.git').mkdir();(root/'.ai-kit').mkdir();(root/'.ai-kit/protected-paths').write_text('target/**\nfinance/closing/**\n',encoding='utf-8')
   (root/'finance/.ai-kit').mkdir(parents=True);(root/'finance/.ai-kit/protected-paths').write_text('seeds/**\n',encoding='utf-8')
   sub=str(root/'finance')
   deny=lambda p:run_hook('protected-paths.py',{'tool_name':'write_file','cwd':sub,'tool_input':{'file_path':p}}).get('decision')
   self.assertEqual(deny(str(root/'target/x.sql')),'deny');self.assertEqual(deny('closing/2026.sql'),'deny');self.assertEqual(deny('seeds/a.csv'),'deny')
   self.assertIsNone(deny('models/margin.sql'));self.assertIsNone(deny(str(root/'marketing/seeds/a.csv')))
 def test_hook_no_longer_written_is_removed(self):
  import hashlib
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);write_personal(home,{'hooks':{'dbt-prod-guard':True}})
   with contextlib.redirect_stdout(io.StringIO()):apply_as('data-analyst',home,False,None,'gemini')
   # A hook script the state tracks at a place this installation no longer writes.
   old=home/'.gemini/hooks/ai-kit/dbt-prod-guard.py';old.parent.mkdir(parents=True);old.write_bytes((H/'dbt-prod-guard.py').read_bytes())
   state=read_json(home/'.ai-kit/state.json');state['files']['.gemini/hooks/ai-kit/dbt-prod-guard.py']=hashlib.sha256(old.read_bytes()).hexdigest()
   (home/'.ai-kit/state.json').write_text(json.dumps(state),encoding='utf-8')
   with contextlib.redirect_stdout(io.StringIO()):apply_as('data-analyst',home,False,None,'gemini')
   self.assertFalse(old.exists());self.assertFalse((home/'.gemini/hooks/ai-kit').exists());self.assertTrue((home/'.ai-kit/hooks/dbt-prod-guard.py').is_file())
   command=read_json(home/'.gemini/settings.json')['hooks']['BeforeTool'][0]['hooks'][0]['command'];self.assertIn('.ai-kit',command)
 def test_malformed_input_never_breaks(self):
  for s in ('dbt-prod-guard.py','protected-paths.py'):
   proc=subprocess.run([sys.executable,'-I',str(H/s)],input='not json',capture_output=True,text=True);self.assertEqual(proc.returncode,0);self.assertEqual(proc.stdout.strip(),'{}')

class HookInstallTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst'):
  with contextlib.redirect_stdout(io.StringIO()):apply_as(role,self.home)
 def overrides(self,v):write_personal(self.home,v)
 def settings(self):return read_json(self.home/'.gemini/settings.json')
 def doctor_text(self):
  out=io.StringIO()
  with contextlib.redirect_stdout(out):doctor(self.home)
  return out.getvalue()
 def test_whats_new_declared_on_every_cli_and_off_by_setting(self):
  with contextlib.redirect_stdout(io.StringIO()):apply_as('data-analyst',self.home,False,None,'all')
  st=read_json(self.home/'.ai-kit/state.json');self.assertIn('whats-new',st['hooks']);self.assertEqual(st['hooks']['whats-new']['event'],'SessionStart');self.assertNotIn('matcher',st['hooks']['whats-new']['group'])
  self.assertTrue((self.home/'.ai-kit/hooks/whats-new.py').is_file())
  self.assertEqual((self.home/'.ai-kit/news/CHANGELOG.md').read_bytes(),(ROOT/'CHANGELOG.md').read_bytes())  # what the hook reads, copied at install (no network at session start)
  g=self.settings()['hooks']['SessionStart'];self.assertEqual(len(g),1);self.assertNotIn('matcher',g[0]);self.assertEqual(g[0]['hooks'][0]['name'],'ai-kit-whats-new');self.assertIn('whats-new.py',g[0]['hooks'][0]['command'])
  c=read_json(self.home/'.claude/settings.json')['hooks'];self.assertEqual(len(c['SessionStart']),1);self.assertNotIn('matcher',c['SessionStart'][0]);self.assertIn('whats-new.py',c['SessionStart'][0]['hooks'][0]['command']);self.assertTrue(all('whats-new' not in h['command'] for grp in c['PreToolUse'] for h in grp['hooks']))
  cfg=(self.home/'.codex/config.toml').read_text(encoding='utf-8');self.assertIn('[[hooks.SessionStart]]\n\n[[hooks.SessionStart.hooks]]',cfg);self.assertIn('whats-new.py',cfg);self.assertNotIn('[[hooks.SessionStart]]\nmatcher',cfg)
  a=read_json(self.home/'.gemini/config/plugins/ai-kit/hooks.json')['ai-kit-whats-new'];self.assertTrue(a['enabled']);self.assertEqual(sorted(a['SessionStart'][0]),['command','timeout','type']);self.assertIn('whats-new.py',a['SessionStart'][0]['command'])  # agy: a flat list for a lifecycle event (plugin validate)
  self.overrides({'hooks':{'whats-new':False}})
  with contextlib.redirect_stdout(io.StringIO()):apply_as('data-analyst',self.home,False,None,'all')
  st=read_json(self.home/'.ai-kit/state.json');self.assertNotIn('whats-new',st['hooks']);self.assertFalse((self.home/'.ai-kit/hooks/whats-new.py').exists())
  self.assertNotIn('SessionStart',self.settings().get('hooks',{}));self.assertNotIn('SessionStart',read_json(self.home/'.claude/settings.json').get('hooks',{}))
  self.assertNotIn('[[hooks.SessionStart]]',(self.home/'.codex/config.toml').read_text(encoding='utf-8'));self.assertFalse(read_json(self.home/'.gemini/config/plugins/ai-kit/hooks.json')['ai-kit-whats-new']['enabled'])
 def test_doctor_proves_whats_new_answers_without_writing(self):
  self.run_kit();text=self.doctor_text()
  self.assertIn('[OK] Hook whats-new: synthetic test, the script runs and answers',text);self.assertFalse((self.home/'.ai-kit/news.json').exists())
  self.assertNotIn('Guardrail whats-new',text)
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
  with contextlib.redirect_stdout(io.StringIO()):apply_as('data-analyst',self.home,False,None,'all')
  self.assertIn('[Check] Codex: kit guardrails approved in Codex (not yet',self.doctor_text())
  cfg=self.home/'.codex/config.toml'
  for i in range(2):cfg.write_text(cfg.read_text(encoding='utf-8')+'\n[hooks.state."'+str(cfg).replace('\\','/')+':pre_tool_use:'+str(i)+':0"]\ntrusted_hash = "sha256:00"\n',encoding='utf-8')  # dbt-prod-guard + protected-paths (on by default)
  # 0.34: approval records cannot be tied to the kit's guardrails (unknown hash, shared indexes): never reported as OK.
  text=self.doctor_text();self.assertNotIn('[OK] Codex: kit guardrails approved',text);self.assertIn('approval not verifiable automatically',text)
  cfg.write_text(cfg.read_text(encoding='utf-8').replace('pre_tool_use','session_start'),encoding='utf-8');self.assertIn('approval not verifiable automatically',self.doctor_text())
 def test_defaults_protect_configuration_only(self):
  # protected-paths is on by default (configuration of the kit and CLIs); dbt-prod-guard stays opt-in.
  self.run_kit();self.assertEqual(sorted(read_json(self.home/'.ai-kit/state.json')['hooks']),['protected-paths','whats-new'])  # whats-new: on by default too (0.47)
  self.assertEqual([g['hooks'][0]['name'] for g in self.settings()['hooks']['BeforeTool']],['ai-kit-protected-paths'])
  self.overrides({'hooks':{'protected-paths':False,'whats-new':False}});self.run_kit();self.assertNotIn('hooks',self.settings());self.assertEqual(read_json(self.home/'.ai-kit/state.json')['hooks'],{})
 def test_enable_then_disable(self):
  self.overrides({'hooks':{'dbt-prod-guard':True,'protected-paths':True}});self.run_kit()
  groups=self.settings()['hooks']['BeforeTool'];self.assertEqual(len(groups),2);names={g['hooks'][0]['name'] for g in groups};self.assertEqual(names,{'ai-kit-dbt-prod-guard','ai-kit-protected-paths'})
  self.assertEqual({g['hooks'][0]['name']:g['matcher'] for g in groups}['ai-kit-dbt-prod-guard'],'run_shell_command');groups=[g for g in groups if g['hooks'][0]['name']=='ai-kit-dbt-prod-guard'];self.assertTrue((self.home/'.ai-kit/hooks/dbt-prod-guard.py').is_file());self.assertIn(str(self.home.resolve()),groups[0]['hooks'][0]['command'])  # Windows: the temporary folder has a short name (RUNNER~1)
  self.overrides({'hooks':{'dbt-prod-guard':True,'protected-paths':False}});self.run_kit()
  groups=self.settings()['hooks']['BeforeTool'];self.assertEqual(len(groups),1);self.assertFalse((self.home/'.ai-kit/hooks/protected-paths.py').exists())
  self.overrides({'hooks':{'protected-paths':False,'whats-new':False}});self.run_kit();self.assertNotIn('hooks',self.settings());self.assertFalse((self.home/'.gemini/hooks/ai-kit').exists())
 def test_user_hooks_preserved(self):
  s=self.home/'.gemini/settings.json';s.parent.mkdir(parents=True);s.write_text(json.dumps({'hooks':{'BeforeTool':[{'matcher':'*','hooks':[{'name':'mine','type':'command','command':'echo'}]}],'SessionStart':[{'hooks':[{'type':'command','command':'x'}]}]}}),encoding='utf-8')
  self.overrides({'hooks':{'dbt-prod-guard':True,'protected-paths':False}});self.run_kit();h=self.settings()['hooks'];self.assertEqual(h['BeforeTool'][0]['hooks'][0]['name'],'mine');self.assertEqual(len(h['BeforeTool']),2)
  self.assertEqual(h['SessionStart'][0]['hooks'][0]['command'],'x');self.assertEqual(len(h['SessionStart']),2);self.assertEqual(h['SessionStart'][1]['hooks'][0]['name'],'ai-kit-whats-new');self.assertEqual(h['SessionStart'][1]['hooks'][0]['timeout'],20000)
  self.overrides({'hooks':{'protected-paths':False,'whats-new':False}});self.run_kit();h=self.settings()['hooks'];self.assertEqual(len(h['BeforeTool']),1);self.assertEqual(h['SessionStart'],[{'hooks':[{'type':'command','command':'x'}]}])
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
S='whats-new.py'
class SessionNewsTests(unittest.TestCase):
 """The whats-new hook: what is new, said once, at startup and resume; read from the copies the installation writes in
 ~/.ai-kit/news (AI Kit 3: no remote, no network)."""
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);t=Path(self.tmp.name)
  self.home=t/'home';self.kit=self.home/'.ai-kit/news';self.kit.mkdir(parents=True)
  (self.kit/'CHANGELOG.md').write_text('# Changelog\n\n## 0.47.0 (2026-11-10)\n\n- News at session start.\n\n## 0.46.0 (2026-11-01)\n\n- Older line.\n',encoding='utf-8')
  self.env={'HOME':str(self.home),'USERPROFILE':str(self.home)};self.state()
 def state(self,**extra):
  s={'version':'0.47.0','team':'data-platform',**extra}
  (self.home/'.ai-kit/state.json').write_text(json.dumps(s),encoding='utf-8')
 def marker(self,**fields):
  p=self.home/'.ai-kit/news.json'
  if fields:p.write_text(json.dumps(fields),encoding='utf-8')
  return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
 def hook(self,payload=None):
  return run_hook(S,{'source':'startup'} if payload is None else payload,self.env)
 def context(self,out):
  self.assertEqual(out.get('hookSpecificOutput',{}).get('hookEventName','SessionStart'),'SessionStart');return out.get('hookSpecificOutput',{}).get('additionalContext','')
 def module(self):
  import importlib.util;spec=importlib.util.spec_from_file_location('h',H/S);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h);return h
 def test_installed_version_announced_once_with_its_changelog_section(self):
  c=self.context(self.hook());self.assertIn('0.47.0',c);self.assertIn('News at session start.',c);self.assertNotIn('Older line',c)
  self.assertEqual(self.marker().get('announced_versions'),['0.47.0']);self.assertEqual(self.hook(),{})
  self.state(version='0.48.0');c=self.context(self.hook());self.assertIn('0.48.0',c);self.assertNotIn('What changed',c)  # no section: the version alone
  self.assertEqual(self.marker()['announced_versions'],['0.47.0','0.48.0']);self.assertEqual(self.hook(),{})
 def test_only_startup_and_resume_and_every_input_shape(self):
  for source in ('clear','compact','fork'):self.assertEqual(self.hook({'source':source}),{});self.assertFalse((self.home/'.ai-kit/news.json').exists(),source)
  self.assertIn('0.47.0',self.context(self.hook({'hook_event_name':'SessionStart','source':'resume','session_id':'x'})))
  self.marker();(self.home/'.ai-kit/news.json').unlink();self.assertIn('0.47.0',self.context(self.hook({})))  # no source: startup
  proc=subprocess.run([sys.executable,'-I',str(H/S)],input='not json',capture_output=True,text=True,env={**os.environ,**self.env});self.assertEqual(json.loads(proc.stdout),{});self.assertEqual(proc.returncode,0)
  (self.home/'.ai-kit/state.json').unlink();self.assertEqual(self.hook(),{})
 def test_gemini_and_codex_inputs(self):
  gemini={'session_id':'s','timestamp':'2026-11-02T10:00:00Z','hook_event_name':'SessionStart','cwd':str(self.home),'source':'startup'}
  codex={'session_id':'s','hook_event_name':'SessionStart','cwd':str(self.home),'transcript_path':'/t','source':'startup'}
  self.assertIn('0.47.0',self.context(self.hook(gemini)));self.assertEqual(self.hook(codex),{})
  (self.home/'.ai-kit/news.json').unlink();self.assertIn('0.47.0',self.context(self.hook(codex)))
  self.assertEqual(self.hook({**gemini,'source':'clear'}),{});self.assertEqual(self.hook({**codex,'source':'compact'}),{})
 def test_no_git_and_no_network_needed(self):
  # AI Kit 3: the hook reads local copies only; with no program on PATH (no git) it still answers, fast.
  import time;start=time.monotonic();c=self.context(run_hook(S,{'source':'startup'},{**self.env,'PATH':str(self.home)}));self.assertLess(time.monotonic()-start,1.0)
  self.assertIn('0.47.0',c);self.assertNotIn('last_check',self.marker())
 def test_missing_news_copies_still_announce_the_version(self):
  (self.kit/'CHANGELOG.md').unlink()
  c=self.context(self.hook());self.assertIn('Kit version 0.47.0 installed.',c);self.assertEqual(self.hook(),{})
 def test_agy_input_gets_agy_output(self):
  # agy's SessionStart contract (its built-in hooks documentation): injectSteps with a nested systemMessage, persisted in the conversation.
  out=self.hook({'conversationId':'c1','workspacePaths':[str(self.home)],'transcriptPath':'/t','modelName':'m'})
  self.assertEqual(list(out),['injectSteps']);step=out['injectSteps'][0];self.assertEqual(list(step),['systemMessage']);self.assertIn('0.47.0',step['systemMessage']['systemMessage'])
  self.assertEqual(self.marker().get('announced_versions'),['0.47.0']);self.assertEqual(self.hook({'conversationId':'c2'}),{})
 def test_news_entries_targeted_expired_seen_and_malformed(self):
  self.marker(announced_versions=['0.47.0'])
  (self.kit/'NEWS.md').write_text('# News\n\n## 2026-11-02 welcome : A channel for news\n\nFirst global entry.\n\n## 2026-11-02 analysts-only : For analysts\nteams: analysts\n\nNot for us.\n\n## 2026-01-01 expired : Old training\nuntil: 2026-01-31\n\nGone.\n\n## 2026-11-02 team-news : Team session\nteams: data-platform, other\n\nFor our team.\n\n## no id here\n\nIgnored.\n',encoding='utf-8')
  c=self.context(self.hook());self.assertIn('A channel for news',c);self.assertIn('First global entry.',c);self.assertIn('Team session',c)
  for absent in ('For analysts','Old training','no id here','Ignored.'):self.assertNotIn(absent,c)
  self.assertEqual(sorted(self.marker()['announced_news']),['team-news','welcome']);self.assertEqual(self.hook(),{})
 def test_whats_new_and_aimed_at_are_pure(self):
  h=self.module()
  entry={'until':'2026-11-30','teams':['data-platform']}
  self.assertTrue(h.aimed_at(entry,'data-platform','2026-11-09'));self.assertFalse(h.aimed_at(entry,'other','2026-11-09'));self.assertFalse(h.aimed_at(entry,'data-platform','2026-12-01'))
  self.assertTrue(h.aimed_at({'until':'','teams':[]},'','2026-11-09'))
  items,marker=h.whats_new({'version':'0.47.0','team':''},{'announced_versions':['0.47.0']},str(self.kit),'2026-11-09')
  self.assertEqual(items,[]);self.assertEqual(marker['announced_versions'],['0.47.0'])
  items,marker=h.whats_new({'version':'0.47.0','team':''},{},str(self.kit),'2026-11-09')
  self.assertEqual(len(items),1);self.assertIn('News at session start.',items[0]);self.assertFalse((self.home/'.ai-kit/news.json').exists())  # writes nothing
 def test_me_offered_once_while_user_context_is_the_kit_one(self):
  # The installer asks nothing: the first session after it offers /me, once, while USER.md is still the one it created.
  self.marker(announced_versions=['0.47.0']);ctx=self.home/'.ai-kit/context';ctx.mkdir(parents=True)
  self.assertEqual(self.hook(),{})  # no USER.md: nothing to offer
  (ctx/'USER.md').write_text('# My context\n\n## Me\n- Data engineer, migrating the billing pipeline.\n',encoding='utf-8')
  self.assertEqual(self.hook(),{})  # filled by the person
  (ctx/'USER.md').write_text('# My context\n\n## Me\n<!-- One line: my role and what I work on these weeks. -->\n',encoding='utf-8')
  c=self.context(self.hook());self.assertIn('/me',c);self.assertIn('$me',c)
  self.assertTrue(self.marker()['offered_me']);self.assertEqual(self.hook(),{})  # once
 def test_role_placeholder_is_the_installer_one(self):
  from installer.cli import ROLE_PLACEHOLDER;self.assertEqual(self.module().ROLE_PLACEHOLDER,ROLE_PLACEHOLDER)
 def test_context_is_capped(self):
  (self.kit/'CHANGELOG.md').write_text('# Changelog\n\n## 0.47.0\n\n'+('- a very long line of changes\n'*2000),encoding='utf-8')
  self.assertLessEqual(len(self.context(self.hook())),8000)
if __name__=='__main__':unittest.main()
