import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText

import handlers.quiz as quiz_handlers
from handlers.quiz import finish_quiz
from database import db


class TestQuizCompletion(unittest.IsolatedAsyncioTestCase):

    async def test_saves_answering_users_telegram_id_and_score(self):
        user_id = 987654321

        message = unittest.mock.Mock()
        message.answer = AsyncMock()

        state = unittest.mock.Mock()
        state.get_data = AsyncMock(return_value={
            "current_index": 4,
            "correct_answers": 3,
            "subject": "Physics",
            "topic": "Motion",
            "difficulty": "advanced",
            "questions": [{} for _ in range(5)],
        })
        state.clear = AsyncMock()

        with patch("handlers.quiz.save_quiz_result") as save_result:
            await finish_quiz(message, state, "en", user_id)

        save_result.assert_called_once_with(
            telegram_id=user_id,
            subject="Physics",
            topic="Motion",
            difficulty="advanced",
            total_questions=5,
            correct_answers=3,
        )

        message.answer.assert_awaited_once()
        self.assertIn("3/5", message.answer.await_args.args[0])
        state.clear.assert_awaited_once()


class TestQuizHistoryDatabase(unittest.TestCase):

    def test_saves_and_retrieves_registered_users_quiz_history(self):
        with tempfile.TemporaryDirectory() as directory:
            test_database = Path(directory) / "quiz_test.sqlite3"

            with patch.object(db, "DATABASE_PATH", test_database):
                db.init_db()
                db.register_user(
                    telegram_id=123456789,
                    username="student",
                    first_name="Student",
                )

                result_id = db.save_quiz_result(
                    telegram_id=123456789,
                    subject="Physics",
                    topic="Motion",
                    difficulty="advanced",
                    total_questions=5,
                    correct_answers=4,
                )

                history = db.get_quiz_history(123456789)

        self.assertIsInstance(result_id, int)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["telegram_id"], 123456789)
        self.assertEqual(history[0]["total_questions"], 5)
        self.assertEqual(history[0]["correct_answers"], 4)
        self.assertEqual(history[0]["score_percent"], 80.0)


QUESTION = {
    "question_en": "What is print()?",
    "question_am": "print() ምንድን ነው?",
    "options_en": ["Output", "Input", "Loop", "Class"],
    "options_am": ["ውጤት", "ግቤት", "ዙር", "ክፍል"],
    "correct_index": 1,
    "explanation_en": "print() displays output.",
    "explanation_am": "print() ውጤት ያሳያል።",
}


class TestQuizPersistenceWhenEditFails(unittest.IsolatedAsyncioTestCase):
    """E-08: scoring must complete even when the feedback edit fails."""

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.test_database = Path(self.temp_directory.name) / "quiz_edit.sqlite3"
        self.database_patch = patch.object(db, "DATABASE_PATH", self.test_database)
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        db.init_db()
        db.register_user(31337, "student", "Student")

    def tearDown(self):
        self.temp_directory.cleanup()

    def make_callback(self):
        callback = MagicMock()
        callback.from_user = SimpleNamespace(id=31337)
        callback.data = "qz:answer:1"
        callback.answer = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.message.answer = AsyncMock()
        return callback

    def make_state(self):
        store = {
            "answered": False,
            "current_index": 0,
            "correct_answers": 0,
            "subject": "Physics",
            "topic": "Motion",
            "difficulty": "advanced",
            "questions": [QUESTION],
        }
        state = MagicMock()
        state.get_data = AsyncMock(return_value=store)
        state.update_data = AsyncMock(side_effect=lambda **kw: store.update(kw))
        state.clear = AsyncMock()
        return state

    async def test_save_quiz_result_runs_when_edit_text_raises(self):
        callback = self.make_callback()
        callback.message.edit_text = AsyncMock(
            side_effect=TelegramBadRequest(
                EditMessageText(chat_id=1, message_id=2, text="x"),
                "Message is not modified",
            )
        )
        state = self.make_state()

        with patch("handlers.quiz.save_quiz_result") as save_result:
            await quiz_handlers.answer_question(callback, state)

        save_result.assert_called_once_with(
            telegram_id=31337,
            subject="Physics",
            topic="Motion",
            difficulty="advanced",
            total_questions=1,
            correct_answers=1,
        )
        callback.message.answer.assert_awaited_once()
        self.assertIn("1/1", callback.message.answer.await_args.args[0])
        state.clear.assert_awaited_once()

    async def test_successful_edit_keeps_existing_behavior(self):
        callback = self.make_callback()
        state = self.make_state()

        with patch("handlers.quiz.save_quiz_result") as save_result:
            await quiz_handlers.answer_question(callback, state)

        callback.message.edit_text.assert_awaited_once()
        save_result.assert_called_once()
        callback.message.answer.assert_awaited_once()
        self.assertIn("Quiz completed", callback.message.answer.await_args.args[0])
        state.clear.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
