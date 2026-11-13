import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from google.genai.errors import ClientError, ServerError

import handlers.assistant as assistant_handlers
import handlers.quiz as quiz_handlers
import handlers.study as study_handlers
from database import db
from services import ai_assistant
from services.ai_assistant import (
    AIRateLimited,
    AIPermanent,
    AITransient,
    generate_reply,
)


def rate_limit_error():
    return ClientError(429, {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "message": "quota exceeded",
        }
    })


def server_error():
    return ServerError(503, {
        "error": {
            "code": 503,
            "status": "UNAVAILABLE",
            "message": "backend error",
        }
    })


def bad_request_error():
    return ClientError(400, {
        "error": {
            "code": 400,
            "status": "INVALID_ARGUMENT",
            "message": "invalid argument",
        }
    })


class TestGenerateReplyErrorMapping(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        client_patch = patch("services.ai_assistant._client")
        self.client = client_patch.start()
        self.addCleanup(client_patch.stop)

        self.generate = AsyncMock()
        self.client.aio.models.generate_content = self.generate
        self.generate.return_value = SimpleNamespace(text=" Hello there ")

    async def test_rate_limit_raises_typed_error_without_retry(self):
        self.generate.side_effect = rate_limit_error()

        with self.assertRaises(AIRateLimited):
            await generate_reply(history=[], language="en")

        self.assertEqual(self.generate.await_count, 1)

    async def test_server_error_retries_exactly_once_then_raises_transient(self):
        self.generate.side_effect = server_error()

        with self.assertRaises(AITransient):
            await generate_reply(history=[], language="en")

        self.assertEqual(self.generate.await_count, 2)

    async def test_server_error_recovers_on_single_retry(self):
        self.generate.side_effect = [server_error(), SimpleNamespace(text="Recovered")]

        answer = await generate_reply(history=[], language="en")

        self.assertEqual(answer, "Recovered")
        self.assertEqual(self.generate.await_count, 2)

    async def test_other_client_error_raises_permanent_without_retry(self):
        self.generate.side_effect = bad_request_error()

        with self.assertRaises(AIPermanent):
            await generate_reply(history=[], language="en")

        self.assertEqual(self.generate.await_count, 1)

    async def test_empty_response_raises_permanent(self):
        self.generate.return_value = SimpleNamespace(text="   ")

        with self.assertRaises(AIPermanent):
            await generate_reply(history=[], language="en")

    async def test_success_returns_stripped_text(self):
        answer = await generate_reply(history=[], language="en")

        self.assertEqual(answer, "Hello there")
        self.assertEqual(self.generate.await_count, 1)

    async def test_success_keeps_model_and_generation_config(self):
        await generate_reply(history=[], language="en")

        kwargs = self.generate.await_args.kwargs
        self.assertEqual(kwargs["model"], ai_assistant.GEMINI_MODEL)
        self.assertEqual(kwargs["config"].temperature, 0.5)
        self.assertEqual(kwargs["config"].max_output_tokens, 2200)


class TestClientConfiguration(unittest.TestCase):

    def test_client_is_built_with_request_timeout(self):
        http_options = ai_assistant._client._api_client._http_options
        self.assertEqual(http_options.timeout, 90_000)


class TestRateLimitedHandlers(unittest.IsolatedAsyncioTestCase):
    """The busy-branch handlers must keep the FSM state and stay distinct."""

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.test_database = Path(self.temp_directory.name) / "ai_errors.sqlite3"
        self.database_patch = patch.object(db, "DATABASE_PATH", self.test_database)
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        db.init_db()

    def make_message(self, user_id):
        message = MagicMock()
        message.from_user = SimpleNamespace(id=user_id)
        status = MagicMock()
        status.edit_text = AsyncMock()
        message.answer = AsyncMock(return_value=status)
        return message, status

    async def test_assistant_busy_branch_preserves_state(self):
        message, status = self.make_message(1001)

        state = MagicMock()
        state.get_data = AsyncMock(return_value={"history": []})
        state.update_data = AsyncMock()
        state.clear = AsyncMock()

        with patch(
            "handlers.assistant.generate_reply",
            AsyncMock(side_effect=AIRateLimited()),
        ):
            await assistant_handlers.process_ai_message(message, state)

        status.edit_text.assert_awaited_once_with(
            assistant_handlers.BUSY_MESSAGES["en"]
        )
        state.clear.assert_not_awaited()
        state.update_data.assert_not_awaited()

    async def test_study_busy_branch_preserves_state(self):
        message, status = self.make_message(1002)

        state = MagicMock()
        state.get_data = AsyncMock(return_value={"study_history": []})
        state.update_data = AsyncMock()
        state.clear = AsyncMock()

        with patch(
            "handlers.study.generate_reply",
            AsyncMock(side_effect=AIRateLimited()),
        ):
            await study_handlers.process_study_question(message, state)

        status.edit_text.assert_awaited_once()
        self.assertEqual(
            status.edit_text.await_args.args[0],
            "The AI request limit has been reached temporarily. "
            "Please wait a little and try again.",
        )
        state.clear.assert_not_awaited()

    async def test_quiz_busy_branch_preserves_state(self):
        user_id = 1003
        db.register_user(user_id, "student", "Student")

        callback = MagicMock()
        callback.from_user = SimpleNamespace(id=user_id)
        callback.data = "qz:count:5"
        callback.answer = AsyncMock()
        callback.message.answer = AsyncMock()

        state = MagicMock()
        state.get_data = AsyncMock(return_value={
            "subject": "Physics",
            "topic": "Motion",
            "difficulty": "beginner",
        })
        state.update_data = AsyncMock()
        state.clear = AsyncMock()

        with patch(
            "handlers.quiz.generate_quiz",
            AsyncMock(side_effect=AIRateLimited()),
        ):
            await quiz_handlers.select_count(callback, state)

        callback.message.answer.assert_awaited()
        self.assertEqual(
            callback.message.answer.await_args_list[-1].args[0],
            quiz_handlers.TEXT["en"]["rate_limited"],
        )
        state.clear.assert_not_awaited()

    async def test_assistant_generic_failure_uses_error_message(self):
        message, status = self.make_message(1004)

        state = MagicMock()
        state.get_data = AsyncMock(return_value={"history": []})
        state.update_data = AsyncMock()

        with patch(
            "handlers.assistant.generate_reply",
            AsyncMock(side_effect=Exception("boom")),
        ):
            await assistant_handlers.process_ai_message(message, state)

        status.edit_text.assert_awaited_once_with(
            assistant_handlers.ERROR_MESSAGES["en"]
        )


if __name__ == "__main__":
    unittest.main()
