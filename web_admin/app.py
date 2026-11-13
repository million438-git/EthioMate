import hashlib
import hmac
import os
import secrets
import sqlite3
from urllib.parse import quote
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates

from database.db import mark_feedback_reviewed
from web_admin import academy_queries
from web_admin.queries import (
    get_dashboard_stats,
    search_users,
    get_feedback,
    get_recent_quizzes,
    get_system_status,
    get_student_profile,
)

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

USERNAME = os.getenv("ADMIN_WEB_USERNAME", "")
PASSWORD_HASH = os.getenv("ADMIN_WEB_PASSWORD_HASH", "")
SECRET_KEY = os.getenv("ADMIN_WEB_SECRET_KEY", "")
ADMIN_IDS = os.getenv("ADMIN_IDS", "")
ADMIN_TELEGRAM_ID = next(
    (int(value.strip()) for value in ADMIN_IDS.split(",")
     if value.strip().isdigit()),
    None,
)

if not USERNAME or not PASSWORD_HASH or not SECRET_KEY:
    raise RuntimeError(
        "Web admin credentials are missing. Configure them in .env first."
    )

if ADMIN_TELEGRAM_ID is None:
    raise RuntimeError("No Telegram ADMIN_IDS are configured.")

app = FastAPI(
    title="EthioMate Administration",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="ethiomate_admin_session",
    max_age=8 * 60 * 60,
    same_site="strict",
    https_only=False,
)

app.mount(
    "/static",
    StaticFiles(directory=str(ROOT / "web_admin" / "static")),
    name="static",
)

templates = Jinja2Templates(
    directory=str(ROOT / "web_admin" / "templates")
)


def verify_password(password):
    try:
        algorithm, rounds, salt, expected = PASSWORD_HASH.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False

        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode("utf-8"),
            int(rounds),
        ).hex()

        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def require_admin(request: Request):
    if request.session.get("admin_authenticated") is not True:
        raise HTTPException(
            status_code=303,
            headers={"Location": "/login"},
        )


def csrf_token(request: Request):
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def verify_csrf(request: Request, submitted_token: str):
    expected = request.session.get("csrf_token", "")
    if not expected or not hmac.compare_digest(expected, submitted_token):
        raise HTTPException(status_code=403, detail="Invalid security token.")


def page(request, template, **context):
    return templates.TemplateResponse(
        request=request,
        name=template,
        context={"request": request, **context},
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("admin_authenticated") is True:
        return RedirectResponse("/", status_code=303)

    return page(
        request,
        "login.html",
        csrf=csrf_token(request),
        error=None,
    )


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf: str = Form(...),
):
    verify_csrf(request, csrf)

    if (
        hmac.compare_digest(username, USERNAME)
        and verify_password(password)
    ):
        request.session.clear()
        request.session["admin_authenticated"] = True
        request.session["csrf_token"] = secrets.token_urlsafe(32)
        return RedirectResponse("/", status_code=303)

    return page(
        request,
        "login.html",
        csrf=csrf_token(request),
        error="Invalid username or password.",
    )


@app.post("/logout")
async def logout(request: Request, csrf: str = Form(...)):
    require_admin(request)
    verify_csrf(request, csrf)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, _: None = Depends(require_admin)):
    return page(
        request,
        "dashboard.html",
        stats=get_dashboard_stats(),
        csrf=csrf_token(request),
        active="overview",
    )


@app.get("/students", response_class=HTMLResponse)
async def students(
    request: Request,
    q: str = "",
    _: None = Depends(require_admin),
):
    return page(
        request,
        "students.html",
        users=search_users(q[:100]),
        search=q,
        csrf=csrf_token(request),
        active="students",
    )



@app.get("/students/{telegram_id}", response_class=HTMLResponse)
async def student_detail(
    request: Request,
    telegram_id: int,
    _: None = Depends(require_admin),
):
    profile = get_student_profile(telegram_id)

    if profile is None:
        raise HTTPException(status_code=404, detail="Student not found.")

    return page(
        request,
        "student_detail.html",
        profile=profile,
        csrf=csrf_token(request),
        active="students",
    )


