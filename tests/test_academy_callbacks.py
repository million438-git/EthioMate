import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import CallbackQuery, Chat, Message, User

from database import db
from handlers import academy as academy_handlers
from services import academy


STUDENT_ID = 123456789
OTHER_ID = 987000111
CALLBACK_ONLY_ID = 555000222


class AcademyCallbackTestBase(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.test_database = Path(self.temp_directory.name) / "academy_cb.sqlite3"
        self.database_patch = patch.object(db, "DATABASE_PATH", self.test_database)
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        db.init_db()

        db.register_user(STUDENT_ID, "student", "Student")

        with db.get_connection() as connection:
            self.category_id = connection.execute("""
                INSERT INTO skill_categories
                    (slug, name_en, name_am, name_om)
                VALUES
                    ('technology', 'Technology', 'ቴክኖሎጂ', 'Teeknooloojii')
            """).lastrowid

            self.course_id = connection.execute("""
                INSERT INTO courses (category_id, slug, level, status)
                VALUES (?, 'python-programming', 'beginner', 'published')
            """, (self.category_id,)).lastrowid

            for language, title in (
                ("en", "Python Programming"),
                ("am", "የPython ፕሮግራሚንግ"),
                ("om", "Sagantaa Python"),
            ):
                connection.execute("""
                    INSERT INTO course_translations
                        (course_id, language, title, description)
                    VALUES (?, ?, ?, 'Course description')
                """, (self.course_id, language, title))

            self.draft_course_id = connection.execute("""
                INSERT INTO courses (category_id, slug, level, status)
                VALUES (?, 'draft-course', 'beginner', 'draft')
            """, (self.category_id,)).lastrowid

            self.module_id = connection.execute("""
                INSERT INTO course_modules
                    (course_id, slug, sort_order, is_published)
                VALUES (?, 'fundamentals', 1, 1)
            """, (self.course_id,)).lastrowid

            connection.execute("""
                INSERT INTO module_translations (module_id, language, title)
                VALUES (?, 'en', 'Python Fundamentals')
            """, (self.module_id,))

            self.lesson_id = connection.execute("""
                INSERT INTO course_lessons
                    (module_id, slug, sort_order, is_published)
                VALUES (?, 'first-program', 1, 1)
            """, (self.module_id,)).lastrowid

            connection.execute("""
                INSERT INTO lesson_translations
                    (lesson_id, language, title, content)
                VALUES (?, 'en', 'Your First Program',
                        'Use print() to display text.')
            """, (self.lesson_id,))

            connection.commit()

    def tearDown(self):
        self.temp_directory.cleanup()

    def make_callback(self, user_id, data):
        callback = MagicMock(spec=CallbackQuery)
        callback.message = MagicMock()
        callback.from_user = SimpleNamespace(
            id=user_id, username="student", first_name="Student"
        )
        callback.data = data
        callback.answer = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.message.answer = AsyncMock()
        return callback

    def edit_text_texts(self, callback):
        return [call.args[0] for call in callback.message.edit_text.await_args_list]


class TestAcademyNavigationCallbacks(AcademyCallbackTestBase):
    """Smoke tests for the seven untouched callback handlers."""

    async def test_ac_home_renders_academy_home(self):
        callback = self.make_callback(STUDENT_ID, "ac:home")
        await academy_handlers.academy_home(callback)

        callback.answer.assert_awaited_once()
        texts = self.edit_text_texts(callback)
        self.assertEqual(len(texts), 1)
        self.assertIn("EthioMate Academy", texts[0])

    async def test_ac_courses_renders_published_courses(self):
        callback = self.make_callback(STUDENT_ID, "ac:courses")
        await academy_handlers.academy_courses(callback)

        texts = self.edit_text_texts(callback)
        self.assertIn("Python Programming", texts[0])

    async def test_ac_mine_without_enrollments_shows_empty_state(self):
        callback = self.make_callback(STUDENT_ID, "ac:mine")
        await academy_handlers.academy_mine(callback)

        texts = self.edit_text_texts(callback)
        self.assertIn("not enrolled in any courses", texts[0])

    async def test_ac_course_detail_shows_enroll_button(self):
        callback = self.make_callback(STUDENT_ID, f"ac:course:{self.course_id}")
        await academy_handlers.academy_course_detail(callback)

        texts = self.edit_text_texts(callback)
        self.assertIn("Python Programming", texts[0])

        markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
        button_data = [
            btn.callback_data
            for row in markup.inline_keyboard
            for btn in row
        ]
        self.assertIn(f"ac:enroll:{self.course_id}", button_data)

    async def test_ac_progress_without_enrollments_shows_empty_state(self):
        callback = self.make_callback(STUDENT_ID, "ac:progress")
        await academy_handlers.academy_all_progress(callback)

        callback.answer.assert_awaited_once()
        self.assertEqual(len(self.edit_text_texts(callback)), 1)

    async def test_ac_oneprogress_for_enrolled_course(self):
        academy.enroll_user(STUDENT_ID, self.course_id)
        callback = self.make_callback(STUDENT_ID, f"ac:oneprogress:{self.course_id}")
        await academy_handlers.academy_course_progress(callback)

        texts = self.edit_text_texts(callback)
        self.assertTrue(any("0/1" in text for text in texts))

    async def test_ac_oneprogress_malformed_id_is_answered_not_raised(self):
        callback = self.make_callback(STUDENT_ID, "ac:oneprogress:abc")
        await academy_handlers.academy_course_progress(callback)

        callback.answer.assert_awaited_once()
        self.assertIn(
            "unavailable",
            callback.answer.await_args.args[0],
        )
        self.assertEqual(callback.answer.await_args.kwargs.get("show_alert"), True)


class TestAcademyCourseDetailErrors(AcademyCallbackTestBase):

    async def test_malformed_course_id_answers_not_found(self):
        callback = self.make_callback(STUDENT_ID, "ac:course:abc")
        await academy_handlers.academy_course_detail(callback)

        callback.answer.assert_awaited_once_with(
            academy_handlers.TEXT["en"]["not_found"], show_alert=True
        )

    async def test_unpublished_course_answers_not_found(self):
        callback = self.make_callback(STUDENT_ID, f"ac:course:{self.draft_course_id}")
        await academy_handlers.academy_course_detail(callback)

        callback.answer.assert_any_await(
            academy_handlers.TEXT["en"]["not_found"], show_alert=True
        )


class TestAcademyEnrollCallback(AcademyCallbackTestBase):

    async def test_new_enrollment_succeeds(self):
        callback = self.make_callback(STUDENT_ID, f"ac:enroll:{self.course_id}")
        await academy_handlers.academy_enroll(callback)

        callback.answer.assert_any_await(
            academy_handlers.TEXT["en"]["enrolled"], show_alert=True
        )
        enrolled = academy.get_enrolled_courses(STUDENT_ID)
        self.assertEqual([item["id"] for item in enrolled], [self.course_id])

    async def test_repeat_enrollment_reports_already_enrolled(self):
        academy.enroll_user(STUDENT_ID, self.course_id)
        callback = self.make_callback(STUDENT_ID, f"ac:enroll:{self.course_id}")
        await academy_handlers.academy_enroll(callback)

        callback.answer.assert_any_await(
            academy_handlers.TEXT["en"]["already"], show_alert=True
        )

    async def test_malformed_course_id_answers_not_found(self):
        callback = self.make_callback(STUDENT_ID, "ac:enroll:abc")
        await academy_handlers.academy_enroll(callback)

        callback.answer.assert_awaited_once_with(
            academy_handlers.TEXT["en"]["not_found"], show_alert=True
        )

    async def test_unpublished_course_answers_not_found(self):
        callback = self.make_callback(STUDENT_ID, f"ac:enroll:{self.draft_course_id}")
        await academy_handlers.academy_enroll(callback)

        callback.answer.assert_awaited_once_with(
            academy_handlers.TEXT["en"]["not_found"], show_alert=True
        )


class TestAcademyCurriculumCallback(AcademyCallbackTestBase):

    async def test_enrolled_student_sees_curriculum(self):
        academy.enroll_user(STUDENT_ID, self.course_id)
        callback = self.make_callback(STUDENT_ID, f"ac:curr:{self.course_id}")
        await academy_handlers.academy_curriculum(callback)

        texts = self.edit_text_texts(callback)
        self.assertIn("Python Fundamentals", texts[0])
        self.assertIn("Your First Program", texts[0])

    async def test_not_enrolled_student_gets_registration_alert(self):
        callback = self.make_callback(OTHER_ID, f"ac:curr:{self.course_id}")
        await academy_handlers.academy_curriculum(callback)

        callback.answer.assert_any_await(
            academy_handlers.TEXT["en"]["not_registered"], show_alert=True
        )
        callback.message.edit_text.assert_not_awaited()

    async def test_malformed_course_id_answers_not_found(self):
        callback = self.make_callback(STUDENT_ID, "ac:curr:abc")
        await academy_handlers.academy_curriculum(callback)

        callback.answer.assert_awaited_once_with(
            academy_handlers.TEXT["en"]["not_found"], show_alert=True
        )


class TestAcademyLessonCallback(AcademyCallbackTestBase):

    async def test_enrolled_student_receives_lesson_content(self):
        academy.enroll_user(STUDENT_ID, self.course_id)
        callback = self.make_callback(
            STUDENT_ID, f"ac:lesson:{self.lesson_id}:{self.course_id}"
        )
        await academy_handlers.academy_lesson(callback)

        sent = [call.args[0] for call in callback.message.answer.await_args_list]
        self.assertTrue(any("print()" in text for text in sent))
        callback.answer.assert_awaited()

    async def test_not_enrolled_student_gets_not_found_alert(self):
        callback = self.make_callback(
            OTHER_ID, f"ac:lesson:{self.lesson_id}:{self.course_id}"
        )
        await academy_handlers.academy_lesson(callback)

        callback.answer.assert_awaited_once_with(
            academy_handlers.TEXT["en"]["not_found"], show_alert=True
        )

    async def test_malformed_lesson_id_answers_not_found(self):
        callback = self.make_callback(STUDENT_ID, f"ac:lesson:abc:{self.course_id}")
        await academy_handlers.academy_lesson(callback)

        callback.answer.assert_awaited_once_with(
            academy_handlers.TEXT["en"]["not_found"], show_alert=True
        )


class TestAcademyCompleteLessonCallback(AcademyCallbackTestBase):

    async def test_enrolled_student_completes_lesson(self):
        academy.enroll_user(STUDENT_ID, self.course_id)
        callback = self.make_callback(
            STUDENT_ID, f"ac:done:{self.lesson_id}:{self.course_id}"
        )
        await academy_handlers.academy_complete_lesson(callback)

        callback.answer.assert_any_await(
            academy_handlers.TEXT["en"]["marked"], show_alert=True
        )

        curriculum = academy.get_course_curriculum(
            self.course_id, telegram_id=STUDENT_ID
        )
        progress = curriculum["modules"][0]["lessons"][0]["progress"]
        self.assertEqual(progress["status"], "completed")

    async def test_not_enrolled_student_gets_registration_alert(self):
        callback = self.make_callback(
            OTHER_ID, f"ac:done:{self.lesson_id}:{self.course_id}"
        )
        await academy_handlers.academy_complete_lesson(callback)

        callback.answer.assert_awaited_once_with(
            academy_handlers.TEXT["en"]["not_registered"], show_alert=True
        )
        with db.get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM lesson_progress WHERE lesson_id = ?",
                (self.lesson_id,),
            ).fetchall()
        self.assertEqual(rows, [])

    async def test_malformed_lesson_id_answers_not_found(self):
        callback = self.make_callback(STUDENT_ID, f"ac:done:abc:{self.course_id}")
        await academy_handlers.academy_complete_lesson(callback)

        callback.answer.assert_awaited_once_with(
            academy_handlers.TEXT["en"]["not_found"], show_alert=True
        )


