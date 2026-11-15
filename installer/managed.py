"""managed-settings: the files IT deploys so that the kit's guardrails hold whatever a person or an agent changes on the
workstation. Generated from the Core's guardrails and MCP servers and from managed.toml; nothing is installed, nothing outside the output folder is written."""
import json
from pathlib import Path

from .core import ROOT, KitError, read_json, is_guardrail, hook_identity, lockable_names, with_followers, cli_event
from .toml_files import toml_value
from .settings import core_settings

# Written by an agent, these would switch a guardrail off or change what every session loads. USER.md and
# ~/.ai-kit/learning stay writable: /me and /learn write there.
KIT_FILES = ('~/.ai-kit/aikit.toml', '~/.ai-kit/state.json', '~/.ai-kit/hooks/**', '~/.ai-kit/bin/**', '~/.ai-kit/backups/**',
             '~/.ai-kit/runtime/**', '~/.ai-kit/schemas/**', '~/.ai-kit/context/00_*', '~/.ai-kit/context/10_*', '~/.ai-kit/context/20_*')
CLAUDE_FILES = ('~/.claude/settings.json', '~/.claude/CLAUDE.md', '~/.claude/agents/ai-kit-*', '~/.claude/skills/ai-kit-*/**', '~/.claude.json')
POSIX_PYTHON = '"$HOME/.ai-kit/runtime/venv/bin/python"'
POSIX_HOOKS = '"$HOME/.ai-kit/hooks/'
# Windows: Claude Code runs a hook through Git Bash, or PowerShell when the hook says so (hooks docs, field shell). The
# Windows file asks for PowerShell, present on every workstation: $HOME expands there, and & runs a quoted program.
WINDOWS_PYTHON = '& "$HOME\\.ai-kit\\runtime\\venv\\Scripts\\python.exe"'
WINDOWS_HOOKS = '"$HOME\\.ai-kit\\hooks\\'


def locked(org, manifest):
    """The guardrails every workstation enforces by default (managed.toml hooks.locked then adds IT's own)."""
    return [n for n, spec in manifest.items() if spec.get('default') and is_guardrail(spec)]


def command(spec, windows=False, served=()):
    served = ''.join(' '+n for n in served)
    if windows:
        return WINDOWS_PYTHON+' -I '+WINDOWS_HOOKS+spec['script']+'"'+served
    return POSIX_PYTHON+' -I '+POSIX_HOOKS+spec['script']+'"'+served


def cmd_command(spec, served=()):
    """A hook command for cmd.exe, which Codex uses to run hooks on Windows (COMSPEC, else cmd.exe, with /C): %USERPROFILE%,
    not PowerShell's $HOME and call operator."""
    served = ''.join(' '+n for n in served)
    return '"%USERPROFILE%\\.ai-kit\\runtime\\venv\\Scripts\\python.exe" -I "%USERPROFILE%\\.ai-kit\\hooks\\'+spec['script']+'"'+served


def declared(names, manifest):
    """(hook name, spec, guardrail names its script receives) for each hook to write: guardrails served by one script share one."""
    found = {}
    for n in names:
        hook_name, served = hook_identity(manifest, n, names)
        found.setdefault(hook_name, (hook_name, manifest[n], served))
    return list(found.values())


def org_servers(org):
    """The MCP servers the Core defines (mcp/servers.toml): the only ones an MCP lock allows, named as the kit installs them."""
    found = {}
    for layer in [org.get('defaults', {})]:
        for name, entry in (layer.get('mcp') or {}).items():
            if isinstance(entry, dict) and isinstance(entry.get('server'), dict):
                found.setdefault('ai-kit-'+name, entry['server'])
    return found


def claude_mcp(servers):
    """allowedMcpServers entries: a remote server by its URL, a local one by its exact command and arguments. A name is
    not a security control (Claude Code docs, managed MCP), so no entry matches by name."""
    entries = []
    for server in servers.values():
        url = server.get('httpUrl') or server.get('url')
        entries.append({'serverUrl': url} if url else {'serverCommand': [server['command']]+list(server.get('args', []))})
    return entries


