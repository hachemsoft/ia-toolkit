import contextlib, io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from installer.cli import apply, doctor
from installer.core import KitError, read_json, ROOT
from installer.adapters.codex import CODEX_MD, CODEX_TOML
H=ROOT/'runtime/hooks'
def run_hook(script,payload):
 p=subprocess.run([sys.executable,'-I',str(H/script)],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8');return json.loads(p.stdout or '{}')

class CodexAdapterTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
  (self.home/'.codex').mkdir();self.agents=self.home/'.codex/AGENTS.md';self.config=self.home/'.codex/config.toml'
  self.agents.write_text('# Mes consignes\n- toujours en français\n',encoding='utf-8');self.config.write_text('model = "gpt-x"\n\n[projects."/x"]\ntrust_level = "trusted"\n',encoding='utf-8')
 def run_kit(self,role='data-developer',target='all',overrides=None):
  if overrides is not None:
   (self.home/'.ai-toolkit').mkdir(exist_ok=True);(self.home/'.ai-toolkit/overrides.json').write_text(json.dumps(overrides),encoding='utf-8')
  out=io.StringIO()
  with contextlib.redirect_stdout(out):apply(role,self.home,False,{'email':'t@example.org'},target)
  return out.getvalue()
 def test_codex_only_keeps_gemini_untouched(self):
  self.run_kit(target='codex')
  self.assertFalse((self.home/'.gemini').exists())
  ctx=self.home/'.ai-toolkit/context'
  self.assertTrue((ctx/'00_KIT.md').is_file());self.assertTrue((ctx/'30_USER.md').is_file())
  self.assertIn((ctx/'00_KIT.md').read_text(encoding='utf-8').strip()[:200],(self.home/'.codex/AGENTS.md').read_text(encoding='utf-8'))
  out=io.StringIO()
  with contextlib.redirect_stdout(out):code=doctor(self.home)
  self.assertEqual(code,0,out.getvalue())

 def test_user_context_follows_location_without_deleting(self):
  self.run_kit(target='all')
  mine='# Moi\nPréférence personnelle conservée.\n'
  (self.home/'.gemini/30_USER.md').write_text(mine,encoding='utf-8')
  self.run_kit(target='codex')
  self.assertEqual((self.home/'.ai-toolkit/context/30_USER.md').read_text(encoding='utf-8'),mine)
  self.assertEqual((self.home/'.gemini/30_USER.md').read_text(encoding='utf-8'),mine)
  self.assertFalse((self.home/'.gemini/00_KIT.md').exists())
  self.assertIn('Préférence personnelle conservée',(self.home/'.codex/AGENTS.md').read_text(encoding='utf-8'))
  self.run_kit(target='all')
  self.assertTrue((self.home/'.gemini/00_KIT.md').is_file());self.assertFalse((self.home/'.ai-toolkit/context/00_KIT.md').exists())
  self.assertEqual((self.home/'.ai-toolkit/context/30_USER.md').read_text(encoding='utf-8'),mine)

 def test_install_keeps_user_content_and_adds_blocks(self):
  self.run_kit();a=self.agents.read_text(encoding='utf-8');c=self.config.read_text(encoding='utf-8')
  self.assertIn('- toujours en français',a);self.assertTrue(a.startswith(CODEX_MD[0]));self.assertIn('$intent',a);self.assertIn('Pratiques entreprise',a);self.assertIn('# Mon contexte',a)
  self.assertIn('model = "gpt-x"',c);self.assertIn('trust_level = "trusted"',c);self.assertTrue(c.rstrip().endswith(CODEX_TOML[1]));self.assertIn('[agents.ai-kit-verifier]',c)
  try:import tomllib
  except ImportError:return
  d=tomllib.loads(c);self.assertEqual(d['model'],'gpt-x');self.assertTrue(Path(d['agents']['ai-kit-verifier']['config_file']).is_file())
  role=tomllib.loads(Path(d['agents']['ai-kit-verifier']['config_file']).read_text(encoding='utf-8'));self.assertIn('Verifying your work',role['developer_instructions'])
 def test_skills_and_explicit_only_policy(self):
  self.run_kit();sk=self.home/'.codex/skills'
  self.assertTrue((sk/'grilling/SKILL.md').is_file());self.assertTrue((sk/'intent/SKILL.md').is_file())
  self.assertIn('allow_implicit_invocation: false',(sk/'intent/agents/openai.yaml').read_text())
  self.assertIn('allow_implicit_invocation: false',(sk/'to-spec/agents/openai.yaml').read_text())
  self.assertFalse((sk/'grilling/agents/openai.yaml').exists())
 def test_idempotent_and_removed_cleanly_when_target_changes(self):
  self.run_kit();self.assertIn('Déjà à jour',self.run_kit())
  self.run_kit(target='gemini')
  self.assertEqual(self.agents.read_text(encoding='utf-8'),'# Mes consignes\n- toujours en français\n');self.assertNotIn('ai-kit',self.config.read_text(encoding='utf-8'))
  self.assertFalse((self.home/'.codex/skills/intent').exists());self.assertFalse((self.home/'.codex/ai-kit').exists())
 def test_hand_edited_block_is_refused(self):
  self.run_kit();self.agents.write_text(self.agents.read_text(encoding='utf-8').replace('# Kit IA (Codex)','# Kit IA modifié'),encoding='utf-8')
  with self.assertRaises(KitError):self.run_kit()
 def test_user_context_change_reaches_codex_on_update(self):
  self.run_kit();u=self.home/'.gemini/30_USER.md';u.write_text(u.read_text(encoding='utf-8')+'\n- Réponses courtes.\n',encoding='utf-8')
  self.run_kit();self.assertIn('- Réponses courtes.',self.agents.read_text(encoding='utf-8'))
 def test_hooks_declared_and_mcp(self):
  out=self.run_kit(overrides={'hooks':{'dbt-prod-guard':True},'mcp':{'documentation':{'enabled':True,'server':{'httpUrl':'https://docs.example.org/mcp'}}}})
  c=self.config.read_text(encoding='utf-8');self.assertIn('[[hooks.PreToolUse]]',c);self.assertIn('dbt-prod-guard.py',c);self.assertIn('[mcp_servers.ai-kit-documentation]',c);self.assertIn('url = "https://docs.example.org/mcp"',c);self.assertIn('Trust',out)
 def test_conflicting_hooks_refused(self):
  self.config.write_text('hooks.PreToolUse = []\n',encoding='utf-8')
  with self.assertRaises(KitError):self.run_kit(overrides={'hooks':{'dbt-prod-guard':True}})
 def test_usage_reads_codex_history(self):
  self.run_kit();import time
  from installer.cli import usage
  now=int(time.time());h=self.home/'.codex/history.jsonl'
  h.write_text('\n'.join(json.dumps({'session_id':'s1','ts':now,'text':x}) for x in ('$intent clients actifs','$intent clients actifs','/nope'))+'\n',encoding='utf-8')
  with contextlib.redirect_stdout(io.StringIO()):usage(self.home,42,self.home/'r.json')
  r=read_json(self.home/'r.json');self.assertEqual(r['commands'].get('intent'),2);self.assertEqual(r['repeated_prompts'],1);self.assertEqual(r['unknown_commands'],{'nope':1})
 def test_doctor_reports_codex_blocks(self):
  self.run_kit();out=io.StringIO()
  with contextlib.redirect_stdout(out):doctor(self.home)
  self.assertIn('[OK] Bloc du kit intact dans ~/.codex/AGENTS.md',out.getvalue());self.assertIn('[OK] Codex a la dernière version de 30_USER.md',out.getvalue())

class CodexHookPayloadTests(unittest.TestCase):
 def test_dbt_guard_codex_shell_list_and_output_format(self):
  r=run_hook('dbt-prod-guard.py',{'hook_event_name':'PreToolUse','tool_name':'shell','tool_input':{'command':['bash','-lc','dbt run -t prod']},'cwd':'/tmp'})
  self.assertEqual(r['hookSpecificOutput']['permissionDecision'],'deny');self.assertEqual(r['hookSpecificOutput']['hookEventName'],'PreToolUse');self.assertNotIn('decision',r)
  self.assertEqual(run_hook('dbt-prod-guard.py',{'hook_event_name':'PreToolUse','tool_name':'exec_command','tool_input':{'cmd':'dbt run -t dev'}}),{})
 def test_protected_paths_apply_patch(self):
  with tempfile.TemporaryDirectory() as tmp:
   (Path(tmp)/'.git').mkdir();(Path(tmp)/'.ai-kit').mkdir();(Path(tmp)/'.ai-kit/protected-paths').write_text('target/**\n',encoding='utf-8')
   patch='*** Begin Patch\n*** Update File: target/run.sql\n@@\n-a\n+b\n*** End Patch\n'
   r=run_hook('protected-paths.py',{'hook_event_name':'PreToolUse','tool_name':'apply_patch','cwd':tmp,'tool_input':{'command':patch}})
   self.assertEqual(r['hookSpecificOutput']['permissionDecision'],'deny')
   ok=patch.replace('target/run.sql','models/a.sql')
   self.assertEqual(run_hook('protected-paths.py',{'hook_event_name':'PreToolUse','tool_name':'apply_patch','cwd':tmp,'tool_input':{'command':ok}}),{})
if __name__=='__main__':unittest.main()
