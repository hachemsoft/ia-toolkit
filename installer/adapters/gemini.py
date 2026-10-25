"""Adaptateur Gemini CLI : couches dans ~/.gemini, skills, commandes TOML, agents, réglages, authentification, journaux."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from typing import Optional

from ..interface import DoctorContext, Plan, Status
from ..core import (ROOT, START, END, EMAIL, USER_CONTEXT, CONTEXT_NAME, PROJECT_ID, KitError, read_json, json_bytes,
                    digest, merge_defaults, run_timed,
                    record_auto_friction, _ts)

PROJECT_CONTEXT = ('GEMINI.md', 'AGENTS.md')  # fichiers de contexte de repo que Gemini doit lire

ENV_MARKER = '# ai-kit : '

ENV_KEYS = ('GOOGLE_GENAI_USE_VERTEXAI', 'GOOGLE_CLOUD_PROJECT', 'GOOGLE_CLOUD_LOCATION')

def env_text(env_file, managed):
    """Contenu de ~/.gemini/.env : les lignes de l'utilisateur sont conservées, les lignes du kit (marqueur + variables gérées) remplacées ou retirées."""
    lines = env_file.read_text(encoding='utf-8').splitlines() if env_file.exists() else []
    kept = [line for line in lines if line.split('=',1)[0].strip() not in ENV_KEYS and not line.strip().startswith(ENV_MARKER)]
    if managed is not None:
        label, variables = managed
        kept += [ENV_MARKER + label + ' (géré par le kit, modifier overrides.json)'] + [k+'='+v for k,v in variables.items()]
    if not kept and not lines:
        return None
    return '\n'.join(kept) + '\n' if kept else ''

def merge_context_filenames(settings, managed=(), retired=()):
    """Garantir le contexte du kit et du projet, sans retirer les fichiers personnels ; retirer les couches que le kit gérait et ne produit plus."""
    context = settings.setdefault('context', {})
    if not isinstance(context, dict):
        raise KitError('context doit être un objet ; configuration laissée intacte.')
    names = context.get('fileName', [])
    if isinstance(names, str):
        names = [names]
    if not isinstance(names, list) or not all(isinstance(name, str) and name.strip() for name in names):
        raise KitError('context.fileName doit être un nom ou une liste de noms non vides ; configuration laissée intacte.')
    stale = set(retired) - set(managed)
    context['fileName'] = list(dict.fromkeys(list(managed) + [USER_CONTEXT] + list(PROJECT_CONTEXT) + [n for n in names if n not in stale]))
    return settings

def context_parts(text):
    if START not in text and END not in text:
        return text, None, ''
    if text.count(START) != 1 or text.count(END) != 1:
        raise KitError('Marqueurs du kit invalides dans GEMINI.md.')
    before, rest = text.split(START)
    managed, after = rest.split(END)
    return before, START+managed+END, after

def gemini_active_account(home):
    """Compte Google actif de Gemini, ou None. Lecture seule, jamais les jetons."""
    path = home/'.gemini/google_accounts.json'
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError, OSError):
        return None
    active = value.get('active') if isinstance(value, dict) else None
    return active if isinstance(active, str) and EMAIL.fullmatch(active) else None

def gemini_command_toml(command):
    """Adaptateur Gemini CLI : fichier de commande TOML (description, prompt avec {{args}})."""
    return 'description = ' + json.dumps(command['description'], ensure_ascii=False) + '\n\nprompt = """\n' + command['prompt'] + '"""\n'

def kit_hook_groups(groups):
    """Indices des groupes de hooks posés par le kit dans une liste de settings."""
    return [i for i,g in enumerate(groups) if isinstance(g,dict) and any(isinstance(h,dict) and str(h.get('name','')).startswith('ai-kit-') for h in g.get('hooks',[]))]

LIVE_PROMPT = 'Réponds uniquement OK.'

