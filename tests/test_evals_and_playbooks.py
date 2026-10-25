import contextlib, io, json, subprocess, sys, tempfile, unittest
from pathlib import Path
from installer.cli import apply
from installer.core import read_json, load_commands, ROOT
sys.path.insert(0,str(ROOT/'evals'))
import run as evals_run

class PlaybookTests(unittest.TestCase):
 def test_domain_skills_have_excuse_tables(self):
  catalog=read_json(ROOT/'skills/catalog.json')
  for k,v in catalog.items():
   if v.get('category')=='domain':
    text=(ROOT/v['path']/'SKILL.md').read_text(encoding='utf-8');self.assertIn('## Excuses entendues et réponses',text,k);self.assertGreaterEqual(text.count('\n| « '),3,k)
 def test_new_playbooks_in_profiles(self):
  a=read_json(ROOT/'profiles/data-analyst.json')['skills'];d=read_json(ROOT/'profiles/data-developer.json')['skills']
  for s in ('kpi-definition','incremental-replay','bigquery-cost-review','perimeter-brief'):self.assertIn(s,a)
  self.assertEqual(read_json(ROOT/'profiles/data-analyst.json')['commands'],['guide','intent','build','test','ship','diagnose','learn','friction'])
  for s in ('incremental-replay','bigquery-cost-review','perimeter-brief'):self.assertIn(s,d)
 def test_doubter_installed_read_only(self):
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp)
   with contextlib.redirect_stdout(io.StringIO()):apply('data-developer',home)
   text=(home/'.gemini/agents/ai-kit-doubter.md').read_text(encoding='utf-8');header=text.split('---')[1]
   self.assertIn('tools: ["read_file", "grep_search"]',header);self.assertIn('non prouvée',text)
 def test_commands_reference_playbooks(self):
  cmds={c['name']:c['prompt'] for c in load_commands()}
  self.assertIn('kpi-definition',cmds['intent']);self.assertIn('incremental-replay',cmds['build']);self.assertIn('bigquery-cost-review',cmds['diagnose']);self.assertIn('ai-kit-doubter',cmds['review']);self.assertIn('ai-kit-verifier',cmds['build'])

class EvalSuiteTests(unittest.TestCase):
 def test_cases_valid_and_reference_installed_commands(self):
  names={c['name'] for c in load_commands()};cases=evals_run.load_cases(ROOT/'evals/cases')
  self.assertGreaterEqual(len(cases),4)
  for case in cases:
   if case['prompt'].startswith('/'):self.assertIn(case['prompt'].split()[0][1:],names,case['name'])
   if case.get('cwd'):self.assertTrue((ROOT/'evals/fixtures'/case['cwd']).is_dir(),case['name'])
 def test_check_logic(self):
  self.assertEqual(evals_run.check('Commencez par /intent puis /spec',{'contains':['/intent'],'not_contains':['grilling'],'regex':['/spec']}),[])
  self.assertEqual(len(evals_run.check('rien',{'contains':['/intent'],'not_contains':['rien'],'regex':['\\d']})),3)
 def test_api_errors_are_not_behaviour_failures(self):
  self.assertIn('API 402',evals_run.api_error(1,'...retryWithBackoff ... {\n  status: 402\n}\nAn unexpected critical error occurred'))
  self.assertIn('authentification',evals_run.api_error(1,'Please set an Auth method in your settings.json'))
  self.assertIn('Antigravity',evals_run.api_error(0,'jetski: no output produced — a tool required the "command" permission that headless mode cannot prompt for'))
  self.assertIsNone(evals_run.api_error(0,'Commencez par /intent.'))
 def test_dry_run_lists_cases(self):
  out=io.StringIO()
  with contextlib.redirect_stdout(out):code=evals_run.main(['--dry-run'])
  self.assertEqual(code,0);self.assertIn('guide-routes-to-commands',out.getvalue())
 def test_workflow_file_targets_evals(self):
  wf=(ROOT/'.github/workflows/agent-evals.yml').read_text(encoding='utf-8');self.assertIn('evals/run.py',wf);self.assertIn('GEMINI_API_KEY',wf)
if __name__=='__main__':unittest.main()
