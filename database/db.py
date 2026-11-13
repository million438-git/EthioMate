from contextlib import contextmanager
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from database.academy_schema import create_academy_tables


DATABASE_PATH = Path(__file__).resolve().parent / "ethiomate.sqlite3"


@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")

    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def current_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db():
    """Create the database and users table if they do not exist."""

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT 'en'
                    CHECK(language IN ('am', 'en', 'om')),
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_last_seen
            ON users(last_seen)
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                total_questions INTEGER NOT NULL,
                correct_answers INTEGER NOT NULL,
                score_percent REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (telegram_id)
                    REFERENCES users(telegram_id)
                    ON DELETE CASCADE
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_quiz_results_user_created
            ON quiz_results(telegram_id, created_at)
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS feedback_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT NOT NULL DEFAULT '',
                submission_type TEXT NOT NULL
                    CHECK(submission_type IN ('feedback', 'report', 'suggest', 'request')),
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'reviewed')),
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                reviewed_by INTEGER,
                FOREIGN KEY (telegram_id)
                    REFERENCES users(telegram_id)
                    ON DELETE CASCADE
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_status_created
            ON feedback_submissions(status, created_at)
        """)

        create_academy_tables(connection)

        connection.commit()


def register_user(telegram_id, username=None, first_name=""):
    """Register a user or update their existing profile."""

    now = current_timestamp()

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO users (
                telegram_id,
                username,
                first_name,
                language,
                created_at,
                last_seen
            )
            VALUES (?, ?, ?, 'en', ?, ?)

            ON CONFLICT(telegram_id)
            DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_seen = excluded.last_seen
        """, (
            telegram_id,
            username,
            first_name or "",
            now,
            now
        ))

        connection.commit()


def set_language(telegram_id, language):
    """Save a user's language preference."""

    if language not in ("am", "en", "om"):
        raise ValueError("Unsupported language")

    with get_connection() as connection:
        connection.execute("""
            UPDATE users
            SET language = ?,
                last_seen = ?
            WHERE telegram_id = ?
        """, (
            language,
            current_timestamp(),
            telegram_id
        ))

        connection.commit()


def get_language(telegram_id):
    """Retrieve the saved language preference."""

    with get_connection() as connection:
        user = connection.execute("""
            SELECT language
            FROM users
            WHERE telegram_id = ?
        """, (telegram_id,)).fetchone()

        return user["language"] if user else "en"


def get_user(telegram_id):
    """Retrieve a complete user profile."""

    with get_connection() as connection:
        user = connection.execute("""
            SELECT *
            FROM users
            WHERE telegram_id = ?
        """, (telegram_id,)).fetchone()

        return dict(user) if user else None


def get_total_users():
    """Return the total registered users."""

    with get_connection() as connection:
        result = connection.execute("""
            SELECT COUNT(*) AS total
            FROM users
        """).fetchone()

        return result["total"]



def save_quiz_result(
    telegram_id,
    subject,
    topic,
    difficulty,
    total_questions,
    correct_answers,
):
    """Save a completed quiz without modifying the user's profile."""

    if total_questions < 1:
        raise ValueError("A quiz must contain at least one question.")

    if not 0 <= correct_answers <= total_questions:
        raise ValueError("Invalid quiz score.")

    score_percent = round((correct_answers / total_questions) * 100, 2)

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO quiz_results (
                telegram_id,
                subject,
                topic,
                difficulty,
                total_questions,
                correct_answers,
                score_percent,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            telegram_id,
            subject,
            topic,
            difficulty,
            total_questions,
            correct_answers,
            score_percent,
            current_timestamp(),
        ))
        connection.commit()
        return cursor.lastrowid


def get_quiz_history(telegram_id, limit=10):
    """Return the most recent quiz results for a user."""

    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM quiz_results
            WHERE telegram_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """, (telegram_id, limit)).fetchall()

        return [dict(row) for row in rows]



def save_feedback(telegram_id, username, first_name, submission_type, content):
    """Persist a user feedback, report, suggestion or feature request."""
    allowed = {"feedback", "report", "suggest", "request"}
    if submission_type not in allowed:
        raise ValueError("Unsupported submission type")

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO feedback_submissions (
                telegram_id, username, first_name,
                submission_type, content, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            telegram_id, username, first_name or "",
            submission_type, content, current_timestamp()
        ))
        connection.commit()
        return cursor.lastrowid


def get_open_feedback(limit=20):
    """Return pending submissions for authorized admin review."""
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM feedback_submissions
            WHERE status = 'pending'
            ORDER BY created_at ASC, id ASC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]


def mark_feedback_reviewed(submission_id, admin_id):
    """Mark a pending submission as reviewed."""
    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE feedback_submissions
            SET status = 'reviewed',
                reviewed_at = ?,
                reviewed_by = ?
            WHERE id = ? AND status = 'pending'
        """, (current_timestamp(), admin_id, submission_id))
        connection.commit()
        return cursor.rowcount == 1