def diagnose_live(returncode, output, timed_out, settings):
    """Un diagnostic en une phrase et le remède, à partir de la sortie d'un appel réel à Gemini."""
    if timed_out:
        return ('Gemini ne répond pas dans le délai : le modèle par défaut est probablement indisponible sur votre accès et Gemini boucle sur un repli.',
                'Fixer un modèle : "model": "gemini-2.5-flash" dans ~/.ai-kit/overrides.json puis update (ou model.name dans ~/.gemini/settings.json).')
    if 'prepayment credits are depleted' in output or ('402' in output and 'credits' in output):
        return ('Crédits AI Studio épuisés : la clé API configurée n’a plus de solde (HTTP 402).',
                'Recharger le projet AI Studio, ou passer en connexion Google (/auth dans gemini), ou en Vertex AI (selectedType vertex-ai, GOOGLE_GENAI_USE_VERTEXAI=true, GOOGLE_CLOUD_PROJECT).')
    if 'API Keys are Disallowed' in output or 'API keys are not supported' in output:
        return ('La politique de votre organisation Google Cloud interdit les clés API.',
                'Utiliser les identifiants applicatifs : gcloud auth application-default login, selectedType vertex-ai, et retirer GEMINI_API_KEY / GOOGLE_API_KEY de l’environnement.')
    if 'aiplatform.googleapis.com' in output and ('has not been used' in output or 'is disabled' in output):
        match = re.search(r'project=([a-z0-9-]+)', output)
        project = match.group(1) if match else os.environ.get('GOOGLE_CLOUD_PROJECT', '<projet>')
        return ('L’API Vertex AI n’est pas activée sur le projet ' + project + ' (HTTP 403).',
                'gcloud services enable aiplatform.googleapis.com --project ' + project)
    if 'When using Vertex AI, you must specify' in output:
        return ('Authentification Vertex AI sans projet ni région.',
                'Déclarer le projet dans ~/.ai-kit/overrides.json : "vertex": {"project": "<projet>", "location": "<région>"} puis update ; ou exporter GOOGLE_CLOUD_PROJECT et GOOGLE_CLOUD_LOCATION.')
    if 'requires setting the GOOGLE_CLOUD_PROJECT' in output:
        return ('Votre compte Gemini Code Assist (licence Standard ou Enterprise) exige un projet Google Cloud.',
                'Déclarer "code_assist": {"project": "<projet>"} dans ~/.ai-kit/overrides.json puis update ; ou exporter GOOGLE_CLOUD_PROJECT.')
    if 'Please set an Auth method' in output:
        return ('Aucune authentification Gemini configurée.',
                'Lancer gemini puis /auth, ou définir GEMINI_API_KEY, ou GOOGLE_GENAI_USE_VERTEXAI=true avec GOOGLE_CLOUD_PROJECT.')
    if re.search(r'status: 403|"code": 403', output):
        return ('Accès refusé par l’API (HTTP 403) : droit IAM manquant sur le projet ou le modèle.',
                'Demander le rôle Vertex AI User sur le projet à son administrateur.')
    if re.search(r'status: 401|"code": 401', output):
        return ('Authentification refusée (HTTP 401).', 'Relancer /auth dans gemini ; si vous utilisez Vertex, gcloud auth application-default login.')
    if re.search(r'status: 429|"code": 429|RESOURCE_EXHAUSTED', output):
        return ('Quota dépassé (HTTP 429).', 'Attendre, ou demander un quota supérieur sur le projet.')
    if returncode == 0 and 'OK' in output:
        return (None, None)
    return ('Gemini a répondu mais pas comme attendu (code ' + str(returncode) + ').', 'Lire la sortie complète : gemini --debug -p "' + LIVE_PROMPT + '"')

def parse_env_file(path):
    """Lecture d'un fichier .env à la façon de dotenv : `export` ignoré, guillemets retirés, commentaire de fin de ligne hors guillemets ignoré."""
    values = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            continue
        if value[:1] in ('"', "'") and value.find(value[0], 1) > 0:
            value = value[1:value.find(value[0], 1)]
        else:
            value = value.split(' #', 1)[0].rstrip()
        values[key] = value
    return values

