import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from services import academy


class TestAcademyService(unittest.TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.test_database = Path(self.temp_directory.name) / "academy.sqlite3"
        self.database_patch = patch.object(
            db, "DATABASE_PATH", self.test_database
        )
        self.database_patch.start()
        db.init_db()

        self.student_id = 123456789
        db.register_user(self.student_id, "academy_student", "Student")

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
                    VALUES (?, ?, ?, ?)
                """, (self.course_id, language, title, "Course description"))

            self.module_id = connection.execute("""
                INSERT INTO course_modules
                    (course_id, slug, sort_order, is_published)
                VALUES (?, 'fundamentals', 1, 1)
            """, (self.course_id,)).lastrowid

            for language, title in (
                ("en", "Python Fundamentals"),
                ("am", "የPython መሠረታዊ እውቀት"),
                ("om", "Bu'uura Python"),
            ):
                connection.execute("""
                    INSERT INTO module_translations
                        (module_id, language, title)
                    VALUES (?, ?, ?)
                """, (self.module_id, language, title))

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

            self.assignment_id = connection.execute("""
                INSERT INTO assignments
                    (lesson_id, slug, is_published)
                VALUES (?, 'hello-world', 1)
            """, (self.lesson_id,)).lastrowid

            connection.commit()

    def tearDown(self):
        self.database_patch.stop()
        self.temp_directory.cleanup()

    def enroll(self):
        return academy.enroll_user(self.student_id, self.course_id)

    def test_lists_published_courses_with_language(self):
        courses = academy.list_published_courses("am")

        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0]["title"], "የPython ፕሮግራሚንግ")

    def test_falls_back_to_english_translation(self):
        course = academy.get_course(self.course_id, "om")
        self.assertEqual(course["title"], "Sagantaa Python")

        curriculum = academy.get_course_curriculum(
            self.course_id, "am"
        )
        self.assertEqual(
            curriculum["modules"][0]["title"],
            "የPython መሠረታዊ እውቀት",
        )
        self.assertEqual(
            curriculum["modules"][0]["lessons"][0]["title"],
            "Your First Program",
        )

    def test_rejects_unsupported_language(self):
        with self.assertRaises(ValueError):
            academy.list_published_courses("xx")

    def test_enrollment_is_created_only_once(self):
        self.assertTrue(self.enroll())
        self.assertFalse(self.enroll())

        courses = academy.get_enrolled_courses(self.student_id)
        self.assertEqual(len(courses), 1)

    def test_unregistered_student_cannot_enroll(self):
        with self.assertRaises(ValueError):
            academy.enroll_user(999999999, self.course_id)

    def test_student_must_be_enrolled_to_view_lesson(self):
        self.assertIsNone(
            academy.get_lesson(self.lesson_id, self.student_id)
        )

        self.enroll()
        lesson = academy.get_lesson(self.lesson_id, self.student_id)
        self.assertIsNotNone(lesson)
        self.assertEqual(lesson["content"], "Use print() to display text.")

    def test_curriculum_requires_enrollment_when_student_is_supplied(self):
        with self.assertRaises(PermissionError):
            academy.get_course_curriculum(
                self.course_id, telegram_id=self.student_id
            )

        self.enroll()
        curriculum = academy.get_course_curriculum(
            self.course_id, telegram_id=self.student_id
        )
        self.assertEqual(len(curriculum["modules"]), 1)

    def test_tracks_lesson_progress_and_completion_percentage(self):
        self.enroll()

        result = academy.update_lesson_progress(
            self.student_id, self.lesson_id, "in_progress"
        )
        self.assertEqual(result["status"], "in_progress")

        progress = academy.get_course_progress(
            self.student_id, self.course_id
        )
        self.assertEqual(progress["completion_percent"], 0.0)

        academy.update_lesson_progress(
            self.student_id, self.lesson_id, "completed"
        )

        progress = academy.get_course_progress(
            self.student_id, self.course_id
        )
        self.assertEqual(progress["completed_lessons"], 1)
        self.assertEqual(progress["completion_percent"], 100.0)

    def test_rejects_invalid_progress_status(self):
        with self.assertRaises(ValueError):
            academy.update_lesson_progress(
                self.student_id, self.lesson_id, "skipped"
            )

    def test_assignment_submission_requires_enrollment(self):
        with self.assertRaises(PermissionError):
            academy.submit_assignment(
                self.student_id, self.assignment_id, "print('Hello')"
            )

        self.enroll()
        submission_id = academy.submit_assignment(
            self.student_id, self.assignment_id, "  print('Hello')  "
        )
        self.assertIsInstance(submission_id, int)

        with db.get_connection() as connection:
            row = connection.execute("""
                SELECT answer_text, status
                FROM assignment_submissions
                WHERE id = ?
            """, (submission_id,)).fetchone()

        self.assertEqual(row["answer_text"], "print('Hello')")
        self.assertEqual(row["status"], "submitted")

    def test_rejects_empty_assignment_answer(self):
        with self.assertRaises(ValueError):
            academy.submit_assignment(
                self.student_id, self.assignment_id, "   "
            )

    def test_database_integrity_after_service_operations(self):
        self.enroll()
        academy.update_lesson_progress(
            self.student_id, self.lesson_id, "completed"
        )
        academy.submit_assignment(
            self.student_id, self.assignment_id, "print('Hello')"
        )

        with db.get_connection() as connection:
            self.assertEqual(
                connection.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0],
                "ok",
            )
            self.assertEqual(
                connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall(),
                [],
            )


if __name__ == "__main__":
    unittest.main()
