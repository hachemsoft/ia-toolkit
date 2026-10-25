import contextlib, io, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
from installer import cli
from installer.cli import apply, doctor, detect_identity, directory_profile
from installer.core import read_json, ROOT
class IdentityTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
 def write(self,p,text):
  f=self.home/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text,encoding='utf-8');return f
 def run_kit(self,role='data-analyst',user=None):
  with contextlib.redirect_stdout(io.StringIO()):apply(role,self.home,False,user)
 def test_gemini_active_account_first(self):
  self.write('.gemini/google_accounts.json',json.dumps({'active':'prenom.nom@societe.fr','old':[]}))
  self.write('.gitconfig','[user]\n\temail = autre@exemple.org\n\tname = Prénom Nom\n')
  identity=detect_identity(self.home);self.assertEqual(identity['email'],'prenom.nom@societe.fr');self.assertEqual(identity['source'],'gemini')
  if shutil.which('git'):self.assertEqual(identity.get('name'),'Prénom Nom')
 @unittest.skipUnless(shutil.which('git'),'git requis')
 def test_git_fallback_when_gemini_inactive(self):
  self.write('.gemini/google_accounts.json',json.dumps({'active':None,'old':['x@y.z']}))
  self.write('.gitconfig','[user]\n\temail = prenom.nom@societe.fr\n\tname = Prénom Nom\n')
  identity=detect_identity(self.home);self.assertEqual(identity,{'email':'prenom.nom@societe.fr','name':'Prénom Nom','source':'git'})
 def test_os_fallback(self):
  with mock.patch.object(cli,'git_identity',return_value={}):identity=detect_identity(self.home)
  self.assertEqual(identity.get('source'),'os');self.assertNotIn('email',identity)
 def test_header_written_once(self):
  self.run_kit(user={'email':'prenom.nom@societe.fr','name':'Prénom Nom','source':'option'})
  u=self.home/'.gemini/30_USER.md';self.assertIn('Personne : Prénom Nom <prenom.nom@societe.fr>',u.read_text(encoding='utf-8'))
  self.assertEqual(read_json(self.home/'.ai-kit/state.json')['user']['email'],'prenom.nom@societe.fr')
  self.run_kit(user={'email':'autre@societe.fr','source':'option'})
  self.assertIn('prenom.nom@societe.fr',u.read_text(encoding='utf-8'));self.assertEqual(read_json(self.home/'.ai-kit/state.json')['user']['email'],'autre@societe.fr')
 def test_no_identity_no_header(self):
  self.run_kit();text=(self.home/'.gemini/30_USER.md').read_text(encoding='utf-8');self.assertNotIn('Personne :',text);self.assertNotIn('{identity}',text)
 def test_invalid_email_refused(self):
  with self.assertRaises(cli.KitError):self.run_kit(user={'email':'pas-un-email','source':'option'})
 def test_cli_user_option_non_interactive(self):
  proc=subprocess.run([sys.executable,'-m','installer','setup','--profile','data-analyst','--user','prenom.nom@societe.fr','--home',str(self.home),'--no-live'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',stdin=subprocess.DEVNULL,env={**os.environ,'PYTHONIOENCODING':'utf-8'})
  self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr);self.assertIn('Identité : prenom.nom@societe.fr (source option)',proc.stdout)
  self.assertEqual(read_json(self.home/'.ai-kit/state.json')['user']['source'],'option')
 def test_directory_suggests_profile(self):
  fake={'emails':{'dev@societe.fr':'data-developer'}}
  real=cli.read_json
  def patched(path,default=None):return fake if path.name=='directory.json' else real(path,default)
  with mock.patch.object(cli,'read_json',side_effect=patched):
   self.assertEqual(directory_profile('Dev@societe.fr'),'data-developer');self.assertIsNone(directory_profile('inconnu@societe.fr'));self.assertIsNone(directory_profile(None))
 def test_directory_profile_used_non_interactive(self):
  fake={'emails':{'dev@societe.fr':'data-developer'}}
  real=cli.read_json
  def patched(path,default=None):return fake if path.name=='directory.json' else real(path,default)
  with mock.patch.object(cli,'read_json',side_effect=patched), mock.patch.object(sys.stdin,'isatty',return_value=False), contextlib.redirect_stdout(io.StringIO()):
   code=cli.main(['setup','--user','dev@societe.fr','--home',str(self.home),'--no-live'])
  self.assertEqual(code,0);self.assertEqual(read_json(self.home/'.ai-kit/state.json')['profile'],'data-developer')
 def test_doctor_domain_and_mismatch_warnings(self):
  self.run_kit(user={'email':'prenom.nom@societe.fr','source':'option'})
  self.write('.gemini/google_accounts.json',json.dumps({'active':'perso@gmail.com','old':[]}))
  out=io.StringIO()
  with mock.patch.object(cli,'allowed_domains',return_value=['societe.fr']), contextlib.redirect_stdout(out):code=doctor(self.home)
  text=out.getvalue();self.assertEqual(code,1);self.assertIn('[À vérifier] Compte Gemini actif identique',text);self.assertIn('[À vérifier] Compte Gemini actif dans les domaines autorisés',text)
 def test_doctor_domain_ok(self):
  self.run_kit(user={'email':'prenom.nom@societe.fr','source':'option'})
  self.write('.gemini/google_accounts.json',json.dumps({'active':'prenom.nom@societe.fr','old':[]}))
  out=io.StringIO()
  with mock.patch.object(cli,'allowed_domains',return_value=['societe.fr']), contextlib.redirect_stdout(out):doctor(self.home)
  self.assertIn('[OK] Compte Gemini actif identique',out.getvalue());self.assertIn('[OK] Compte Gemini actif dans les domaines autorisés',out.getvalue())
if __name__=='__main__':unittest.main()
