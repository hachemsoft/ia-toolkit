import contextlib, io, tempfile, unittest
from pathlib import Path
from installer.adapters.gemini import diagnose_live
from v1_profiles import apply_as  # noqa: E402
S_KEY={'security':{'auth':{'selectedType':'gemini-api-key'}}}
class LiveDiagnosisTests(unittest.TestCase):
 def test_ok(self):
  self.assertEqual(diagnose_live(0,'OK\n',False,S_KEY),(None,None))
 def test_credits(self):
  d,r=diagnose_live(1,'"code": 402, "message": "Your prepayment credits are depleted."',False,S_KEY);self.assertIn('AI Studio credits',d);self.assertIn('/auth',r)
 def test_api_keys_disallowed(self):
  d,r=diagnose_live(1,'API Keys are Disallowed. Your organization...',False,S_KEY);self.assertIn('forbids API keys',d);self.assertIn('application-default login',r)
 def test_vertex_api_disabled(self):
  d,r=diagnose_live(1,'Agent Platform API has not been used in project demo-project-01 ... aiplatform.googleapis.com/overview?project=demo-project-01 status: 403',False,S_KEY);self.assertIn('demo-project-01',d);self.assertEqual(r,'gcloud services enable aiplatform.googleapis.com --project demo-project-01')
 def test_no_auth(self):
  d,r=diagnose_live(1,'Please set an Auth method in your settings.json',False,{});self.assertIn('No Gemini authentication',d)
 def test_timeout_model_loop(self):
  d,r=diagnose_live(None,'Model fallback activated: switching from gemini-3.8-flash',True,S_KEY);self.assertIn('looping',d);self.assertIn('model.name',r)
 def test_403_iam(self):
  d,r=diagnose_live(1,'status: 403 PERMISSION_DENIED',False,S_KEY);self.assertIn('IAM',d)
 def test_unknown(self):
  d,r=diagnose_live(1,'something odd',False,S_KEY);self.assertIn('not as expected',d)
if __name__=='__main__':unittest.main()

class RetiredAuthAndModelTests(unittest.TestCase):
 """0.36: the kit no longer writes authentication or models. What an earlier version wrote stays, now the person's."""
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def run_kit(self):
  out=io.StringIO()
  with contextlib.redirect_stdout(out):notices=apply_as('data-analyst',self.home,False,None,'gemini')
  return notices
 def test_uninstall_keeps_the_authentication(self):
  env=self.home/'.gemini/.env';env.parent.mkdir(parents=True);env.write_text('# ai-kit : Vertex AI (managed by the kit)\nGOOGLE_CLOUD_PROJECT=demo-project-01\n',encoding='utf-8')
  self.run_kit()
  from installer.cli import uninstall
  with contextlib.redirect_stdout(io.StringIO()):uninstall(self.home)
  self.assertIn('GOOGLE_CLOUD_PROJECT=demo-project-01',env.read_text(encoding='utf-8'))
 def test_diagnoses_point_to_the_cli_not_to_the_kit(self):
  for output in ('When using Vertex AI, you must specify either: GOOGLE_CLOUD_PROJECT','This account requires setting the GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_PROJECT_ID env var.'):
   d,r=diagnose_live(1,output,False,{});self.assertNotIn('overrides.json',r);self.assertIn('GOOGLE_CLOUD_PROJECT',r)
  d,r=diagnose_live(None,'Model fallback activated',True,{});self.assertNotIn('overrides.json',r);self.assertIn('/model',r)
