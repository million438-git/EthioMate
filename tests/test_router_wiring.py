import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    Chat,
    Message,
    Update,
    User,
)

import bot as bot_module
import handlers.calculator as calculator_handlers
import handlers.quiz as quiz_handlers
import handlers.translation as translation_handlers
from database import db


class TestDeadHandlersRemoved(unittest.TestCase):

    def test_cancel_translation_no_longer_exists(self):
        self.assertFalse(hasattr(translation_handlers, "cancel_translation"))

    def test_cancel_calculation_no_longer_exists(self):
        self.assertFalse(hasattr(calculator_handlers, "cancel_calculation"))

    def test_core_cancel_owner_exists(self):
        self.assertTrue(hasattr(bot_module, "cancel_current_workflow"))


class TestCancelDuringActiveState(unittest.IsolatedAsyncioTestCase):
    """Feed a real update through a dispatcher wired exactly like bot.main."""

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.test_database = Path(self.temp_directory.name) / "wiring.sqlite3"
        self.database_patch = patch.object(db, "DATABASE_PATH", self.test_database)
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        db.init_db()

    def tearDown(self):
        self.temp_directory.cleanup()

    def build_dispatcher(self):
        dp = Dispatcher(storage=MemoryStorage())
        dp.message.middleware(bot_module.UserActivityMiddleware())
        dp.callback_query.middleware(bot_module.UserActivityMiddleware())
        dp.include_router(bot_module.core_router)
        dp.include_router(bot_module.commands_router)
        dp.include_router(bot_module.translation_router)
        dp.include_router(bot_module.calculator_router)
        dp.include_router(bot_module.assistant_router)
        dp.include_router(bot_module.quiz_router)
        dp.include_router(bot_module.academy_router)
        dp.include_router(bot_module.study_router)
        dp.include_router(bot_module.fallback_router)
        return dp

    def make_bot(self):
        bot = Bot(token="42:TEST_TOKEN")
        bot.session.make_request = AsyncMock(return_value=MagicMock())
        return bot

    def make_message(self, chat_id, user_id, text):
        return Message(
            message_id=1,
            date=datetime.now(),
            chat=Chat(id=chat_id, type="private"),
            from_user=User(
                id=user_id, is_bot=False, first_name="Tester", username="tester"
            ),
            text=text,
        )

    async def test_cancel_reaches_core_handler_from_active_state(self):
        from aiogram.fsm.state import State, StatesGroup

        class ForeignStates(StatesGroup):
            waiting = State()

        bot = self.make_bot()
        dp = self.build_dispatcher()

        # --- Scenario 1: /cancel inside a foreign active state ---------
        chat_id, user_id = 4242, 4242
        key = StorageKey(bot_id=42, chat_id=chat_id, user_id=user_id)
        await dp.storage.set_state(key, ForeignStates.waiting)

        update = Update(
            update_id=1,
            message=self.make_message(chat_id, user_id, "/cancel"),
        )
        await dp.feed_update(bot, update)

        method = bot.session.make_request.await_args_list[-1].args[1]
        self.assertIn("current operation was cancelled", method.text)
        self.assertIsNone(await dp.storage.get_state(key))

        # --- Scenario 2: /cancel inside the translation FSM state ------
        from handlers.translation import TranslationStates

        chat_id, user_id = 4343, 4343
        key = StorageKey(bot_id=42, chat_id=chat_id, user_id=user_id)
        await dp.storage.set_state(key, TranslationStates.waiting_for_text)

        update = Update(
            update_id=2,
            message=self.make_message(chat_id, user_id, "/cancel"),
        )
        await dp.feed_update(bot, update)

        method = bot.session.make_request.await_args_list[-1].args[1]
        self.assertIn("current operation was cancelled", method.text)
        self.assertIsNone(await dp.storage.get_state(key))

        # --- Scenario 3: callback-only user registered via middleware --
        chat_id, user_id = 4444, 4444
        callback_message = Message(
            message_id=10,
            date=datetime.now(),
            chat=Chat(id=chat_id, type="private"),
            from_user=User(
                id=user_id, is_bot=False, first_name="Callback", username="cb"
            ),
            text="original",
        )
        update = Update(
            update_id=3,
            callback_query=CallbackQuery(
                id="cbw1",
                from_user=User(
                    id=user_id, is_bot=False, first_name="Callback", username="cb"
                ),
                chat_instance="ci",
                message=callback_message,
                data="ac:home",
            ),
        )
        await dp.feed_update(bot, update)

        self.assertIsNotNone(db.get_user(user_id))


class TestStaleQuizCallback(unittest.IsolatedAsyncioTestCase):
    """These handlers call get_language, so the DB must be a temp copy."""

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.test_database = Path(self.temp_directory.name) / "stale_quiz.sqlite3"
        self.database_patch = patch.object(db, "DATABASE_PATH", self.test_database)
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        db.init_db()

    def tearDown(self):
        self.temp_directory.cleanup()

    async def test_stale_callback_is_answered_with_expiry_alert(self):
        callback = MagicMock()
        callback.from_user = SimpleNamespace(id=5001)
        callback.data = "qz:answer:0"
        callback.answer = AsyncMock()

        state = MagicMock()
        state.get_data = AsyncMock(return_value={})

        await quiz_handlers.stale_quiz_callback(callback, state)

        callback.answer.assert_awaited_once_with(
            quiz_handlers.TEXT["en"]["expired"], show_alert=True
        )

    async def test_active_quiz_callback_is_not_masked(self):
        callback = MagicMock()
        callback.from_user = SimpleNamespace(id=5002)
        callback.data = "qz:unknown"
        callback.answer = AsyncMock()

        state = MagicMock()
        state.get_data = AsyncMock(return_value={"questions": [{}]})

        await quiz_handlers.stale_quiz_callback(callback, state)

        callback.answer.assert_awaited_once_with()
        self.assertEqual(callback.answer.await_args.args, ())


if __name__ == "__main__":
    unittest.main()