@app.get("/feedback", response_class=HTMLResponse)
async def feedback(
    request: Request,
    status: str = "pending",
    _: None = Depends(require_admin),
):
    if status not in ("pending", "reviewed", "all"):
        status = "pending"

    return page(
        request,
        "feedback.html",
        submissions=get_feedback(status),
        selected_status=status,
        csrf=csrf_token(request),
        active="feedback",
    )


@app.post("/feedback/{submission_id}/review")
async def review_submission(
    request: Request,
    submission_id: int,
    csrf: str = Form(...),
    _: None = Depends(require_admin),
):
    verify_csrf(request, csrf)

    updated = mark_feedback_reviewed(submission_id, ADMIN_TELEGRAM_ID)
    destination = "/feedback?status=pending"

    if not updated:
        destination = "/feedback?status=all"

    return RedirectResponse(destination, status_code=303)


@app.get("/quizzes", response_class=HTMLResponse)
async def quizzes(request: Request, _: None = Depends(require_admin)):
    return page(
        request,
        "quizzes.html",
        quizzes=get_recent_quizzes(),
        csrf=csrf_token(request),
        active="quizzes",
    )


@app.get("/system", response_class=HTMLResponse)
async def system(request: Request, _: None = Depends(require_admin)):
    return page(
        request,
        "system.html",
        status=get_system_status(),
        csrf=csrf_token(request),
        active="system",
    )


# ---------------------------------------------------------------------
# Academy administration
# ---------------------------------------------------------------------

@app.get("/academy", response_class=HTMLResponse)
async def academy_dashboard(
    request: Request,
    status: str = "",
    _: None = Depends(require_admin),
):
    if status not in ("", "draft", "published", "archived"):
        status = ""

    return page(
        request,
        "academy.html",
        overview=academy_queries.get_academy_overview(),
        courses=academy_queries.list_admin_courses(status or None),
        selected_status=status,
        csrf=csrf_token(request),
        active="academy",
        error=request.query_params.get("error"),
        success=request.query_params.get("success"),
    )


@app.get("/academy/categories", response_class=HTMLResponse)
async def academy_categories_page(
    request: Request,
    _: None = Depends(require_admin),
):
    return page(
        request,
        "academy_categories.html",
        categories=academy_queries.list_admin_categories(),
        csrf=csrf_token(request),
        active="academy",
        error=request.query_params.get("error"),
        success=request.query_params.get("success"),
    )


@app.post("/academy/categories")
async def academy_create_category(
    request: Request,
    csrf: str = Form(...),
    slug: str = Form(...),
    name_en: str = Form(...),
    name_am: str = Form(...),
    name_om: str = Form(...),
    description_en: str = Form(""),
    description_am: str = Form(""),
    description_om: str = Form(""),
    _: None = Depends(require_admin),
):
    verify_csrf(request, csrf)

    try:
        academy_queries.create_category(
            slug=slug,
            name_en=name_en,
            name_am=name_am,
            name_om=name_om,
            description_en=description_en,
            description_am=description_am,
            description_om=description_om,
        )
    except ValueError as exc:
        return RedirectResponse(
            f"/academy/categories?error={quote(str(exc))}",
            status_code=303,
        )
    except sqlite3.IntegrityError:
        return RedirectResponse(
            "/academy/categories?error=That+category+slug+already+exists.",
            status_code=303,
        )

    return RedirectResponse(
        "/academy/categories?success=Category+created+successfully.",
        status_code=303,
    )


@app.get("/academy/courses/new", response_class=HTMLResponse)
async def academy_new_course_page(
    request: Request,
    _: None = Depends(require_admin),
):
    return page(
        request,
        "academy_course_form.html",
        course=None,
        categories=[
            category
            for category in academy_queries.list_admin_categories()
            if category["is_active"]
        ],
        csrf=csrf_token(request),
        active="academy",
        error=None,
    )


