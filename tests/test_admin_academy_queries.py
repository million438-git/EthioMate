import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from web_admin import academy_queries as academy_admin


class TestAcademyAdminQueries(unittest.TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.test_database = Path(self.temp_directory.name) / "admin.sqlite3"

        self.database_patch = patch.object(
            db, "DATABASE_PATH", self.test_database
        )
        self.database_patch.start()
        db.init_db()

        self.category_id = academy_admin.create_category(
            "technology",
            "Technology",
            "ቴክኖሎጂ",
            "Teeknooloojii",
        )

        self.translations = {
            "en": {
                "title": "Python Programming",
                "description": "Learn Python from the beginning.",
            },
            "am": {
                "title": "የPython ፕሮግራሚንግ",
                "description": "Python ከመሠረቱ ይማሩ።",
            },
            "om": {
                "title": "Sagantaa Python",
                "description": "Python jalqabaa kaasee baradhu.",
            },
        }

    def tearDown(self):
        self.database_patch.stop()
        self.temp_directory.cleanup()

    def create_course(self):
        return academy_admin.create_course(
            self.category_id,
            "python-programming",
            "beginner",
            self.translations,
        )

    def test_category_creation_and_listing(self):
        categories = academy_admin.list_admin_categories()

        self.assertEqual(len(categories), 1)
        self.assertEqual(categories[0]["slug"], "technology")
        self.assertEqual(categories[0]["name_am"], "ቴክኖሎጂ")

    def test_rejects_invalid_category_slug(self):
        with self.assertRaises(ValueError):
            academy_admin.create_category(
                "../technology",
                "Technology",
                "ቴክኖሎጂ",
                "Teeknooloojii",
            )

    def test_creates_course_as_draft_with_three_translations(self):
        course_id = self.create_course()
        course = academy_admin.get_admin_course(course_id)

        self.assertEqual(course["status"], "draft")
        self.assertEqual(course["level"], "beginner")
        self.assertEqual(
            course["translations"]["am"]["title"],
            "የPython ፕሮግራሚንግ",
        )
        self.assertEqual(
            course["translations"]["om"]["title"],
            "Sagantaa Python",
        )

    def test_course_creation_requires_english_title(self):
        translations = {
            "en": {"title": "", "description": ""},
        }

        with self.assertRaises(ValueError):
            academy_admin.create_course(
                self.category_id,
                "missing-title",
                "beginner",
                translations,
            )

    def test_rejects_invalid_course_level(self):
        with self.assertRaises(ValueError):
            academy_admin.create_course(
                self.category_id,
                "python-programming",
                "expert",
                self.translations,
            )

    def test_course_starts_as_draft_and_can_be_published(self):
        course_id = self.create_course()

        self.assertTrue(
            academy_admin.set_course_status(course_id, "published")
        )

        course = academy_admin.get_admin_course(course_id)
        self.assertEqual(course["status"], "published")

    def test_course_can_be_archived_without_deletion(self):
        course_id = self.create_course()

        self.assertTrue(
            academy_admin.set_course_status(course_id, "archived")
        )

        course = academy_admin.get_admin_course(course_id)

        self.assertIsNotNone(course)
        self.assertEqual(course["status"], "archived")

    def test_cannot_publish_course_without_english_translation(self):
        course_id = academy_admin.create_course(
            self.category_id,
            "draft-course",
            "beginner",
            {"en": {"title": "", "description": ""}},
        ) if False else None

        # Create a course directly to verify the publication safeguard.
        with db.get_connection() as connection:
            course_id = connection.execute("""
                INSERT INTO courses (
                    category_id, slug, level, status
                )
                VALUES (?, 'incomplete-course', 'beginner', 'draft')
            """, (self.category_id,)).lastrowid
            connection.commit()

        with self.assertRaises(ValueError):
            academy_admin.set_course_status(course_id, "published")

    def test_updates_course_without_removing_translations(self):
        course_id = self.create_course()

        updated = {
            **self.translations,
            "en": {
                "title": "Python Programming: Beginner to Practical",
                "description": "A practical Python course.",
            },
        }

        self.assertTrue(
            academy_admin.update_course(
                course_id,
                self.category_id,
                "python-programming",
                "intermediate",
                updated,
            )
        )

        course = academy_admin.get_admin_course(course_id)

        self.assertEqual(course["level"], "intermediate")
        self.assertEqual(
            course["translations"]["en"]["title"],
            "Python Programming: Beginner to Practical",
        )
        self.assertIn("am", course["translations"])
        self.assertIn("om", course["translations"])

    def test_lists_real_course_statistics(self):
        course_id = self.create_course()
        academy_admin.set_course_status(course_id, "published")

        courses = academy_admin.list_admin_courses()

        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0]["title"], "Python Programming")
        self.assertEqual(courses[0]["status"], "published")

        overview = academy_admin.get_academy_overview()

        self.assertEqual(overview["total_courses"], 1)
        self.assertEqual(overview["published_courses"], 1)
        self.assertEqual(overview["active_categories"], 1)

    def test_rejects_invalid_status(self):
        course_id = self.create_course()

        with self.assertRaises(ValueError):
            academy_admin.set_course_status(course_id, "deleted")

    def test_unknown_course_returns_false(self):
        self.assertFalse(
            academy_admin.set_course_status(99999, "archived")
        )

    def test_database_integrity(self):
        self.create_course()

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
