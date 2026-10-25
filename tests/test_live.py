import unittest
from installer.adapters.gemini import diagnose_live
S_KEY={'security':{'auth':{'selectedType':'gemini-api-key'}}}
class LiveDiagnosisTests(unittest.TestCase):
 def test_ok(self):
  self.assertEqual(diagnose_live(0,'OK\n',False,S_KEY),(None,None))
 def test_credits(self):
  d,r=diagnose_live(1,'"code": 402, "message": "Your prepayment credits are depleted."',False,S_KEY);self.assertIn('Crédits AI Studio',d);self.assertIn('/auth',r)
 def test_api_keys_disallowed(self):
  d,r=diagnose_live(1,'API Keys are Disallowed. Your organization...',False,S_KEY);self.assertIn('interdit les clés',d);self.assertIn('application-default login',r)
 def test_vertex_api_disabled(self):
  d,r=diagnose_live(1,'Agent Platform API has not been used in project demo-project-01 ... aiplatform.googleapis.com/overview?project=demo-project-01 status: 403',False,S_KEY);self.assertIn('demo-project-01',d);self.assertEqual(r,'gcloud services enable aiplatform.googleapis.com --project demo-project-01')
 def test_no_auth(self):
  d,r=diagnose_live(1,'Please set an Auth method in your settings.json',False,{});self.assertIn('Aucune authentification',d)
 def test_timeout_model_loop(self):
  d,r=diagnose_live(None,'Model fallback activated: switching from gemini-3.8-flash',True,S_KEY);self.assertIn('boucle',d);self.assertIn('gemini-2.5-flash',r)
 def test_403_iam(self):
  d,r=diagnose_live(1,'status: 403 PERMISSION_DENIED',False,S_KEY);self.assertIn('IAM',d)
 def test_unknown(self):
  d,r=diagnose_live(1,'something odd',False,S_KEY);self.assertIn('pas comme attendu',d)
if __name__=='__main__':unittest.main()

import contextlib, io, json, tempfile
from pathlib import Path
from installer.cli import apply
from installer.core import KitError, read_json
class VertexConfigTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def overrides(self,v):
  p=self.home/'.ai-toolkit/overrides.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v),encoding='utf-8')
 def run_kit(self):
  with contextlib.redirect_stdout(io.StringIO()):apply('data-analyst',self.home)
 def test_vertex_configured_end_to_end(self):
  e=self.home/'.gemini/.env';e.parent.mkdir(parents=True);e.write_text('PERSO=1\nGOOGLE_CLOUD_PROJECT=ancien\n')
  self.overrides({'vertex':{'project':'demo-project-01','location':'europe-west1'}});self.run_kit()
  self.assertEqual(read_json(self.home/'.gemini/settings.json')['security']['auth']['selectedType'],'vertex-ai')
  text=e.read_text();self.assertIn('PERSO=1',text);self.assertIn('GOOGLE_CLOUD_PROJECT=demo-project-01',text);self.assertNotIn('ancien',text);self.assertIn('GOOGLE_GENAI_USE_VERTEXAI=true',text);self.assertIn('GOOGLE_CLOUD_LOCATION=europe-west1',text)
  self.run_kit();self.assertEqual(e.read_text().count('GOOGLE_CLOUD_PROJECT'),1)
 def test_no_vertex_leaves_auth_alone(self):
  self.run_kit();self.assertNotIn('security',read_json(self.home/'.gemini/settings.json'));self.assertFalse((self.home/'.gemini/.env').exists())
 def test_invalid_vertex_refused(self):
  self.overrides({'vertex':{'project':'Bad Project!'}})
  with self.assertRaises(KitError):self.run_kit()
 def test_model_override_sets_model_name(self):
  self.overrides({'model':'gemini-2.5-flash'});self.run_kit()
  self.assertEqual(read_json(self.home/'.gemini/settings.json')['model']['name'],'gemini-2.5-flash')
 def test_no_model_imposed_by_default(self):
  self.run_kit();self.assertNotIn('model',read_json(self.home/'.gemini/settings.json'))
 def test_invalid_model_refused(self):
  self.overrides({'model':'pas un modèle'})
  with self.assertRaises(KitError):self.run_kit()
 def test_code_assist_project(self):
  self.overrides({'code_assist':{'project':'demo-project-01'}});self.run_kit()
  self.assertEqual(read_json(self.home/'.gemini/settings.json')['security']['auth']['selectedType'],'oauth-personal')
  text=(self.home/'.gemini/.env').read_text();self.assertIn('GOOGLE_CLOUD_PROJECT=demo-project-01',text);self.assertNotIn('VERTEXAI',text)
 def test_vertex_and_code_assist_exclusive(self):
  self.overrides({'vertex':{'project':'demo-project-01'},'code_assist':{'project':'demo-project-01'}})
  with self.assertRaises(KitError):self.run_kit()
 def test_switching_auth_replaces_kit_lines_only(self):
  e=self.home/'.gemini/.env';e.parent.mkdir(parents=True);e.write_text('PERSO=1\n')
  self.overrides({'vertex':{'project':'demo-project-01'}});self.run_kit()
  self.overrides({'code_assist':{'project':'demo-project-02'}});self.run_kit()
  text=e.read_text();self.assertIn('PERSO=1',text);self.assertNotIn('VERTEXAI',text);self.assertNotIn('demo-project-01',text);self.assertEqual(text.count('# ai-kit'),1)
  self.overrides({});self.run_kit();self.assertEqual(e.read_text(),'PERSO=1\n')
 def test_code_assist_project_required_diagnosis(self):
  d,r=diagnose_live(1,'This account requires setting the GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_PROJECT_ID env var.',False,{});self.assertIn('Code Assist',d);self.assertIn('code_assist',r)
 def test_vertex_missing_project_diagnosis(self):
  d,r=diagnose_live(41,'When using Vertex AI, you must specify either: GOOGLE_CLOUD_PROJECT',False,{});self.assertIn('sans projet',d);self.assertIn('overrides.json',r)