@app.post("/academy/courses")
async def academy_create_course(
    request: Request,
    csrf: str = Form(...),
    category_id: int = Form(...),
    slug: str = Form(...),
    level: str = Form(...),
    sort_order: int = Form(0),
    title_en: str = Form(...),
    description_en: str = Form(""),
    title_am: str = Form(""),
    description_am: str = Form(""),
    title_om: str = Form(""),
    description_om: str = Form(""),
    _: None = Depends(require_admin),
):
    verify_csrf(request, csrf)

    translations = {
        "en": {"title": title_en, "description": description_en},
        "am": {"title": title_am, "description": description_am},
        "om": {"title": title_om, "description": description_om},
    }

    try:
        course_id = academy_queries.create_course(
            category_id=category_id,
            slug=slug,
            level=level,
            translations=translations,
            sort_order=sort_order,
        )
    except ValueError as exc:
        return RedirectResponse(
            f"/academy/courses/new?error={quote(str(exc))}",
            status_code=303,
        )
    except sqlite3.IntegrityError:
        return RedirectResponse(
            "/academy/courses/new?error=The+course+slug+or+sort+order+already+exists.",
            status_code=303,
        )

    return RedirectResponse(
        f"/academy/courses/{course_id}/edit?success=Course+created+as+a+draft.",
        status_code=303,
    )


@app.get(
    "/academy/courses/{course_id}/edit",
    response_class=HTMLResponse,
)
async def academy_edit_course_page(
    request: Request,
    course_id: int,
    _: None = Depends(require_admin),
):
    course = academy_queries.get_admin_course(course_id)

    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")

    return page(
        request,
        "academy_course_form.html",
        course=course,
        categories=[
            category
            for category in academy_queries.list_admin_categories()
            if category["is_active"]
            or category["id"] == course["category_id"]
        ],
        csrf=csrf_token(request),
        active="academy",
        error=request.query_params.get("error"),
        success=request.query_params.get("success"),
    )


@app.post("/academy/courses/{course_id}/edit")
async def academy_update_course(
    request: Request,
    course_id: int,
    csrf: str = Form(...),
    category_id: int = Form(...),
    slug: str = Form(...),
    level: str = Form(...),
    sort_order: int = Form(0),
    title_en: str = Form(...),
    description_en: str = Form(""),
    title_am: str = Form(""),
    description_am: str = Form(""),
    title_om: str = Form(""),
    description_om: str = Form(""),
    _: None = Depends(require_admin),
):
    verify_csrf(request, csrf)

    translations = {
        "en": {"title": title_en, "description": description_en},
        "am": {"title": title_am, "description": description_am},
        "om": {"title": title_om, "description": description_om},
    }

    try:
        updated = academy_queries.update_course(
            course_id=course_id,
            category_id=category_id,
            slug=slug,
            level=level,
            translations=translations,
            sort_order=sort_order,
        )
    except ValueError as exc:
        return RedirectResponse(
            f"/academy/courses/{course_id}/edit?error={quote(str(exc))}",
            status_code=303,
        )
    except sqlite3.IntegrityError:
        return RedirectResponse(
            f"/academy/courses/{course_id}/edit?error=The+course+slug+or+sort+order+already+exists.",
            status_code=303,
        )

    if not updated:
        raise HTTPException(status_code=404, detail="Course not found.")

    return RedirectResponse(
        f"/academy/courses/{course_id}/edit?success=Course+details+saved.",
        status_code=303,
    )


@app.post("/academy/courses/{course_id}/status")
async def academy_change_course_status(
    request: Request,
    course_id: int,
    status: str = Form(...),
    csrf: str = Form(...),
    _: None = Depends(require_admin),
):
    verify_csrf(request, csrf)

    try:
        updated = academy_queries.set_course_status(course_id, status)
    except ValueError as exc:
        return RedirectResponse(
            f"/academy?error={quote(str(exc))}",
            status_code=303,
        )

    if not updated:
        raise HTTPException(status_code=404, detail="Course not found.")

    return RedirectResponse(
        "/academy?success=Course+status+updated.",
        status_code=303,
    )


# ---------------------------------------------------------------------
# Academy curriculum management
# ---------------------------------------------------------------------

@app.get(
    "/academy/courses/{course_id}/curriculum",
    response_class=HTMLResponse,
)
async def academy_curriculum_page(
    request: Request,
    course_id: int,
    _: None = Depends(require_admin),
):
    course = academy_queries.get_admin_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")

    modules = academy_queries.list_admin_modules(course_id) or []

    return page(
        request,
        "academy_curriculum.html",
        course=course,
        modules=modules,
        csrf=csrf_token(request),
        active="academy",
        error=request.query_params.get("error"),
        success=request.query_params.get("success"),
    )


