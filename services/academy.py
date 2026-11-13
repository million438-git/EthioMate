"""Business logic for the EthioMate Professional Skills Academy."""

from database import db


SUPPORTED_LANGUAGES = {"en", "am", "om"}


def _validate_language(language):
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported language. Use 'en', 'am', or 'om'.")


def _translated(row, language, prefix=""):
    """Select requested translation, then English, then the first available."""
    translations = row.get("translations", {})
    selected = translations.get(language) or translations.get("en")

    if selected is None and translations:
        selected = next(iter(translations.values()))

    return selected or {}


def _load_translations(connection, table, foreign_key, record_id):
    rows = connection.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE {foreign_key} = ?
        ORDER BY CASE language WHEN 'en' THEN 0
                               WHEN 'am' THEN 1
                               ELSE 2 END
        """,
        (record_id,),
    ).fetchall()

    return {row["language"]: dict(row) for row in rows}


def list_categories(language="en"):
    """Return active skill categories in the requested language."""
    _validate_language(language)

    with db.get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM skill_categories
            WHERE is_active = 1
            ORDER BY sort_order, name_en
        """).fetchall()

        results = []
        for row in rows:
            item = dict(row)
            suffix = {"en": "en", "am": "am", "om": "om"}[language]
            item["name"] = item[f"name_{suffix}"]
            item["description"] = item[f"description_{suffix}"]
            results.append(item)

        return results


def list_published_courses(language="en", category_slug=None):
    """List published courses, optionally filtered by category."""
    _validate_language(language)

    query = """
        SELECT
            c.id, c.category_id, c.slug, c.level, c.status,
            c.sort_order, c.created_at, c.updated_at,
            sc.slug AS category_slug,
            sc.name_en AS category_name_en,
            sc.name_am AS category_name_am,
            sc.name_om AS category_name_om
        FROM courses c
        JOIN skill_categories sc ON sc.id = c.category_id
        WHERE c.status = 'published'
          AND sc.is_active = 1
    """
    parameters = []

    if category_slug is not None:
        query += " AND sc.slug = ?"
        parameters.append(category_slug)

    query += " ORDER BY sc.sort_order, c.sort_order, c.id"

    with db.get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
        results = []

        for row in rows:
            item = dict(row)
            item["category_name"] = item[f"category_name_{language}"]
            item["translations"] = _load_translations(
                connection, "course_translations", "course_id", item["id"]
            )
            translation = _translated(item, language)
            item["title"] = translation.get("title", item["slug"])
            item["description"] = translation.get("description", "")
            results.append(item)

        return results


def get_course(course_id, language="en"):
    """Return one published course and its category information."""
    _validate_language(language)

    with db.get_connection() as connection:
        row = connection.execute("""
            SELECT
                c.*,
                sc.slug AS category_slug,
                sc.name_en AS category_name_en,
                sc.name_am AS category_name_am,
                sc.name_om AS category_name_om
            FROM courses c
            JOIN skill_categories sc ON sc.id = c.category_id
            WHERE c.id = ?
              AND c.status = 'published'
              AND sc.is_active = 1
        """, (course_id,)).fetchone()

        if row is None:
            return None

        item = dict(row)
        item["category_name"] = item[f"category_name_{language}"]
        item["translations"] = _load_translations(
            connection, "course_translations", "course_id", course_id
        )
        translation = _translated(item, language)
        item["title"] = translation.get("title", item["slug"])
        item["description"] = translation.get("description", "")
        return item


def enroll_user(telegram_id, course_id):
    """
    Enroll a registered student in a published course.

    Returns True for a new enrollment and False if already enrolled.
    """
    with db.get_connection() as connection:
        course = connection.execute("""
            SELECT courses.id
            FROM courses
            JOIN skill_categories ON skill_categories.id = courses.category_id
            WHERE courses.id = ?
              AND courses.status = 'published'
              AND skill_categories.is_active = 1
        """, (course_id,)).fetchone()

        if course is None:
            raise ValueError("Course is unavailable.")

        user = connection.execute("""
            SELECT telegram_id FROM users WHERE telegram_id = ?
        """, (telegram_id,)).fetchone()

        if user is None:
            raise ValueError("Student is not registered.")

        existing = connection.execute("""
            SELECT id, status
            FROM course_enrollments
            WHERE telegram_id = ? AND course_id = ?
        """, (telegram_id, course_id)).fetchone()

        if existing is not None:
            if existing["status"] == "paused":
                connection.execute("""
                    UPDATE course_enrollments
                    SET status = 'enrolled', completed_at = NULL
                    WHERE id = ?
                """, (existing["id"],))
                connection.commit()
                return True
            return False

        connection.execute("""
            INSERT INTO course_enrollments (telegram_id, course_id)
            VALUES (?, ?)
        """, (telegram_id, course_id))
        connection.commit()
        return True