def live_check(home, timeout=90):
    """Appel réel au modèle depuis un dossier vide. Retourne (ok, diagnostic, remède)."""
    settings = read_json(home/'.gemini/settings.json')
    warnings = []
    # Même lecture que Gemini (dotenv) : l'environnement du shell l'emporte sur ~/.gemini/.env ; rien n'est écrit dans os.environ.
    env = dict(os.environ)
    for key, value in parse_env_file(home/'.gemini/.env').items():
        env.setdefault(key, value)
    auth = (settings.get('security') or {}).get('auth', {}).get('selectedType')
    if auth == 'gemini-api-key' and env.get('GOOGLE_GENAI_USE_VERTEXAI', '').lower() in ('true', '1', 'yes'):
        warnings.append('selectedType vaut gemini-api-key : les variables Vertex de l’environnement sont ignorées. Passer selectedType à vertex-ai pour utiliser Vertex.')
    if auth == 'vertex-ai' and not env.get('GOOGLE_CLOUD_PROJECT'):
        warnings.append('selectedType vaut vertex-ai sans GOOGLE_CLOUD_PROJECT dans l’environnement.')
    if auth == 'vertex-ai' and (env.get('GEMINI_API_KEY') or env.get('GOOGLE_API_KEY')):
        warnings.append('Une clé API est présente dans l’environnement alors que l’authentification est Vertex : retirer GEMINI_API_KEY / GOOGLE_API_KEY si l’organisation interdit les clés.')
    if not shutil.which('gemini'):
        return False, 'Gemini CLI absent du PATH.', 'Installer Gemini CLI selon la procédure IT.', warnings
    model = (settings.get('model') or {}).get('name')
    with tempfile.TemporaryDirectory() as tmp:
        command = ['gemini', '--approval-mode', 'plan', '--skip-trust'] + (['-m', model] if model else []) + ['-p', LIVE_PROMPT]
        try:
            proc = run_timed(command, timeout, cwd=tmp, text=True, encoding='utf-8', stdin=subprocess.DEVNULL, env=env)
            output, code, timed_out = proc.stdout + '\n' + proc.stderr, proc.returncode, False
        except subprocess.TimeoutExpired as exc:
            def text(v):
                return v.decode('utf-8', 'replace') if isinstance(v, bytes) else (v or '')
            output, code, timed_out = text(exc.stdout) + '\n' + text(exc.stderr), None, True
        except OSError as exc:
            return False, 'Impossible de lancer gemini : ' + str(exc), 'Vérifier l’installation de Gemini CLI.', warnings
    diagnostic, remedy = diagnose_live(code, output, timed_out, settings)
    return diagnostic is None, diagnostic, remedy, warnings

def print_live(home, timeout=90):
    ok, diagnostic, remedy, warnings = live_check(home, timeout)
    for warning in warnings:
        print('[À vérifier] '+warning)
    if ok:
        print('[OK] Appel réel au modèle : Gemini répond.')
        return 0
    print('[À vérifier] '+diagnostic)
    print('           Remède : '+remedy)
    record_auto_friction(home, diagnostic, 'gemini')
    return 1

# --- Interface d'adaptateur ---------------------------------------------------------------------------------------
NAME = 'gemini'
LABEL = 'Gemini CLI'
COMMAND = 'gemini'
HOME_DIR = '.gemini'
MANAGED_PREFIXES = ('.gemini/skills/', '.gemini/agents/', '.gemini/commands/', '.gemini/hooks/ai-kit/')  # le dernier : ancien emplacement des garde-fous

# Commandes intégrées : ne comptent pas comme commandes inconnues dans le relevé d'usage.
BUILTIN_COMMANDS = {'about','agents','auth','bug','chat','clear','commands','compress','copy','corgi','directory','docs','editor','extensions','help','hooks','ide','init','mcp','memory','model','permissions','plan','planning','policies','privacy','quit','exit','restore','resume','settings','setup-github','skills','stats','terminal-setup','theme','tools','vim','config','diff','keybindings','remote-control','login','logout'}