@app.post("/academy/courses/{course_id}/modules")
async def academy_create_module(
    request: Request,
    course_id: int,
    csrf: str = Form(...),
    slug: str = Form(...),
    sort_order: int = Form(0),
    title_en: str = Form(...),
    description_en: str = Form(""),
    title_am: str = Form(""),
    description_am: str = Form(""),
    title_om: str = Form(""),
    description_om: str = Form(""),
    _: None = Depends(require_admin),
):
    verify_csrf(request, csrf)
    translations = {
        "en": {"title": title_en, "description": description_en},
        "am": {"title": title_am, "description": description_am},
        "om": {"title": title_om, "description": description_om},
    }

    try:
        academy_queries.create_module(
            course_id, slug, translations, sort_order
        )
    except ValueError as exc:
        return RedirectResponse(
            f"/academy/courses/{course_id}/curriculum?error={quote(str(exc))}",
            status_code=303,
        )
    except sqlite3.IntegrityError:
        return RedirectResponse(
            f"/academy/courses/{course_id}/curriculum?error=Module+slug+or+order+already+exists.",
            status_code=303,
        )

    return RedirectResponse(
        f"/academy/courses/{course_id}/curriculum?success=Module+created+as+a+draft.",
        status_code=303,
    )


@app.post("/academy/modules/{module_id}/edit")
async def academy_update_module(
    request: Request,
    module_id: int,
    csrf: str = Form(...),
    slug: str = Form(...),
    sort_order: int = Form(...),
    title_en: str = Form(...),
    description_en: str = Form(""),
    title_am: str = Form(""),
    description_am: str = Form(""),
    title_om: str = Form(""),
    description_om: str = Form(""),
    _: None = Depends(require_admin),
):
    verify_csrf(request, csrf)
    module = academy_queries.get_admin_module(module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found.")

    translations = {
        "en": {"title": title_en, "description": description_en},
        "am": {"title": title_am, "description": description_am},
        "om": {"title": title_om, "description": description_om},
    }

    try:
        academy_queries.update_module(
            module_id, slug, translations, sort_order
        )
    except ValueError as exc:
        return RedirectResponse(
            f"/academy/courses/{module['course_id']}/curriculum?error={quote(str(exc))}",
            status_code=303,
        )
    except sqlite3.IntegrityError:
        return RedirectResponse(
            f"/academy/courses/{module['course_id']}/curriculum?error=Module+slug+or+order+already+exists.",
            status_code=303,
        )

    return RedirectResponse(
        f"/academy/courses/{module['course_id']}/curriculum?success=Module+details+saved.",
        status_code=303,
    )


@app.post("/academy/modules/{module_id}/status")
async def academy_change_module_status(
    request: Request,
    module_id: int,
    csrf: str = Form(...),
    is_published: int = Form(...),
    _: None = Depends(require_admin),
):
    verify_csrf(request, csrf)
    module = academy_queries.get_admin_module(module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found.")

    try:
        academy_queries.set_module_status(module_id, is_published)
    except ValueError as exc:
        return RedirectResponse(
            f"/academy/courses/{module['course_id']}/curriculum?error={quote(str(exc))}",
            status_code=303,
        )

    return RedirectResponse(
        f"/academy/courses/{module['course_id']}/curriculum?success=Module+publication+updated.",
        status_code=303,
    )


@app.post("/academy/modules/{module_id}/lessons")
async def academy_create_lesson(
    request: Request,
    module_id: int,
    csrf: str = Form(...),
    slug: str = Form(...),
    lesson_type: str = Form(...),
    sort_order: int = Form(0),
    estimated_minutes: int = Form(15),
    title_en: str = Form(...),
    content_en: str = Form(...),
    title_am: str = Form(""),
    content_am: str = Form(""),
    title_om: str = Form(""),
    content_om: str = Form(""),
    _: None = Depends(require_admin),
):
    verify_csrf(request, csrf)
    module = academy_queries.get_admin_module(module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found.")

    translations = {
        "en": {"title": title_en, "content": content_en},
        "am": {"title": title_am, "content": content_am},
        "om": {"title": title_om, "content": content_om},
    }

    try:
        lesson_id = academy_queries.create_lesson(
            module_id=module_id,
            slug=slug,
            lesson_type=lesson_type,
            translations=translations,
            sort_order=sort_order,
            estimated_minutes=estimated_minutes,
        )
    except ValueError as exc:
        return RedirectResponse(
            f"/academy/lessons/new?module_id={module_id}&error={quote(str(exc))}",
            status_code=303,
        )
    except sqlite3.IntegrityError:
        return RedirectResponse(
            f"/academy/lessons/new?module_id={module_id}&error=Lesson+slug+or+order+already+exists.",
            status_code=303,
        )

    return RedirectResponse(
        f"/academy/lessons/{lesson_id}/edit?success=Lesson+created+as+a+draft.",
        status_code=303,
    )


@app.get("/academy/lessons/new", response_class=HTMLResponse)
async def academy_new_lesson_page(
    request: Request,
    module_id: int,
    _: None = Depends(require_admin),
):
    module = academy_queries.get_admin_module(module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found.")

    return page(
        request,
        "academy_lesson_form.html",
        lesson=None,
        module=module,
        csrf=csrf_token(request),
        active="academy",
        error=request.query_params.get("error"),
        success=None,
    )


@app.get(
    "/academy/lessons/{lesson_id}/edit",
    response_class=HTMLResponse,
)
async def academy_edit_lesson_page(
    request: Request,
    lesson_id: int,
    _: None = Depends(require_admin),
):
    lesson = academy_queries.get_admin_lesson(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found.")

    module = academy_queries.get_admin_module(lesson["module_id"])

    return page(
        request,
        "academy_lesson_form.html",
        lesson=lesson,
        module=module,
        csrf=csrf_token(request),
        active="academy",
        error=request.query_params.get("error"),
        success=request.query_params.get("success"),
    )


@app.post("/academy/lessons/{lesson_id}/edit")
async def academy_update_lesson(
    request: Request,
    lesson_id: int,
    csrf: str = Form(...),
    slug: str = Form(...),
    lesson_type: str = Form(...),
    sort_order: int = Form(...),
    estimated_minutes: int = Form(...),
    title_en: str = Form(...),
    content_en: str = Form(...),
    title_am: str = Form(""),
    content_am: str = Form(""),
    title_om: str = Form(""),
    content_om: str = Form(""),
    _: None = Depends(require_admin),
):
    verify_csrf(request, csrf)
    lesson = academy_queries.get_admin_lesson(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found.")

    translations = {
        "en": {"title": title_en, "content": content_en},
        "am": {"title": title_am, "content": content_am},
        "om": {"title": title_om, "content": content_om},
    }

    try:
        academy_queries.update_lesson(
            lesson_id=lesson_id,
            slug=slug,
            lesson_type=lesson_type,
            translations=translations,
            sort_order=sort_order,
            estimated_minutes=estimated_minutes,
        )
    except ValueError as exc:
        return RedirectResponse(
            f"/academy/lessons/{lesson_id}/edit?error={quote(str(exc))}",
            status_code=303,
        )
    except sqlite3.IntegrityError:
        return RedirectResponse(
            f"/academy/lessons/{lesson_id}/edit?error=Lesson+slug+or+order+already+exists.",
            status_code=303,
        )

    return RedirectResponse(
        f"/academy/lessons/{lesson_id}/edit?success=Lesson+saved.",
        status_code=303,
    )


@app.post("/academy/lessons/{lesson_id}/status")
async def academy_change_lesson_status(
    request: Request,
    lesson_id: int,
    csrf: str = Form(...),
    is_published: int = Form(...),
    _: None = Depends(require_admin),
):
    verify_csrf(request, csrf)
    lesson = academy_queries.get_admin_lesson(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found.")

    try:
        academy_queries.set_lesson_status(lesson_id, is_published)
    except ValueError as exc:
        return RedirectResponse(
            f"/academy/lessons/{lesson_id}/edit?error={quote(str(exc))}",
            status_code=303,
        )

    return RedirectResponse(
        f"/academy/lessons/{lesson_id}/edit?success=Lesson+publication+updated.",
        status_code=303,
    )