class TestCallbackOnlyUserRegistration(AcademyCallbackTestBase):
    """W-4: users first seen via a callback must be registered."""

    async def assert_middleware_registers(self, event):
        from bot import UserActivityMiddleware

        middleware = UserActivityMiddleware()
        handler = AsyncMock()

        await middleware(handler, event, {})

        handler.assert_awaited_once()
        self.assertIs(handler.await_args.args[0], event)
        return db.get_user(event.from_user.id)

    async def test_callback_query_middleware_registers_new_user(self):
        event = CallbackQuery(
            id="cb1",
            from_user=User(
                id=CALLBACK_ONLY_ID, is_bot=False, first_name="Callback", username="cb"
            ),
            chat_instance="ci1",
            data="ac:home",
        )

        user = await self.assert_middleware_registers(event)

        self.assertIsNotNone(user)
        self.assertEqual(user["language"], "en")

    async def test_message_middleware_still_registers_users(self):
        event = Message(
            message_id=1,
            date=datetime.now(),
            chat=Chat(id=CALLBACK_ONLY_ID, type="private"),
            from_user=User(
                id=CALLBACK_ONLY_ID, is_bot=False, first_name="Msg", username="msg"
            ),
            text="/start",
        )

        user = await self.assert_middleware_registers(event)

        self.assertIsNotNone(user)

    async def test_callback_only_user_can_enroll_after_registration(self):
        event = CallbackQuery(
            id="cb2",
            from_user=User(
                id=CALLBACK_ONLY_ID, is_bot=False, first_name="Callback"
            ),
            chat_instance="ci2",
            data=f"ac:enroll:{self.course_id}",
        )
        await self.assert_middleware_registers(event)

        callback = self.make_callback(CALLBACK_ONLY_ID, f"ac:enroll:{self.course_id}")
        await academy_handlers.academy_enroll(callback)

        callback.answer.assert_any_await(
            academy_handlers.TEXT["en"]["enrolled"], show_alert=True
        )
        enrolled = academy.get_enrolled_courses(CALLBACK_ONLY_ID)
        self.assertEqual([item["id"] for item in enrolled], [self.course_id])


class TestUpssertProtectsExistingUsers(AcademyCallbackTestBase):

    def test_language_and_created_at_survive_re_registration(self):
        db.set_language(STUDENT_ID, "am")

        with db.get_connection() as connection:
            original = connection.execute(
                "SELECT language, created_at FROM users WHERE telegram_id = ?",
                (STUDENT_ID,),
            ).fetchone()
        original_created_at = original["created_at"]

        db.register_user(STUDENT_ID, "newname", "New Name")

        with db.get_connection() as connection:
            updated = connection.execute(
                "SELECT language, created_at, username FROM users "
                "WHERE telegram_id = ?",
                (STUDENT_ID,),
            ).fetchone()

        self.assertEqual(updated["language"], "am")
        self.assertEqual(updated["created_at"], original_created_at)
        self.assertEqual(updated["username"], "newname")


if __name__ == "__main__":
    unittest.main()
