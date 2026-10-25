"""Adaptateur Codex CLI : skills dans ~/.codex/skills, blocs gérés dans ~/.codex/AGENTS.md et ~/.codex/config.toml."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from ..core import (ROOT, START, END, KIT_CONTEXT, USER_CONTEXT, CONTEXT_NAME, PROJECT_ID, KitError, read_json, json_bytes,
                    digest, safe_id, inside, merge_defaults, quote_path, split_block, place_block, command_skill_text, run_timed,
                    record_auto_friction, _ts)

CODEX_DIR = '.codex'
CODEX_MD = ('<!-- ai-kit:début : bloc géré par le kit IA ; modifier ~/.gemini/30_USER.md ou ~/.ai-toolkit/overrides.json, puis update -->', '<!-- ai-kit:fin -->')
CODEX_TOML = ('# >>> ai-kit : bloc géré par le kit IA ; modifier ~/.ai-toolkit/overrides.json, puis update >>>', '# <<< ai-kit <<<')
CODEX_EXPLICIT_ONLY = 'policy:\n  allow_implicit_invocation: false\n'

def explicit_only(skill_text):
    """Skill marqué « sur commande seulement » dans son en-tête (disable-model-invocation: true)."""
    head = skill_text.split('\n---', 1)[0] if skill_text.startswith('---') else ''
    return bool(re.search(r'^disable-model-invocation:\s*true\s*$', head, re.M))

def toml_value(value):
    """Chaîne, liste ou table en ligne TOML ; une chaîne JSON est une chaîne TOML valide."""
    if isinstance(value, dict):
        return '{ '+', '.join(json.dumps(str(k), ensure_ascii=False)+' = '+toml_value(v) for k, v in value.items())+' }'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return '['+', '.join(toml_value(v) for v in value)+']'
    return json.dumps(str(value), ensure_ascii=False)

def codex_context_block(kit_text, practice_texts, user_text):
    lines = [CODEX_MD[0], '# Kit IA (Codex)', '',
             'Dans Codex, les commandes du kit sont des skills : on les appelle par `$intent`, `$build`, `$test`… (`/skills` les liste). Partout où ce contexte ou un skill écrit `/intent`, comprendre `$intent`, et dans tes réponses écrire toujours les commandes du kit avec `$` (`$intent`), jamais avec `/`.',
             '', kit_text.strip(), '']
    lines += [t.strip()+'\n' for t in practice_texts]
    if user_text.strip():
        lines += ['<!-- Copie de ~/.gemini/30_USER.md, mise à jour par update. -->', user_text.strip(), '']
    lines.append(CODEX_MD[1])
    return '\n'.join(lines)

def codex_config_block(agent_entries, hook_commands, mcp_servers):
    lines = [CODEX_TOML[0]]
    for name, (description, config_file) in agent_entries.items():
        lines += ['', '[agents.'+name+']', 'description = '+toml_value(description), 'config_file = '+toml_value(config_file)]
    for command in hook_commands:
        lines += ['', '[[hooks.PreToolUse]]', 'matcher = ".*"', '', '[[hooks.PreToolUse.hooks]]', 'type = "command"', 'command = '+toml_value(command), 'timeout = 20']
    for name, server in mcp_servers.items():
        lines += ['', '[mcp_servers.'+name+']']
        for key in ('command', 'args', 'env', 'cwd'):
            if key in server:
                lines.append(key+' = '+toml_value(server[key]))
        if server.get('url') or server.get('httpUrl'):
            lines.append('url = '+toml_value(server.get('httpUrl') or server.get('url')))
        if server.get('headers'):
            lines.append('http_headers = '+toml_value(server['headers']))
    lines += ['', CODEX_TOML[1]]
    return '\n'.join(lines)

# --- Interface d'adaptateur ---------------------------------------------------------------------------------------
NAME = 'codex'
LABEL = 'Codex CLI'
COMMAND = 'codex'
HOME_DIR = CODEX_DIR
BUILTIN_COMMANDS = {'skills', 'model', 'review', 'init', 'new', 'compact', 'diff', 'mention', 'status', 'mcp', 'approvals', 'logout', 'quit', 'exit', 'hooks', 'agents', 'resume'}
MANAGED_PREFIXES = (CODEX_DIR+'/skills/', CODEX_DIR+'/ai-kit/')

def is_managed(rel):
    return rel.startswith(MANAGED_PREFIXES)

def active_account(home):
    return None  # le compte Codex n'est pas lu : il vit avec les identifiants

def doctor_hint():
    return 'Codex : vérifier /skills dans Codex et lancer codex doctor.' if shutil.which(COMMAND) else None

def present(home):
    return bool(shutil.which('codex')) or (home/CODEX_DIR).is_dir()

codex_present = present

def install(p):
    """Skills (avec « sur commande seulement » natif), skills de commande et rôles d'agents."""
    codex = p.home/CODEX_DIR
    for skill, source in p.skill_sources:
        for src in source.rglob('*'):
            if src.is_file():
                p.managed_write(codex/'skills'/skill/src.relative_to(source), src.read_bytes(), 'Skill Codex')
        # Codex respecte « sur commande seulement » par agents/openai.yaml.
        if explicit_only((source/'SKILL.md').read_text(encoding='utf-8')) and not (source/'agents'/'openai.yaml').exists():
            p.managed_write(codex/'skills'/skill/'agents'/'openai.yaml', CODEX_EXPLICIT_ONLY.encode('utf-8'), 'Skill Codex')
    for command in p.commands:
        if command['name'] in p.selected:
            continue  # un skill du même nom sert de commande
        p.managed_write(codex/'skills'/command['name']/'SKILL.md', command_skill_text(command).encode('utf-8'), 'Skill de commande Codex')
        p.managed_write(codex/'skills'/command['name']/'agents'/'openai.yaml', CODEX_EXPLICIT_ONLY.encode('utf-8'), 'Skill de commande Codex')
    p.codex_agents = {}
    for agent, definition in p.agents:
        name = 'ai-kit-'+agent
        role_file = codex/'ai-kit'/'agents'/(name+'.toml')
        p.managed_write(role_file, ('# Agent du kit IA, géré par le kit.\ndeveloper_instructions = '+toml_value(p.agent_body(definition))+'\n').encode('utf-8'), 'Agent Codex')
        p.codex_agents[name] = (definition['description'], str(role_file))

