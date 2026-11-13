import unittest
from pathlib import Path
from types import SimpleNamespace

import jinja2


TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "web_admin" / "templates"


def make_environment():
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    env.globals["url_for"] = lambda endpoint, **kwargs: "/" + str(
        kwargs.get("path", "")
    ).lstrip("/")
    return env


LESSON_FORM_CONTEXT = {
    "module": SimpleNamespace(
        translations={"en": {"title": "Intro to Python"}},
        slug="intro-to-python",
        course_id=1,
    ),
    "csrf": "test-csrf-token",
    "lesson": None,
    "error": None,
    "success": None,
}


class TestAcademyLessonFormTemplate(unittest.TestCase):

    def setUp(self):
        self.rendered = make_environment().get_template(
            "academy_lesson_form.html"
        ).render(**LESSON_FORM_CONTEXT)

    def test_title_is_clean(self):
        start = self.rendered.index("<title>") + len("<title>")
        end = self.rendered.index("</title>")
        title = self.rendered[start:end]

        self.assertEqual(title, "New lesson · EthioMate Admin")
        self.assertNotIn("\\n", title)
        self.assertNotIn("<script", title)

    def test_heading_is_clean(self):
        start = self.rendered.index("<h1>") + len("<h1>")
        end = self.rendered.index("</h1>")
        heading = self.rendered[start:end]

        self.assertEqual(heading, "Create lesson")
        self.assertNotIn("<script", heading)
        self.assertNotIn("\\n", heading)

    def test_script_appears_exactly_once(self):
        count = self.rendered.count('<script src="/static/lesson-editor.js"')
        self.assertEqual(count, 1)

    def test_script_is_inside_head(self):
        head = self.rendered[: self.rendered.index("</head>")]
        self.assertIn('<script src="/static/lesson-editor.js"', head)

    def test_literal_backslash_n_removed(self):
        self.assertNotIn("\\n{% endblock %}", self.rendered)

    def test_editor_loads_with_defer(self):
        self.assertIn('<script src="/static/lesson-editor.js" defer></script>',
                      self.rendered)


class TestBaseTemplateHeadBlock(unittest.TestCase):

    def test_head_block_exists(self):
        rendered = make_environment().get_template("base.html").render(
            active="overview", csrf="test-csrf-token"
        )
        self.assertIn("{% block head %}", _read_base_source())

    def test_dashboard_renders_unchanged(self):
        stats = {
            "total_users": 2,
            "new_users_today": 0,
            "active_users_week": 1,
            "quiz_attempts": 1,
            "questions_answered": 5,
            "average_score": 60.0,
            "correct_answers": 3,
            "pending_feedback": 1,
            "feedback_total": 1,
        }
        rendered = make_environment().get_template("dashboard.html").render(
            active="overview", csrf="test-csrf-token", stats=stats
        )

        self.assertIn("System overview", rendered)
        self.assertIn("<strong>2</strong>", rendered)
        self.assertNotIn("<script", rendered)


def _read_base_source():
    return (TEMPLATES_DIR / "base.html").read_text()


if __name__ == "__main__":
    unittest.main()
