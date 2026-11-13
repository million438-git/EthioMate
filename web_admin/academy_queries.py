"""Database operations for the EthioMate Academy administration."""

import re

from database import db


LANGUAGES = ("en", "am", "om")
COURSE_LEVELS = ("beginner", "intermediate", "advanced")
COURSE_STATUSES = ("draft", "published", "archived")

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _validate_slug(slug):
    if not isinstance(slug, str):
        raise ValueError("A valid slug is required.")

    slug = slug.strip().lower()

    if not SLUG_PATTERN.fullmatch(slug) or len(slug) > 100:
        raise ValueError(
            "Use lowercase letters, numbers and single hyphens in slugs."
        )

    return slug


def _validate_text(value, field, maximum=500):
    if not isinstance(value, str):
        raise ValueError(f"{field} is required.")

    value = value.strip()

    if not value:
        raise ValueError(f"{field} cannot be empty.")

    if len(value) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters.")

    return value


def get_academy_overview():
    """Return live Academy statistics."""

    with db.get_connection() as connection:
        courses = connection.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END)
                    AS published,
                SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END)
                    AS drafts,
                SUM(CASE WHEN status = 'archived' THEN 1 ELSE 0 END)
                    AS archived
            FROM courses
        """).fetchone()

        categories = connection.execute("""
            SELECT COUNT(*) FROM skill_categories WHERE is_active = 1
        """).fetchone()[0]

        enrollments = connection.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)
                    AS completed
            FROM course_enrollments
        """).fetchone()

        submissions = connection.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END)
                    AS pending
            FROM assignment_submissions
        """).fetchone()

    return {
        "total_courses": courses["total"] or 0,
        "published_courses": courses["published"] or 0,
        "draft_courses": courses["drafts"] or 0,
        "archived_courses": courses["archived"] or 0,
        "active_categories": categories,
        "total_enrollments": enrollments["total"] or 0,
        "completed_enrollments": enrollments["completed"] or 0,
        "total_submissions": submissions["total"] or 0,
        "pending_submissions": submissions["pending"] or 0,
    }


def list_admin_categories():
    """List categories, including inactive categories."""

    with db.get_connection() as connection:
        rows = connection.execute("""
            SELECT
                sc.*,
                COUNT(c.id) AS course_count
            FROM skill_categories sc
            LEFT JOIN courses c ON c.category_id = sc.id
            GROUP BY sc.id
            ORDER BY sc.sort_order, sc.name_en
        """).fetchall()

    return [dict(row) for row in rows]


def create_category(
    slug,
    name_en,
    name_am,
    name_om,
    description_en="",
    description_am="",
    description_om="",
):
    """Create a multilingual Academy category."""

    slug = _validate_slug(slug)

    names = {
        "en": _validate_text(name_en, "English category name", 120),
        "am": _validate_text(name_am, "Amharic category name", 120),
        "om": _validate_text(name_om, "Afaan Oromo category name", 120),
    }

    descriptions = {}
    for language, value in (
        ("en", description_en),
        ("am", description_am),
        ("om", description_om),
    ):
        if not isinstance(value, str) or len(value) > 1000:
            raise ValueError("Category descriptions must be under 1000 characters.")
        descriptions[language] = value.strip()

    with db.get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO skill_categories (
                slug,
                name_en, name_am, name_om,
                description_en, description_am, description_om
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            slug,
            names["en"], names["am"], names["om"],
            descriptions["en"], descriptions["am"], descriptions["om"],
        ))

        connection.commit()
        return cursor.lastrowid


def list_admin_courses(status=None):
    """List courses with real enrollment and curriculum counts."""

    if status is not None and status not in COURSE_STATUSES:
        raise ValueError("Invalid course status.")

    query = """
        SELECT
            c.id,
            c.category_id,
            c.slug,
            c.level,
            c.status,
            c.sort_order,
            c.created_at,
            c.updated_at,
            sc.slug AS category_slug,
            sc.name_en AS category_name,
            COUNT(DISTINCT m.id) AS module_count,
            COUNT(DISTINCT e.id) AS enrollment_count
        FROM courses c
        JOIN skill_categories sc ON sc.id = c.category_id
        LEFT JOIN course_modules m ON m.course_id = c.id
        LEFT JOIN course_enrollments e ON e.course_id = c.id
    """

    parameters = []

    if status is not None:
        query += " WHERE c.status = ?"
        parameters.append(status)

    query += """
        GROUP BY c.id
        ORDER BY
            CASE c.status
                WHEN 'published' THEN 0
                WHEN 'draft' THEN 1
                ELSE 2
            END,
            c.sort_order,
            c.id DESC
    """

    with db.get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
        results = []

        for row in rows:
            item = dict(row)

            translations = connection.execute("""
                SELECT language, title, description
                FROM course_translations
                WHERE course_id = ?
            """, (item["id"],)).fetchall()

            item["translations"] = {
                translation["language"]: dict(translation)
                for translation in translations
            }

            item["title"] = (
                item["translations"].get("en", {}).get("title")
                or item["slug"]
            )

            results.append(item)

    return results


def get_admin_course(course_id):
    """Return a course and all its translations for editing."""

    with db.get_connection() as connection:
        course = connection.execute("""
            SELECT c.*, sc.name_en AS category_name
            FROM courses c
            JOIN skill_categories sc ON sc.id = c.category_id
            WHERE c.id = ?
        """, (course_id,)).fetchone()

        if course is None:
            return None

        result = dict(course)

        translations = connection.execute("""
            SELECT language, title, description
            FROM course_translations
            WHERE course_id = ?
        """, (course_id,)).fetchall()

        result["translations"] = {
            row["language"]: dict(row)
            for row in translations
        }

        return result


def _validate_course_data(
    slug,
    level,
    translations,
):
    slug = _validate_slug(slug)

    if level not in COURSE_LEVELS:
        raise ValueError("Invalid course level.")

    if not isinstance(translations, dict):
        raise ValueError("Course translations are required.")

    clean_translations = {}

    for language in LANGUAGES:
        translation = translations.get(language, {})

        if not isinstance(translation, dict):
            raise ValueError("Invalid course translation.")

        title = translation.get("title", "")
        description = translation.get("description", "")

        if language == "en":
            title = _validate_text(title, "English course title", 180)
        else:
            title = title.strip() if isinstance(title, str) else ""

            if len(title) > 180:
                raise ValueError("Course title is too long.")

        if not isinstance(description, str) or len(description) > 5000:
            raise ValueError("Course description is too long.")

        clean_translations[language] = {
            "title": title,
            "description": description.strip(),
        }

    return slug, clean_translations


def _save_course_translations(connection, course_id, translations):
    for language, translation in translations.items():
        if not translation["title"]:
            # An explicitly blank optional translation means it is cleared.
            # English is validated as required before this function is called.
            connection.execute("""
                DELETE FROM course_translations
                WHERE course_id = ? AND language = ?
            """, (course_id, language))
            continue

        connection.execute("""
            INSERT INTO course_translations (
                course_id, language, title, description
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(course_id, language)
            DO UPDATE SET
                title = excluded.title,
                description = excluded.description
        """, (
            course_id,
            language,
            translation["title"],
            translation["description"],
        ))


def create_course(
    category_id,
    slug,
    level,
    translations,
    sort_order=0,
):
    """Create a course initially as a draft."""

    slug, translations = _validate_course_data(
        slug, level, translations
    )

    if not isinstance(sort_order, int) or sort_order < 0:
        raise ValueError("Sort order must be a non-negative integer.")

    with db.get_connection() as connection:
        category = connection.execute("""
            SELECT id
            FROM skill_categories
            WHERE id = ? AND is_active = 1
        """, (category_id,)).fetchone()

        if category is None:
            raise ValueError("Select an active category.")

        cursor = connection.execute("""
            INSERT INTO courses (
                category_id, slug, level, status, sort_order
            )
            VALUES (?, ?, ?, 'draft', ?)
        """, (category_id, slug, level, sort_order))

        course_id = cursor.lastrowid

        _save_course_translations(
            connection, course_id, translations
        )

        connection.commit()
        return course_id


def update_course(
    course_id,
    category_id,
    slug,
    level,
    translations,
    sort_order=0,
):
    """Update course metadata without deleting its curriculum."""

    slug, translations = _validate_course_data(
        slug, level, translations
    )

    if not isinstance(sort_order, int) or sort_order < 0:
        raise ValueError("Sort order must be a non-negative integer.")

    with db.get_connection() as connection:
        course = connection.execute("""
            SELECT id FROM courses WHERE id = ?
        """, (course_id,)).fetchone()

        category = connection.execute("""
            SELECT id FROM skill_categories
            WHERE id = ? AND is_active = 1
        """, (category_id,)).fetchone()

        if course is None:
            return False

        if category is None:
            raise ValueError("Select an active category.")

        connection.execute("""
            UPDATE courses
            SET category_id = ?,
                slug = ?,
                level = ?,
                sort_order = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (category_id, slug, level, sort_order, course_id))

        _save_course_translations(
            connection, course_id, translations
        )

        connection.commit()
        return True


