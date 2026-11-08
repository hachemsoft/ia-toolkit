"""ai-kit status [--verbose] (V2 slice 5, docs/v2/cli.md): what is active, read from local files only, no network, no write.
Core and Team (tag, commit), the configuration rollback returns to, the CLIs configured, the keys IT imposes; --verbose adds
where each setting comes from, the installed resources and each CLI's capabilities."""
from .adapters import ADAPTERS
from .config import ManagedConfigError, load_managed, provenance, summary
from .core import ROOT, read_json
from .sync import lock_summary


def status(home, verbose=False):
    kit = home/'.ai-kit'
    state = read_json(kit/'state.json')
    print('AI Kit '+(ROOT/'VERSION').read_text(encoding='utf-8').strip()+(' | configuration applied by '+state['version'] if state.get('version') else ' | not installed: run ai-kit init'))
    print(lock_summary(kit) or 'Core: the package content (no Core source synced) | Team: '+(state.get('team') or 'none'))
    if state:
        print('CLIs: '+', '.join(state.get('targets') or []))
    try:
        managed = load_managed()
        print(summary(managed) if managed is not None else 'Not administered (no managed.toml).')
    except ManagedConfigError as exc:
        managed = None
        print('[Check] '+str(exc))
    if state:
        from .core import friction_module
        upkeep = friction_module().housekeep(str(home), state.get('frictions_retention'))
        if upkeep['waiting']:
            print(str(upkeep['waiting'])+' friction(s) wait for your approval: ai-kit friction --sync sends them.')
    if not verbose or not state:
        return 0
    from .plan import effective_settings
    org_defaults, team_layer, personal, _, _ = effective_settings(kit, state.get('team'), None)
    origin = provenance(org_defaults, team_layer, personal, managed)
    print('Settings and where they come from: '+(', '.join(k+' ('+v+')' for k, v in origin.items()) or 'defaults only'))
    installed = state.get('installed') or {}
    for kind in ('skills', 'commands', 'agents'):
        print(kind.capitalize()+' ('+str(len(installed.get(kind, [])))+'): '+', '.join(installed.get(kind, [])))
    from .config import server_identity
    for name, server in sorted((state.get('mcp') or {}).items()):
        print('MCP '+name+': '+server_identity(server)+' (the identity IT lists in managed.toml mcp.allowed_stdio or allowed_http)')
    for adapter in ADAPTERS:
        if adapter.NAME in (state.get('targets') or []):
            caps = getattr(adapter, 'CAPABILITIES', {})
            print(adapter.LABEL+': '+', '.join(k+' '+s for k, (s, _) in caps.items()))
    return 0
