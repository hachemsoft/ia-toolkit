"""4.24.1: the MCP server checks read a name by its words and a command line by its options. A harmless setting whose name
holds "auth", "token" or "secret" inside another word is accepted (AUTHOR, --max-tokens, SECRET_MANAGER_PROJECT); a shell
script as the command, a user name in a URL, an interpreter's code flag glued to others (python3 -Ic) are refused; a
fetch-and-run launcher is pinned only when every package it fetches is, an option's value never counting as the package."""
import unittest

from installer import config
from installer.core import KitError
from installer.settings import SECRET_NAME, validate_server


class SecretNameTests(unittest.TestCase):
    def test_a_name_is_secret_by_its_last_words_not_by_a_piece_of_a_word(self):
        for name in ('TOKEN', 'API_TOKEN', '--token', 'GITHUB_TOKEN', 'accessToken', 'DB_PASSWORD', 'passwd', 'CLIENT_SECRET', 'Authorization',
                     'X-Api-Key', 'api_key', 'apikey', '--api-key', 'AWS_SECRET_ACCESS_KEY', 'PRIVATE_KEY', 'credential', 'SERVICE_CREDENTIALS',
                     'auth', 'BASIC_AUTH', '--auth'):
            self.assertTrue(SECRET_NAME.search(name), name)
        for name in ('AUTHOR', 'AUTH_TYPE', '--max-tokens', '--auth-mode', '--no-auth', 'SECRET_MANAGER_PROJECT', 'TOKENIZER', 'KEYBOARD', 'PORT',
                     '--token-file', 'AUTHORITY_URL', 'max_tokens', 'TOKEN_URL'):
            self.assertFalse(SECRET_NAME.search(name), name)

    def test_harmless_settings_are_accepted_and_real_secrets_still_refused(self):
        for server in ({'command': 'tool', 'env': {'AUTHOR': 'the team', 'AUTH_TYPE': 'oauth', 'SECRET_MANAGER_PROJECT': 'my-project'}},
                       {'command': 'tool', 'args': ['--max-tokens', '4096', '--auth-mode', 'device', '--no-auth', '--port', '8080']},
                       {'command': 'tool', 'args': ['--max-tokens=4096', '--auth-mode=device']},
                       {'url': 'https://h.example.org/mcp?max_tokens=100&auth_type=none'},
                       {'httpUrl': 'https://h.example.org/mcp', 'headers': {'X-Author': 'the team'}}):
            with self.subTest(server=server):
                validate_server(server)
        for server in ({'command': 'tool', 'env': {'API_TOKEN': 'abc123'}}, {'command': 'tool', 'args': ['--token', 'abc123']},
                       {'command': 'tool', 'args': ['--client-secret=abc123']}, {'url': 'https://h.example.org/mcp?access_token=abc123'},
                       {'httpUrl': 'https://h.example.org/mcp', 'headers': {'Authorization': 'Bearer abc123'}},
                       {'command': 'tool', 'env': {'BASIC_AUTH': 'user:abc123'}}):
            with self.subTest(server=server), self.assertRaises(KitError) as caught:
                validate_server(server)
            self.assertNotIn('abc123', str(caught.exception))


