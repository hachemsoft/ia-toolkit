"""Kit IA : orchestration de l'installation. Construit un plan neutre, puis chaque adaptateur (installer/adapters/) le traduit pour sa CLI.
Ne modifie aucun repo projet."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone

from .core import (_PACKAGE_DIR, ROOT, KIT_CONTEXT, USER_CONTEXT, EMAIL, KitError, read_json, json_bytes, digest,
                   safe_id, inside, quote_path, load_commands, _ts)
from .adapters import ADAPTERS
from .interface import ContextHost, DoctorContext, LiveCheck, Plan

def practice_file(practice_id):
    """Fichier source d'une pratique et nom du fichier de contexte produit."""
    safe_id(practice_id)
    matches = sorted((ROOT/'practices').glob('[0-9][0-9]-'+practice_id+'.md'))
    if len(matches) != 1:
        raise KitError('Pratique introuvable ou ambiguë : ' + practice_id)
    source = matches[0]
    return source, source.stem[:2]+'_'+practice_id.upper().replace('-','_')+'.md'

PROFILE_MENU = [('general', 'Général : le workflow et les outils, sans playbook métier'),
                ('java-developer', 'Développeur Java : Maven ou Gradle, Spring, JUnit'),
                ('devops', 'DevOps : Terraform, Kubernetes, Helm, pipelines CI/CD'),
                ('architect', 'Architecte : décisions d’architecture (ADR), conception, revue de design'),
                ('data-analyst', 'Data Analyst : SQL, dbt, BigQuery, indicateurs'),
                ('data-developer', 'Développeur Data : SQL, dbt et BigQuery, plus Python et JavaScript')]

def profile_ids():
    return sorted(p.stem for p in (ROOT/'profiles').glob('*.json') if p.stem != 'directory')

def managed_context_names(profile):
    names = [KIT_CONTEXT] + [practice_file(p)[1] for p in profile['practices']]
    if len(set(names)) != len(names):
        raise KitError('Préfixes de pratiques en double dans le profil.')
    return names

def validate_server(server):
    if not isinstance(server, dict):
        raise KitError('Configuration MCP : objet attendu.')
    transports = [key for key in ('command','httpUrl','url') if server.get(key)]
    if len(transports) != 1:
        raise KitError('MCP : choisir un seul transport command, httpUrl ou url.')
    key = transports[0]
    if not isinstance(server[key], str):
        raise KitError('MCP : transport de type texte attendu.')
    if key != 'command' and not server[key].startswith('https://'):
        raise KitError('MCP distant : URL HTTPS attendue.')
    if 'args' in server and (not isinstance(server['args'],list) or not all(isinstance(x,str) for x in server['args'])):
        raise KitError('MCP : args doit être une liste de chaînes.')
    # Ne jamais présélectionner la confiance automatique.
    if server.get('trust') is True:
        raise KitError('MCP : trust=true non pris en charge par ce kit.')
    return server