def present(home):
    return bool(shutil.which(COMMAND)) or (home/HOME_DIR/'settings.json').is_file()

def context_dir(home):
    """Gemini n'importe que des fichiers situés dans ~/.gemini (vérifié sur 0.65) : quand il est installé, il héberge les couches et 30_USER.md."""
    return home/HOME_DIR

def is_managed(rel):
    """Chemin qu'une installation du kit a pu poser pour Gemini, donc qu'il peut retirer s'il est intact."""
    if rel.startswith(MANAGED_PREFIXES):
        return True
    return rel.startswith('.gemini/') and bool(CONTEXT_NAME.fullmatch(rel[len('.gemini/'):])) and rel != '.gemini/'+USER_CONTEXT

def active_account(home):
    return gemini_active_account(home)

def install(p: Plan) -> None:
    """Skills, commandes TOML et agents dans ~/.gemini ; les couches y sont déjà, écrites par l'orchestrateur."""
    gemini = p.home/'.gemini'
    # Bloc hérité des versions 0.0.x dans GEMINI.md : retiré s'il est intact.
    context_file = gemini/'GEMINI.md'
    if context_file.exists():
        old_context = context_file.read_text(encoding='utf-8')
        before, old_block, after = context_parts(old_context)
        if old_block is not None:
            if p.state.get('context_hash') != digest(old_block.encode()):
                raise KitError('Bloc du kit modifié ou non reconnu dans GEMINI.md. Déplacer vos changements vers '+str(p.user_file)+' puis retirer le bloc entre les marqueurs ai-kit avant update.')
            remaining = (before.rstrip('\n')+'\n\n'+after.lstrip('\n')).strip('\n')
            if remaining:
                p.writes[context_file] = (remaining+'\n').encode('utf-8')
            else:
                p.deletes.append(context_file)
    write_skills(p)
    for command in p.commands:
        p.managed_write(gemini/'commands'/(command['name']+'.toml'), gemini_command_toml(command).encode('utf-8'), 'Commande')
    for agent, definition in p.agents:
        name = 'ai-kit-'+agent
        data = agent_markdown(p, agent, definition)
        p.managed_write(gemini/'agents'/(name+'.md'), data, 'Agent')
        p.agent_markdown[name] = data

def write_skills(p: Plan) -> None:
    """Skills du profil dans ~/.gemini/skills, dossier lu par Gemini et par agy."""
    for skill, source in p.skill_sources:
        for src in source.rglob('*'):
            if src.is_file():
                p.managed_write(p.home/'.gemini'/'skills'/skill/src.relative_to(source), src.read_bytes(), 'Skill')

def agent_markdown(p: Plan, agent: str, definition: dict) -> bytes:
    """Agent au format Markdown à frontmatter, commun à Gemini et agy."""
    agent_defaults = read_json(ROOT/'agents/defaults.json')
    capability = definition.get('capability', 'default')
    # Les identifiants sont des slugs validés ; JSON string est aussi une chaîne YAML valide.
    header = ['---', 'name: ai-kit-'+agent, 'description: '+json.dumps(definition['description'], ensure_ascii=False),
              'kind: local', 'tools: '+json.dumps(definition.get('tools', agent_defaults['tools'])),
              'max_turns: '+str(definition.get('max_turns', agent_defaults['max_turns']))]
    header += (['model: '+p.models[capability]] if capability in p.models else [])
    header += ['timeout_mins: '+str(definition.get('timeout_mins', agent_defaults['timeout_mins'])), '---']
    return ('\n'.join(header)+'\n\n'+p.agent_body(definition)).encode('utf-8')

