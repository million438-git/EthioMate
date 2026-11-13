import json
import unittest
from unittest.mock import AsyncMock, patch

from services.quiz_generator import generate_quiz, parse_quiz_response


def make_question():
    return {
        "question_en": "What is the SI unit of force?",
        "question_am": "የኃይል የSI መለኪያ ምንድነው?",
        "options_en": ["Newton", "Joule", "Watt", "Pascal"],
        "options_am": ["ኒውተን", "ጁል", "ዋት", "ፓስካል"],
        "correct_index": 0,
        "explanation_en": "Force is measured in newtons.",
        "explanation_am": "ኃይል በኒውተን ይለካል።",
    }


def make_response(count=1):
    questions = []
    for number in range(1, count + 1):
        question = make_question()
        question["question_en"] += f" (Question {number})"
        question["question_am"] += f" ({number})"
        questions.append(question)

    return json.dumps({"questions": questions})


class TestParseQuizResponse(unittest.TestCase):

    def test_accepts_valid_quiz(self):
        result = parse_quiz_response(make_response(), 1)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["correct_index"], 0)
        self.assertEqual(len(result[0]["options_en"]), 4)
        self.assertEqual(len(result[0]["options_am"]), 4)

    def test_accepts_multiple_questions(self):
        result = parse_quiz_response(make_response(5), 5)

        self.assertEqual(len(result), 5)

    def test_accepts_json_markdown_fence(self):
        raw = f"```json\n{make_response()}\n```"

        result = parse_quiz_response(raw, 1)

        self.assertEqual(len(result), 1)

    def test_rejects_empty_response(self):
        for raw in ("", "   ", None):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    parse_quiz_response(raw, 1)

    def test_rejects_invalid_json(self):
        with self.assertRaises(ValueError):
            parse_quiz_response('{"questions": [', 1)

    def test_rejects_missing_questions_list(self):
        with self.assertRaises(ValueError):
            parse_quiz_response('{"items": []}', 1)

    def test_rejects_wrong_question_count(self):
        with self.assertRaises(ValueError):
            parse_quiz_response(make_response(2), 3)

    def test_rejects_non_dictionary_question(self):
        raw = json.dumps({"questions": ["not a question"]})

        with self.assertRaises(ValueError):
            parse_quiz_response(raw, 1)

    def test_rejects_missing_required_text(self):
        question = make_question()
        del question["question_am"]
        raw = json.dumps({"questions": [question]})

        with self.assertRaises(ValueError):
            parse_quiz_response(raw, 1)

    def test_rejects_empty_required_text(self):
        question = make_question()
        question["explanation_en"] = "   "
        raw = json.dumps({"questions": [question]})

        with self.assertRaises(ValueError):
            parse_quiz_response(raw, 1)

    def test_rejects_invalid_options(self):
        invalid_options = [
            ["Only one option"],
            ["A", "B", "C"],
            ["A", "B", "C", " "],
            ["A", "B", "C", 4],
            "A, B, C, D",
        ]

        for options in invalid_options:
            with self.subTest(options=options):
                question = make_question()
                question["options_en"] = options
                raw = json.dumps({"questions": [question]})

                with self.assertRaises(ValueError):
                    parse_quiz_response(raw, 1)

    def test_rejects_invalid_correct_index(self):
        invalid_indexes = [-1, 4, 1.5, "0", True, None]

        for index in invalid_indexes:
            with self.subTest(index=index):
                question = make_question()
                question["correct_index"] = index
                raw = json.dumps({"questions": [question]})

                with self.assertRaises(ValueError):
                    parse_quiz_response(raw, 1)

    def test_rejects_duplicate_questions(self):
        question = make_question()
        raw = json.dumps({"questions": [question, question]})

        with self.assertRaises(ValueError):
            parse_quiz_response(raw, 2)

    def test_rejects_duplicate_english_options(self):
        question = make_question()
        question["options_en"] = ["Newton", "Joule", "Newton", "Pascal"]
        raw = json.dumps({"questions": [question]})

        with self.assertRaises(ValueError):
            parse_quiz_response(raw, 1)

    def test_rejects_duplicate_amharic_options(self):
        question = make_question()
        question["options_am"] = ["ኒውተን", "ጁል", "ኒውተን", "ፓስካል"]
        raw = json.dumps({"questions": [question]})

        with self.assertRaises(ValueError):
            parse_quiz_response(raw, 1)

    def test_strips_surrounding_whitespace(self):
        question = make_question()
        question["question_en"] = "  What is force?  "
        question["options_en"][0] = "  Newton  "
        question["explanation_en"] = "  Force explanation.  "
        raw = json.dumps({"questions": [question]})

        result = parse_quiz_response(raw, 1)

        self.assertEqual(result[0]["question_en"], "What is force?")
        self.assertEqual(result[0]["options_en"][0], "Newton")
        self.assertEqual(result[0]["explanation_en"], "Force explanation.")


