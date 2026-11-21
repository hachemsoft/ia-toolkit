"""scripts/gitlab_release.py (4.19.2): the ZIP of a vX.Y.Z tag attached to the tag's GitLab release."""
import importlib.util, os, tempfile, unittest
from pathlib import Path
from unittest import mock
from installer.core import ROOT

spec = importlib.util.spec_from_file_location('gitlab_release', ROOT/'scripts/gitlab_release.py')
release = importlib.util.module_from_spec(spec); spec.loader.exec_module(release)
VERSION = (ROOT/'VERSION').read_text(encoding='utf-8').strip()
ENV = {'CI_COMMIT_TAG': 'v'+VERSION, 'CI_JOB_TOKEN': 't', 'CI_API_V4_URL': 'https://git.example.org/api/v4', 'CI_PROJECT_ID': '7'}


class GitlabReleaseTests(unittest.TestCase):
    def test_release_notes_are_the_tag_s_changelog_section(self):
        text = '# Changelog\n\n## 1.2.0 (2026-01-02)\n\nNew.\n\n- a\n\n## 1.1.0 (2026-01-01)\n\nOld.\n'
        self.assertEqual(release.changelog_section(text, '1.2.0'), 'New.\n\n- a')
        self.assertEqual(release.changelog_section(text, '1.1.0'), 'Old.')
        self.assertEqual(release.changelog_section(text, '1.2'), '')  # never a prefix of another version
        self.assertTrue(release.changelog_section((ROOT/'CHANGELOG.md').read_text(encoding='utf-8'), VERSION))

    def test_only_missing_links_are_added(self):
        wanted = [{'name': 'ai-kit-1.zip', 'url': 'u1'}, {'name': 'SHA256SUMS.txt', 'url': 'u2'}]
        self.assertEqual(release.plan_links([{'name': 'ai-kit-1.zip', 'url': 'x'}], wanted), [wanted[1]])

    def run_main(self, env, existing=None):
        calls = []
        def api(method, url, token, data=None, raw=None):
            calls.append((method, url, data))
            if method == 'GET':
                return (404, None) if existing is None else (200, existing)
            return 201, {}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(release, 'ROOT', Path(tmp)), mock.patch.object(release, 'api', side_effect=api):
            for name in ('VERSION', 'CHANGELOG.md'):
                (Path(tmp)/name).write_text((ROOT/name).read_text(encoding='utf-8'), encoding='utf-8')
            (Path(tmp)/'dist').mkdir(); (Path(tmp)/'dist'/('ai-kit-'+VERSION+'.zip')).write_bytes(b'zip')
            release.main()
        return calls

    def test_a_tag_without_release_gets_one_with_the_zip_and_its_checksum(self):
        calls = self.run_main(ENV)
        puts = [url for method, url, _ in calls if method == 'PUT']
        self.assertEqual(puts, [ENV['CI_API_V4_URL']+'/projects/7/packages/generic/ai-kit/'+VERSION+'/'+name
                                for name in ('ai-kit-'+VERSION+'.zip', 'SHA256SUMS.txt')])
        created = [data for method, url, data in calls if method == 'POST' and url.endswith('/releases')][0]
        self.assertEqual(created['tag_name'], 'v'+VERSION)
        self.assertEqual([link['name'] for link in created['assets']['links']], ['ai-kit-'+VERSION+'.zip', 'SHA256SUMS.txt'])

    def test_an_existing_release_only_gets_the_missing_links(self):
        calls = self.run_main(ENV, existing={'assets': {'links': [{'name': 'SHA256SUMS.txt'}]}})
        posts = [(url, data['name']) for method, url, data in calls if method == 'POST']
        self.assertEqual(posts, [(ENV['CI_API_V4_URL']+'/projects/7/releases/v'+VERSION+'/assets/links', 'ai-kit-'+VERSION+'.zip')])

    def test_a_tag_other_than_v_version_is_refused_before_any_upload(self):
        with self.assertRaises(SystemExit) as raised:
            self.run_main({**ENV, 'CI_COMMIT_TAG': 'v0.0.1'})
        self.assertIn('VERSION', str(raised.exception))


if __name__ == '__main__':
    unittest.main()