def git_identity(home):
    """Identité git globale lue dans le dossier personnel donné."""
    if not shutil.which('git'):
        return {}
    env = {**os.environ, 'HOME': str(home), 'USERPROFILE': str(home), 'XDG_CONFIG_HOME': str(home/'.config'), 'GIT_CONFIG_NOSYSTEM': '1'}
    result = {}
    for key in ('email','name'):
        try:
            proc = subprocess.run(['git','config','--global','--get','user.'+key], capture_output=True, text=True, encoding='utf-8', env=env, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return {}
        value = proc.stdout.strip()
        if proc.returncode == 0 and value:
            result[key] = value
    if 'email' in result and not EMAIL.fullmatch(result['email']):
        result.pop('email')
    return result

def detect_identity(home):
    """Identité déclarative : première source disponible. Jamais une authentification."""
    found = next(((a.NAME, a.active_account(home)) for a in ADAPTERS if a.active_account(home)), (None, None))
    git = git_identity(home)
    if found[1]:
        identity = {'email': found[1], 'source': found[0]}
        if git.get('name'):
            identity['name'] = git['name']
        return identity
    if git.get('email'):
        identity = {'email': git['email'], 'source': 'git'}
        if git.get('name'):
            identity['name'] = git['name']
        return identity
    try:
        login = getpass.getuser()
    except Exception:
        return {}
    return {'name': login, 'source': 'os'} if login else {}

def allowed_domains():
    value = read_json(ROOT/'profiles/directory.json').get('allowed_domains', [])
    if not isinstance(value, list) or not all(isinstance(x,str) and x for x in value):
        raise KitError('directory.json : allowed_domains doit être une liste de domaines.')
    return [x.lower().lstrip('@') for x in value]

def domain_allowed(email, domains):
    return not domains or email.rsplit('@',1)[-1].lower() in domains

def directory_profile(email):
    """Profil proposé par l'annuaire facultatif, ou None."""
    if not email:
        return None
    entries = read_json(ROOT/'profiles/directory.json').get('emails', {})
    if not isinstance(entries, dict):
        raise KitError('directory.json : emails doit être un objet.')
    profile = entries.get(email.lower())
    return safe_id(profile) if profile else None

def resolve_skills(profile, overrides, catalog, log=print):
    """Sélection finale : profil + extra, remplacements suivis, dépendances ajoutées, désactivations respectées."""
    disabled = set(overrides.get('disabled_skills', []))
    selected = []
    def add(name, via=None):
        safe_id(name)
        if name not in catalog:
            raise KitError('Skill inconnu : '+name)
        entry = catalog[name]
        if entry.get('replaced_by'):
            log('Skill remplacé : '+name+' → '+', '.join(entry['replaced_by']))
            for replacement in entry['replaced_by']:
                add(replacement, via)
            return
        if name in disabled:
            if via:
                raise KitError('Skill '+name+' désactivé dans overrides.json mais requis par '+via+'.')
            return
        if name in selected:
            return
        selected.append(name)
        for dependency in entry.get('requires', []):
            add(dependency, name)
    for name in list(profile['skills']) + list(overrides.get('extra_skills', [])):
        add(name)
    return selected

def allowed_commands(profile_commands, overrides, command_names):
    """Liste des commandes autorisées : celle du profil (ou toutes), plus extra_commands, moins disabled_commands ; None quand rien ne restreint."""
    extra, disabled = overrides.get('extra_commands', []), set(overrides.get('disabled_commands', []))
    if profile_commands is None and not disabled:
        return None
    base = list(profile_commands) if profile_commands is not None else list(command_names)
    return [c for c in base + [e for e in extra if e not in base] if c not in disabled]

def selected_commands(selected, manifest, allowed=None):
    """Commandes dont tous les skills sont installés, dans l'ordre du manifeste ; restreintes à la liste du profil si elle existe."""
    return [c for c in manifest if all(s in selected for s in c['skills']) and (allowed is None or c['name'] in allowed)]

def command_lines(commands):
    lines = []
    for category, title in (('workflow', 'Étapes'), ('tool', 'Outils')):
        names = [c for c in commands if c['category'] == category]
        if names:
            lines.append('### '+title)
            lines += ['- /'+c['name']+' — '+c['description'] for c in names]
    return '\n'.join(lines) if lines else '- Aucune commande installée.'

FRICTION_SIGNALS = 'la personne corrige ou annule ce que tu viens de faire ; une vérification est rouge après « c’est fait » ; elle abandonne ou repose la même demande ; tu contournes un skill ou un garde-fou ; la cérémonie était disproportionnée.'

def friction_rule(mode):
    """Section « Frictions » de 00_KIT.md selon overrides.json (frictions : propose par défaut, auto, off)."""
    if mode == 'off':
        return ''
    if mode == 'auto':
        return ('## Frictions\nNoter toi-même la friction, sans demander, en lançant le script de la commande `/friction`, puis le dire en une ligne et reprendre le travail, quand : '
                + FRICTION_SIGNALS + ' Une phrase factuelle, jamais le texte d’un prompt ni un secret.\n\n')
    return '## Frictions\nProposer en une ligne de noter `/friction` (sans l’écrire soi-même) quand : ' + FRICTION_SIGNALS + '\n\n'

def playbook_lines(selected, catalog):
    names = [s for s in selected if catalog[s].get('category') == 'domain']
    return '\n'.join('- '+s+' : '+catalog[s]['description'] for s in names) if names else '- Aucun playbook métier installé.'

def user_context_text(identity):
    template = (ROOT/'templates/user-context.md').read_text(encoding='utf-8')
    parts = [identity.get('name'), '<'+identity['email']+'>' if identity.get('email') else None]
    line = ' '.join(p for p in parts if p)
    return template.replace('{identity}\n', 'Personne : '+line+'\n' if line else '')


AGENT_INSTRUCTION = ('Lire les instructions et le contexte du repo courant. Ne pas supposer que les skills, '
                     'les outils MCP ou tout l’historique du parent sont disponibles. '
                     'Demander au parent les éléments manquants. Utiliser uniquement les outils de lecture autorisés.\n')

def context_locations():
    """Dossiers possibles du contexte, relatifs au dossier personnel : ceux des CLI qui l'hébergent, puis celui du kit."""
    return [a.HOME_DIR for a in ADAPTERS if isinstance(a, ContextHost)] + ['.ai-toolkit/context']

def context_location(home, active):
    """Dossier des couches et de 30_USER.md : celui d'une CLI active qui ne lit son contexte que chez elle (context_dir),
    sinon ~/.ai-toolkit/context, que les autres CLI incluent ou recopient."""
    host = next((a for a in active if isinstance(a, ContextHost)), None)
    return host.context_dir(home) if host else home/'.ai-toolkit'/'context'

TARGETS = {'auto': None, 'gemini': ('gemini',), 'agy': ('agy',), 'codex': ('codex',), 'both': ('gemini', 'agy'), 'all': tuple(a.NAME for a in ADAPTERS)}

def selected_adapters(target, home):
    """Adaptateurs à installer : ceux que la cible nomme ; en auto, ceux dont la CLI est présente sur le poste,
    ou le premier de ADAPTERS (CLI par défaut) si aucune n'est détectée, pour un poste où la CLI sera installée ensuite."""
    if target not in TARGETS:
        raise KitError('--target doit valoir '+', '.join(TARGETS)+'.')
    wanted = TARGETS[target]
    if wanted is None:
        return [a for a in ADAPTERS if a.present(home)] or [ADAPTERS[0]]
    return [a for a in ADAPTERS if a.NAME in wanted]

def apply(profile_id, home, dry_run=False, user=None, target='auto'):
    """Prévalidation complète, plan neutre, adaptateurs, sauvegarde puis écriture atomique fichier par fichier."""
    home = home.resolve()
    kit = home / '.ai-toolkit'
    active = selected_adapters(target, home)
    context_dir = context_location(home, active)
    profile_id = safe_id(profile_id)
    profile_path = ROOT/'profiles'/(profile_id+'.json')
    if not profile_path.exists():
        raise KitError('Profil inconnu : '+profile_id)
    profile = read_json(profile_path)
    state = read_json(kit/'state.json')
    overrides = read_json(kit/'overrides.json', read_json(ROOT/'templates/user-overrides.json'))
    if overrides.get('frictions', 'propose') not in ('propose', 'auto', 'off'):
        raise KitError('frictions doit valoir propose (par défaut), auto ou off.')
    models = overrides.get('models', {})
    if not isinstance(models, dict) or not all(isinstance(k, str) and k in ('fast', 'deep', 'default') and isinstance(v, str) and re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,60}', v) for k, v in models.items()):
        raise KitError('models doit être un objet {"fast"|"deep"|"default": "<nom de modèle>"}.')
    for key in ('extra_skills','disabled_skills','extra_agents','disabled_agents','extra_commands','disabled_commands'):
        if not isinstance(overrides.get(key,[]),list) or not all(isinstance(x,str) for x in overrides.get(key,[])):
            raise KitError(key+' doit être une liste de noms.')
    catalog = read_json(ROOT/'skills/catalog.json')
    manifest = load_commands()
    command_names = [c['name'] for c in manifest]
    for key in ('extra_commands','disabled_commands'):
        for name in overrides.get(key, []):
            if name not in command_names:
                raise KitError(key+' : commande inconnue '+name+'. Commandes du kit : '+', '.join(command_names))
    # Une commande ajoutée d'une ligne (extra_commands) installe aussi ses skills.
    extra_command_skills = [s for c in manifest if c['name'] in overrides.get('extra_commands', []) for s in c['skills']]
    selected = resolve_skills({**profile, 'skills': list(profile['skills']) + extra_command_skills}, overrides, catalog)
    allowed = allowed_commands(profile.get('commands'), overrides, command_names)
    writes, deletes = {}, []
    if not (kit/'overrides.json').exists():
        writes[kit/'overrides.json'] = (ROOT/'templates/user-overrides.json').read_bytes()
    identity = dict(user) if user else dict(state.get('user', {}))
    if identity.get('email') and not EMAIL.fullmatch(identity['email']):
        raise KitError('Email invalide : '+identity['email'])
    files = {}
    old_files = state.get('files',{})
    def managed_write(target, data, label):
        rel = target.relative_to(home).as_posix()
        if target.exists():
            previous = target.read_bytes()
            if rel in old_files:
                if digest(previous) != old_files[rel]:
                    raise KitError(label+' modifié localement : '+str(target))
            elif previous != data:
                raise KitError(label+' existant non géré par le kit : '+str(target))
        writes[target] = data
        files[rel] = digest(data)
    # --- Plan neutre : ce qu'il faut installer, sans rien de propre à une CLI. ---
    context_names = managed_context_names(profile)
    commands = selected_commands(selected, manifest, allowed)
    kit_text = (ROOT/'templates/kit-context.md').read_text(encoding='utf-8').format(profile=profile_id, commands=command_lines(commands), playbooks=playbook_lines(selected, catalog), frictions=friction_rule(overrides.get('frictions', 'propose')))
    practice_names, practice_texts = [], []
    for practice_id in profile['practices']:
        source, name = practice_file(practice_id)
        practice_names.append(name)
        practice_texts.append(source.read_text(encoding='utf-8'))
    practices = '\n'.join(practice_texts)
    skill_sources = []
    for skill in selected:
        source = inside(ROOT,catalog[skill]['path'])
        if not (source/'SKILL.md').is_file():
            raise KitError('SKILL.md absent : '+skill)
        for src in source.rglob('*'):
            if src.is_symlink():
                raise KitError('Lien symbolique non pris en charge : '+str(src))
        skill_sources.append((skill, source))
    agent_catalog = read_json(ROOT/'agents/catalog.json')
    selected_agents = list(dict.fromkeys(profile.get('agents',[]) + overrides.get('extra_agents',[])))
    selected_agents = [x for x in selected_agents if x not in overrides.get('disabled_agents',[])]
    agents = []
    for agent in selected_agents:
        safe_id(agent)
        if agent not in agent_catalog:
            raise KitError('Agent inconnu : '+agent)
        agents.append((agent, read_json(inside(ROOT,agent_catalog[agent]['path']))))
    hooks_dir = kit/'hooks'  # scripts partagés par toutes les CLI, comme kit/bin/friction.py
    hook_manifest = read_json(ROOT/'runtime/hooks/hooks.json').get('hooks', {})
    wanted_hooks = overrides.get('hooks', {})
    if not isinstance(wanted_hooks, dict) or not all(isinstance(v, bool) for v in wanted_hooks.values()):
        raise KitError('hooks doit être un objet nom → true/false.')
    enabled_hooks = {}
    for name, flag in wanted_hooks.items():
        safe_id(name)
        if name not in hook_manifest:
            raise KitError('Garde-fou inconnu : '+name+'. Disponibles : '+', '.join(sorted(hook_manifest)))
        if not flag:
            continue
        spec = hook_manifest[name]
        script = hooks_dir/spec['script']
        enabled_hooks[name] = {'event': spec['event'], 'group': {'matcher': spec['matcher'], 'hooks': [{'name': 'ai-kit-'+name, 'type': 'command', 'command': quote_path(sys.executable)+' '+quote_path(script)}]}}
    mcp_entries = overrides.get('mcp',{})
    if not isinstance(mcp_entries,dict):
        raise KitError('mcp doit être un objet.')
    enabled_mcp = {}
    for name,entry in mcp_entries.items():
        safe_id(name)
        if not isinstance(entry,dict) or not isinstance(entry.get('enabled',False),bool):
            raise KitError('MCP : entrée ou enabled invalide.')
        if entry.get('enabled'):
            enabled_mcp['ai-kit-'+name] = validate_server(entry.get('server'))
    p = Plan(active=[a.NAME for a in active],
        home=home, kit=kit, state=state, old_files=old_files, overrides=overrides, profile_id=profile_id, profile=profile,
        catalog=catalog, selected=selected, skill_sources=skill_sources, commands=commands, context_names=context_names,
        kit_text=kit_text, practice_names=practice_names, practice_texts=practice_texts, user_file=context_dir/USER_CONTEXT, context_dir=context_dir,
        user_context_text=user_context_text(identity), agents=agents, models=models, hooks_dir=hooks_dir,
        hook_manifest=hook_manifest, enabled_hooks=enabled_hooks, enabled_mcp=enabled_mcp, writes=writes, deletes=deletes,
        managed_write=managed_write, 
        agent_body=lambda definition: practices+'\n'+AGENT_INSTRUCTION+'\n'+definition['instructions']+'\n')
    # Scripts partagés par toutes les CLI : frictions et garde-fous activés.
    managed_write(kit/'bin'/'friction.py', (ROOT/'runtime/friction.py').read_bytes(), 'Script du kit')
    for name in enabled_hooks:
        managed_write(hooks_dir/hook_manifest[name]['script'], (ROOT/'runtime/hooks'/hook_manifest[name]['script']).read_bytes(), 'Garde-fou')
    # Couches de contexte et 30_USER.md, dans le dossier de contexte (voir context_location).
    managed_write(context_dir/KIT_CONTEXT, kit_text.encode('utf-8'), 'Fichier de contexte')
    for name, text in zip(practice_names, practice_texts):
        managed_write(context_dir/name, text.encode('utf-8'), 'Fichier de contexte')
    user_file = context_dir/USER_CONTEXT
    if not user_file.exists():
        # Créé une fois, jamais réécrit ni suivi. Si l'emplacement a changé, recopier la version existante : l'original reste en place.
        previous = next((f for f in (home/d/USER_CONTEXT for d in context_locations()) if f != user_file and f.is_file()), None)
        legacy_prefs = kit/'preferences.md'
        writes[user_file] = previous.read_bytes() if previous else legacy_prefs.read_bytes() if legacy_prefs.exists() else p.user_context_text.encode('utf-8')
    if (kit/'preferences.md').exists():
        writes[kit/'preferences.md.migrated'] = (kit/'preferences.md').read_bytes()
        deletes.append(kit/'preferences.md')
        p.migrated_prefs = True
    # --- Adaptateurs : chacun traduit le plan pour sa CLI. ---
    for adapter in active:
        adapter.install(p)
    for rel, previous_hash in old_files.items():
        if rel in files:
            continue
        target_path = inside(home,rel)
        if not (rel.startswith(KIT_MANAGED) or any(a.is_managed(rel) for a in ADAPTERS)):
            raise KitError('État invalide : suppression hors périmètre géré.')
        if target_path.exists():
            if digest(target_path.read_bytes()) != previous_hash:
                raise KitError('Ancien fichier géré modifié localement : '+str(target_path))
            deletes.append(target_path)
    for adapter in ADAPTERS:
        adapter.finalize(p, active=adapter in active)  # inactif : retire ce qu'une installation précédente avait posé
    new_state = {'schema_version':2,'version':(ROOT/'VERSION').read_text().strip(),'profile':profile_id,'files':files,'mcp':enabled_mcp,'hooks':enabled_hooks,'user':identity,'blocks':p.blocks,'context_dir':context_dir.relative_to(home).as_posix(),
                 'installed':{'skills':selected,'commands':[c['name'] for c in commands],'agents':['ai-kit-'+a for a,_ in agents],'clis':[a.NAME for a in active]}}
    writes[kit/'state.json'] = json_bytes(new_state)
    writes = {path:b for path,b in writes.items() if not path.exists() or path.read_bytes()!=b}
    # Refuser les liens dans les chemins gérés avant toute écriture.
    for path in list(writes)+deletes:
        for part in (path,*path.parents):
            if part == home:
                break
            if part.is_symlink():
                raise KitError('Lien symbolique dans un chemin géré : '+str(part))
    print('Profil : '+profile_id+' | '+str(len(selected))+' skills | '+str(len(agents))+' agents | '+str(len(enabled_mcp))+' MCP activés | '+str(len(enabled_hooks))+' garde-fous')
    if identity.get('email'):
        print('Identité : '+identity['email']+' (source '+identity.get('source','?')+')')
    if dry_run:
        print('Simulation : '+str(len(writes))+' fichiers à écrire, '+str(len(deletes))+' à retirer. Aucune modification.')
        return
    # Pas de téléchargement, installation de dépendances ou exécution MCP.
    changed = list(writes)+deletes
    backup = kit/'backups'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
    originals = {}
    for path in changed:
        originals[path] = path.read_bytes() if path.exists() else None
    if changed:
        backup.mkdir(parents=True,exist_ok=True)
        try:
            if os.name != 'nt':
                backup.chmod(0o700)
            for path,data in originals.items():
                if data is not None:
                    dest = backup/path.relative_to(home)
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(data)
                    if os.name != 'nt':
                        dest.chmod(0o600)
            (backup/'manifest.json').write_bytes(json_bytes({'created':[p.relative_to(home).as_posix() for p,b in originals.items() if b is None],'restore':'Copier les fichiers sauvegardés vers le dossier personnel ; retirer uniquement les fichiers created si inchangés.'}))
            for path,data in writes.items():
                atomic_write(path,data)
            for path in deletes:
                path.unlink()
                prune_empty_dirs(path.parent, next((home/d for d in managed_roots(home) if path.is_relative_to(home/d)), home/'.ai-toolkit'))
        except OSError:
            for path,data in originals.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path,data)
            raise
    print('Installation terminée.' if changed else 'Déjà à jour.')
    print('Votre contexte personnel : '+str(p.user_file))
    if p.migrated_prefs:
        print('Anciennes préférences migrées vers ce fichier ; copie conservée dans preferences.md.migrated.')
    print('MCP optionnels : configurer overrides.json puis lancer update. Voir docs/mcp.md.')
    print(str(len(commands))+' commandes installées ; /guide explique par quoi commencer.')
    for adapter in active:
        line = adapter.summary(p)
        if line:
            print(line)
    print('Ouvrir un projet, lancer la CLI et taper /guide ; vérifications propres à chaque CLI : docs/cli/.')