def finalize(p: Plan, active: bool = True) -> None:
    """Réglages ~/.gemini/settings.json (défauts, authentification déclarée, couches, garde-fous, MCP) et ~/.gemini/.env."""
    if not active:
        return
    gemini = p.home/'.gemini'
    overrides, state = p.overrides, p.state
    settings_file = gemini/'settings.json'
    settings = read_json(settings_file)
    merge_defaults(settings, read_json(Path(__file__).resolve().parent/'gemini_defaults.json'))
    # Authentification : le kit ne la touche que sur déclaration explicite dans overrides.json (vertex ou code_assist).
    vertex, code_assist, model = overrides.get('vertex'), overrides.get('code_assist'), overrides.get('model')
    if vertex is not None and code_assist is not None:
        raise KitError('overrides.json : déclarer vertex ou code_assist, pas les deux.')
    if model is not None:
        if not isinstance(model, str) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,60}', model):
            raise KitError('model doit être un nom de modèle Gemini, par exemple gemini-2.5-flash.')
        settings.setdefault('model', {})['name'] = model
    env_managed = None
    if vertex is not None:
        if not isinstance(vertex, dict) or not isinstance(vertex.get('project'), str) or not re.fullmatch(PROJECT_ID, vertex['project']):
            raise KitError('vertex.project doit être un identifiant de projet Google Cloud.')
        location = vertex.get('location', 'us-central1')
        if not isinstance(location, str) or not re.fullmatch(r'[a-z0-9-]+|global', location):
            raise KitError('vertex.location invalide.')
        settings.setdefault('security', {}).setdefault('auth', {})['selectedType'] = 'vertex-ai'
        env_managed = ('Vertex AI', {'GOOGLE_GENAI_USE_VERTEXAI': 'true', 'GOOGLE_CLOUD_PROJECT': vertex['project'], 'GOOGLE_CLOUD_LOCATION': location})
    elif code_assist is not None:
        if not isinstance(code_assist, dict) or not isinstance(code_assist.get('project'), str) or not re.fullmatch(PROJECT_ID, code_assist['project']):
            raise KitError('code_assist.project doit être un identifiant de projet Google Cloud.')
        settings.setdefault('security', {}).setdefault('auth', {})['selectedType'] = 'oauth-personal'
        env_managed = ('Gemini Code Assist', {'GOOGLE_CLOUD_PROJECT': code_assist['project']})
    env_file = gemini/'.env'
    if env_managed is not None or (env_file.exists() and ENV_MARKER in env_file.read_text(encoding='utf-8')):
        content = env_text(env_file, env_managed)
        if content == '' and env_file.exists():
            p.deletes.append(env_file)
        elif content:
            p.writes[env_file] = content.encode('utf-8')
    retired = [rel.split('/',1)[1] for rel in p.old_files if re.fullmatch(r'\.gemini/\d\d_[A-Z_]+\.md', rel)]
    merge_context_filenames(settings, p.context_names, retired)
    original_hooks = settings.get('hooks')
    if original_hooks is not None and not isinstance(original_hooks, dict):
        raise KitError('hooks doit être un objet dans settings.json.')
    original_hooks = original_hooks or {}
    old_hooks = state.get('hooks', {})
    for name, old in old_hooks.items():
        groups = original_hooks.get(old['event'], [])
        if not isinstance(groups, list):
            raise KitError('settings.json : hooks.'+old['event']+' doit être une liste.')
        for i in kit_hook_groups(groups):
            if any(h.get('name') == 'ai-kit-'+name for h in groups[i].get('hooks', [])) and groups[i] != old['group']:
                raise KitError('Garde-fou du kit modifié dans settings.json : '+name)
    merged_hooks = {}
    for event, groups in original_hooks.items():
        if not isinstance(groups, list):
            merged_hooks[event] = groups
            continue
        kept = [g for i, g in enumerate(groups) if i not in kit_hook_groups(groups)]
        if kept or not groups:
            merged_hooks[event] = kept
    for name, spec in p.enabled_hooks.items():
        merged_hooks.setdefault(spec['event'], []).append(spec['group'])
    if merged_hooks or ('hooks' in settings and not any(kit_hook_groups(g) for g in original_hooks.values() if isinstance(g, list))):
        settings['hooks'] = merged_hooks
    else:
        settings.pop('hooks', None)
    servers = settings.get('mcpServers',{})
    if not isinstance(servers,dict):
        raise KitError('mcpServers doit être un objet.')
    old_mcp = state.get('mcp',{})
    for name,old in old_mcp.items():
        if name in servers and servers[name] != old:
            raise KitError('MCP du kit modifié dans settings.json : '+name)
        servers.pop(name,None)
    for name,server in p.enabled_mcp.items():
        if name in servers and servers[name] != server:
            raise KitError('Nom de MCP déjà utilisé : '+name)
        servers[name] = server
    if servers or 'mcpServers' in settings:
        settings['mcpServers'] = servers
    p.writes[settings_file] = json_bytes(settings)

