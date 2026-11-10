import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from installer.core import KitError, read_json, ROOT
from installer.toml_files import dump_toml
from personal import write_personal  # noqa: E402
from presets import apply_as  # noqa: E402
class AgentTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst'):
  with contextlib.redirect_stdout(io.StringIO()):apply_as(role,self.home)
 def agent(self,name):return self.home/'.gemini/agents'/('ai-kit-'+name+'.md')
 def overrides(self,v):
  write_personal(self.home,v)
 def test_analyst_selection(self):
  self.run_kit();self.assertTrue(self.agent('repo-investigator').exists());self.assertTrue(self.agent('sql-reviewer').exists());self.assertTrue(self.agent('dbt-reviewer').exists());self.assertTrue(self.agent('code-reviewer').exists())  # a Core default for everyone
 def test_agents_inherit_the_session_model(self):
  # 0.36: the kit no longer chooses models; a "models" table in aikit.toml is an unknown key, ignored (and reported), every agent inherits.
  p=self.home/'.ai-kit/aikit.toml';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(dump_toml({'schema':1,'models':{'fast':'gemini-2.5-flash','deep':'gemini-2.5-pro'}}),encoding='utf-8');self.run_kit('data-developer')
  for name in ('verifier','doubter','sql-reviewer'):self.assertNotIn('model:',self.agent(name).read_text(encoding='utf-8'))
 def test_developer_and_switch(self):
  self.run_kit();self.assertTrue(self.agent('doubter').exists());self.assertFalse(self.agent('infra-reviewer').exists());self.run_kit('data-developer');self.assertTrue(self.agent('code-reviewer').exists());self.assertTrue(self.agent('sql-reviewer').exists());self.assertTrue(self.agent('doubter').exists());self.assertTrue(self.agent('repo-investigator').exists())
 def test_extra_and_disable(self):
  self.overrides({'extra_agents':['code-reviewer'],'disabled_agents':['dbt-reviewer']});self.run_kit();self.assertTrue(self.agent('code-reviewer').exists());self.assertFalse(self.agent('dbt-reviewer').exists())
 def test_modified_agent_blocks(self):
  self.run_kit();self.agent('sql-reviewer').write_text('personal',encoding='utf-8')
  with self.assertRaises(KitError):self.run_kit('data-developer')
 def test_existing_agent_blocks(self):
  p=self.agent('sql-reviewer');p.parent.mkdir(parents=True);p.write_text('third-party',encoding='utf-8')
  with self.assertRaises(KitError):self.run_kit()
  self.assertFalse((self.home/'.ai-kit/state.json').exists())
 def test_unknown_agent(self):
  self.overrides({'extra_agents':['unknown']})
  with self.assertRaises(KitError):self.run_kit()
 def test_generated_tools_and_context(self):
  self.run_kit();text=self.agent('sql-reviewer').read_text(encoding='utf-8');header=text.split('---')[1];self.assertIn('name: ai-kit-sql-reviewer',header);self.assertIn('kind: local',header);self.assertIn('tools: ["read_file", "grep_search"]',header);self.assertNotIn('run_shell_command',header);self.assertNotIn('mcp_*',header);self.assertIn('Team practices',text);self.assertIn('Company practices',text);self.assertNotIn('My context',text)
 def test_older_state_without_agents(self):
  self.run_kit()
  state_path=self.home/'.ai-kit/state.json';state=read_json(state_path)
  for rel in list(state['files']):
   if rel.startswith('.gemini/agents/'):
    (self.home/rel).unlink();del state['files'][rel]
  state['version']='0.0.2';state_path.write_text(json.dumps(state),encoding='utf-8')
  self.run_kit();self.assertTrue(self.agent('sql-reviewer').exists());self.assertEqual(read_json(state_path)['version'],(ROOT/'VERSION').read_text(encoding='utf-8').strip())
