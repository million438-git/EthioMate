import unittest

from services.telegram_formatting import format_telegram_html


class TestTelegramFormatting(unittest.TestCase):

    def test_empty_text(self):
        self.assertEqual(format_telegram_html(""), "")

    def test_plain_text(self):
        self.assertEqual(
            format_telegram_html("Hello EthioMate"),
            "Hello EthioMate"
        )

    def test_bold_text(self):
        self.assertEqual(
            format_telegram_html("**Important**"),
            "<b>Important</b>"
        )

    def test_heading(self):
        self.assertEqual(
            format_telegram_html("## Introduction"),
            "<b>Introduction</b>"
        )

    def test_italic_text(self):
        self.assertEqual(
            format_telegram_html("*Important detail*"),
            "<i>Important detail</i>"
        )

    def test_strikethrough(self):
        self.assertEqual(
            format_telegram_html("~~Old text~~"),
            "<s>Old text</s>"
        )

    def test_unordered_list(self):
        self.assertEqual(
            format_telegram_html("- First\n- Second"),
            "• First\n• Second"
        )

    def test_html_is_escaped(self):
        self.assertEqual(
            format_telegram_html("<script>alert('x')</script>"),
            "&lt;script&gt;alert('x')&lt;/script&gt;"
        )

    def test_inline_code(self):
        self.assertEqual(
            format_telegram_html("Use `print()`"),
            "Use <code>print()</code>"
        )

    def test_fenced_code_block(self):
        result = format_telegram_html(
            "Example:\n```python\nprint('Hello')\n```"
        )
        self.assertIn("<pre><code>", result)
        self.assertIn("print('Hello')", result)
        self.assertIn("</code></pre>", result)

    def test_html_inside_code_is_escaped(self):
        self.assertEqual(
            format_telegram_html("`<b>text</b>`"),
            "<code>&lt;b&gt;text&lt;/b&gt;</code>"
        )


if __name__ == "__main__":
    unittest.main()