class CommandTests(unittest.TestCase):
    def refused(self, server):
        try:
            validate_server(server)
        except KitError:
            return True
        return False

    def test_a_shell_script_as_the_command_is_refused(self):
        for command in ('./start.sh', '/opt/tools/run.bash', 'serve.zsh', 'C:\\tools\\Start.PS1', 'my-server.cmd', 'C:\\tools\\run.BAT'):
            self.assertTrue(self.refused({'command': command}), command)
        for server in ({'command': 'npx.cmd', 'args': ['-y', 'pkg@1.0.0']}, {'command': r'C:\Program Files\nodejs\NPX.CMD', 'args': ['pkg@1.0.0']},
                       {'command': 'uvx.exe', 'args': ['tool==1.0.0']}, {'command': 'tracker-mcp.exe'}, {'command': '/usr/local/bin/tracker-mcp'}):
            self.assertFalse(self.refused(server), server)

    def test_a_user_name_in_a_url_is_refused(self):
        for url in ('https://x@blocked.example.org/mcp', 'https://allowed.example.org@blocked.example.org/mcp', 'https://user:${PW}@h.example.org/mcp'):
            self.assertTrue(self.refused({'httpUrl': url}), url)
            self.assertTrue(self.refused({'url': url}), url)
        self.assertFalse(self.refused({'httpUrl': 'https://h.example.org/mcp/@scope'}))

    def test_code_on_the_command_line_is_found_when_its_flag_is_glued(self):
        for command, args in (('python3', ['-Ic', 'import os']), ('python', ['-c', 'x']), ('python3.12', ['-cimport os']), ('python3', ['-Isc', 'x']),
                              ('py', ['-3', '-Ic', 'x']), ('node', ['-e', 'x']), ('node', ['-econsole.log(1)']), ('node', ['-pe', 'x']),
                              ('node', ['--eval=x']), ('node', ['--print=x']), ('ruby', ['-ne', 'x']), ('perl', ['-pe', 'x']), ('perl', ['-lane', 'x']),
                              ('php', ['-r', 'x']), ('bun', ['-e', 'x'])):
            self.assertTrue(self.refused({'command': command, 'args': args}), (command, args))
        for command, args in (('python3', ['-I', 'server.py']), ('python3', ['-m', 'my_server']), ('python', ['-X', 'utf8', 'server.py']),
                              ('python3', ['-W', 'ignore', 'server.py']), ('node', ['server.js']), ('node', ['--experimental-vm-modules', 'server.js']),
                              ('node', ['-r', 'dotenv/config', 'server.js']), ('ruby', ['server.rb']), ('deno', ['run', 'server.ts'])):
            self.assertFalse(self.refused({'command': command, 'args': args}), (command, args))


class LauncherTests(unittest.TestCase):
    def unpinned(self, command, *args):
        return config.unpinned_launcher({'command': command, 'args': list(args)})

    def test_an_option_value_is_never_taken_for_the_package(self):
        for command, args in (('npx', ('--cache', '/tmp/@1', 'evil-pkg')), ('npx', ('--registry', 'https://r.example.org/@1', 'evil-pkg')),
                              ('uvx', ('--python', '3.12', 'evil-tool')), ('uvx', ('-p', '3.12', 'evil-tool')), ('uvx', ('--cache-dir', '/c/@2', 'evil')),
                              ('pipx', ('run', '--python', '3.12', 'evil')), ('npx', ('/tmp/@1',)), ('npx', ('./local@1',))):
            self.assertTrue(self.unpinned(command, *args), (command, args))
        for command, args in (('npx', ('--cache', '/tmp/c', 'pkg@1.2.3')), ('npx', ('-y', '--registry=https://r.example.org', '@scope/pkg@1.2.3', 'serve')),
                              ('uvx', ('--python', '3.12', 'tool==1.2.0')), ('uvx', ('-p', '3.12', 'tool==1.2.0', '--port', '80')),
                              ('pipx', ('run', 'tool==1.2.0')), ('bunx', ('pkg@1.2.3',)), ('pnpx', ('pkg@1.2.3',))):
            self.assertFalse(self.unpinned(command, *args), (command, args))

    def test_every_package_the_launcher_fetches_is_pinned(self):
        for command, args in (('uvx', ('--with', 'evil', 'tool==1.2.0')), ('uvx', ('--with=evil', 'tool==1.2.0')), ('uvx', ('--from', 'evil', 'tool')),
                              ('npx', ('-p', 'evil', 'pkg@1.2.3')), ('npx', ('--package', 'evil', '-y', 'pkg@1.2.3')), ('npx', ('--package=evil', 'pkg@1.2.3')),
                              ('pipx', ('run', '--spec', 'evil', 'tool')), ('bunx', ('-p', 'evil', 'pkg@1.2.3'))):
            self.assertTrue(self.unpinned(command, *args), (command, args))
        for command, args in (('uvx', ('--with', 'helper==2.0.0', 'tool==1.2.0')), ('uvx', ('--from', 'tool==1.2.0', 'tool')),
                              ('npx', ('-p', 'helper@2.0.0', 'pkg@1.2.3')), ('pipx', ('run', '--spec', 'tool==1.2.0', 'tool'))):
            self.assertFalse(self.unpinned(command, *args), (command, args))


if __name__ == '__main__':
    unittest.main()