KIT_MANAGED = ('.ai-toolkit/bin/', '.ai-toolkit/hooks/', '.ai-toolkit/context/')

def managed_roots(home):
    """Dossiers racines où le kit pose des fichiers : le sien et celui de chaque CLI."""
    return ['.ai-toolkit'] + sorted({a.HOME_DIR for a in ADAPTERS})

def prune_empty_dirs(directory, stop):
    """Retirer les dossiers vides laissés par une suppression, sans jamais retirer un dossier racine ni ses dossiers structurants."""
    roots = {stop} | {stop/name for name in ('skills', 'agents', 'commands', 'hooks', 'bin', 'config', 'config/plugins')}
    while directory not in roots and directory.is_relative_to(stop) and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent

def atomic_write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp = tempfile.mkstemp(prefix='.ai-kit-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def doctor(home):
    issues = 0
    def status(ok,message):
        nonlocal issues
        print(('[OK] ' if ok else '[À vérifier] ')+message)
        if not ok:
            issues += 1
    status(sys.version_info >= (3,9),'Python 3.9 minimum')
    state = read_json(home/'.ai-toolkit/state.json')
    status(bool(state),'Installation du kit ; lancer setup si absente.')
    hints = []
    if state:
        print('Profil : '+state['profile']+' | version '+state['version'])
        identity = state.get('user', {})
        print('Identité enregistrée : '+(identity.get('email') or identity.get('name') or 'aucune')+(' (source '+identity['source']+')' if identity.get('source') else ''))
        profile = read_json(ROOT/'profiles'/(safe_id(state['profile'])+'.json'))
        ctx = DoctorContext(profile=profile, load_commands=load_commands, managed_context_names=managed_context_names,
                                    allowed_domains=allowed_domains, domain_allowed=domain_allowed)
        context = state.get('context_dir', '.gemini')
        status((home/context/USER_CONTEXT).is_file(),'Contexte personnel présent : '+context+'/'+USER_CONTEXT)
        for rel,expected in state.get('files',{}).items():
            path = inside(home,rel)
            status(path.is_file() and digest(path.read_bytes())==expected,rel)
        installed = set(state.get('installed', {}).get('clis') or [a.NAME for a in ADAPTERS])
        for adapter in ADAPTERS:
            if adapter.NAME in installed:
                adapter.doctor(home, state, status, ctx)
                hints.append(adapter.doctor_hint())
        for name in profile['mcp']['recommended']:
            print('[Optionnel] '+name+' : '+('configuré' if 'ai-kit-'+name in state.get('mcp',{}) else 'non configuré'))
    print('Diagnostic local uniquement : authentification, connexion MCP et droits IAM non testés ; doctor --live fait un appel réel au modèle.')
    for hint in hints:
        if hint:
            print(hint)
    return 1 if issues else 0

def usage(home, since_days=42, as_json=None, min_sessions=10, min_prompts=50):
    """Relevé d'usage pour la revue d'usage (docs/usage-review.md) : commandes tapées, skills activés, agents appelés, depuis les journaux que chaque CLI écrit déjà."""
    from collections import Counter
    state = read_json(home/'.ai-toolkit/state.json')
    if not state:
        raise KitError('Kit absent : lancer setup.')
    catalog = read_json(ROOT/'skills/catalog.json')
    installed = state.get('installed') or next(a for a in ADAPTERS if isinstance(a, ContextHost)).installed_from_files(state)
    installed_skills, installed_commands, installed_agents = (sorted(installed.get(k, [])) for k in ('skills', 'commands', 'agents'))
    cutoff = datetime.now(timezone.utc).timestamp() - since_days*86400
    commands, skills, agents = Counter(), Counter(), Counter()
    unknown_commands = Counter()
    repeated = errors = prompts = 0
    sessions_seen, seen_texts = set(), {}
    # Chaque adaptateur lit les journaux de sa CLI et rend des événements neutres (prompt, skill, agent, erreur).
    for adapter in ADAPTERS:
        for event in adapter.history(home, state):
            if event.get('ts', 0) < cutoff:
                continue
            session = event.get('session')
            if session:
                sessions_seen.add(session)
            kind = event['kind']
            if kind == 'error':
                errors += 1
            elif kind == 'skill':
                skills[event['name']] += 1
            elif kind == 'agent':
                agents[event['name']] += 1
            elif kind == 'prompt':
                prompts += 1
                shown = event['text']
                match = re.match(r'^[$/]([a-z][a-z0-9:-]*)', shown)
                if match:
                    if match.group(1) in installed_commands:
                        commands[match.group(1)] += 1
                    elif not any(match.group(1) in a.BUILTIN_COMMANDS for a in ADAPTERS):
                        unknown_commands[match.group(1)] += 1
                text = ' '.join(shown.split()).lower()
                if len(text) >= 15:
                    seen = seen_texts.setdefault(session, set())
                    if text in seen:
                        repeated += 1
                    seen.add(text)
    sessions = len(sessions_seen)
    unused_commands = [c for c in installed_commands if commands[c] == 0]
    unused_skills = [s for s in installed_skills if skills[s] == 0 and s not in installed_commands]  # un skill qui porte le nom d'une commande est mesuré par la commande
    unused_agents = [a for a in installed_agents if agents[a] == 0]
    by_name = {c['name']: c for c in load_commands()}
    required_by_used = set(skills)
    for name in commands:
        required_by_used.update(by_name.get(name, {}).get('skills', []))
    frontier = list(required_by_used)
    while frontier:
        for dependency in catalog.get(frontier.pop(), {}).get('requires', []):
            if dependency not in required_by_used:
                required_by_used.add(dependency)
                frontier.append(dependency)
    def core_candidates():
        out = []
        for s in unused_skills:
            entry = catalog.get(s, {})
            if entry.get('tier') == 'core' and s not in required_by_used and entry.get('category') in ('workflow','tool'):
                out.append(s)
        return out
    # Frictions notées par /friction : ~/.ai-toolkit/frictions.jsonl, une ligne par friction, sur la fenêtre.
    frictions = []
    frictions_file = home/'.ai-toolkit/frictions.jsonl'
    if frictions_file.is_file():
        for line in frictions_file.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict) and _ts(entry.get('ts')) >= cutoff:
                frictions.append({k: entry.get(k) for k in ('ts', 'category', 'command', 'text', 'cli', 'os', 'kit', 'profile', 'source') if entry.get(k) is not None})
    frictions_by_category = Counter(str(f.get('category')) for f in frictions)
    enough = sessions >= min_sessions and prompts >= min_prompts
    report = {'window_days': since_days, 'sessions': sessions, 'prompts': prompts, 'errors': errors,
              'commands': dict(commands), 'skills': dict(skills), 'agents': dict(agents),
              'unused_commands': unused_commands, 'unused_skills': unused_skills, 'unused_agents': unused_agents,
              'core_candidates_to_demote': core_candidates() if enough else [], 'enough_data': enough,
              'frictions': frictions, 'frictions_by_category': dict(frictions_by_category),
              'unknown_commands': dict(unknown_commands), 'repeated_prompts': repeated}
    print('Fenêtre : '+str(since_days)+' jours | '+str(sessions)+' sessions | '+str(prompts)+' prompts | '+str(errors)+' erreurs')
    print('Commandes tapées : '+(', '.join(k+' ×'+str(v) for k,v in commands.most_common()) or 'aucune'))
    print('Skills activés : '+(', '.join(k+' ×'+str(v) for k,v in skills.most_common()) or 'aucun'))
    print('Agents appelés : '+(', '.join(k+' ×'+str(v) for k,v in agents.most_common()) or 'aucun'))
    print('Jamais utilisés : '+str(len(unused_commands))+' commandes, '+str(len(unused_skills))+' skills, '+str(len(unused_agents))+' agents.')
    print('Commandes inconnues tapées : '+(', '.join('/'+k+' ×'+str(v) for k,v in unknown_commands.most_common()) or 'aucune')+' | demandes répétées dans une même session : '+str(repeated))
    print('Frictions notées : '+str(len(frictions))+(' ('+', '.join(k+' ×'+str(v) for k,v in frictions_by_category.most_common())+')' if frictions else '')+' ; /friction pour en noter une.')
    if not enough:
        print('Données insuffisantes pour recommander (seuil : '+str(min_sessions)+' sessions et '+str(min_prompts)+' prompts dans la fenêtre ; --min-sessions et --min-prompts pour l’ajuster). Aucune recommandation.')
    elif report['core_candidates_to_demote']:
        print('Candidats à sortir du noyau (jamais activés, non requis par une commande utilisée) : '+', '.join(report['core_candidates_to_demote']))
    else:
        print('Aucun skill du noyau à sortir sur cette fenêtre.')
    print('Procédure : docs/usage-review.md. Les journaux lus sont locaux ; rien n’est envoyé.')
    if as_json:
        as_json.write_text(json_bytes(report).decode('utf-8'), encoding='utf-8')
    return 0