def codex_mcp(servers):
    """requirements.toml mcp_servers: Codex enables a server only when its name and identity match (Codex docs, managed
    configuration); a local server's executable and each argument must match exactly. Present but empty disables them all."""
    if not servers:
        return 'mcp_servers = {}\n'
    lines = []
    for name, server in servers.items():
        url = server.get('httpUrl') or server.get('url')
        if url:
            lines += ['[mcp_servers.'+name+']', 'identity = { url = '+toml_value(url)+' }', '']
        else:
            args = ', '.join('{ match = "exact", value = '+toml_value(a)+' }' for a in server.get('args', []))
            lines += ['[mcp_servers.'+name+'.identity]', 'command = { executable = '+toml_value(server['command'])+', args = ['+args+'] }', '']
    return '\n'.join(lines)


def claude(names, manifest, hooks_only, mcp=None, windows=False):
    from .adapters.claude import hook_matcher
    shell = {'shell': 'powershell'} if windows else {}
    hooks = {}
    for _, spec, served in declared(names, manifest):
        group = {'hooks': [{'type': 'command', 'command': command(spec, windows, served), **shell, 'timeout': 20}]}
        if is_guardrail(spec):
            group = {'matcher': hook_matcher(spec['matcher']), **group}  # a guardrail sees its tools; the integrity check every tool
        hooks.setdefault(cli_event(spec['event']), []).append(group)
    settings = {'permissions': {'deny': ['Edit('+p+')' for p in KIT_FILES + CLAUDE_FILES]}, 'hooks': hooks}
    if hooks_only:
        settings['allowManagedHooksOnly'] = True
    if mcp is not None:
        settings['allowManagedMcpServersOnly'] = True
        settings['allowedMcpServers'] = claude_mcp(mcp)
    return json.dumps(settings, indent=2)+'\n'


def gemini(names, manifest, windows=False):
    """On Windows, Gemini CLI's docs do not say which shell runs a hook: no hook is written there, YOLO mode stays off."""
    settings = {'hooks': {}, 'security': {'disableYoloMode': True}}
    for n, spec, served in ([] if windows else declared(names, manifest)):
        settings['hooks'].setdefault(spec['event'], []).append(
            {**({'matcher': spec['matcher']} if spec['matcher'] else {}), 'hooks': [{'name': 'ai-kit-'+n, 'type': 'command', 'command': command(spec, served=served)}]})
    if not settings['hooks']:
        settings.pop('hooks')
    return json.dumps(settings, indent=2)+'\n'


def codex(mcp=None, names=(), manifest=None):
    """requirements.toml; with the integrity check locked, its managed hooks too (Codex reads [hooks] and [features] there,
    openai/codex #18893; managed hooks need no approval): every tool after the call, whats-new at session start. The hooks
    come last, so that a bare key of the MCP block stays at the top level."""
    text = ('# Codex CLI requirements: the agent writes only inside the repo it works in (so never to ~/.codex or ~/.ai-kit),\n'
            '# and the person cannot start it without a sandbox or without approvals.\n'
            'allowed_sandbox_modes = ["read-only", "workspace-write"]\n'
            'allowed_approval_policies = ["untrusted", "on-request"]\n')
    if mcp is not None:
        text += '\n# MCP: only the servers the Core defines (mcp/servers.toml), by name and identity.\n'+codex_mcp(mcp)
    hooks = [(spec, served) for _, spec, served in declared(names, manifest or {}) if not is_guardrail(spec)]
    if hooks:
        text += ('\n# The integrity check IT locks (managed.toml): it reports a change to what the kit installed, it does not block.\n'
                 '[features]\nhooks = true\n')
        for spec, served in hooks:
            event = cli_event(spec['event'])
            text += ('\n[[hooks.'+event+']]\n'+('matcher = "*"\n' if event == 'PostToolUse' else '')+'\n[[hooks.'+event+'.hooks]]\ntype = "command"\n'
                     'command = '+toml_value(command(spec, served=served))+'\n'
                     'command_windows = '+toml_value(cmd_command(spec, served))+'\n')
    return text




