import unittest

from handlers.assistant import split_message


class TestAssistantMessageSplitting(unittest.TestCase):

    def test_short_message_remains_unchanged(self):
        message = "Hello, welcome to EthioMate."

        self.assertEqual(split_message(message), [message])

    def test_empty_message_returns_empty_list(self):
        self.assertEqual(split_message(""), [])

    def test_long_message_is_split(self):
        message = ("EthioMate provides professional assistance. " * 100)

        chunks = split_message(message, limit=100)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))
        self.assertTrue(all(chunk.strip() for chunk in chunks))

    def test_splitting_prefers_word_boundaries(self):
        message = "This is a professional assistant message."

        chunks = split_message(message, limit=20)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0], "This is a")
        self.assertTrue(all(len(chunk) <= 20 for chunk in chunks))

    def test_splitting_handles_long_words(self):
        message = "A" * 250

        chunks = split_message(message, limit=100)

        self.assertEqual([len(chunk) for chunk in chunks], [100, 100, 50])
        self.assertTrue(all(chunk for chunk in chunks))

    def test_custom_limit_is_respected(self):
        message = "One two three four five six seven eight nine ten."

        chunks = split_message(message, limit=12)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 12 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
