import contextlib, io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from installer.cli import apply, usage
from installer.core import read_json, ROOT
class FrictionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self,role='data-analyst'):
  with contextlib.redirect_stdout(io.StringIO()):apply(role,self.home,False,None,'gemini')
 def test_script_installed_and_command_present(self):
  self.run_kit();script=self.home/'.ai-toolkit/bin/friction.py';self.assertTrue(script.is_file())
  self.assertTrue((self.home/'.gemini/commands/friction.toml').is_file());self.assertIn('.ai-toolkit/bin/friction.py',read_json(self.home/'.ai-toolkit/state.json')['files'])
 def test_script_appends_and_usage_counts(self):
  self.run_kit();script=self.home/'.ai-toolkit/bin/friction.py';env={**os.environ,'HOME':str(self.home),'USERPROFILE':str(self.home)}
  p=subprocess.run([sys.executable,'-I',str(script),'--category','docs','--command','/intent','--text','La page dit X mais la commande fait Y'],capture_output=True,text=True,env=env)
  self.assertEqual(p.returncode,0,p.stderr);lines=(self.home/'.ai-toolkit/frictions.jsonl').read_text(encoding='utf-8').splitlines();self.assertEqual(len(lines),1)
  e=json.loads(lines[0]);self.assertEqual(e['category'],'docs');self.assertEqual(e['command'],'intent')
  p=subprocess.run([sys.executable,'-I',str(script),'--category','nope','--text','x'],capture_output=True,text=True,env=env);self.assertNotEqual(p.returncode,0)
  out=io.StringIO()
  with contextlib.redirect_stdout(out):usage(self.home,42,self.home/'r.json')
  self.assertIn('Frictions notées : 1 (docs ×1)',out.getvalue());rep=read_json(self.home/'r.json');self.assertEqual(rep['frictions_by_category'],{'docs':1});self.assertEqual(rep['frictions'][0]['text'],'La page dit X mais la commande fait Y')
 def test_aggregate_script(self):
  a={'sessions':3,'prompts':10,'errors':0,'commands':{'intent':2},'skills':{'tdd':1},'agents':{},'unused_skills':['grilling','retro'],'frictions':[{'ts':'2026-10-25T00:00:00Z','category':'docs','command':'intent','text':'x'}],'frictions_by_category':{'docs':1}}
  b={'sessions':2,'prompts':5,'errors':1,'commands':{'intent':1,'test':1},'skills':{},'agents':{'ai-kit-verifier':1},'unused_skills':['grilling'],'frictions':[],'frictions_by_category':{}}
  (self.home/'a.json').write_text(json.dumps(a));(self.home/'b.json').write_text(json.dumps(b))
  p=subprocess.run([sys.executable,'-I',str(ROOT/'scripts/usage-aggregate.py'),str(self.home/'a.json'),str(self.home/'b.json')],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stderr);self.assertIn('2 postes | 5 sessions | 15 prompts | 1 erreurs',p.stdout);self.assertIn('| `intent` | 3 |',p.stdout);self.assertIn('`grilling`',p.stdout);self.assertNotIn('`retro`',p.stdout);self.assertIn('| docs | /intent | x |',p.stdout)

class FrictionSignalTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
  with contextlib.redirect_stdout(io.StringIO()):apply('data-analyst',self.home,False,None,'gemini')
  self.env={**os.environ,'HOME':str(self.home),'USERPROFILE':str(self.home)}
 def lines(self):
  return [json.loads(line) for line in (self.home/'.ai-toolkit/frictions.jsonl').read_text(encoding='utf-8').splitlines()]
 def test_context_added_automatically(self):
  subprocess.run([sys.executable,'-I',str(self.home/'.ai-toolkit/bin/friction.py'),'--category','skill','--cli','agy','--text','x y z'],capture_output=True,text=True,env=self.env,check=True)
  e=self.lines()[0];self.assertEqual(e['profile'],'data-analyst');self.assertEqual(e['kit'],read_json(ROOT/'profiles/data-analyst.json') and (ROOT/'VERSION').read_text().strip());self.assertEqual(e['cli'],'agy');self.assertIn(e['os'],('mac','windows','linux'));self.assertEqual(e['source'],'person')
 def test_doctor_failure_recorded_without_asking(self):
  from installer.core import record_auto_friction
  record_auto_friction(self.home,'Quota dépassé (HTTP 429).')
  e=self.lines()[0];self.assertEqual((e['category'],e['command'],e['source']),('auth','doctor','doctor'));self.assertIn('429',e['text'])
 def test_usage_counts_unknown_commands_and_repeats(self):
  chats=self.home/'.gemini/tmp/p/chats';chats.mkdir(parents=True)
  from datetime import datetime, timezone
  now=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
  msgs=[{'type':'user','timestamp':now,'content':c} for c in ('/spec la vente','/help','/intent clients actifs du tableau','/intent clients actifs du tableau')]
  (chats/'s.json').write_text(json.dumps({'messages':msgs}),encoding='utf-8')
  with contextlib.redirect_stdout(io.StringIO()):usage(self.home,42,self.home/'r.json')
  r=read_json(self.home/'r.json');self.assertEqual(r['unknown_commands'],{'spec':1});self.assertEqual(r['repeated_prompts'],1)
 def test_friction_mode_option(self):
  kit=lambda:(self.home/'.gemini/00_KIT.md').read_text(encoding='utf-8')
  self.assertIn('Proposer en une ligne de noter `/friction`',kit())
  ov=self.home/'.ai-toolkit/overrides.json'
  for mode,needle,absent in (('auto','Noter toi-même la friction, sans demander','Proposer en une ligne'),('off',None,'## Frictions')):
   d=read_json(ov);d['frictions']=mode;ov.write_text(json.dumps(d),encoding='utf-8')
   with contextlib.redirect_stdout(io.StringIO()):apply('data-analyst',self.home,False,None,'gemini')
   (self.assertIn(needle,kit()) if needle else None);self.assertNotIn(absent,kit())
  d=read_json(ov);d['frictions']='toujours';ov.write_text(json.dumps(d),encoding='utf-8')
  from installer.core import KitError
  with self.assertRaises(KitError),contextlib.redirect_stdout(io.StringIO()):apply('data-analyst',self.home,False,None,'gemini')
 def test_aggregate_groups_and_flags_two_or_more(self):
  f=lambda c,m:{'ts':'2026-10-25T00:00:00Z','category':c,'command':m,'text':'t','cli':'gemini','os':'mac','kit':'0.15','profile':'data-analyst','source':'person'}
  (self.home/'a.json').write_text(json.dumps({'sessions':1,'prompts':1,'frictions':[f('command','test'),f('command','test'),f('docs','intent')],'unknown_commands':{'spec':2},'repeated_prompts':3}))
  p=subprocess.run([sys.executable,'-I',str(ROOT/'scripts/usage-aggregate.py'),str(self.home/'a.json')],capture_output=True,text=True,check=True)
  self.assertIn('| command | /test | 2 |',p.stdout);self.assertNotIn('| docs | /intent | 1 |',p.stdout);self.assertIn('/spec ×2',p.stdout);self.assertIn('session : 3',p.stdout);self.assertIn('gemini mac 0.15 data-analyst',p.stdout)
if __name__=='__main__':unittest.main()