def set_course_status(course_id, status):
    """Change publication state without deleting course data."""

    if status not in COURSE_STATUSES:
        raise ValueError("Invalid course status.")

    with db.get_connection() as connection:
        course = connection.execute("""
            SELECT id FROM courses WHERE id = ?
        """, (course_id,)).fetchone()

        if course is None:
            return False

        if status == "published":
            english = connection.execute("""
                SELECT title
                FROM course_translations
                WHERE course_id = ? AND language = 'en'
            """, (course_id,)).fetchone()

            if english is None or not english["title"].strip():
                raise ValueError(
                    "Add an English course title before publishing."
                )

        connection.execute("""
            UPDATE courses
            SET status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, course_id))

        connection.commit()
        return True


# ---------------------------------------------------------------------
# Curriculum administration: modules and lessons
# ---------------------------------------------------------------------

def _validate_translations(translations, content_field, content_limit):
    """Validate multilingual module or lesson translations."""
    if not isinstance(translations, dict):
        raise ValueError("Translations must be provided.")

    cleaned = {}

    for language in LANGUAGES:
        item = translations.get(language, {})
        if not isinstance(item, dict):
            raise ValueError("Invalid translation data.")

        title = item.get("title", "")
        if language == "en":
            title = _validate_text(title, "English title", 180)
        else:
            title = title.strip() if isinstance(title, str) else ""
            if len(title) > 180:
                raise ValueError("Translation title exceeds 180 characters.")

        content = item.get(content_field, "")
        if not isinstance(content, str) or len(content) > content_limit:
            raise ValueError("Translation content is too long.")

        cleaned[language] = {
            "title": title,
            content_field: content.strip(),
        }

    return cleaned


def _save_translations(
    connection, table, foreign_key, record_id, translations
):
    """Save or clear optional translations using fixed internal table names."""
    for language, translation in translations.items():
        if not translation["title"]:
            connection.execute(
                f"DELETE FROM {table} "
                f"WHERE {foreign_key} = ? AND language = ?",
                (record_id, language),
            )
            continue

        fields = list(translation.keys())
        columns = ", ".join([foreign_key, "language"] + fields)
        placeholders = ", ".join(["?"] * (len(fields) + 2))
        updates = ", ".join(
            f"{field} = excluded.{field}" for field in fields
        )

        connection.execute(
            f"""
            INSERT INTO {table} ({columns})
            VALUES ({placeholders})
            ON CONFLICT({foreign_key}, language)
            DO UPDATE SET {updates}
            """,
            (
                record_id,
                language,
                *(translation[field] for field in fields),
            ),
        )


def _load_admin_translations(
    connection, table, foreign_key, record_id
):
    rows = connection.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE {foreign_key} = ?
        ORDER BY CASE language
            WHEN 'en' THEN 0
            WHEN 'am' THEN 1
            ELSE 2
        END
        """,
        (record_id,),
    ).fetchall()

    return {row["language"]: dict(row) for row in rows}