def finalize(p, active=True):
    """Blocs gérés dans ~/.codex/AGENTS.md et ~/.codex/config.toml ; le reste des deux fichiers ne bouge pas. Inactif : retire les blocs."""
    old_blocks = p.state.get('blocks', {})
    for rel, markers, position, label in ((CODEX_DIR+'/AGENTS.md', CODEX_MD, 'top', '~/.codex/AGENTS.md'), (CODEX_DIR+'/config.toml', CODEX_TOML, 'end', '~/.codex/config.toml')):
        path = p.home/rel
        text = path.read_text(encoding='utf-8') if path.exists() else ''
        before, old_block, after = split_block(text, markers, label)
        if old_block is not None and old_blocks.get(rel) != digest(old_block.encode('utf-8')):
            raise KitError('Bloc du kit modifié à la main dans '+label+' : reporter vos changements hors du bloc (ou dans overrides.json), retirer le bloc, puis update.')
        outside = before.rstrip('\n')+('\n' if before.strip() and after.strip() else '')+after.lstrip('\n')
        block = None
        if active and rel.endswith('AGENTS.md'):
            user_text = p.user_file.read_text(encoding='utf-8') if p.user_file.exists() else (p.writes.get(p.user_file) or b'').decode('utf-8')
            block = codex_context_block(p.kit_text, p.practice_texts, user_text)
        elif active:
            if p.enabled_hooks and re.search(r'^\s*(hooks\.)?PreToolUse\s*=', outside, re.M):
                raise KitError('~/.codex/config.toml définit déjà hooks.PreToolUse sous une autre forme : le kit ne peut pas y ajouter ses garde-fous sans le réécrire.')
            if re.search(r'^\s*\[\s*(agents|mcp_servers)\.ai-kit-', outside, re.M):
                raise KitError('~/.codex/config.toml contient déjà des entrées ai-kit- hors du bloc du kit : les retirer, puis update.')
            hook_commands = [quote_path(sys.executable)+' '+quote_path(p.hooks_dir/p.hook_manifest[name]['script']) for name in p.enabled_hooks]
            block = codex_config_block(getattr(p, 'codex_agents', {}), hook_commands, p.enabled_mcp)
        new_text = place_block(outside, block, position)
        if rel.endswith('config.toml') and block is not None:
            try:
                tomllib = __import__('tomllib')  # Python 3.11+ ; avant, pas de validation et le bloc est écrit tel que généré
            except ImportError:
                tomllib = None
            if tomllib is not None:
                try:
                    tomllib.loads(new_text)
                except ValueError as exc:
                    raise KitError('~/.codex/config.toml deviendrait invalide avec le bloc du kit ('+str(exc)+') ; rien n’est écrit.')
        if block is not None:
            p.blocks[rel] = digest(block.encode('utf-8'))
        if new_text != text and (block is not None or old_block is not None):
            p.writes[path] = new_text.encode('utf-8')  # jamais supprimé : le fichier appartient à la personne

