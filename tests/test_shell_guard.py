"""The rules of the shared shell guardrail (runtime/hooks/shell-guard.py): for each rule, the commands it must refuse and
the ones it must let through, above all the commands that only talk about a dangerous action."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from installer.cli import doctor, usage
from installer.core import read_json
from installer.managed import managed_settings
from personal import write_personal  # noqa: E402
from presets import apply_as  # noqa: E402

GUARD = Path(__file__).resolve().parents[1]/'runtime'/'hooks'/'shell-guard.py'
ALL = ('dbt-prod-guard', 'git-guard', 'bq-cost-guard', 'infra-prod-guard')


def run(rules, command, cwd=None, env=None, tool='run_shell_command'):
    clean = {k: v for k, v in os.environ.items() if k not in ('AI_KIT_ALLOW_PROD', 'AI_KIT_PROD_TARGETS', 'AI_KIT_PROTECTED_BRANCHES',
                                                               'TF_WORKSPACE', 'KUBECONFIG', 'DBT_TARGET')}
    proc = subprocess.run([sys.executable, '-I', str(GUARD), *rules], input=json.dumps({'tool_name': tool, 'tool_input': {'command': command}, 'cwd': cwd or tempfile.gettempdir()}),
                          capture_output=True, text=True, encoding='utf-8', env={**clean, **(env or {})})
    return json.loads(proc.stdout or '{}')


def denied(answer):
    return answer.get('decision') == 'deny'


class Folder(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        self.env = {'HOME': str(self.home), 'USERPROFILE': str(self.home)}

    def repo(self, branch='main', name='repo'):
        repo = self.home/name
        (repo/'.git').mkdir(parents=True)
        (repo/'.git'/'HEAD').write_text('ref: refs/heads/'+branch+'\n', encoding='utf-8')
        return repo


class GitGuardTests(Folder):
    REFUSED = ('git reset --hard', 'git reset --hard HEAD~1', 'cd repo && git clean -fd', 'git clean -xdf', 'git clean --force -d',
               'git checkout -- .', 'git checkout .', 'git checkout -f other', 'git restore .', 'git restore --staged --worktree .',
               'git branch -D old', 'git branch --delete --force old', 'git push --force origin main', 'git push -f origin master',
               'git push origin +main', 'git push --force-with-lease origin main', 'git push origin HEAD:main --force',
               'git push origin --delete main', 'git push origin :main', 'git push --force --all',
               'sh -c "git push -f origin main"', 'bash -lc git reset --hard', 'sudo git reset --hard', 'git -C repo reset --hard',
               'git status\ngit reset --hard', 'git status; git clean -fd', 'echo $(git reset --hard)', 'true | xargs git clean -f',
               'GIT_DIR=x git reset --hard', '/usr/bin/git reset --hard', 'git.exe reset --hard', 'eval "git reset --hard"')
    ALLOWED = ('git status', 'git diff', 'git log --grep="reset --hard"', 'echo "git clean -fd" >> notes.md', 'grep -r "push --force" docs/',
               'git reset HEAD~1', 'git reset --soft HEAD~1', 'git clean -n', 'git clean -nfd', 'git clean --dry-run -f', 'git checkout main',
               'git checkout -b feature', 'git checkout -- src/a.py', 'git restore src/a.py', 'git restore --staged .', 'git branch -d merged',
               'git push', 'git push origin feature', 'git push --force-with-lease origin feature', 'git push --force origin feature',
               'git commit -m "explain git reset --hard"', 'cat <<EOF > notes.md\ngit reset --hard\nEOF', 'git stash', 'git push -u origin feature')

    def test_refused(self):
        for command in self.REFUSED:
            self.assertTrue(denied(run(['git-guard'], command, env=self.env)), command)

    def test_allowed(self):
        for command in self.ALLOWED:
            self.assertEqual(run(['git-guard'], command, env=self.env), {}, command)

    def test_forced_push_reads_the_current_branch(self):
        self.assertTrue(denied(run(['git-guard'], 'git push --force', cwd=str(self.repo('main')), env=self.env)))
        self.assertTrue(denied(run(['git-guard'], 'git push --force-with-lease', cwd=str(self.repo('master', 'other')), env=self.env)))
        feature = str(self.repo('feature', 'third'))
        self.assertEqual(run(['git-guard'], 'git push --force', cwd=feature, env=self.env), {})
        self.assertEqual(run(['git-guard'], 'git push --force-with-lease', cwd=feature, env=self.env), {})
        # No repository to read: a plain forced push is refused, a push with lease is not.
        self.assertTrue(denied(run(['git-guard'], 'git push --force', cwd=str(self.home), env=self.env)))
        self.assertEqual(run(['git-guard'], 'git push --force-with-lease', cwd=str(self.home), env=self.env), {})

    def test_the_organization_adds_main_branches(self):
        env = {**self.env, 'AI_KIT_PROTECTED_BRANCHES': 'develop, release'}
        self.assertTrue(denied(run(['git-guard'], 'git push --force origin develop', env=env)))
        self.assertTrue(denied(run(['git-guard'], 'git push --force origin main', env=env)))
        self.assertEqual(run(['git-guard'], 'git push --force origin develop', env=self.env), {})

    def test_the_refusal_says_what_to_do(self):
        reason = run(['git-guard'], 'git reset --hard', env=self.env)['reason']
        self.assertIn('Blocked by the kit', reason)
        self.assertIn('run it yourself', reason)


class BqCostGuardTests(Folder):
    REFUSED = ('bq query "select 1"', 'bq query --use_legacy_sql=false "select * from t"', 'bq --project_id=p query "select 1"',
               'bq --location=EU query --nouse_legacy_sql "select 1"', 'bq query --dry_run=false "select 1"',
               'cd x && bq query "select 1"', 'echo "select 1" | bq query', 'sh -c "bq query \'select 1\'"')
    ALLOWED = ('bq query --dry_run "select 1"', 'bq query --dry_run=true "select 1"', 'bq query --maximum_bytes_billed=1000000 "select 1"',
               'bq --project_id=p query --dry_run "select 1"', 'bq ls', 'bq show p:d.t', 'bq head -n 5 d.t', 'bq mk d',
               'echo "bq query select 1"', 'grep -r "bq query" docs', 'git commit -m "bq query"')

    def test_refused(self):
        for command in self.REFUSED:
            self.assertTrue(denied(run(['bq-cost-guard'], command, env=self.env)), command)

    def test_allowed(self):
        for command in self.ALLOWED:
            self.assertEqual(run(['bq-cost-guard'], command, env=self.env), {}, command)


class InfraProdGuardTests(Folder):
    REFUSED = ('kubectl --context prod delete pod x', 'kubectl delete pod x --context=gke_project_prod_eu', 'kubectl -n production apply -f x.yaml',
               'kubectl --namespace=app-prod scale deploy/x --replicas=0', 'kubectl --context prd rollout restart deploy/x',
               'kubectl --context=$CTX delete pod x', 'kubectl --cluster prod-eu patch deploy x -p {}',
               'terraform apply -var-file=prod.tfvars', 'terraform destroy -var-file envs/production.tfvars', 'terraform -chdir=envs/prod apply',
               'TF_WORKSPACE=prod terraform apply -auto-approve', 'tofu -chdir=live/prd destroy', 'sh -c "kubectl --context prod delete ns x"')
    ALLOWED = ('kubectl --context prod get pods', 'kubectl --context prod describe pod x', 'kubectl --context prod logs x',
               'kubectl --context prod rollout status deploy/x', 'kubectl --context dev delete pod x', 'kubectl -n staging apply -f x.yaml',
               'kubectl --context dev delete pod product-api', 'terraform plan -var-file=prod.tfvars', 'terraform -chdir=envs/prod plan',
               'terraform apply -var-file=dev.tfvars', 'terraform -chdir=envs/dev apply', 'terraform workspace select prod',
               'echo "kubectl --context prod delete pod x"', 'grep -r "terraform destroy" docs', 'terraform fmt')

    def test_refused(self):
        for command in self.REFUSED:
            self.assertTrue(denied(run(['infra-prod-guard'], command, cwd=str(self.home), env=self.env)), command)

    def test_allowed(self):
        for command in self.ALLOWED:
            self.assertEqual(run(['infra-prod-guard'], command, cwd=str(self.home), env=self.env), {}, command)

    def test_kubectl_reads_the_current_context(self):
        (self.home/'.kube').mkdir()
        (self.home/'.kube'/'config').write_text('apiVersion: v1\ncurrent-context: gke_p_prod\n', encoding='utf-8')
        self.assertTrue(denied(run(['infra-prod-guard'], 'kubectl delete pod x', env=self.env)))
        self.assertEqual(run(['infra-prod-guard'], 'kubectl get pods', env=self.env), {})
        self.assertEqual(run(['infra-prod-guard'], 'kubectl --context dev delete pod x', env=self.env), {})  # the context named wins
        other = self.home/'dev.yaml'
        other.write_text('current-context: dev\n', encoding='utf-8')
        self.assertEqual(run(['infra-prod-guard'], 'kubectl delete pod x', env={**self.env, 'KUBECONFIG': str(other)}), {})
        self.assertEqual(run(['infra-prod-guard'], 'kubectl --kubeconfig '+str(other)+' delete pod x', env=self.env), {})

    def test_terraform_reads_the_workspace_and_the_folder(self):
        repo = self.repo()
        (repo/'.terraform').mkdir()
        (repo/'.terraform'/'environment').write_text('prod', encoding='utf-8')
        self.assertTrue(denied(run(['infra-prod-guard'], 'terraform apply', cwd=str(repo), env=self.env)))
        (repo/'.terraform'/'environment').write_text('dev', encoding='utf-8')
        self.assertEqual(run(['infra-prod-guard'], 'terraform apply', cwd=str(repo), env=self.env), {})
        (repo/'envs'/'prod').mkdir(parents=True)
        self.assertTrue(denied(run(['infra-prod-guard'], 'terraform apply', cwd=str(repo/'envs'/'prod'), env=self.env)))
        # A repository named after production is not a production folder: only the folders below its root count.
        named = self.repo(name='production-infra')
        self.assertEqual(run(['infra-prod-guard'], 'terraform apply', cwd=str(named), env=self.env), {})

    def test_extra_production_names_and_the_one_off_permission(self):
        self.assertTrue(denied(run(['infra-prod-guard'], 'kubectl --context live delete pod x', env={**self.env, 'AI_KIT_PROD_TARGETS': 'live'})))
        allowed = run(['infra-prod-guard'], 'kubectl --context prod delete pod x', cwd=str(self.home), env={**self.env, 'AI_KIT_ALLOW_PROD': '1'})
        self.assertIn('allowed by AI_KIT_ALLOW_PROD=1', allowed.get('systemMessage', ''))
        (self.home/'.env').write_text('AI_KIT_ALLOW_PROD=1\n', encoding='utf-8')  # a file the agent can write does not allow it
        self.assertTrue(denied(run(['infra-prod-guard'], 'kubectl --context prod delete pod x', cwd=str(self.home), env={**self.env, 'AI_KIT_ALLOW_PROD': '1'})))


class SharedScriptTests(Folder):
    def test_only_the_rules_named_apply(self):
        self.assertEqual(run([], 'git reset --hard', env=self.env), {})
        self.assertEqual(run(['bq-cost-guard'], 'git reset --hard', env=self.env), {})
        self.assertTrue(denied(run(ALL, 'git reset --hard', env=self.env)))
        self.assertTrue(denied(run(ALL, 'dbt run --target prod', env=self.env)))
        self.assertTrue(denied(run(ALL, 'bq query "select 1"', env=self.env)))
        self.assertEqual(run(['unknown-rule'], 'git reset --hard', env=self.env), {})

    def test_other_tools_and_odd_commands_pass(self):
        self.assertEqual(run(ALL, 'git reset --hard', env=self.env, tool='write_file'), {})
        for command in ('', '"', "echo 'unbalanced", 'ls -la', '(((', 'a' * 20000):
            self.assertEqual(run(ALL, command, env=self.env), {}, command[:30])

    def test_the_cli_shapes(self):
        payloads = ({'toolCall': {'name': 'run_command', 'args': {'CommandLine': 'git reset --hard'}}, 'workspacePaths': [str(self.home)]},
                    {'hook_event_name': 'PreToolUse', 'tool_name': 'shell', 'tool_input': {'command': ['bash', '-lc', 'git reset --hard']}, 'cwd': str(self.home)},
                    {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': 'git reset --hard'}, 'cwd': str(self.home)})
        for payload in payloads:
            proc = subprocess.run([sys.executable, '-I', str(GUARD), 'git-guard'], input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8')
            answer = json.loads(proc.stdout)
            self.assertTrue(denied(answer) or answer.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny', payload)


class RefusalCountTests(Folder):
    """Each refusal leaves one line, a date and a guardrail name, written by the installed copy only; ai-kit usage counts them."""
    def installed(self, script):
        hooks = self.home/'.ai-kit'/'hooks'
        hooks.mkdir(parents=True, exist_ok=True)
        shutil.copy(GUARD.parent/script, hooks/script)
        return hooks/script

    def call(self, script, rules, payload, env=None):
        proc = subprocess.run([sys.executable, '-I', str(script), *rules], input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8',
                              env={**os.environ, **self.env, **(env or {})})
        return json.loads(proc.stdout or '{}')

    def test_a_refusal_is_recorded_without_the_command(self):
        shell, paths = self.installed('shell-guard.py'), self.installed('protected-paths.py')
        log = self.home/'.ai-kit'/'refusals.jsonl'
        command = {'tool_name': 'run_shell_command', 'tool_input': {'command': 'git reset --hard secret-branch'}, 'cwd': str(self.home)}
        self.assertTrue(denied(self.call(shell, ['git-guard'], command)))
        self.assertEqual(self.call(shell, ['git-guard'], {**command, 'tool_input': {'command': 'git status'}}), {})
        self.assertTrue(denied(self.call(paths, [], {'tool_name': 'write_file', 'tool_input': {'file_path': str(self.home/'.ai-kit'/'aikit.toml')}, 'cwd': str(self.home)})))
        lines = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
        self.assertEqual([entry['guardrail'] for entry in lines], ['git-guard', 'protected-paths'])
        self.assertEqual(sorted(lines[0]), ['guardrail', 'ts'])
        self.assertNotIn('secret-branch', log.read_text(encoding='utf-8'))
        # A doctor probe is not a refusal of the agent's work.
        self.assertTrue(denied(self.call(shell, ['git-guard'], command, {'AI_KIT_PROBE': '1'})))
        self.assertEqual(len(log.read_text(encoding='utf-8').splitlines()), 2)

    def test_the_copy_in_the_repo_records_nothing(self):
        (self.home/'.ai-kit').mkdir()
        self.assertTrue(denied(run(['git-guard'], 'git reset --hard', env=self.env)))
        self.assertFalse((self.home/'.ai-kit'/'refusals.jsonl').exists())

    def test_the_file_stays_small(self):
        shell = self.installed('shell-guard.py')
        log = self.home/'.ai-kit'/'refusals.jsonl'
        log.write_text(''.join(json.dumps({'ts': '2020-01-01T00:00:00Z', 'guardrail': 'git-guard'})+'\n' for _ in range(5000)), encoding='utf-8')
        self.call(shell, ['git-guard'], {'tool_name': 'run_shell_command', 'tool_input': {'command': 'git reset --hard'}})
        self.assertEqual(len(log.read_text(encoding='utf-8').splitlines()), 1001)

    def test_usage_counts_the_refusals_of_the_window(self):
        with contextlib.redirect_stdout(io.StringIO()):
            apply_as('data-analyst', self.home, False, None, 'gemini')
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        entries = [{'ts': now, 'guardrail': 'protected-paths'}] * 2 + [{'ts': now, 'guardrail': 'git-guard'}, {'ts': '2020-01-01T00:00:00Z', 'guardrail': 'git-guard'}]
        (self.home/'.ai-kit'/'refusals.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in entries)+'not json\n', encoding='utf-8')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            usage(self.home, 42, self.home/'r.json')
        self.assertIn('Guardrail refusals: 3 (protected-paths ×2, git-guard ×1)', out.getvalue())
        self.assertEqual(read_json(self.home/'r.json')['guardrail_refusals'], {'protected-paths': 2, 'git-guard': 1})


class OneHookTests(Folder):
    """However many shell guardrails are on, each CLI gets one hook for them, told which ones are on."""
    def install(self, hooks):
        (self.home/'.codex').mkdir(exist_ok=True)
        (self.home/'.claude').mkdir(exist_ok=True)
        with contextlib.redirect_stdout(io.StringIO()):
            write_personal(self.home, {'hooks': hooks})
            apply_as('data-analyst', self.home, False, None, 'all')

    def test_one_hook_on_the_four_clis(self):
        self.install({name: True for name in ALL})
        served = ' dbt-prod-guard git-guard bq-cost-guard infra-prod-guard'
        gemini = [g['hooks'][0] for g in read_json(self.home/'.gemini/settings.json')['hooks']['BeforeTool']]
        self.assertEqual(sorted(h['name'] for h in gemini), ['ai-kit-protected-paths', 'ai-kit-shell-guard'])
        self.assertTrue(next(h for h in gemini if h['name'] == 'ai-kit-shell-guard')['command'].endswith(served))
        claude = [g['hooks'][0]['command'] for g in read_json(self.home/'.claude/settings.json')['hooks']['PreToolUse']]
        self.assertEqual(sum('shell-guard.py' in c for c in claude), 1)
        self.assertTrue(next(c for c in claude if 'shell-guard.py' in c).endswith(served))
        codex = (self.home/'.codex/config.toml').read_text(encoding='utf-8')
        self.assertEqual(codex.count('shell-guard.py'), 1)
        self.assertIn(served, codex)
        agy = read_json(self.home/'.gemini/config/plugins/ai-kit/hooks.json')
        self.assertEqual(sorted(agy), ['ai-kit-protected-paths', 'ai-kit-shell-guard', 'ai-kit-whats-new'])
        self.assertTrue(agy['ai-kit-shell-guard']['enabled'])
        state = read_json(self.home/'.ai-kit/state.json')
        self.assertEqual(sorted(state['hooks']), sorted(ALL + ('protected-paths', 'whats-new')))  # the names a person writes
        self.assertEqual(sorted(p.name for p in (self.home/'.ai-kit/hooks').iterdir()), ['protected-paths.py', 'shell-guard.py', 'whats-new.py'])

    def test_turning_one_off_keeps_the_others(self):
        self.install({name: True for name in ALL})
        self.install({'git-guard': True})
        command = next(g['hooks'][0]['command'] for g in read_json(self.home/'.gemini/settings.json')['hooks']['BeforeTool'] if g['hooks'][0]['name'] == 'ai-kit-shell-guard')
        self.assertTrue(command.endswith('shell-guard.py git-guard') or command.endswith("shell-guard.py' git-guard") or command.endswith('shell-guard.py" git-guard'))
        self.install({})
        self.assertEqual([g['hooks'][0]['name'] for g in read_json(self.home/'.gemini/settings.json')['hooks']['BeforeTool']], ['ai-kit-protected-paths'])
        self.assertFalse((self.home/'.ai-kit/hooks/shell-guard.py').exists())
        self.assertFalse(read_json(self.home/'.gemini/config/plugins/ai-kit/hooks.json')['ai-kit-shell-guard']['enabled'])

    def test_doctor_proves_each_rule_turned_on(self):
        self.install({name: True for name in ALL})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            doctor(self.home)
        for name in ALL + ('protected-paths',):
            self.assertIn('[OK] Guardrail '+name+': synthetic test, the script blocks a known case when run', out.getvalue())
        self.assertFalse((self.home/'.ai-kit/refusals.jsonl').exists())  # the probes are not counted

    def test_it_files_carry_one_hook(self):
        imposed = self.home/'managed.toml'
        imposed.write_text('managed_schema = 1\n[hooks]\nlocked = ["protected-paths", "git-guard", "dbt-prod-guard"]\n', encoding='utf-8')
        with mock.patch('installer.config.ownership_problem', return_value=None), contextlib.redirect_stdout(io.StringIO()):
            managed_settings(self.home/'out', True, False, managed_file=imposed)
        for rel in ('claude-code/managed-settings.json', 'windows/claude-code/managed-settings.json'):
            commands = [h['command'] for g in read_json(self.home/'out'/rel)['hooks']['PreToolUse'] for h in g['hooks']]
            self.assertEqual(len(commands), 2, rel)
            self.assertTrue(any(c.endswith('shell-guard.py" git-guard dbt-prod-guard') or c.endswith('shell-guard.py" dbt-prod-guard git-guard') for c in commands), commands)


class TimeTests(Folder):
    def test_a_guardrail_answers_quickly(self):
        """A coarse ceiling: one run on a harmless command, best of three, well under half a second. It catches a guardrail
        that starts loading or reading much more, not a few milliseconds."""
        payload = json.dumps({'tool_name': 'run_shell_command', 'tool_input': {'command': 'cd src && grep -rn target models | head -20 && git status'}, 'cwd': str(self.home)})
        for script, rules in (('shell-guard.py', list(ALL)), ('protected-paths.py', [])):
            best = None
            for _ in range(3):
                start = time.perf_counter()
                proc = subprocess.run([sys.executable, '-I', str(GUARD.parent/script), *rules], input=payload, capture_output=True, text=True, encoding='utf-8')
                elapsed = time.perf_counter() - start
                best = elapsed if best is None else min(best, elapsed)
                self.assertEqual(proc.stdout.strip(), '{}')
            self.assertLess(best, 0.5, script)


if __name__ == '__main__':
    unittest.main()
