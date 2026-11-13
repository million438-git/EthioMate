from database.db import get_connection


def get_dashboard_stats():
    with get_connection() as connection:
        users = connection.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN date(created_at) = date('now') THEN 1 ELSE 0 END) AS today,
                SUM(CASE WHEN datetime(last_seen) >= datetime('now', '-7 days') THEN 1 ELSE 0 END) AS active_week
            FROM users
        """).fetchone()

        quizzes = connection.execute("""
            SELECT
                COUNT(*) AS attempts,
                COALESCE(SUM(total_questions), 0) AS questions,
                COALESCE(SUM(correct_answers), 0) AS correct,
                COALESCE(AVG(score_percent), 0) AS average_score
            FROM quiz_results
        """).fetchone()

        feedback = connection.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending
            FROM feedback_submissions
        """).fetchone()

    return {
        "total_users": users["total"] or 0,
        "new_users_today": users["today"] or 0,
        "active_users_week": users["active_week"] or 0,
        "quiz_attempts": quizzes["attempts"] or 0,
        "questions_answered": quizzes["questions"] or 0,
        "correct_answers": quizzes["correct"] or 0,
        "average_score": round(quizzes["average_score"] or 0, 1),
        "feedback_total": feedback["total"] or 0,
        "pending_feedback": feedback["pending"] or 0,
    }


def search_users(search=""):
    with get_connection() as connection:
        if search:
            term = f"%{search.strip()}%"
            rows = connection.execute("""
                SELECT telegram_id, username, first_name, language,
                       created_at, last_seen
                FROM users
                WHERE CAST(telegram_id AS TEXT) LIKE ?
                   OR username LIKE ?
                   OR first_name LIKE ?
                ORDER BY last_seen DESC
                LIMIT 100
            """, (term, term, term)).fetchall()
        else:
            rows = connection.execute("""
                SELECT telegram_id, username, first_name, language,
                       created_at, last_seen
                FROM users
                ORDER BY last_seen DESC
                LIMIT 100
            """).fetchall()

    return [dict(row) for row in rows]


def get_feedback(status="pending"):
    if status not in ("pending", "reviewed", "all"):
        status = "pending"

    with get_connection() as connection:
        if status == "all":
            rows = connection.execute("""
                SELECT f.*, u.language
                FROM feedback_submissions f
                LEFT JOIN users u ON u.telegram_id = f.telegram_id
                ORDER BY f.created_at DESC
                LIMIT 200
            """).fetchall()
        else:
            rows = connection.execute("""
                SELECT f.*, u.language
                FROM feedback_submissions f
                LEFT JOIN users u ON u.telegram_id = f.telegram_id
                WHERE f.status = ?
                ORDER BY f.created_at DESC
                LIMIT 200
            """, (status,)).fetchall()

    return [dict(row) for row in rows]


def get_recent_quizzes():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT q.*, u.first_name, u.username
            FROM quiz_results q
            LEFT JOIN users u ON u.telegram_id = q.telegram_id
            ORDER BY q.created_at DESC, q.id DESC
            LIMIT 50
        """).fetchall()

    return [dict(row) for row in rows]


def get_system_status():
    import os

    with get_connection() as connection:
        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        journal = connection.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0]

    return {
        "database_integrity": integrity,
        "database_journal_mode": journal,
        "telegram_configured": bool(os.getenv("BOT_TOKEN")),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
    }



def get_student_profile(telegram_id):
    """Return a student's profile, quiz statistics and recent submissions."""

    with get_connection() as connection:
        user = connection.execute("""
            SELECT telegram_id, username, first_name, language,
                   created_at, last_seen
            FROM users
            WHERE telegram_id = ?
        """, (telegram_id,)).fetchone()

        if user is None:
            return None

        quiz_stats = connection.execute("""
            SELECT
                COUNT(*) AS attempts,
                COALESCE(SUM(total_questions), 0) AS questions_answered,
                COALESCE(SUM(correct_answers), 0) AS correct_answers,
                COALESCE(AVG(score_percent), 0) AS average_score
            FROM quiz_results
            WHERE telegram_id = ?
        """, (telegram_id,)).fetchone()

        quizzes = connection.execute("""
            SELECT id, subject, topic, difficulty,
                   total_questions, correct_answers,
                   score_percent, created_at
            FROM quiz_results
            WHERE telegram_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 20
        """, (telegram_id,)).fetchall()

        feedback = connection.execute("""
            SELECT id, submission_type, content, status,
                   created_at, reviewed_at
            FROM feedback_submissions
            WHERE telegram_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 20
        """, (telegram_id,)).fetchall()

        feedback_count = connection.execute("""
            SELECT COUNT(*)
            FROM feedback_submissions
            WHERE telegram_id = ?
        """, (telegram_id,)).fetchone()[0]

    return {
        "user": dict(user),
        "quiz_stats": {
            "attempts": quiz_stats["attempts"] or 0,
            "questions_answered": quiz_stats["questions_answered"] or 0,
            "correct_answers": quiz_stats["correct_answers"] or 0,
            "average_score": round(quiz_stats["average_score"] or 0, 1),
        },
        "quizzes": [dict(row) for row in quizzes],
        "feedback": [dict(row) for row in feedback],
        "feedback_count": feedback_count,
    }