def summary(p: Plan) -> Optional[str]:
    return None

def skill_description_weight(home, skill_names):
    """Octets de descriptions injectés par Gemini à chaque tour pour les skills installés."""
    total = 0
    for name in skill_names:
        path = home/'.gemini/skills'/name/'SKILL.md'
        if not path.is_file():
            continue
        match = re.search(r'^description:\s*(.+?)\s*$', path.read_text(encoding='utf-8'), re.M)
        total += len((match.group(1) if match else '').encode('utf-8')) + len(name)
    return total

def installed_skills(home, state):
    names = sorted({rel.split('/')[2] for rel in state.get('files',{}) if rel.startswith('.gemini/skills/')})
    return [s for s in names if (home/'.gemini/skills'/s/'SKILL.md').is_file()]

def doctor(home: Path, state: dict, status: Status, ctx: DoctorContext) -> None:
    """Contrôles propres à Gemini : exécutable, compte actif, contexte personnel, commandes, skills masqués, réglages."""
    status(bool(shutil.which(COMMAND)),'Gemini CLI dans le PATH. Si absent : suivre la procédure IT approuvée.')
    active = gemini_active_account(home)
    identity = state.get('user', {})
    if active:
        status(not identity.get('email') or active.lower() == identity['email'].lower(),'Compte Gemini actif identique à l’identité enregistrée : '+active)
        status(ctx.domain_allowed(active, ctx.allowed_domains()),'Compte Gemini actif dans les domaines autorisés')
    else:
        print('[Info] Aucun compte Gemini actif détecté (non connecté, ou mode clé API / Vertex).')
    skills = installed_skills(home, state)
    installed_commands = sorted(rel.split('/')[2][:-5] for rel in state.get('files',{}) if rel.startswith('.gemini/commands/'))
    by_name = {c['name']: c for c in ctx.load_commands()}
    for name in installed_commands:
        missing = [s for s in by_name.get(name,{}).get('skills',[]) if s not in skills]
        status(name in by_name and not missing,'Commande /'+name+' : skills présents'+(' (manque '+', '.join(missing)+')' if missing else ''))
    print('[Info] '+str(len(skills))+' skills, '+str(len(installed_commands))+' commandes ; descriptions de skills injectées à chaque tour : '+str(skill_description_weight(home, skills))+' octets.')
    shadowed = [s for s in skills if (home/'.agents/skills'/s/'SKILL.md').is_file()]
    status(not shadowed,'Aucun skill du kit masqué par une copie dans ~/.agents/skills'+(' (masqués : '+', '.join(shadowed)+')' if shadowed else ''))
    legacy = home/'.gemini/GEMINI.md'
    status(not legacy.exists() or START not in legacy.read_text(encoding='utf-8'),'Aucun bloc hérité du kit dans GEMINI.md')
    settings = read_json(home/'.gemini/settings.json')
    names = settings.get('context',{}).get('fileName',[])
    names = [names] if isinstance(names,str) else names
    expected_names = ctx.managed_context_names(ctx.profile)+[USER_CONTEXT]+list(PROJECT_CONTEXT)
    status(isinstance(names,list) and all(n in names for n in expected_names),'context.fileName contient les couches du kit, GEMINI.md et AGENTS.md')
    status(settings.get('skills',{}).get('enabled',True) is not False,'Skills non désactivés dans les settings utilisateur')
    agents_enabled = settings.get('experimental',{}).get('enableAgents',True) is not False
    status(agents_enabled,'Agents non désactivés dans les settings utilisateur')
    if not agents_enabled:
        catalog = read_json(ROOT/'skills/catalog.json')
        needing = sorted(s for s in skills if catalog.get(s,{}).get('needs_agents'))
        if needing:
            print('[Info] Skills qui délèguent à des sous-agents, dégradés sans eux : '+', '.join(needing))
    for name,hook in state.get('hooks',{}).items():
        groups = (settings.get('hooks') or {}).get(hook['event'], [])
        script = Path(hook['group']['hooks'][0]['command'].split()[-1].strip('"\''))
        status(isinstance(groups,list) and hook['group'] in groups and script.is_file(),'Garde-fou actif : '+name)
    if not state.get('hooks'):
        print('[Info] Aucun garde-fou activé ; voir docs/hooks.md (dbt-prod-guard, protected-paths).')
    for name,server in state.get('mcp',{}).items():
        status(settings.get('mcpServers',{}).get(name)==server,'Configuration MCP : '+name)
        if server.get('command'):
            status(bool(shutil.which(server['command'])),'Exécutable MCP disponible : '+name)

