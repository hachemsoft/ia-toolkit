"""scripts/release_status.py: the verdict on a release tag, from what GitHub and GitLab report (read only, no network here).
2026-11-22: the same gh/glab watch was written by hand for each of nine releases."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_status', ROOT/'scripts/release_status.py')


def module():
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


ASSETS = ['ai-kit-4.24.0.zip', 'SHA256SUMS.txt']
GREEN = {'status': 'completed', 'conclusion': 'success', 'jobs': [{'name': 'Publish the release', 'conclusion': 'success'}]}


class VerdictTests(unittest.TestCase):
    def verdict(self, github=GREEN, gitlab='success', gh_assets=ASSETS, gl_assets=ASSETS):
        self.assertTrue((ROOT/'scripts/release_status.py').is_file(), 'scripts/release_status.py is missing')
        return module().verdict('4.24.0', github, gitlab, gh_assets, gl_assets)

    def test_a_published_release_is_ok(self):
        result = self.verdict()
        self.assertEqual(result['state'], 'ok', result)
        self.assertEqual(result['problems'], [])

    def test_a_failed_required_job_is_a_problem(self):
        github = {'status': 'completed', 'conclusion': 'failure',
                  'jobs': [{'name': 'windows-latest / Python 3.14', 'conclusion': 'failure'}, {'name': 'Publish the release', 'conclusion': 'skipped'}]}
        result = self.verdict(github=github, gh_assets=[])
        self.assertEqual(result['state'], 'failed', result)
        self.assertTrue(any('windows-latest / Python 3.14' in p for p in result['problems']), result)
        self.assertTrue(any('GitHub release' in p for p in result['problems']), result)

    def test_an_indicative_job_is_a_warning_not_a_problem(self):
        github = {'status': 'completed', 'conclusion': 'failure',
                  'jobs': [{'name': 'Upgrade from the latest release (container, indicative)', 'conclusion': 'failure'},
                           {'name': 'Publish the release', 'conclusion': 'success'}]}
        result = self.verdict(github=github)
        self.assertEqual(result['state'], 'ok', result)
        self.assertTrue(any('indicative' in w for w in result['warnings']), result)

    def test_a_missing_gitlab_asset_is_a_problem(self):
        result = self.verdict(gl_assets=['ai-kit-4.24.0.zip'])
        self.assertEqual(result['state'], 'failed', result)
        self.assertTrue(any('GitLab release' in p and 'SHA256SUMS.txt' in p for p in result['problems']), result)

    def test_a_run_still_going_is_pending(self):
        result = self.verdict(github={'status': 'in_progress', 'conclusion': '', 'jobs': []}, gitlab='running', gh_assets=[], gl_assets=[])
        self.assertEqual(result['state'], 'pending', result)

    def test_no_run_for_the_tag_is_a_problem(self):
        result = self.verdict(github=None, gitlab=None, gh_assets=[], gl_assets=[])
        self.assertEqual(result['state'], 'failed', result)
        self.assertTrue(any('no GitHub run' in p for p in result['problems']), result)


if __name__ == '__main__':
    unittest.main()