def get_enrolled_courses(telegram_id, language="en"):
    """Return a student's enrolled courses and their current status."""
    _validate_language(language)

    with db.get_connection() as connection:
        rows = connection.execute("""
            SELECT c.*, e.status AS enrollment_status,
                   e.enrolled_at, e.completed_at
            FROM course_enrollments e
            JOIN courses c ON c.id = e.course_id
            WHERE e.telegram_id = ?
            ORDER BY e.enrolled_at DESC, e.id DESC
        """, (telegram_id,)).fetchall()

        results = []
        for row in rows:
            item = dict(row)
            item["translations"] = _load_translations(
                connection, "course_translations", "course_id", item["id"]
            )
            translation = _translated(item, language)
            item["title"] = translation.get("title", item["slug"])
            item["description"] = translation.get("description", "")
            results.append(item)

        return results


def get_course_curriculum(course_id, language="en", telegram_id=None):
    """Return published modules and lessons for a published course.

    If telegram_id is supplied, include that student's lesson progress.
    """
    _validate_language(language)

    with db.get_connection() as connection:
        course = connection.execute("""
            SELECT id, slug, level
            FROM courses
            WHERE id = ? AND status = 'published'
        """, (course_id,)).fetchone()

        if course is None:
            return None

        if telegram_id is not None:
            enrollment = connection.execute("""
                SELECT id
                FROM course_enrollments
                WHERE telegram_id = ?
                  AND course_id = ?
                  AND status IN ('enrolled', 'completed')
            """, (telegram_id, course_id)).fetchone()

            if enrollment is None:
                raise PermissionError("Student is not enrolled in this course.")

        modules = connection.execute("""
            SELECT *
            FROM course_modules
            WHERE course_id = ? AND is_published = 1
            ORDER BY sort_order, id
        """, (course_id,)).fetchall()

        result = {"course": dict(course), "modules": []}

        for module_row in modules:
            module = dict(module_row)
            module["translations"] = _load_translations(
                connection, "module_translations", "module_id", module["id"]
            )
            module_translation = _translated(module, language)
            module["title"] = module_translation.get("title", module["slug"])
            module["description"] = module_translation.get("description", "")
            module["lessons"] = []

            lessons = connection.execute("""
                SELECT *
                FROM course_lessons
                WHERE module_id = ? AND is_published = 1
                ORDER BY sort_order, id
            """, (module["id"],)).fetchall()

            for lesson_row in lessons:
                lesson = dict(lesson_row)
                lesson["translations"] = _load_translations(
                    connection, "lesson_translations", "lesson_id", lesson["id"]
                )
                lesson_translation = _translated(lesson, language)
                lesson["title"] = lesson_translation.get(
                    "title", lesson["slug"]
                )

                if telegram_id is not None:
                    progress = connection.execute("""
                        SELECT status, started_at, completed_at, updated_at
                        FROM lesson_progress
                        WHERE telegram_id = ? AND lesson_id = ?
                    """, (telegram_id, lesson["id"])).fetchone()
                    lesson["progress"] = (
                        dict(progress) if progress else None
                    )

                module["lessons"].append(lesson)

            result["modules"].append(module)

        return result


def get_lesson(lesson_id, telegram_id, language="en"):
    """Return lesson content only to a student enrolled in its course."""
    _validate_language(language)

    with db.get_connection() as connection:
        row = connection.execute("""
            SELECT
                l.*,
                m.course_id,
                c.slug AS course_slug
            FROM course_lessons l
            JOIN course_modules m ON m.id = l.module_id
            JOIN courses c ON c.id = m.course_id
            JOIN course_enrollments e ON e.course_id = c.id
            WHERE l.id = ?
              AND e.telegram_id = ?
              AND e.status IN ('enrolled', 'completed')
              AND l.is_published = 1
              AND m.is_published = 1
              AND c.status = 'published'
        """, (lesson_id, telegram_id)).fetchone()

        if row is None:
            return None

        lesson = dict(row)
        lesson["translations"] = _load_translations(
            connection, "lesson_translations", "lesson_id", lesson_id
        )
        translation = _translated(lesson, language)

        lesson["title"] = translation.get("title", lesson["slug"])
        lesson["content"] = translation.get("content", "")
        return lesson


