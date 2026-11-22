"""4.24.2: a ;, &, && or || inside quotes is text, not the end of a command. protected-paths split a command line on these
operators wherever they were, so `echo "x & ai-kit sync"` (a word of a message, a commit, a search) was refused as if it
ran the command. The text a shell is given to run (bash -c, pwsh -Command, cmd /c, eval) stays a command line of its own,
read with the same rule: every form that runs the kit command is still refused."""
import unittest

import test_guardrail_bypasses

KIT = 'ai-kit '  # assembled with the action below: these commands are read by the hook, never run


class QuotedOperatorTests(test_guardrail_bypasses.Base):
    def test_an_operator_inside_quotes_is_text(self):
        for command in ('echo "x & ' + KIT + 'sync"', "echo 'x & " + KIT + "sync'", 'echo "x; ' + KIT + 'sync"',
                        'echo "a && ' + KIT + 'rollback"', "printf '%s' \"x || " + KIT + "uninstall\"",
                        'git commit -m "docs: build; then ' + KIT + 'sync --offline"', 'grep -rn "a & ' + KIT + 'sync" docs'):
            self.assertIsNone(self.shell(command), command)

    def test_a_line_read_two_ways_is_refused_when_either_runs_the_command(self):
        # A POSIX shell reads \" inside double quotes as a quote character (text); PowerShell ends the string there, and its ;
        # then separates two commands. The guardrail cannot tell which shell runs the line: it refuses.
        self.assertEqual(self.shell('echo "it\\"s fine; ' + KIT + 'sync"'), 'deny')
        # A line with a backslash is not plain: it is split on every operator, as in 4.24.1.
        self.assertEqual(self.shell("printf '%s\\n' \"x || " + KIT + "uninstall\""), 'deny')

    def test_an_operator_outside_quotes_still_ends_the_command(self):
        for command in ('echo x & ' + KIT + 'sync', 'echo "x" & ' + KIT + 'sync', "echo 'a;b'; " + KIT + 'sync',
                        'echo \\"x & ' + KIT + 'sync\\"', 'echo "x" && ' + KIT + 'rollback', 'false || ' + KIT + 'uninstall --yes'):
            self.assertEqual(self.shell(command), 'deny', command)

    def test_the_text_a_shell_runs_is_read_as_a_command_line(self):
        for command in ('bash -c "echo x; ' + KIT + 'sync"', "sh -c 'cd /tmp && " + KIT + "sync'", 'zsh -lc "true || ' + KIT + 'rollback"',
                        'pwsh -Command "echo x; & ' + KIT + 'sync"', 'cmd /c "echo x & ' + KIT + 'sync"', 'eval "echo x; ' + KIT + 'sync"',
                        'bash -c "echo \'quoted; text\'; ' + KIT + 'uninstall"'):
            self.assertEqual(self.shell(command), 'deny', command)
        for command in ('bash -c "echo \'x; ' + KIT + 'sync\'"', 'bash -c "echo x; ' + KIT + 'status"'):
            self.assertIsNone(self.shell(command), command)


    def test_a_substitution_or_a_group_runs_the_command(self):
        # Refused by none of the versions before 4.24.2: the closing ) or ` stuck to the action, an opening ( or { alone hid
        # the program after it.
        for command in ('$(' + KIT + 'sync)', 'echo "$(' + KIT + 'sync)"', 'echo `' + KIT + 'sync`', 'echo "`' + KIT + 'rollback`"',
                        '(' + KIT + 'sync)', '( ' + KIT + 'sync )', '{ ' + KIT + 'sync; }', 'x=$(' + KIT + 'uninstall --yes)',
                        'bash -c "eval \\"' + KIT + 'sync\\""'):
            self.assertEqual(self.shell(command), 'deny', command)
        for command in ('echo "$(' + KIT + 'status)"', '(' + KIT + 'doctor)', "echo '$(" + KIT + "sync)'"):
            self.assertIsNone(self.shell(command), command)


    def test_a_quote_the_shell_does_not_read_as_one_hides_nothing(self):
        # From the review of 4.24.2: a quote left open, or a character another shell reads differently, must not hide
        # the command after it.
        for command in ("# Let's resync the kit\n" + KIT + 'sync', "# don't\n" + KIT + "sync # it's",
                        'cmd /c "echo it\'s done & ' + KIT + 'sync"', "echo it's done & " + KIT + 'sync',
                        "git commit -m $'don\\'t\\nfix' && " + KIT + 'sync', "echo don`'t; " + KIT + 'sync',
                        'echo `"x; ' + KIT + 'sync; echo `"', 'echo "$(grep -c \'a)\' f; ' + KIT + 'sync)"',
                        "cat <<'END-NOTE'\nnote\nEND-NOTE\n" + KIT + 'sync', "iex '" + KIT + "sync'",
                        'Invoke-Expression "' + KIT + 'rollback"', 'powershell -c "iex \'' + KIT + 'sync\'"'):
            self.assertEqual(self.shell(command), 'deny', command)

    def test_a_line_too_intricate_to_read_is_refused_in_time(self):
        import time
        started = time.monotonic()
        self.assertEqual(self.shell(' '.join(['eval'] * 30) + ' x'), 'deny')
        self.assertLess(time.monotonic() - started, 10)


    def test_what_a_second_review_found(self):
        # A here-string is no heredoc; a PowerShell here-string pairs no quote; a shell keyword or a runner hides no program.
        for command in ('grep -q ok <<< "$out"\n' + KIT + 'sync', "$n = @'\nIt's ready\n'@\n" + KIT + "sync --offline  # don't forget",
                        'for d in a b; do ' + KIT + 'sync; done', 'if ! ' + KIT + 'doctor; then ' + KIT + 'sync; fi', '! ' + KIT + 'sync',
                        'while true; do ' + KIT + 'rollback; done', 'timeout 600 ' + KIT + 'sync --offline', 'timeout -s KILL 5m ' + KIT + 'sync',
                        'uv run ' + KIT + 'sync', 'poetry run ' + KIT + 'uninstall --yes', 'echo x\n' + KIT + 'sync',
                        'diff <(' + KIT + 'status) <(' + KIT + 'sync)', 'tee >(' + KIT + 'rollback) < f', 'eval ' * 3 + KIT + 'sync',
                        ' '.join(['eval'] * 20000) + ' ' + KIT + 'sync'):
            self.assertEqual(self.shell(command), 'deny', command)
        for command in ('for f in a b; do echo "$f; ' + KIT + 'sync"; done', 'timeout 5 ' + KIT + 'status', 'uv run pytest -q'):
            self.assertIsNone(self.shell(command), command)

    def test_a_huge_line_is_read_in_time(self):
        import time
        for command in (' '.join(['eval'] * 20000) + ' x', ' '.join(['bash'] * 20000) + ' x', 'echo "' + 'a & b; ' * 20000 + '"'):
            started = time.monotonic()
            self.shell(command)
            self.assertLess(time.monotonic() - started, 10, command[:30])
        self.assertEqual(self.shell('echo "' + 'a & b; ' * 20000 + '"; ' + KIT + 'sync'), 'deny')


    def test_each_reading_follows_its_own_cd(self):
        # Third review: a cd shared by two readings was skipped in one and applied twice in the other, and a launcher
        # PowerShell runs (its "a\" ends the string) was then looked for in the wrong folder.
        kit = self.home/'kit'
        (kit/'scripts').mkdir(parents=True)
        for name in ('bootstrap.sh', 'launcher.py', 'bootstrap.ps1'):
            (kit/'scripts'/name).write_text('', encoding='utf-8')
        for command in ('cd ' + (kit/'scripts').as_posix() + '; echo "a\\"; ./bootstrap.ps1; echo "\\"',
                        'cd kit/scripts; echo "a\\"; ./bootstrap.ps1; echo "b"'):
            self.assertEqual(self.shell(command), 'deny', command)

    def test_a_heredoc_piped_to_a_shell_is_read(self):
        for command in ("cat <<'END-NOTE' | sh\nEND\n" + KIT + "sync\nEND-NOTE", 'cat <<EOF | bash\n' + KIT + 'sync\nEOF',
                        "cat <<'EOF' | pwsh -Command -\n" + KIT + "rollback\nEOF"):
            self.assertEqual(self.shell(command), 'deny', command)
        self.assertIsNone(self.shell("cat <<'EOF' | grep sync\n" + KIT + "sync\nEOF"))


    def test_only_a_plain_line_is_read_for_its_quotes(self):
        # Fourth review: "$( … )" opens a quoting context of its own, PowerShell ends a string at a typographic quote, and
        # <# … #> is a PowerShell comment. A line with any of them is split as before, quotes or not.
        for command in ('echo "$(echo \'"\')"; ' + KIT + "sync # '", "echo '\u2018; " + KIT + "sync; \u2018'",
                        'echo "\u201cx; ' + KIT + 'sync\u201d"', "<# it's 'x #> " + KIT + 'sync',
                        'echo x >&2# ; ' + KIT + 'sync', "git --% '\n" + KIT + "sync\ngit --% '"):
            self.assertEqual(self.shell(command), 'deny', command)

    def test_a_long_nested_line_is_read_in_time(self):
        import time
        line = 'echo "' + 'x ' * 4000 + '"'
        for _ in range(4):
            line = 'eval "$(' + line + ')" \\; ' + line
        started = time.monotonic()
        self.shell(line[:19000])
        self.assertLess(time.monotonic() - started, 5)


if __name__ == '__main__':
    unittest.main()