INTEGRITY_README = ('\n\nIntegrity check locked (managed.toml): integrity and whats-new are written in the Claude Code, Gemini CLI (not on\n'
                    'Windows) and Codex files above. It reports a change, it does not block: it tells what the kit installed changed. agy\n'
                    '(Antigravity CLI) has no policy file: there, the lock holds through the kit installation (managed.toml), reinstalled at\n'
                    'each sync.')


def mcp_readme(mcp):
    if mcp is None:
        return ''
    listed = ', '.join(sorted(mcp)) or 'none: every MCP server is blocked'
    return ('\n\nMCP lock (--managed-mcp-only): only the servers the Core defines (mcp/servers.toml) are allowed ('+listed+').\n'
            '  Claude Code: allowedMcpServers with allowManagedMcpServersOnly, so a person cannot widen the list; a remote\n'
            '  server matches by URL, a local one by its exact command and arguments.\n'
            '  Codex CLI: mcp_servers in requirements.toml, matched by the name the kit installs (ai-kit-<name>) and the\n'
            '  same URL or exact command.\n'
            '  Gemini CLI: not generated. Its settings have mcp.allowed, mcp.excluded and admin.mcp.config, but their docs\n'
            '  do not say what an entry holds; set them by hand after checking your version.\n'
            '  A URL or an argument that uses ${VARIABLE} may not match once expanded: try one workstation first.')


def managed_settings(out, hooks_only=False, mcp_only=False, managed_file=None):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise KitError(str(out)+' is not empty: give a new folder, nothing is overwritten.')
    manifest = read_json(ROOT/'runtime'/'hooks'/'hooks.json')['hooks']
    org = core_settings()
    names = locked(org, manifest)
    mcp = org_servers(org) if mcp_only else None
    # managed.toml goes into the native files too. Its hooks.locked add to the Core's locked guardrails,
    # a guardrail it turns off is not locked, and its MCP refusals (denied, allow_stdio, allowlists) apply to the MCP lock.
    from .config import filter_mcp, load_managed
    imposed = load_managed(managed_file, lockable_names(manifest))
    if imposed:
        off = [n for n, v in imposed.get('hooks', {}).items() if v is False]
        names = with_followers([n for n in dict.fromkeys(list(names) + list(imposed.get('hooks', {}).get('locked', []))) if n not in off], manifest)
        if mcp is not None:
            mcp, notices = filter_mcp(mcp, imposed)
            for line in notices:
                print(line)
    files = {'claude-code/managed-settings.json': claude(names, manifest, hooks_only, mcp),
             'gemini-cli/settings.json': gemini(names, manifest),
             'windows/claude-code/managed-settings.json': claude(names, manifest, hooks_only, mcp, windows=True),
             'windows/gemini-cli/settings.json': gemini(names, manifest, windows=True),
             'codex/requirements.toml': codex(mcp, names, manifest),
             'README.txt': (ROOT/'templates'/'managed-settings-README.txt').read_text(encoding='utf-8').format(version=(ROOT/'VERSION').read_text(encoding='utf-8').strip(), hooks=', '.join(n for n in names if is_guardrail(manifest[n])) or 'none',
                                         integrity=INTEGRITY_README if 'integrity' in names else '',
                                         hooks_only=' With allowManagedHooksOnly, hooks from any other source are ignored.' if hooks_only else '',
                                         mcp=mcp_readme(mcp))}
    for rel, text in files.items():
        path = out/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    if mcp is not None and not mcp:
        print('[Info] The Core defines no MCP server (mcp/servers.toml): the MCP lock allows none, in Claude Code and Codex CLI.')
    print('Managed settings written to '+str(out)+' ('+', '.join(sorted(files))+'). Where to deploy them: README.txt.')
    return 0
