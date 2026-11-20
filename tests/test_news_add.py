"""ai-kit news --add and /news (4.19.0, docs/sdlc/2026-11-20-news-add/spec.md): an entry written in a Core's NEWS.md that the
whats-new hook reads in full, or nothing written at all."""
import os, re, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
from installer.core import ROOT, KitError
from installer import news
from installer.core import load_commands

HEADER = '# News\n\nAnnouncements.\n\n'
OLD = '## 2026-11-09 older-one : Older\n\nOld text.\n'
TODAY = '2026-11-20'


def hook():
    import importlib.util
    spec = importlib.util.spec_from_file_location('whats_new', ROOT/'runtime/hooks/whats-new.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class NewsAddTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)/'home'; self.home.mkdir()
        self.core = Path(temp.name)/'core'; self.core.mkdir()
        (self.core/'aikit.toml').write_text('', encoding='utf-8')
        self.file = self.core/'NEWS.md'; self.file.write_text(HEADER+OLD, encoding='utf-8')

    def add(self, **kw):
        args = {'title': 'Gemini CLI sur Windows corrigé !', 'text': 'Mettez à jour le kit.', 'today': TODAY, 'home': self.home, **kw}
        return news.add_entry(self.core, **args)

    def unchanged(self):
        self.assertEqual(self.file.read_text(encoding='utf-8'), HEADER+OLD)

    # R1
    def test_entry_inserted_first_and_the_rest_intact(self):
        self.add(teams=['data', 'sales'], until='2099-01-01')
        text = self.file.read_text(encoding='utf-8')
        entry = '## 2026-11-20 gemini-cli-sur-windows-corrige : Gemini CLI sur Windows corrigé !\nteams: data, sales\nuntil: 2099-01-01\n\nMettez à jour le kit.\n\n'
        self.assertEqual(text, HEADER+entry+OLD)
        first = hook().parse_news(text)[0]
        self.assertEqual((first['id'], first['teams'], first['until'], first['text']), ('gemini-cli-sur-windows-corrige', ['data', 'sales'], '2099-01-01', 'Mettez à jour le kit.'))

    def test_a_file_without_entries_gets_one_at_the_end(self):
        self.file.write_text(HEADER, encoding='utf-8')
        self.add(id='first')
        self.assertEqual(hook().parse_news(self.file.read_text(encoding='utf-8'))[0]['id'], 'first')
        self.assertTrue(self.file.read_text(encoding='utf-8').startswith(HEADER))

    # R2
    def test_id_from_title_or_given_and_never_twice(self):
        self.assertEqual(news.slug('Gemini CLI sur Windows corrigé !'), 'gemini-cli-sur-windows-corrige')
        self.assertLessEqual(len(news.slug('x'*80)), 32)
        with self.assertRaises(KitError) as raised:
            self.add(id='older-one')
        self.assertIn('older-one', str(raised.exception)); self.unchanged()
        with self.assertRaises(KitError):
            self.add(title='?!')  # no id can be derived: --id asked
        self.unchanged()

    # R3
    def test_dates_checked_before_writing(self):
        for until in ('2026-02-30', 'soon', '2026-11-19'):
            with self.assertRaises(KitError, msg=until):
                self.add(until=until)
            self.unchanged()
        self.add(until=TODAY)  # today still shows

    def test_a_text_that_would_cut_or_add_an_entry_is_refused(self):
        for text in ('# Big title\nrest', 'ok\n## 2026-11-20 sneaky : Another entry\n\nHidden.'):
            with self.assertRaises(KitError, msg=text):
                self.add(text=text)
            self.unchanged()
        with self.assertRaises(KitError):
            self.add(title='Two\nlines')
        with self.assertRaises(KitError):
            self.add(teams=['data team'])
        self.unchanged()

    def test_a_check_failure_puts_the_file_back(self):
        with mock.patch.object(news, 'problems', return_value=['line 1: forced']):
            with self.assertRaises(KitError) as raised:
                self.add()
        self.assertIn('forced', str(raised.exception)); self.unchanged()

    # R4
    def test_only_a_core_repository_outside_the_kit_folder(self):
        (self.core/'aikit.toml').unlink()
        with self.assertRaises(KitError):
            self.add()
        self.unchanged()
        kit = self.home/'.ai-kit/sources/core'; kit.mkdir(parents=True)
        (kit/'aikit.toml').write_text('', encoding='utf-8'); (kit/'NEWS.md').write_text(HEADER, encoding='utf-8')
        with self.assertRaises(KitError):
            news.add_entry(kit, title='T', text='x', today=TODAY, home=self.home)
        self.assertEqual((kit/'NEWS.md').read_text(encoding='utf-8'), HEADER)

    # R5
    def test_text_size(self):
        with self.assertRaises(KitError):
            self.add(text='   ')
        with self.assertRaises(KitError):
            self.add(text='a'*1501)
        self.unchanged()
        self.add(text='a'*1500)


class NewsCommandLineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)/'home'; self.home.mkdir()
        self.core = Path(temp.name)/'core'; self.core.mkdir()
        (self.core/'aikit.toml').write_text('', encoding='utf-8')
        (self.core/'NEWS.md').write_text(HEADER+OLD, encoding='utf-8')

    def run_kit(self, *args, stdin=''):
        """The command line in a subprocess, stdin a pipe: no terminal, as when an agent runs it."""
        env = {**os.environ, 'AI_KIT_SOURCE_DIR': '', 'AI_KIT_NO_LIVE': '1'}
        proc = subprocess.run([sys.executable, '-m', 'installer', 'news', *args, '--home', str(self.home)], input=stdin, capture_output=True,
                              text=True, encoding='utf-8', cwd=ROOT, env=env)
        return proc.returncode, proc.stdout+proc.stderr

    # R6, R8
    def test_without_a_terminal_everything_in_options_and_the_text_on_stdin(self):
        code, out = self.run_kit('--add', '--path', str(self.core), '--title', 'Hello', '--until', '2099-01-01', stdin='Body $(not run) `here`.\n')
        self.assertEqual(code, 0, out)
        self.assertIn('Body $(not run) `here`.', (self.core/'NEWS.md').read_text(encoding='utf-8'))
        for step in ('merge request', 'tag', 'ai-kit sync'):
            self.assertIn(step, out)

    def test_without_a_terminal_a_missing_title_or_text_writes_nothing(self):
        for args, stdin in ((('--add', '--path', str(self.core)), 'Body.\n'), (('--add', '--path', str(self.core), '--title', 'Hello'), '')):
            code, out = self.run_kit(*args, stdin=stdin)
            self.assertEqual(code, 2, out)
            self.assertEqual((self.core/'NEWS.md').read_text(encoding='utf-8'), HEADER+OLD)

    def test_the_text_is_read_as_utf8_whatever_the_console(self):
        env = {**os.environ, 'AI_KIT_SOURCE_DIR': '', 'PYTHONIOENCODING': 'cp1252'}
        base = [sys.executable, '-m', 'installer', 'news', '--add', '--path', str(self.core), '--home', str(self.home)]
        proc = subprocess.run(base+['--title', 'Accents'], input='Corrigé, déjà là.\n'.encode('utf-8'), capture_output=True, cwd=ROOT, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('Corrigé, déjà là.', (self.core/'NEWS.md').read_text(encoding='utf-8'))
        proc = subprocess.run(base+['--title', 'Latin'], input='Corrig\xe9\n'.encode('latin-1'), capture_output=True, cwd=ROOT, env=env)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn(b'OutputEncoding', proc.stderr)

    def test_refusals_exit_1_and_news_needs_add(self):
        code, out = self.run_kit('--add', '--path', str(self.core), '--title', 'Again', '--id', 'older-one', stdin='Body.\n')
        self.assertEqual(code, 1, out)
        code, out = self.run_kit()
        self.assertEqual(code, 2, out)

    def test_default_path_is_the_current_folder(self):
        args = [sys.executable, '-m', 'installer', 'news', '--add', '--title', 'Here', '--home', str(self.home)]
        env = {**os.environ, 'AI_KIT_SOURCE_DIR': '', 'PYTHONPATH': str(ROOT)}
        proc = subprocess.run(args, input='Body.\n', capture_output=True, text=True, encoding='utf-8', cwd=self.core, env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout+proc.stderr)
        self.assertIn('## ', (self.core/'NEWS.md').read_text(encoding='utf-8').split(OLD)[0])


class NewsKitCommandTests(unittest.TestCase):
    # R7
    def test_news_command_optional_text_on_stdin_within_budget(self):
        command = next(c for c in load_commands() if c["name"] == "news")
        self.assertIs(command.get('default'), False)
        prompt = command['prompt']
        self.assertLess(len(prompt), 4000)
        self.assertIn('ai-kit news --add', prompt)
        self.assertIn("<<'AI_KIT_NEWS_END'", prompt)  # macOS and Linux: a quoted here-document, nothing expanded
        self.assertIn("@'", prompt)  # PowerShell: a literal here-string
        self.assertFalse(re.search(r'--text\b', prompt))
        self.assertIn('never commit', prompt.lower())


class CheckNewsScriptTests(unittest.TestCase):
    def test_the_ci_script_and_the_command_apply_one_rule(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('check_news', ROOT/'scripts/check_news.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertIs(module.problems, news.problems)


if __name__ == '__main__':
    unittest.main()