def list_admin_modules(course_id):
    """Return all modules and lessons for an administrator."""
    with db.get_connection() as connection:
        course = connection.execute(
            "SELECT id FROM courses WHERE id = ?", (course_id,)
        ).fetchone()

        if course is None:
            return None

        modules = connection.execute(
            """
            SELECT *
            FROM course_modules
            WHERE course_id = ?
            ORDER BY sort_order, id
            """,
            (course_id,),
        ).fetchall()

        results = []

        for row in modules:
            module = dict(row)
            module["translations"] = _load_admin_translations(
                connection,
                "module_translations",
                "module_id",
                module["id"],
            )
            module["title"] = (
                module["translations"].get("en", {}).get("title")
                or module["slug"]
            )

            lessons = connection.execute(
                """
                SELECT *
                FROM course_lessons
                WHERE module_id = ?
                ORDER BY sort_order, id
                """,
                (module["id"],),
            ).fetchall()

            module["lessons"] = []

            for lesson_row in lessons:
                lesson = dict(lesson_row)
                lesson["translations"] = _load_admin_translations(
                    connection,
                    "lesson_translations",
                    "lesson_id",
                    lesson["id"],
                )
                lesson["title"] = (
                    lesson["translations"].get("en", {}).get("title")
                    or lesson["slug"]
                )
                module["lessons"].append(lesson)

            results.append(module)

        return results


