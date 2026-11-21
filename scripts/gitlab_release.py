"""Publishes the release ZIP of a vX.Y.Z tag on a GitLab copy of the kit: the ZIP and its SHA256SUMS.txt go to the
project's generic package registry, then the tag's GitLab release links them, so that people download the ZIP from the
release page. Run by the publish-release job of .gitlab-ci.yml, after release-zip, on a tag only.

The release is created when the tag has none, with the tag's CHANGELOG section as its text; when one exists (made by hand
or by another tool), only the missing links are added. The tag must be v<VERSION>: the ZIP's name and the Core bundle it
ships both come from VERSION. Standard library only; authenticates with the job's CI_JOB_TOKEN."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = 'ai-kit'


def changelog_section(text, version):
    """The body of the CHANGELOG section '## <version> (...)', without its heading; '' when there is none."""
    match = re.search(r'^## '+re.escape(version)+r'(?=\s).*?\n(.*?)(?=^## |\Z)', text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ''


def plan_links(existing, wanted):
    """The links of wanted ({name, url, ...}) not already on the release (same name)."""
    names = {link['name'] for link in existing}
    return [link for link in wanted if link['name'] not in names]


def api(method, url, token, data=None, raw=None):
    """One GitLab API call with the job token; (status, parsed JSON or None)."""
    headers = {'JOB-TOKEN': token}
    body = raw
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = request.Request(url, data=body, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=120) as resp:
            payload = resp.read()
            return resp.status, (json.loads(payload) if payload.strip() else None)
    except error.HTTPError as exc:
        if exc.code == 404 and method == 'GET':
            return 404, None
        raise SystemExit(method+' '+url+' failed: HTTP '+str(exc.code)+' '+exc.read().decode('utf-8', 'replace')[:300]) from None


def main():
    env = os.environ
    tag, token = env.get('CI_COMMIT_TAG', ''), env.get('CI_JOB_TOKEN', '')
    base = env.get('CI_API_V4_URL', '')+'/projects/'+env.get('CI_PROJECT_ID', '')
    version = (ROOT/'VERSION').read_text(encoding='utf-8').strip()
    if not (tag and token and env.get('CI_API_V4_URL') and env.get('CI_PROJECT_ID')):
        raise SystemExit('Run in a GitLab CI job of a tag: CI_COMMIT_TAG, CI_JOB_TOKEN, CI_API_V4_URL and CI_PROJECT_ID are needed.')
    if tag != 'v'+version:
        raise SystemExit('Tag '+tag+' is not v'+version+' (VERSION): the ZIP and its Core bundle are named after VERSION; tag v'+version+' instead.')
    zip_path = ROOT/'dist'/('ai-kit-'+version+'.zip')
    if not zip_path.is_file():
        raise SystemExit(str(zip_path)+' is missing: the release-zip job builds it.')
    data = zip_path.read_bytes()
    sums = (hashlib.sha256(data).hexdigest()+'  '+zip_path.name+'\n').encode('utf-8')

    wanted = []
    for name, content in ((zip_path.name, data), ('SHA256SUMS.txt', sums)):
        url = base+'/packages/generic/'+PACKAGE+'/'+version+'/'+name
        api('PUT', url, token, raw=content)
        wanted.append({'name': name, 'url': url, 'link_type': 'package', 'direct_asset_path': '/'+name})
        print('Uploaded '+name+' to the package registry ('+PACKAGE+' '+version+').')

    release_url = base+'/releases/'+parse.quote(tag, safe='')
    status, release = api('GET', release_url, token)
    if status == 404:
        notes = changelog_section((ROOT/'CHANGELOG.md').read_text(encoding='utf-8'), version) or 'AI Kit '+version+'.'
        api('POST', base+'/releases', token, data={'tag_name': tag, 'name': 'AI Kit '+version, 'description': notes,
                                                     'assets': {'links': wanted}})
        print('Release '+tag+' created with '+', '.join(link['name'] for link in wanted)+'.')
        return
    missing = plan_links(release.get('assets', {}).get('links', []), wanted)
    for link in missing:
        api('POST', release_url+'/assets/links', token, data=link)
    print('Release '+tag+' already exists: '+(('added '+', '.join(link['name'] for link in missing)) if missing else 'links already there')+'.')


if __name__ == '__main__':
    sys.exit(main())
