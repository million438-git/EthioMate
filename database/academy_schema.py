"""Database schema for the EthioMate Professional Skills Academy."""


def create_academy_tables(connection):
    """Create Academy tables and indexes without altering existing tables."""

    statements = [
        """
        CREATE TABLE IF NOT EXISTS skill_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            name_en TEXT NOT NULL,
            name_am TEXT NOT NULL,
            name_om TEXT NOT NULL,
            description_en TEXT NOT NULL DEFAULT '',
            description_am TEXT NOT NULL DEFAULT '',
            description_om TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1
                CHECK(is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            level TEXT NOT NULL
                CHECK(level IN ('beginner', 'intermediate', 'advanced')),
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK(status IN ('draft', 'published', 'archived')),
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id)
                REFERENCES skill_categories(id)
                ON DELETE RESTRICT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS course_translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            language TEXT NOT NULL
                CHECK(language IN ('en', 'am', 'om')),
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            UNIQUE(course_id, language),
            FOREIGN KEY (course_id)
                REFERENCES courses(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS course_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            slug TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_published INTEGER NOT NULL DEFAULT 0
                CHECK(is_published IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(course_id, slug),
            UNIQUE(course_id, sort_order),
            FOREIGN KEY (course_id)
                REFERENCES courses(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS module_translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            language TEXT NOT NULL
                CHECK(language IN ('en', 'am', 'om')),
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            UNIQUE(module_id, language),
            FOREIGN KEY (module_id)
                REFERENCES course_modules(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS course_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            slug TEXT NOT NULL,
            lesson_type TEXT NOT NULL DEFAULT 'lesson'
                CHECK(lesson_type IN ('lesson', 'exercise', 'project')),
            sort_order INTEGER NOT NULL DEFAULT 0,
            estimated_minutes INTEGER NOT NULL DEFAULT 15
                CHECK(estimated_minutes > 0),
            is_published INTEGER NOT NULL DEFAULT 0
                CHECK(is_published IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(module_id, slug),
            UNIQUE(module_id, sort_order),
            FOREIGN KEY (module_id)
                REFERENCES course_modules(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS lesson_translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            language TEXT NOT NULL
                CHECK(language IN ('en', 'am', 'om')),
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            UNIQUE(lesson_id, language),
            FOREIGN KEY (lesson_id)
                REFERENCES course_lessons(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS course_enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'enrolled'
                CHECK(status IN ('enrolled', 'completed', 'paused')),
            enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            UNIQUE(telegram_id, course_id),
            FOREIGN KEY (telegram_id)
                REFERENCES users(telegram_id)
                ON DELETE CASCADE,
            FOREIGN KEY (course_id)
                REFERENCES courses(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS lesson_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            lesson_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'in_progress'
                CHECK(status IN ('in_progress', 'completed')),
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(telegram_id, lesson_id),
            FOREIGN KEY (telegram_id)
                REFERENCES users(telegram_id)
                ON DELETE CASCADE,
            FOREIGN KEY (lesson_id)
                REFERENCES course_lessons(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            slug TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            max_score REAL NOT NULL DEFAULT 100
                CHECK(max_score > 0),
            is_published INTEGER NOT NULL DEFAULT 0
                CHECK(is_published IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(lesson_id, slug),
            FOREIGN KEY (lesson_id)
                REFERENCES course_lessons(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS assignment_translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            language TEXT NOT NULL
                CHECK(language IN ('en', 'am', 'om')),
            title TEXT NOT NULL,
            instructions TEXT NOT NULL,
            UNIQUE(assignment_id, language),
            FOREIGN KEY (assignment_id)
                REFERENCES assignments(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS assignment_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            telegram_id INTEGER NOT NULL,
            answer_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'submitted'
                CHECK(status IN ('submitted', 'reviewed', 'returned')),
            score REAL,
            feedback TEXT,
            submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT,
            reviewed_by INTEGER,
            FOREIGN KEY (assignment_id)
                REFERENCES assignments(id)
                ON DELETE CASCADE,
            FOREIGN KEY (telegram_id)
                REFERENCES users(telegram_id)
                ON DELETE CASCADE
        )
        """,
    ]

    indexes = [
        """
        CREATE INDEX IF NOT EXISTS idx_courses_category_status
        ON courses(category_id, status, sort_order)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_modules_course_order
        ON course_modules(course_id, sort_order)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_lessons_module_order
        ON course_lessons(module_id, sort_order)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_enrollments_user_status
        ON course_enrollments(telegram_id, status)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_enrollments_course
        ON course_enrollments(course_id, status)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_lesson_progress_user_status
        ON lesson_progress(telegram_id, status)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_assignments_lesson
        ON assignments(lesson_id, sort_order)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_submissions_assignment_status
        ON assignment_submissions(assignment_id, status, submitted_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_submissions_student
        ON assignment_submissions(telegram_id, submitted_at)
        """,
    ]

    for statement in statements:
        connection.execute(statement)

    for statement in indexes:
        connection.execute(statement)