def create_module(course_id, slug, translations, sort_order=0):
    """Create a draft module in an existing course."""
    slug = _validate_slug(slug)
    translations = _validate_translations(
        translations, "description", 5000
    )

    if not isinstance(sort_order, int) or sort_order < 0:
        raise ValueError("Module order must be a non-negative integer.")

    with db.get_connection() as connection:
        course = connection.execute(
            "SELECT id FROM courses WHERE id = ?", (course_id,)
        ).fetchone()

        if course is None:
            raise ValueError("Course not found.")

        cursor = connection.execute(
            """
            INSERT INTO course_modules
                (course_id, slug, sort_order, is_published)
            VALUES (?, ?, ?, 0)
            """,
            (course_id, slug, sort_order),
        )

        module_id = cursor.lastrowid
        _save_translations(
            connection,
            "module_translations",
            "module_id",
            module_id,
            translations,
        )
        connection.commit()
        return module_id


def update_module(module_id, slug, translations, sort_order):
    """Update module details without deleting its lessons."""
    slug = _validate_slug(slug)
    translations = _validate_translations(
        translations, "description", 5000
    )

    if not isinstance(sort_order, int) or sort_order < 0:
        raise ValueError("Module order must be a non-negative integer.")

    with db.get_connection() as connection:
        module = connection.execute(
            "SELECT id FROM course_modules WHERE id = ?", (module_id,)
        ).fetchone()

        if module is None:
            return False

        connection.execute(
            """
            UPDATE course_modules
            SET slug = ?, sort_order = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (slug, sort_order, module_id),
        )

        _save_translations(
            connection,
            "module_translations",
            "module_id",
            module_id,
            translations,
        )
        connection.commit()
        return True


def set_module_status(module_id, is_published):
    """Publish or unpublish a module without deleting its contents."""
    if is_published not in (0, 1, False, True):
        raise ValueError("Invalid module publication status.")

    with db.get_connection() as connection:
        module = connection.execute(
            "SELECT id FROM course_modules WHERE id = ?", (module_id,)
        ).fetchone()

        if module is None:
            return False

        if is_published:
            english = connection.execute(
                """
                SELECT title FROM module_translations
                WHERE module_id = ? AND language = 'en'
                """,
                (module_id,),
            ).fetchone()

            if english is None or not english["title"].strip():
                raise ValueError(
                    "Add an English module title before publishing."
                )

        connection.execute(
            """
            UPDATE course_modules
            SET is_published = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (int(is_published), module_id),
        )
        connection.commit()
        return True