def summary(p):
    return 'Codex : skills dans ~/.codex/skills, blocs du kit dans ~/.codex/AGENTS.md et ~/.codex/config.toml ; les commandes s’appellent $intent, $build…'+(' Au premier lancement, Codex demande d’approuver les garde-fous du kit : répondre « Trust », sinon ils ne s’exécutent pas.' if p.enabled_hooks else '')

def doctor(home, state, status, ctx):
    blocks = state.get('blocks', {})
    if not blocks:
        return
    for rel, markers in ((CODEX_DIR+'/AGENTS.md', CODEX_MD), (CODEX_DIR+'/config.toml', CODEX_TOML)):
        path = home/rel
        text = path.read_text(encoding='utf-8') if path.exists() else ''
        try:
            _, block, _ = split_block(text, markers, rel)
        except KitError as exc:
            status(False, str(exc))
            continue
        status(block is not None and digest(block.encode('utf-8')) == blocks.get(rel), 'Bloc du kit intact dans ~/'+rel)
    agents_md = home/CODEX_DIR/'AGENTS.md'
    user_file = home/state.get('context_dir', '.gemini')/USER_CONTEXT
    if agents_md.exists() and user_file.exists():
        current = user_file.read_text(encoding='utf-8').strip() in agents_md.read_text(encoding='utf-8')
        status(current, 'Codex a la dernière version de 30_USER.md'+('' if current else ' (lancer update après l’avoir modifié)'))
    if (home/CODEX_DIR/'AGENTS.override.md').exists():
        status(False, '~/.codex/AGENTS.override.md existe : Codex le lit à la place de AGENTS.md, le contexte du kit est ignoré')
    if state.get('hooks'):
        print('[Info] Garde-fous déclarés à Codex : ils ne s’exécutent qu’après approbation dans Codex (« Trust » au premier lancement).')
    if not shutil.which('codex'):
        print('[Info] Codex installé par le kit mais absent du PATH.')

def history(home, state):
    """~/.codex/history.jsonl : une ligne par prompt (session_id, ts en secondes, text) ; commandes tapées $intent ou /intent."""
    path = home/CODEX_DIR/'history.jsonl'
    if not path.is_file() or not any(rel.startswith(CODEX_DIR+'/skills/') for rel in state.get('files', {})):
        return
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        stamp = entry.get('ts', 0)
        if not isinstance(stamp, (int, float)):
            continue
        yield {'kind': 'prompt', 'session': ('codex:'+str(entry['session_id'])) if entry.get('session_id') else None, 'ts': stamp/1000 if stamp > 1e12 else stamp, 'text': str(entry.get('text', '')).strip()}
