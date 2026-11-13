import unittest
from unittest.mock import AsyncMock, patch

from services.translation import translate_text


class TestTranslationService(unittest.IsolatedAsyncioTestCase):

    @patch(
        "services.translation.generate_reply",
        new_callable=AsyncMock
    )
    async def test_english_translation(self, mock_generate):
        mock_generate.return_value = "Hello translated"

        result = await translate_text("Hello", "am")

        self.assertEqual(result, "Hello translated")
        mock_generate.assert_awaited_once()

        call_kwargs = mock_generate.await_args.kwargs
        self.assertEqual(call_kwargs["language"], "am")

        prompt = call_kwargs["history"][0]["parts"][0]["text"]
        self.assertIn("Amharic", prompt)
        self.assertIn("Hello", prompt)
        self.assertIn("Automatically detect the source language", prompt)

    @patch(
        "services.translation.generate_reply",
        new_callable=AsyncMock
    )
    async def test_all_supported_target_languages(self, mock_generate):
        mock_generate.return_value = "Translated"

        for language in ("am", "en", "om"):
            with self.subTest(language=language):
                result = await translate_text("Test text", language)
                self.assertEqual(result, "Translated")

        self.assertEqual(mock_generate.await_count, 3)

    @patch(
        "services.translation.generate_reply",
        new_callable=AsyncMock
    )
    async def test_unsupported_language(self, mock_generate):
        with self.assertRaisesRegex(ValueError, "Unsupported target"):
            await translate_text("Hello", "fr")

        mock_generate.assert_not_awaited()

    @patch(
        "services.translation.generate_reply",
        new_callable=AsyncMock
    )
    async def test_empty_text(self, mock_generate):
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            await translate_text("", "am")

        mock_generate.assert_not_awaited()

    @patch(
        "services.translation.generate_reply",
        new_callable=AsyncMock
    )
    async def test_whitespace_only_text(self, mock_generate):
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            await translate_text("   \n\t  ", "en")

        mock_generate.assert_not_awaited()

    @patch(
        "services.translation.generate_reply",
        new_callable=AsyncMock
    )
    async def test_text_exceeding_limit(self, mock_generate):
        long_text = "A" * 12001

        with self.assertRaisesRegex(ValueError, "too long"):
            await translate_text(long_text, "om")

        mock_generate.assert_not_awaited()

    @patch(
        "services.translation.generate_reply",
        new_callable=AsyncMock
    )
    async def test_maximum_allowed_text_length(self, mock_generate):
        mock_generate.return_value = "Translated"

        result = await translate_text("A" * 12000, "en")

        self.assertEqual(result, "Translated")
        mock_generate.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
