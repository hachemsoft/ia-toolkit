"""0.41: the secret detector (refused 30_USER.md, doctor on overrides.toml, redacted frictions and messages) catches the
common forms the 0.40 audit found missing, and not ordinary settings."""
import unittest

from installer.core import SECRET

CAUGHT = ('DB_PASSWORD=hunter22x', 'AWS_SECRET_ACCESS_KEY=abcdEFGH1234', 'access_token = "abcdef123456"', '"password": "s3cretValue"',
          'client_secret: Zz9yy8xx', 'postgres://admin:pa55word@db:5432/x', 'Authorization: Basic dXNlcjpwYXNzd29yZDEyMzQ=',
          'sk_live_abcdefghijklmnop1234', 'hf_' + 'a' * 34, 'npm_' + 'b' * 36, 'api_key = abcdefghijklmnop1234')
ALLOWED = ('max_tokens = 400000', 'tokenizer = bpe-fast', 'token: ${MY_TOKEN}', 'password = "${DB_PASSWORD}"',
           'https://example.org/docs', 'the password policy', 'env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }')


class SecretTests(unittest.TestCase):
    def test_common_forms_are_caught(self):
        self.assertEqual([s for s in CAUGHT if not SECRET.search(s)], [])

    def test_settings_and_variables_are_not_secrets(self):
        self.assertEqual([s for s in ALLOWED if SECRET.search(s)], [])


class McpSecretTests(unittest.TestCase):
    def test_a_secret_value_in_a_server_is_refused_a_variable_accepted(self):
        from installer import cli
        from installer.core import KitError
        cli.validate_server({'command': 'my-mcp', 'env': {'GITHUB_TOKEN': '${GITHUB_TOKEN}', 'REGION': 'eu'}})
        for env in ({'GITHUB_TOKEN': 'ghp_' + 'x' * 36}, {'API_KEY': 'abc123def456'}, {'X': 'postgres://u:pa55word@h/db'}):
            with self.subTest(env), self.assertRaises(KitError):
                cli.validate_server({'command': 'my-mcp', 'env': env})
        with self.assertRaises(KitError):
            cli.validate_server({'httpUrl': 'https://x.example.org/mcp', 'headers': {'Authorization': 'Bearer abcdefghijklmnopqrst'}})


class BackupTests(unittest.TestCase):
    def test_only_the_most_recent_backups_stay(self):
        import tempfile
        from pathlib import Path
        from installer import cli
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp)
            for i in range(25):
                (kit/'backups'/('202611%02dT000000-abcd1234' % (i + 1))).mkdir(parents=True)
            (kit/'backups'/'manual-copy').mkdir()
            cli.prune_backups(kit, keep=20)
            names = sorted(p.name for p in (kit/'backups').iterdir())
            self.assertEqual(len(names), 21)
            self.assertIn('manual-copy', names)  # only the kit's dated backups are pruned
            self.assertNotIn('20261101T000000-abcd1234', names)


class LockedHookTests(unittest.TestCase):
    def test_a_locked_guardrail_stays_on_whatever_the_person_writes(self):
        import contextlib, io, json, tempfile
        from pathlib import Path
        from unittest import mock
        from installer import cli
        from installer.toml_files import dump_toml
        with tempfile.TemporaryDirectory() as tmp, mock.patch('shutil.which', return_value=None):
            home = Path(tmp)
            (home/'.ai-kit').mkdir()
            (home/'.ai-kit/overrides.toml').write_text(dump_toml({'hooks': {'protected-paths': False}}), encoding='utf-8')
            real = cli.read_toml
            org = {'locked_hooks': ['protected-paths'], 'defaults': {}}
            with mock.patch.object(cli, 'read_toml', side_effect=lambda p, d=None: org if Path(p).name == 'organization.toml' else real(p, d)), \
                    contextlib.redirect_stdout(io.StringIO()):
                notices = cli.apply('general', home, False, {'email': 'a@example.org', 'source': 'option'}, 'gemini')
            self.assertIn('protected-paths', json.loads((home/'.ai-kit/state.json').read_text(encoding='utf-8'))['hooks'])
            self.assertTrue(any('stays on' in n for n in notices))


class ReleaseTests(unittest.TestCase):
    def test_actions_are_pinned_by_commit_and_assets_never_overwritten(self):
        import re
        from installer.core import ROOT
        for workflow in (ROOT/'.github/workflows').glob('*.yml'):
            text = workflow.read_text(encoding='utf-8')
            for use in re.findall(r'uses:\s*(\S+)', text):
                self.assertRegex(use, r'@[0-9a-f]{40}$', workflow.name + ': ' + use)
        publish = (ROOT/'.github/workflows/portability.yml').read_text(encoding='utf-8')
        self.assertNotIn('--clobber', publish)
        self.assertIn('SHA256SUMS.txt', publish)
        self.assertIn('attest-build-provenance', publish)


if __name__ == '__main__':
    unittest.main()
