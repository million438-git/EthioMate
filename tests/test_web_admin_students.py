import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from web_admin.queries import get_student_profile


class TestStudentAdminProfile(unittest.TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.test_database = Path(self.temp_directory.name) / "admin_test.sqlite3"
        self.database_patch = patch.object(db, "DATABASE_PATH", self.test_database)
        self.database_patch.start()
        db.init_db()

    def tearDown(self):
        self.database_patch.stop()
        self.temp_directory.cleanup()

    def test_returns_student_profile_and_real_activity(self):
        student_id = 123456789

        db.register_user(
            telegram_id=student_id,
            username="profile_student",
            first_name="Profile Student",
        )
        db.set_language(student_id, "am")

        db.save_quiz_result(
            telegram_id=student_id,
            subject="Physics",
            topic="Motion",
            difficulty="advanced",
            total_questions=5,
            correct_answers=4,
        )

        db.save_feedback(
            telegram_id=student_id,
            username="profile_student",
            first_name="Profile Student",
            submission_type="suggest",
            content="Please add more physics questions.",
        )

        profile = get_student_profile(student_id)

        self.assertIsNotNone(profile)
        self.assertEqual(profile["user"]["telegram_id"], student_id)
        self.assertEqual(profile["user"]["language"], "am")
        self.assertEqual(profile["quiz_stats"]["attempts"], 1)
        self.assertEqual(profile["quiz_stats"]["questions_answered"], 5)
        self.assertEqual(profile["quiz_stats"]["correct_answers"], 4)
        self.assertEqual(profile["quiz_stats"]["average_score"], 80.0)
        self.assertEqual(len(profile["quizzes"]), 1)
        self.assertEqual(profile["quizzes"][0]["topic"], "Motion")
        self.assertEqual(len(profile["feedback"]), 1)
        self.assertEqual(profile["feedback_count"], 1)
        self.assertEqual(profile["feedback"][0]["submission_type"], "suggest")

    def test_returns_zero_activity_for_student_without_history(self):
        student_id = 123456788

        db.register_user(
            telegram_id=student_id,
            username="new_student",
            first_name="New Student",
        )

        profile = get_student_profile(student_id)

        self.assertEqual(profile["quiz_stats"]["attempts"], 0)
        self.assertEqual(profile["quiz_stats"]["average_score"], 0)
        self.assertEqual(profile["quizzes"], [])
        self.assertEqual(profile["feedback"], [])
        self.assertEqual(profile["feedback_count"], 0)

    def test_returns_none_for_unknown_student(self):
        self.assertIsNone(get_student_profile(999999999))


if __name__ == "__main__":
    unittest.main()
