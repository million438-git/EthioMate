import unittest

from handlers.study import (
    BILINGUAL_TUTOR_INSTRUCTIONS,
    STUDY_SYSTEM_INSTRUCTIONS,
    STUDY_WELCOME_MESSAGES,
    split_study_message,
)


class TestStudyTutorQuality(unittest.TestCase):

    def test_all_interface_languages_use_bilingual_tutor_instructions(self):
        self.assertEqual(set(STUDY_SYSTEM_INSTRUCTIONS), {"en", "am", "om"})

        for language, instructions in STUDY_SYSTEM_INSTRUCTIONS.items():
            with self.subTest(language=language):
                self.assertIn("Amharic explanation", instructions)
                self.assertIn("English explanation", instructions)

    def test_substantial_lessons_require_both_languages(self):
        self.assertIn("MANDATORY LANGUAGE POLICY", BILINGUAL_TUTOR_INSTRUCTIONS)
        self.assertIn("🇬🇧 ENGLISH EXPLANATION", BILINGUAL_TUTOR_INSTRUCTIONS)
        self.assertIn("🇪🇹 በአማርኛ ማብራሪያ", BILINGUAL_TUTOR_INSTRUCTIONS)

    def test_prompt_discourages_markdown_tables_and_raw_headings(self):
        self.assertIn("Do not use Markdown tables", BILINGUAL_TUTOR_INSTRUCTIONS)
        self.assertIn("Do not print heading markers such as ###", BILINGUAL_TUTOR_INSTRUCTIONS)

    def test_welcome_messages_contain_real_line_breaks(self):
        for language, welcome in STUDY_WELCOME_MESSAGES.items():
            with self.subTest(language=language):
                self.assertIn("\n", welcome)
                self.assertNotIn(r"\n", welcome)

    def test_message_split_uses_real_newlines(self):
        chunks = split_study_message(
            "First line\nSecond line is longer",
            limit=30
        )

        self.assertEqual(chunks, ["First line", "Second line is longer"])

    def test_short_message_is_not_split(self):
        message = "A short lesson."
        self.assertEqual(split_study_message(message), [message])


if __name__ == "__main__":
    unittest.main()