def update_lesson_progress(telegram_id, lesson_id, status="in_progress"):
    """Create or update a student's progress on an enrolled course lesson."""
    if status not in {"in_progress", "completed"}:
        raise ValueError("Invalid lesson progress status.")

    now = db.current_timestamp()

    with db.get_connection() as connection:
        lesson = connection.execute("""
            SELECT l.id
            FROM course_lessons l
            JOIN course_modules m ON m.id = l.module_id
            JOIN courses c ON c.id = m.course_id
            JOIN course_enrollments e ON e.course_id = c.id
            WHERE l.id = ?
              AND e.telegram_id = ?
              AND e.status IN ('enrolled', 'completed')
              AND l.is_published = 1
              AND m.is_published = 1
              AND c.status = 'published'
        """, (lesson_id, telegram_id)).fetchone()

        if lesson is None:
            raise PermissionError(
                "Lesson is unavailable or the student is not enrolled."
            )

        completed_at = now if status == "completed" else None

        connection.execute("""
            INSERT INTO lesson_progress (
                telegram_id, lesson_id, status,
                started_at, completed_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id, lesson_id)
            DO UPDATE SET
                status = excluded.status,
                completed_at = excluded.completed_at,
                updated_at = excluded.updated_at
        """, (
            telegram_id, lesson_id, status,
            now, completed_at, now,
        ))

        connection.commit()

        return {
            "telegram_id": telegram_id,
            "lesson_id": lesson_id,
            "status": status,
            "completed_at": completed_at,
        }


def get_course_progress(telegram_id, course_id):
    """Calculate completion using published lessons only."""
    with db.get_connection() as connection:
        enrollment = connection.execute("""
            SELECT status
            FROM course_enrollments
            WHERE telegram_id = ? AND course_id = ?
        """, (telegram_id, course_id)).fetchone()

        if enrollment is None:
            return None

        totals = connection.execute("""
            SELECT
                COUNT(l.id) AS total_lessons,
                SUM(
                    CASE WHEN p.status = 'completed' THEN 1 ELSE 0 END
                ) AS completed_lessons
            FROM course_modules m
            JOIN course_lessons l ON l.module_id = m.id
            LEFT JOIN lesson_progress p
                ON p.lesson_id = l.id
               AND p.telegram_id = ?
            WHERE m.course_id = ?
              AND m.is_published = 1
              AND l.is_published = 1
        """, (telegram_id, course_id)).fetchone()

        total = totals["total_lessons"] or 0
        completed = totals["completed_lessons"] or 0
        percentage = round(completed * 100 / total, 1) if total else 0.0

        return {
            "course_id": course_id,
            "enrollment_status": enrollment["status"],
            "total_lessons": total,
            "completed_lessons": completed,
            "remaining_lessons": total - completed,
            "completion_percent": percentage,
        }


def submit_assignment(telegram_id, assignment_id, answer_text):
    """Save a student's submission for a published assignment."""
    if not isinstance(answer_text, str) or not answer_text.strip():
        raise ValueError("Assignment answer cannot be empty.")

    with db.get_connection() as connection:
        assignment = connection.execute("""
            SELECT a.id
            FROM assignments a
            JOIN course_lessons l ON l.id = a.lesson_id
            JOIN course_modules m ON m.id = l.module_id
            JOIN courses c ON c.id = m.course_id
            JOIN course_enrollments e ON e.course_id = c.id
            WHERE a.id = ?
              AND e.telegram_id = ?
              AND e.status IN ('enrolled', 'completed')
              AND a.is_published = 1
              AND l.is_published = 1
              AND m.is_published = 1
              AND c.status = 'published'
        """, (assignment_id, telegram_id)).fetchone()

        if assignment is None:
            raise PermissionError(
                "Assignment is unavailable or the student is not enrolled."
            )

        cursor = connection.execute("""
            INSERT INTO assignment_submissions (
                assignment_id, telegram_id, answer_text
            )
            VALUES (?, ?, ?)
        """, (assignment_id, telegram_id, answer_text.strip()))

        connection.commit()
        return cursor.lastrowid
