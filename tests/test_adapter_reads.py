"""4.24.1: what two adapters read back. Codex doctor compares the copy of USER.md in ~/.codex/AGENTS.md with the file, whole
(a shorter USER.md is found inside the older copy and passed for current); the Gemini history reads a prompt stored as a
list of text blocks, not the text Python prints for that list."""
import json

from installer.adapters import codex, gemini
import test_cli_parity


class CodexCopyTests(test_cli_parity.Base):
    def current(self):
        lines, _ = self.doctor_lines(codex)
        return [line[:6] for line in lines if 'Codex has the latest version of USER.md' in line]

    def test_a_shorter_user_file_is_not_the_copy_codex_has(self):
        user = self.home/'.ai-kit/context/USER.md'
        user.parent.mkdir(parents=True, exist_ok=True)
        user.write_text('# My context\n\n- Reply in French.\n- Always show the checks as a table.\n', encoding='utf-8')
        self.run_kit('codex')
        self.assertEqual(self.current(), ['[OK] C'])
        user.write_text('# My context\r\n\r\n- Reply in French.\r\n- Always show the checks as a table.\r\n', encoding='utf-8', newline='')
        self.assertEqual(self.current(), ['[OK] C'])  # the same text saved with Windows line endings
        user.write_text('- Reply in French.\n', encoding='utf-8')  # a line of the old copy: found inside it, yet not the copy
        self.assertEqual(self.current(), ['[Fail]'])
        user.write_text('', encoding='utf-8')
        self.assertEqual(self.current(), ['[Fail]'])
        self.run_kit('codex')
        self.assertEqual(self.current(), ['[OK] C'])
        self.assertEqual(codex.copied_user_text(self.read('.codex/AGENTS.md')), '')


class GeminiPromptTests(test_cli_parity.Base):
    def test_a_prompt_stored_as_text_blocks_is_read_as_its_text(self):
        chat = self.home/'.gemini/tmp/p/chats'
        chat.mkdir(parents=True)
        stamp = '2099-01-01T10:00:00Z'
        messages = [{'type': 'user', 'timestamp': stamp, 'displayContent': [{'text': '/intent it\'s an idea'}]},
                    {'type': 'user', 'timestamp': stamp, 'content': [{'text': '/build "the" '}, {'text': 'export'}]},
                    {'type': 'user', 'timestamp': stamp, 'displayContent': '/review'},
                    {'type': 'user', 'timestamp': stamp, 'displayContent': "[{'text': '/ship'}]"},  # the older stored form
                    {'type': 'user', 'timestamp': stamp, 'content': [{'inlineData': {}}, 'x']}]
        (chat/'s.json').write_text(json.dumps({'messages': messages}), encoding='utf-8')
        texts = [e['text'] for e in gemini.history(self.home, {}) if e['kind'] == 'prompt']
        self.assertEqual(texts[:3], ["/intent it's an idea", '/build "the" export', '/review'])
        self.assertTrue(texts[3].startswith('/ship'))
        self.assertEqual(texts[4], 'x')