def live_checks(home, announce=False):
    """Appel réel au modèle par chaque CLI installée qui sait le faire (live) ; 1 si l'une ne répond pas."""
    code = 0
    for adapter in ADAPTERS:
        if isinstance(adapter, LiveCheck) and shutil.which(adapter.COMMAND):
            if announce:
                print('Vérification par un appel réel au modèle, '+adapter.LABEL+' (--no-live pour sauter) :')
            code = max(code, adapter.live(home))
    return code

def resolve_identity(args, home, state):
    """Identité confirmée en interactif, --user sinon ; jamais imposée."""
    if args.user:
        if not EMAIL.fullmatch(args.user):
            raise KitError('--user attend un email.')
        return {'email': args.user, 'source': 'option'}
    if args.action == 'update' and state.get('user'):
        return None
    detected = detect_identity(home)
    shown = detected.get('email') or detected.get('name')
    if not sys.stdin.isatty():
        if shown:
            print('Identité détectée non confirmée : '+shown+' ; utiliser --user pour l’enregistrer.')
        return {}
    prompt = ('Identité détectée : '+shown+' (source '+detected['source']+'). Entrée pour confirmer, ou saisir votre email : ') if shown else 'Votre email professionnel (Entrée pour ignorer) : '
    answer = input(prompt).strip()
    if not answer:
        return detected
    if not EMAIL.fullmatch(answer):
        raise KitError('Email invalide.')
    return {'email': answer, 'source': 'saisie'}