def doctor_hint():
    return 'Gemini : vérifier /memory show, /mcp et /skills list dans Gemini.'

def live(home):
    """Appel réel au modèle, avec diagnostic et remède ; 0 si Gemini répond."""
    return print_live(home)

def installed_from_files(state):
    """État écrit avant la 0.17 : les noms installés se déduisent des chemins Gemini enregistrés."""
    files = state.get('files', {})
    return {'skills': sorted({rel.split('/')[2] for rel in files if rel.startswith('.gemini/skills/')}),
            'commands': sorted(rel.split('/')[2][:-5] for rel in files if rel.startswith('.gemini/commands/')),
            'agents': sorted(rel.split('/')[2][:-3] for rel in files if rel.startswith('.gemini/agents/'))}

def session_logs(home):
    return sorted((home/'.gemini/tmp').glob('*/chats/*.json')) if (home/'.gemini/tmp').is_dir() else []

def history(home, state):
    """Événements d'usage lus dans les journaux de session Gemini : prompts, skills activés, agents appelés, erreurs."""
    for path in session_logs(home):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        messages = data.get('messages', []) if isinstance(data, dict) else []
        session = 'gemini:'+str(path)
        for m in messages:
            if not isinstance(m, dict) or not str(m.get('timestamp',''))[:19]:
                continue
            ts = _ts(m.get('timestamp'))
            if m.get('type') == 'user':
                shown = str(m.get('displayContent') or m.get('content') or '')
                stripped = shown.strip()
                if stripped.startswith("[{'text': '"):
                    stripped = stripped[len("[{'text': '"):]
                yield {'kind': 'prompt', 'session': session, 'ts': ts, 'text': stripped}
            elif m.get('type') == 'error':
                yield {'kind': 'error', 'session': session, 'ts': ts}
            elif m.get('type') == 'gemini':
                yield {'kind': 'activity', 'session': session, 'ts': ts}
                for call in m.get('toolCalls', []) or []:
                    name = call.get('name', '')
                    if name == 'activate_skill':
                        yield {'kind': 'skill', 'session': session, 'ts': ts, 'name': str((call.get('args') or {}).get('name',''))}
                    elif name.startswith('ai-kit-'):
                        yield {'kind': 'agent', 'session': session, 'ts': ts, 'name': name}
            else:
                yield {'kind': 'activity', 'session': session, 'ts': ts}
