"""Where a release tag stands on GitHub and GitLab: the tag's CI, the jobs that failed, and whether each release carries
its ZIP and SHA256SUMS.txt. Read only: it calls `gh` and `glab` to read, never to push, tag or publish.

Usage: python3 scripts/release_status.py vX.Y.Z [--wait] [--interval 45] [--timeout 1800]
The GitHub and GitLab projects are read from the `origin` and `gitlab` remotes (--github-remote, --gitlab-remote).
Exit code: 0 published, 1 a problem, 2 still running (without --wait) or a tool missing.
A job whose name says "indicative" is reported as a warning: it never blocks the release (portability.yml).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time

WORKFLOW = 'Portability'


def expected_assets(version):
    return ['ai-kit-' + version + '.zip', 'SHA256SUMS.txt']


def verdict(version, github, gitlab, gh_assets, gl_assets):
    """{'state': ok | pending | failed, 'problems': [...], 'warnings': [...]} from what the two hosts report.
    github: {'status', 'conclusion', 'jobs': [{'name', 'conclusion'}]} or None; gitlab: a pipeline status or None."""
    problems, warnings = [], []
    if github is None:
        problems.append('no GitHub run for the tag')
    if gitlab is None:
        problems.append('no GitLab pipeline for the tag')
    pending = (github is not None and github.get('status') != 'completed') or gitlab in ('running', 'pending', 'created')
    if pending:
        return {'state': 'pending', 'problems': problems, 'warnings': warnings}
    for job in (github or {}).get('jobs', []):
        if job.get('conclusion') in ('success', 'skipped', None, ''):
            continue
        line = 'GitHub job ' + job.get('conclusion', '?') + ': ' + job.get('name', '?')
        (warnings if 'indicative' in job.get('name', '').lower() else problems).append(line)
    if gitlab not in (None, 'success'):
        problems.append('GitLab pipeline ' + str(gitlab))
    for host, assets in (('GitHub release', gh_assets), ('GitLab release', gl_assets)):
        missing = [name for name in expected_assets(version) if name not in assets]
        if missing:
            problems.append(host + ' lacks ' + ', '.join(missing))
    return {'state': 'failed' if problems else 'ok', 'problems': problems, 'warnings': warnings}


def run(*command):
    proc = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return proc.stdout if proc.returncode == 0 else ''


def project(remote):
    """owner/name of a remote's URL (git@host:owner/name.git or https://host/owner/name.git)."""
    url = run('git', 'remote', 'get-url', remote).strip()
    match = re.search(r'[:/]([^/:]+/[^/]+?)(?:\.git)?$', url)
    return match.group(1) if match else None


def github_state(repo, tag):
    listed = run('gh', 'run', 'list', '-R', repo, '--branch', tag, '--workflow', WORKFLOW, '--limit', '1', '--json', 'databaseId')
    runs = json.loads(listed) if listed.strip() else []
    if not runs:
        return None
    viewed = run('gh', 'run', 'view', str(runs[0]['databaseId']), '-R', repo, '--json', 'status,conclusion,jobs')
    data = json.loads(viewed) if viewed.strip() else {}
    return {'status': data.get('status'), 'conclusion': data.get('conclusion'),
            'jobs': [{'name': j.get('name'), 'conclusion': j.get('conclusion')} for j in data.get('jobs', [])]}


def gitlab_state(repo, tag):
    for line in run('glab', 'ci', 'list', '-R', repo, '--per-page', '20').splitlines():
        if re.search(r'\s' + re.escape(tag) + r'\s', line + ' '):
            match = re.match(r'\((\w+)\)', line.strip())
            return match.group(1) if match else None
    return None


def assets(tag, version, github_repo, gitlab_repo):
    listed = run('gh', 'release', 'view', tag, '-R', github_repo, '--json', 'assets')
    gh = [a['name'] for a in json.loads(listed).get('assets', [])] if listed.strip() else []
    text = run('glab', 'release', 'view', tag, '-R', gitlab_repo)
    gl = [name for name in expected_assets(version) if name in text]
    return gh, gl


def main(argv=None):
    parser = argparse.ArgumentParser(description='Where a release tag stands on GitHub and GitLab (read only).')
    parser.add_argument('tag')
    parser.add_argument('--wait', action='store_true', help='poll until both hosts are done')
    parser.add_argument('--interval', type=int, default=45)
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--github-remote', default='origin')
    parser.add_argument('--gitlab-remote', default='gitlab')
    args = parser.parse_args(argv)
    missing = [tool for tool in ('gh', 'glab', 'git') if not shutil.which(tool)]
    if missing:
        print('Missing: ' + ', '.join(missing), file=sys.stderr)
        return 2
    version = args.tag[1:] if args.tag.startswith('v') else args.tag
    github_repo, gitlab_repo = project(args.github_remote), project(args.gitlab_remote)
    deadline = time.monotonic() + args.timeout
    while True:
        github, gitlab = github_state(github_repo, args.tag), gitlab_state(gitlab_repo, args.tag)
        gh_assets, gl_assets = assets(args.tag, version, github_repo, gitlab_repo)
        result = verdict(version, github, gitlab, gh_assets, gl_assets)
        if result['state'] != 'pending' or not args.wait or time.monotonic() > deadline:
            break
        time.sleep(args.interval)
    print(args.tag + ': ' + result['state'] + ' (GitHub ' + str(github_repo) + ', GitLab ' + str(gitlab_repo) + ')')
    for line in result['problems']:
        print('  problem: ' + line)
    for line in result['warnings']:
        print('  warning: ' + line)
    return {'ok': 0, 'failed': 1}.get(result['state'], 2)


if __name__ == '__main__':
    raise SystemExit(main())