def main(argv=None):
    if sys.version_info < (3,9):
        print('Python 3.9 minimum requis.',file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(prog='ai-kit' if _PACKAGE_DIR.name == 'ai_kit' else 'python3 -m installer', description='Kit IA — '+', '.join(a.LABEL for a in ADAPTERS)+' ; Mac et Windows')
    parser.add_argument('action',choices=['setup','update','doctor','usage'])
    parser.add_argument('--since',type=int,default=42,help='usage : fenêtre en jours (défaut 42)')
    parser.add_argument('--json',type=Path,help='usage : écrire le relevé dans ce fichier')
    parser.add_argument('--min-sessions',type=int,default=10,help='usage : sessions minimales avant recommandation (défaut 10)')
    parser.add_argument('--min-prompts',type=int,default=50,help='usage : prompts minimaux avant recommandation (défaut 50)')
    parser.add_argument('--profile',choices=profile_ids())
    parser.add_argument('--user',help='Email professionnel à enregistrer, sans confirmation interactive')
    parser.add_argument('--home',type=Path,default=Path.home(),help='Dossier personnel alternatif pour un essai isolé')
    parser.add_argument('--dry-run',action='store_true',help='Afficher le plan sans écrire')
    parser.add_argument('--target',choices=list(TARGETS),default='auto',help='auto : les CLI présentes sur le poste (Gemini si aucune) ; gemini, agy, codex : cette CLI seule ; both : Gemini et agy ; all : toutes les CLI prises en charge')
    parser.add_argument('--live',action='store_true',help='doctor : faire un appel réel au modèle et diagnostiquer')
    parser.add_argument('--no-live',action='store_true',help='setup/update : ne pas vérifier par un appel réel au modèle')
    args = parser.parse_args(argv)
    try:
        home = args.home.resolve()
        if args.action == 'doctor':
            code = doctor(home)
            if args.live:
                code = max(code, live_checks(home))
            return code
        if args.action == 'usage':
            return usage(home, args.since, args.json, args.min_sessions, args.min_prompts)
        state = read_json(home/'.ai-toolkit/state.json')
        identity = resolve_identity(args, home, state)
        email = (identity or state.get('user') or {}).get('email')
        role = args.profile or state.get('profile')
        suggested = directory_profile(email)
        if not role:
            if args.action == 'update':
                raise KitError('Kit absent : lancer setup.')
            if suggested and not sys.stdin.isatty():
                print('Profil proposé par l’annuaire : '+suggested)
                role = suggested
            elif not sys.stdin.isatty():
                raise KitError('Préciser --profile parmi : '+', '.join(profile_ids())+'.')
            else:
                choices = PROFILE_MENU
                default = next((str(i+1) for i,(pid,_) in enumerate(choices) if pid == suggested), None)
                print('Bienvenue dans le Kit IA\n'+'\n'.join(str(i+1)+'. '+label for i,(_,label) in enumerate(choices)))
                answer = input('Votre profil [1-'+str(len(choices))+']'+(' (Entrée = '+default+', proposé par l’annuaire)' if default else '')+' : ').strip() or default
                if answer not in [str(i+1) for i in range(len(choices))]:
                    raise KitError('Choisir un numéro entre 1 et '+str(len(choices))+'.')
                role = choices[int(answer)-1][0]
        apply(role,home,args.dry_run,identity,args.target)
        for adapter in selected_adapters(args.target, home):
            if not shutil.which(adapter.COMMAND):
                print(adapter.LABEL+' absent du PATH : configuration prête, installation et authentification à réaliser selon la procédure IT.')
        if not args.dry_run and not args.no_live and os.environ.get('AI_KIT_NO_LIVE') != '1' and live_checks(home, announce=True):
            print('Installation faite, mais le modèle ne répond pas encore : appliquer le remède ci-dessus puis relancer doctor --live.')
        return 0
    except (KitError,OSError,UnicodeError) as exc:
        print('Erreur : '+str(exc),file=sys.stderr)
        return 2
    except (EOFError,KeyboardInterrupt):
        print('\nOpération annulée.',file=sys.stderr)
        return 130
