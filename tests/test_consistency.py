import re, unittest
from pathlib import Path
from installer.cli import allowed_commands
from installer.core import ROOT, read_json, load_commands, parse_frontmatter
from installer.adapters.gemini import gemini_command_toml, parse_env_file
import tempfile

class ConsistencyTests(unittest.TestCase):
 """Cohérence produit vérifiée en continu : profils, tiers, commandes, termes interdits, dépendances Python."""
 def setUp(self):
  self.cat=read_json(ROOT/'skills/catalog.json');self.cmds=load_commands()
  self.profiles={p.stem:read_json(p) for p in (ROOT/'profiles').glob('*.json') if p.stem!='directory'}
 def test_core_tier_installed_in_every_profile(self):
  for n,e in self.cat.items():
   if e.get('tier')=='core' and not e.get('replaced_by'):
    for pid,p in self.profiles.items():self.assertIn(n,p['skills'],n+' est core mais absent du profil '+pid)
 def test_command_prompts_only_cite_installed_playbooks(self):
  for pid,p in self.profiles.items():
   installed=[c for c in self.cmds if all(s in p['skills'] for s in c['skills']) and (not p.get('commands') or c['name'] in p['commands'])]
   for c in installed:
    text=c['prompt']
    for s,tail in re.findall(r'follow (?:the )?([a-z0-9-]+)(?: skill)?([^;.]*)',text):
     if s in self.cat and 'if installed' not in tail:self.assertIn(s,p['skills'],'/'+c['name']+' cite '+s+' absent du profil '+pid)
 def test_commands_cited_by_guide_exist(self):
  text=(ROOT/'skills/internal/common/guide/SKILL.md').read_text(encoding='utf-8');names={c['name'] for c in self.cmds}
  for m in set(re.findall(r'`/([a-z]+)',text)):self.assertIn(m,names,'/'+m)
 def test_no_upstream_author_or_internal_names(self):
  for f in ROOT.rglob('*'):
   if f.is_file() and f.suffix in ('.md','.json','.toml','.py','.sh','.ps1','.yml') and 'dist' not in f.parts and '.codegraph' not in f.parts and f.name!='LICENSE-UPSTREAM-MIT':
    t=f.read_text(encoding='utf-8',errors='replace').lower()
    for term in ('po'+'cock','ask-'+'matt','setup-'+'matt'):self.assertNotIn(term,t,str(f))
 def test_contrib_skills_rules(self):
  for n,e in self.cat.items():
   if e.get('origin')=='contrib':
    self.assertTrue(e['path'].startswith('skills/contrib/'),n);self.assertEqual(e.get('tier'),'optional',n+' : un skill contribué est optional');self.assertTrue(e.get('owner'),n+' : owner requis')
   elif e.get('path','').startswith('skills/contrib/'):self.fail(n+' : sous skills/contrib mais origin != contrib')
  self.assertTrue((ROOT/'skills/contrib/README.md').is_file())
 def test_general_docs_do_not_name_a_cli(self):
  """Les pages générales parlent de « l'agent » et de « la CLI » ; le spécifique va dans docs/cli/ (tableaux et liens tolérés)."""
  # README.md n'en fait pas partie : c'est la page d'accueil, qui présente les CLI prises en charge.
  general=['docs/'+n for n in ('getting-started.md','workflow.md','tools.md','customization.md','project-context.md','usage-review.md','extending.md','pilote.md','contributing.md','skills-reference.md','hooks.md','agents.md','format.md','identity.md','mcp.md','troubleshooting.md','ca-coince.md','evals.md')]
  allowed=re.compile(r"cli/(gemini|matrice|agy|codex)|`gemini` ou `agy`|`gemini`, `agy` ou `codex`|gemini-2\.5|gemini-api-key|GEMINI_API_KEY|--cli gemini|\.gemini/protected-paths|Gemini CLI et Antigravity CLI|Gemini CLI, Antigravity CLI, Codex CLI|`~/\.gemini/` si Gemini CLI est installé",re.I)
  bad=[]
  for f in general:
   fence=False
   for i,line in enumerate((ROOT/f).read_text(encoding='utf-8').splitlines(),1):
    if line.strip().startswith('```'):fence=not fence;continue
    if fence or line.lstrip().startswith('|'):continue
    for word in ('gemini','antigravity','codex'):
     if word in line.lower() and not allowed.search(line):bad.append(f+':'+str(i))
  self.assertEqual(bad,[],'nommer la CLI dans docs/cli/ ou dans un tableau')
 def test_python_39_imports(self):
  for f in list((ROOT/'installer').glob('*.py'))+list((ROOT/'tests').glob('*.py'))+[ROOT/'evals/run.py']+list((ROOT/'runtime/hooks').glob('*.py')):
   self.assertNotRegex(f.read_text(encoding='utf-8'),r'^\s*(import|from)\s+(tomllib|zoneinfo\b.*|graphlib)',str(f))
 def test_generated_gemini_toml_is_valid(self):
  try:import tomllib
  except ImportError:self.skipTest('tomllib absent')
  for c in self.cmds:
   ref=tomllib.loads(gemini_command_toml(c))
   self.assertEqual(ref['description'],c['description'],c['name']);self.assertEqual(ref['prompt'],c['prompt'],c['name'])
 def test_pivot_frontmatter(self):
  meta,body=parse_frontmatter('---\nname: x\ndescription: "A: b, c"\nskills: [a, b]\norder: 10\n---\nBody\n')
  self.assertEqual(meta,{'name':'x','description':'A: b, c','skills':['a','b'],'order':10});self.assertEqual(body,'Body\n')
 def test_allowed_commands(self):
  names=['a','b','c']
  self.assertIsNone(allowed_commands(None,{},names));self.assertEqual(allowed_commands(None,{'disabled_commands':['b']},names),['a','c'])
  self.assertEqual(allowed_commands(['a'],{'extra_commands':['c','a'],'disabled_commands':['a']},names),['c'])
 def test_parse_env_file(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'.env';p.write_text('# c\nexport A="x y" # note\nB=plain # note\nC=\'q\'\n1BAD=z\nD=a=b\n',encoding='utf-8')
   self.assertEqual(parse_env_file(p),{'A':'x y','B':'plain','C':'q','D':'a=b'})
 def test_docs_links_resolve(self):
  for md in list(ROOT.glob('*.md'))+list((ROOT/'docs').glob('*.md')):
   for m in re.finditer(r'\]\(([^)#\s]+)(#[^)]*)?\)',md.read_text(encoding='utf-8')):
    link=m.group(1)
    if link.startswith(('http','mailto','~')) or ('.' not in link and '/' not in link):continue
    self.assertTrue((md.parent/link).exists(),str(md)+' → '+link)
if __name__=='__main__':unittest.main()
