import contextlib, io, json, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from installer.cli import apply, usage
from installer.core import KitError, read_json
def msg(kind, ts, **extra):
 return {'id':'x','timestamp':ts.strftime('%Y-%m-%dT%H:%M:%S.000Z'),'type':kind,**extra}

class UsageTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
  with contextlib.redirect_stdout(io.StringIO()):apply('data-analyst',self.home)
 def write_session(self,name,messages):
  p=self.home/'.gemini/tmp/proj/chats'/(name+'.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'sessionId':name,'messages':messages}),encoding='utf-8')
 def run_usage(self,**kw):
  out=io.StringIO();rep=self.home/'report.json'
  with contextlib.redirect_stdout(out):usage(self.home,as_json=rep,**kw)
  return out.getvalue(),json.loads(rep.read_text(encoding='utf-8'))
 def test_counts_commands_skills_agents(self):
  now=datetime.now(timezone.utc)
  self.write_session('s1',[msg('user',now,displayContent="[{'text': '/intent idée'}]"),msg('gemini',now,toolCalls=[{'name':'activate_skill','args':{'name':'grill-with-docs'}},{'name':'ai-kit-verifier','args':{}}]),msg('user',now,displayContent="[{'text': 'bonjour /intent dans une phrase'}]"),msg('error',now,content='x')])
  text,rep=self.run_usage()
  self.assertEqual(rep['commands'],{'intent':1});self.assertEqual(rep['skills'],{'grill-with-docs':1});self.assertEqual(rep['agents'],{'ai-kit-verifier':1});self.assertEqual(rep['errors'],1);self.assertEqual(rep['sessions'],1)
  self.assertIn('intent',rep['unused_commands'] and [] or ['intent']);self.assertNotIn('intent',rep['unused_commands']);self.assertIn('ship',rep['unused_commands']);self.assertFalse(rep['enough_data']);self.assertIn('Données insuffisantes',text)
 def test_old_sessions_ignored(self):
  old=datetime.now(timezone.utc)-timedelta(days=100)
  self.write_session('old',[msg('user',old,displayContent="[{'text': '/ship'}]")])
  text,rep=self.run_usage();self.assertEqual(rep['sessions'],0);self.assertEqual(rep['commands'],{})
  text,rep=self.run_usage(since_days=200);self.assertEqual(rep['commands'],{'ship':1})
 def test_recommendations_when_enough_data(self):
  now=datetime.now(timezone.utc)
  for i in range(10):
   self.write_session('s'+str(i),[msg('user',now,displayContent="[{'text': '/intent x'}]") for _ in range(5)]+[msg('gemini',now,toolCalls=[{'name':'activate_skill','args':{'name':'grill-with-docs'}}])])
  text,rep=self.run_usage()
  self.assertTrue(rep['enough_data']);c=rep['core_candidates_to_demote']
  self.assertIn('teach',c);self.assertNotIn('grill-with-docs',c);self.assertNotIn('grilling',c);self.assertNotIn('domain-modeling',c);self.assertNotIn('sql-review',c);self.assertIn('Candidats à sortir du noyau',text)
 def test_agy_history_counted(self):
  import time;now=int(time.time()*1000);h=self.home/'.gemini/antigravity-cli/history.jsonl';h.parent.mkdir(parents=True,exist_ok=True)
  h.write_text('\n'.join([json.dumps({'display':'/intent idée','timestamp':now,'conversationId':'c1'}),json.dumps({'display':'bonjour','timestamp':now,'conversationId':'c1'}),json.dumps({'display':'/ship','timestamp':now-200*86400*1000,'conversationId':'old'}),'pas du json']),encoding='utf-8')
  text,rep=self.run_usage();self.assertEqual(rep['commands'],{'intent':1});self.assertEqual(rep['sessions'],1);self.assertEqual(rep['prompts'],2)
 def test_requires_installation(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(KitError):usage(Path(tmp))
 def test_malformed_log_ignored(self):
  p=self.home/'.gemini/tmp/proj/chats/bad.json';p.parent.mkdir(parents=True);p.write_text('{broken')
  text,rep=self.run_usage();self.assertEqual(rep['sessions'],0)
if __name__=='__main__':unittest.main()