class TestGenerateQuizPrompt(unittest.IsolatedAsyncioTestCase):

    @patch("services.quiz_generator.generate_reply", new_callable=AsyncMock)
    async def test_includes_requested_quiz_details(self, mock_generate):
        mock_generate.return_value = make_response(2)

        await generate_quiz("Physics", "Motion", "advanced", 2)

        prompt = mock_generate.await_args.kwargs["history"][0]["parts"][0]["text"]

        for expected in ("Physics", "Motion", "advanced", "exactly 2"):
            with self.subTest(expected=expected):
                self.assertIn(expected, prompt)

    @patch("services.quiz_generator.generate_reply", new_callable=AsyncMock)
    async def test_requires_conceptual_and_applied_questions(self, mock_generate):
        mock_generate.return_value = make_response(2)

        await generate_quiz("Physics", "Motion", "advanced", 2)

        prompt = mock_generate.await_args.kwargs["history"][0]["parts"][0]["text"].lower()

        self.assertIn("conceptual understanding", prompt)
        self.assertIn("application", prompt)
        self.assertIn("problem-solving", prompt)

    @patch("services.quiz_generator.generate_reply", new_callable=AsyncMock)
    async def test_requires_quality_distractors(self, mock_generate):
        mock_generate.return_value = make_response(2)

        await generate_quiz("Physics", "Motion", "advanced", 2)

        prompt = mock_generate.await_args.kwargs["history"][0]["parts"][0]["text"].lower()

        self.assertIn("plausible distractors", prompt)
        self.assertIn("all of the above", prompt)
        self.assertIn("none of the above", prompt)

    @patch("services.quiz_generator.generate_reply", new_callable=AsyncMock)
    async def test_requires_consistent_bilingual_options(self, mock_generate):
        mock_generate.return_value = make_response(2)

        await generate_quiz("Physics", "Motion", "advanced", 2)

        prompt = mock_generate.await_args.kwargs["history"][0]["parts"][0]["text"].lower()

        self.assertIn("same order", prompt)
        self.assertIn("same meaning", prompt)
        self.assertIn("correct_index", prompt)

    @patch("services.quiz_generator.generate_reply", new_callable=AsyncMock)
    async def test_requires_explanatory_reasoning(self, mock_generate):
        mock_generate.return_value = make_response(2)

        await generate_quiz("Physics", "Motion", "advanced", 2)

        prompt = mock_generate.await_args.kwargs["history"][0]["parts"][0]["text"].lower()

        self.assertIn("explain the reasoning", prompt)
        self.assertIn("relevant formula", prompt)
        self.assertIn("units", prompt)

    @patch("services.quiz_generator.generate_reply", new_callable=AsyncMock)
    async def test_requires_accurate_and_unambiguous_content(self, mock_generate):
        mock_generate.return_value = make_response(2)

        await generate_quiz("Physics", "Motion", "advanced", 2)

        prompt = mock_generate.await_args.kwargs["history"][0]["parts"][0]["text"].lower()

        self.assertIn("unambiguous", prompt)
        self.assertIn("do not invent", prompt)
        self.assertIn("requested subject and topic", prompt)



if __name__ == "__main__":
    unittest.main()


class TestGenerateQuizBatching(unittest.IsolatedAsyncioTestCase):

    def make_unique_batch_response(self, batch_number, count=5):
        questions = []

        for question_number in range(1, count + 1):
            question = make_question()
            question["question_en"] += (
                f" Batch {batch_number} Question {question_number}"
            )
            question["question_am"] += (
                f" ባች {batch_number} ጥያቄ {question_number}"
            )
            questions.append(question)

        return json.dumps(
            {"questions": questions},
            ensure_ascii=False,
        )

    async def assert_batch_count(self, requested_count, expected_calls):
        batch_responses = []

        remaining = requested_count
        batch_number = 1

        while remaining > 0:
            batch_size = min(5, remaining)
            batch_responses.append(
                self.make_unique_batch_response(batch_number, batch_size)
            )
            remaining -= batch_size
            batch_number += 1

        mock_generate = AsyncMock(side_effect=batch_responses)

        with patch(
            "services.quiz_generator.generate_reply",
            mock_generate,
        ):
            result = await generate_quiz(
                "Physics",
                "Motion",
                "advanced",
                requested_count,
            )

        self.assertEqual(len(result), requested_count)
        self.assertEqual(mock_generate.await_count, expected_calls)

    async def test_five_questions_use_one_ai_request(self):
        await self.assert_batch_count(5, 1)

    async def test_ten_questions_use_two_ai_requests(self):
        await self.assert_batch_count(10, 2)

    async def test_fifteen_questions_use_three_ai_requests(self):
        await self.assert_batch_count(15, 3)

    async def test_recovers_from_duplicates_across_batches(self):
        mock_generate = AsyncMock(
            side_effect=[
                make_response(5),
                make_response(5),
                self.make_unique_batch_response(2, 5),
            ]
        )

        with patch(
            "services.quiz_generator.generate_reply",
            mock_generate,
        ):
            result = await generate_quiz(
                "Physics",
                "Motion",
                "advanced",
                10,
            )

        self.assertEqual(len(result), 10)
        self.assertEqual(mock_generate.await_count, 3)

        retry_prompt = (
            mock_generate.await_args_list[2]
            .kwargs["history"][0]["parts"][0]["text"]
        )

        self.assertIn("PREVIOUSLY GENERATED QUESTIONS", retry_prompt)
        self.assertIn("What is the SI unit of force?", retry_prompt)

    async def test_fails_after_three_duplicate_attempts(self):
        mock_generate = AsyncMock(
            side_effect=[
                make_response(5),
                make_response(5),
                make_response(5),
                make_response(5),
            ]
        )

        with patch(
            "services.quiz_generator.generate_reply",
            mock_generate,
        ):
            with self.assertRaises(ValueError):
                await generate_quiz(
                    "Physics",
                    "Motion",
                    "advanced",
                    10,
                )

        # One successful first batch and three attempts for the second.
        self.assertEqual(mock_generate.await_count, 4)

    async def test_rejects_invalid_counts_without_ai_requests(self):
        mock_generate = AsyncMock()

        with patch(
            "services.quiz_generator.generate_reply",
            mock_generate,
        ):
            for invalid_count in (0, 16, True):
                with self.subTest(count=invalid_count):
                    with self.assertRaises(ValueError):
                        await generate_quiz(
                            "Physics",
                            "Motion",
                            "advanced",
                            invalid_count,
                        )

        mock_generate.assert_not_awaited()