def create_lesson(
    module_id,
    slug,
    lesson_type,
    translations,
    sort_order=0,
    estimated_minutes=15,
):
    """Create a draft lesson, exercise or project."""
    slug = _validate_slug(slug)

    if lesson_type not in ("lesson", "exercise", "project"):
        raise ValueError("Invalid lesson type.")

    translations = _validate_translations(
        translations, "content", 50000
    )

    if not isinstance(sort_order, int) or sort_order < 0:
        raise ValueError("Lesson order must be a non-negative integer.")

    if (
        not isinstance(estimated_minutes, int)
        or not 1 <= estimated_minutes <= 1440
    ):
        raise ValueError("Duration must be between 1 and 1440 minutes.")

    with db.get_connection() as connection:
        module = connection.execute(
            "SELECT id FROM course_modules WHERE id = ?", (module_id,)
        ).fetchone()

        if module is None:
            raise ValueError("Module not found.")

        cursor = connection.execute(
            """
            INSERT INTO course_lessons (
                module_id, slug, lesson_type, sort_order,
                estimated_minutes, is_published
            )
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                module_id,
                slug,
                lesson_type,
                sort_order,
                estimated_minutes,
            ),
        )

        lesson_id = cursor.lastrowid
        _save_translations(
            connection,
            "lesson_translations",
            "lesson_id",
            lesson_id,
            translations,
        )
        connection.commit()
        return lesson_id


def update_lesson(
    lesson_id,
    slug,
    lesson_type,
    translations,
    sort_order,
    estimated_minutes,
):
    """Update lesson content and settings without deleting progress."""
    slug = _validate_slug(slug)

    if lesson_type not in ("lesson", "exercise", "project"):
        raise ValueError("Invalid lesson type.")

    translations = _validate_translations(
        translations, "content", 50000
    )

    if not isinstance(sort_order, int) or sort_order < 0:
        raise ValueError("Lesson order must be a non-negative integer.")

    if (
        not isinstance(estimated_minutes, int)
        or not 1 <= estimated_minutes <= 1440
    ):
        raise ValueError("Duration must be between 1 and 1440 minutes.")

    with db.get_connection() as connection:
        lesson = connection.execute(
            "SELECT id FROM course_lessons WHERE id = ?", (lesson_id,)
        ).fetchone()

        if lesson is None:
            return False

        connection.execute(
            """
            UPDATE course_lessons
            SET slug = ?, lesson_type = ?, sort_order = ?,
                estimated_minutes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                slug,
                lesson_type,
                sort_order,
                estimated_minutes,
                lesson_id,
            ),
        )

        _save_translations(
            connection,
            "lesson_translations",
            "lesson_id",
            lesson_id,
            translations,
        )
        connection.commit()
        return True


def set_lesson_status(lesson_id, is_published):
    """Publish or unpublish a lesson without deleting student progress."""
    if is_published not in (0, 1, False, True):
        raise ValueError("Invalid lesson publication status.")

    with db.get_connection() as connection:
        lesson = connection.execute(
            "SELECT id FROM course_lessons WHERE id = ?", (lesson_id,)
        ).fetchone()

        if lesson is None:
            return False

        if is_published:
            english = connection.execute(
                """
                SELECT title, content
                FROM lesson_translations
                WHERE lesson_id = ? AND language = 'en'
                """,
                (lesson_id,),
            ).fetchone()

            if (
                english is None
                or not english["title"].strip()
                or not english["content"].strip()
            ):
                raise ValueError(
                    "Add an English lesson title and content before publishing."
                )

        connection.execute(
            """
            UPDATE course_lessons
            SET is_published = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (int(is_published), lesson_id),
        )
        connection.commit()
        return True


def get_admin_module(module_id):
    """Return a module and its parent course for administration."""
    with db.get_connection() as connection:
        row = connection.execute("""
            SELECT m.*, c.slug AS course_slug
            FROM course_modules m
            JOIN courses c ON c.id = m.course_id
            WHERE m.id = ?
        """, (module_id,)).fetchone()

        if row is None:
            return None

        result = dict(row)
        result["translations"] = _load_admin_translations(
            connection, "module_translations", "module_id", module_id
        )
        return result


def get_admin_lesson(lesson_id):
    """Return a lesson, its module, parent course and translations."""
    with db.get_connection() as connection:
        row = connection.execute("""
            SELECT l.*, m.course_id, m.slug AS module_slug,
                   c.slug AS course_slug
            FROM course_lessons l
            JOIN course_modules m ON m.id = l.module_id
            JOIN courses c ON c.id = m.course_id
            WHERE l.id = ?
        """, (lesson_id,)).fetchone()

        if row is None:
            return None

        result = dict(row)
        result["translations"] = _load_admin_translations(
            connection, "lesson_translations", "lesson_id", lesson_id
        )
        return result
