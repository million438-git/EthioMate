import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.exceptions import TelegramBadRequest

from database.db import get_language
from services import academy
from services.telegram_formatting import format_telegram_html

logger = logging.getLogger(__name__)
router = Router()

async def safe_callback_answer(callback, *args, **kwargs):
    """Acknowledge Telegram callbacks without crashing on expired queries."""
    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest as exc:
        message = str(exc).lower()
        if (
            "query is too old" in message
            or "query id is invalid" in message
            or "query is already answered" in message
        ):
            logger.debug("Ignoring expired or already answered Academy callback.")
            return
        raise



TEXT = {
    "en": {
        "title": "🎓 <b>EthioMate Academy</b>",
        "intro": "Explore practical courses and build real-world skills.",
        "no_courses": "There are no published courses available yet.",
        "no_enrollments": "You have not enrolled in any courses yet.",
        "courses": "📚 Browse Courses",
        "mine": "📖 My Courses",
        "progress": "📊 My Learning Progress",
        "enroll": "Enroll in Course",
        "already": "You are already enrolled in this course.",
        "enrolled": "You are now enrolled successfully!",
        "open": "Open Course",
        "back": "⬅️ Back",
        "home": "🏠 Academy Home",
        "completed": "✅ Mark as Completed",
        "marked": "Lesson marked as completed.",
        "not_found": "This course or lesson is unavailable.",
        "not_registered": "You are not enrolled in this course yet. Please enroll first.",
        "lesson": "📖 Lesson",
        "modules": "📚 Course Curriculum",
        "minutes": "minutes",
        "completed_count": "Completed",
        "remaining": "Remaining",
        "completion": "Course completion",
        "draft": "No published lessons are available in this course yet.",
    },
    "am": {
        "title": "🎓 <b>EthioMate አካዳሚ</b>",
        "intro": "ተግባራዊ ኮርሶችን ይማሩ፤ በእውነተኛ ስራ የሚጠቅሙ ክህሎቶችን ያዳብሩ።",
        "no_courses": "እስካሁን የታተሙ ኮርሶች የሉም።",
        "no_enrollments": "እስካሁን በምንም ኮርስ አልተመዘገቡም።",
        "courses": "📚 ኮርሶችን ይመልከቱ",
        "mine": "📖 የእኔ ኮርሶች",
        "progress": "📊 የትምህርት እድገቴ",
        "enroll": "በኮርሱ ይመዝገቡ",
        "already": "በዚህ ኮርስ ተመዝግበዋል።",
        "enrolled": "በተሳካ ሁኔታ ተመዝግበዋል!",
        "open": "ኮርሱን ይክፈቱ",
        "back": "⬅️ ተመለስ",
        "home": "🏠 የአካዳሚ መነሻ",
        "completed": "✅ ትምህርቱን አጠናቅቄያለሁ",
        "marked": "ትምህርቱ እንደተጠናቀቀ ተመዝግቧል።",
        "not_found": "ይህ ኮርስ ወይም ትምህርት አይገኝም።",
        "not_registered": "እስካሁን በዚህ ኮርስ አልተመዘገቡም። እባክዎ አስቀድመው ይመዝገቡ።",
        "lesson": "📖 ትምህርት",
        "modules": "📚 የኮርስ ይዘት",
        "minutes": "ደቂቃ",
        "completed_count": "የተጠናቀቁ",
        "remaining": "የቀሩ",
        "completion": "የኮርስ እድገት",
        "draft": "በዚህ ኮርስ ውስጥ የታተሙ ትምህርቶች ገና የሉም።",
    },
    "om": {
        "title": "🎓 <b>EthioMate Academy</b>",
        "intro": "Koorsii hojii irratti hundaa'e baradhu; dandeettii hojii dhugaa keessatti fayyadu ijaari.",
        "no_courses": "Ammaaf koorsiin maxxanfame hin jiru.",
        "no_enrollments": "Ammaaf koorsii tokko illee hin galmoofne.",
        "courses": "📚 Koorsii Ilaali",
        "mine": "📖 Koorsii Koo",
        "progress": "📊 Guddina Barnootaa Koo",
        "enroll": "Koorsii Galmaa'i",
        "already": "Koorsii kana keessatti duraan galmoofteetta.",
        "enrolled": "Milkaa'inaan galmoofteetta!",
        "open": "Koorsii Bani",
        "back": "⬅️ Duubatti",
        "home": "🏠 Fuula Jalqabaa Academy",
        "completed": "✅ Barnoota Xumureera",
        "marked": "Barnootni akka xumurame galmaa'eera.",
        "not_found": "Koorsiin ykn barnootni kun hin jiru.",
        "not_registered": "Ammaaf koorsii kanaan hin galmoofne. Maaloo dura galmaa'aa.",
        "lesson": "📖 Barnoota",
        "modules": "📚 Qabiyyee Koorsii",
        "minutes": "daqiiqaa",
        "completed_count": "Xumurame",
        "remaining": "Hafe",
        "completion": "Guddina koorsii",
        "draft": "Koorsii kana keessatti barnootni maxxanfame ammaaf hin jiru.",
    },
}


def language_for(user_id):
    language = get_language(user_id)
    return language if language in TEXT else "en"


def button(label, data):
    return InlineKeyboardButton(text=label, callback_data=data)


def home_keyboard(language):
    t = TEXT[language]
    return InlineKeyboardMarkup(inline_keyboard=[
        [button(t["courses"], "ac:courses")],
        [button(t["mine"], "ac:mine")],
        [button(t["progress"], "ac:progress")],
    ])


def back_keyboard(language, destination="ac:home"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [button(TEXT[language]["back"], destination)],
        [button(TEXT[language]["home"], "ac:home")],
    ])


async def show_home(message, language):
    t = TEXT[language]
    await message.answer(
        f'{t["title"]}\n\n{t["intro"]}',
        reply_markup=home_keyboard(language),
        parse_mode="HTML",
    )


async def edit_or_send(callback, text, keyboard, parse_mode="HTML"):
    try:
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode=parse_mode,
        )
    except TelegramBadRequest:
        await callback.message.answer(
            text,
            reply_markup=keyboard,
            parse_mode=parse_mode,
        )


def course_keyboard(courses, language):
    rows = []
    for course in courses:
        title = course.get("title") or course.get("slug") or "Course"
        rows.append([
            button(title[:55], f'ac:course:{course["id"]}')
        ])

    rows.append([button(TEXT[language]["home"], "ac:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_courses(target, language):
    t = TEXT[language]
    courses = academy.list_published_courses(language=language)

    if not courses:
        text = f'{t["title"]}\n\n{t["no_courses"]}'
        keyboard = back_keyboard(language)
    else:
        lines = [t["title"], "", t["courses"], ""]
        for course in courses:
            lines.append(
                f'• <b>{course.get("title", "Course")}</b>\n'
                f'{course.get("description", "")[:180]}\n'
                f'<i>{course.get("level", "").title()}</i>'
            )
        text = "\n\n".join(lines)
        keyboard = course_keyboard(courses, language)

    if isinstance(target, CallbackQuery):
        await edit_or_send(target, text, keyboard)
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def show_my_courses(target, language, user_id):
    t = TEXT[language]
    courses = academy.get_enrolled_courses(user_id, language=language)

    if not courses:
        keyboard = back_keyboard(language, "ac:courses")
        text = f'{t["title"]}\n\n{t["no_enrollments"]}'
    else:
        lines = [f'<b>{t["mine"]}</b>', ""]
        for course in courses:
            lines.append(
                f'• <b>{course.get("title", "Course")}</b>\n'
                f'<i>{course.get("enrollment_status", "enrolled").title()}</i>'
            )
        keyboard = course_keyboard(courses, language)
        text = "\n\n".join(lines)

    if isinstance(target, CallbackQuery):
        await edit_or_send(target, text, keyboard)
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def show_course(callback, language, course_id):
    t = TEXT[language]
    course = academy.get_course(course_id, language=language)

    if not course:
        await safe_callback_answer(callback, t["not_found"], show_alert=True)
        return

    user_id = callback.from_user.id
    enrolled = any(
        item["id"] == course_id
        for item in academy.get_enrolled_courses(user_id, language)
    )

    lines = [
        f'<b>{course.get("title", "Course")}</b>',
        "",
        course.get("description", ""),
        "",
        f'<b>Level:</b> {course.get("level", "").title()}',
    ]

    if enrolled:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [button(t["open"], f"ac:curr:{course_id}")],
            [button(t["progress"], f"ac:oneprogress:{course_id}")],
            [button(t["back"], "ac:courses")],
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [button(t["enroll"], f"ac:enroll:{course_id}")],
            [button(t["back"], "ac:courses")],
        ])

    await edit_or_send(callback, "\n".join(lines), keyboard)


async def show_curriculum(callback, language, course_id):
    t = TEXT[language]
    user_id = callback.from_user.id

    curriculum = academy.get_course_curriculum(
        course_id,
        language=language,
        telegram_id=user_id,
    )

    if not curriculum:
        await safe_callback_answer(callback, t["not_found"], show_alert=True)
        return

    lines = [
        f'<b>{curriculum["course"].get("title", "Course")}</b>',
        "",
        f'<b>{t["modules"]}</b>',
    ]
    rows = []

    for module in curriculum.get("modules", []):
        lines.append(f'\n<b>{module.get("title", "Module")}</b>')

        for lesson in module.get("lessons", []):
            progress = lesson.get("progress") or {}
            complete = progress.get("status") == "completed"
            prefix = "✅" if complete else "📖"
            lines.append(f'{prefix} {lesson.get("title", "Lesson")}')

            rows.append([
                button(
                    f'{prefix} {lesson.get("title", "Lesson")}'[:55],
                    f'ac:lesson:{lesson["id"]}:{course_id}',
                )
            ])

    if not rows:
        lines.append(f'\n{t["draft"]}')

    rows.append([button(t["back"], f"ac:course:{course_id}")])
    rows.append([button(t["home"], "ac:home")])

    await edit_or_send(
        callback,
        "\n".join(lines),
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


def lesson_chunks(content, limit=3400):
    """Split Markdown on paragraph boundaries before HTML conversion."""
    paragraphs = content.split("\n\n")
    chunks = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if len(candidate) > limit and current:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks or [""]


async def show_lesson(callback, language, lesson_id, course_id):
    t = TEXT[language]
    lesson = academy.get_lesson(
        lesson_id,
        callback.from_user.id,
        language=language,
    )

    if not lesson:
        await safe_callback_answer(callback, t["not_found"], show_alert=True)
        return

    await safe_callback_answer(callback, )

    title = lesson.get("title", t["lesson"])
    content = lesson.get("content", "")
    chunks = lesson_chunks(content)

    for index, chunk in enumerate(chunks):
        heading = f'<b>{title}</b>\n\n' if index == 0 else ""
        formatted = format_telegram_html(chunk)
        await callback.message.answer(
            heading + formatted,
            parse_mode="HTML",
        )

    progress = lesson.get("progress") or {}
    if progress.get("status") == "completed":
        completion_text = t["marked"]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [button(t["back"], f"ac:curr:{course_id}")],
            [button(t["home"], "ac:home")],
        ])
    else:
        completion_text = t["completed"]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [button(t["completed"], f"ac:done:{lesson_id}:{course_id}")],
            [button(t["back"], f"ac:curr:{course_id}")],
            [button(t["home"], "ac:home")],
        ])

    await callback.message.answer(
        completion_text,
        reply_markup=keyboard,
    )


async def show_progress(callback, language, course_id=None):
    t = TEXT[language]
    user_id = callback.from_user.id
    courses = academy.get_enrolled_courses(user_id, language)

    if course_id is not None:
        courses = [item for item in courses if item["id"] == course_id]

    if not courses:
        await edit_or_send(
            callback,
            t["no_enrollments"],
            back_keyboard(language),
            parse_mode=None,
        )
        return

    lines = [f'<b>{t["progress"]}</b>', ""]

    for course in courses:
        progress = academy.get_course_progress(user_id, course["id"])
        if not progress:
            continue

        lines.extend([
            f'<b>{course.get("title", "Course")}</b>',
            f'{t["completed_count"]}: {progress["completed_lessons"]}/{progress["total_lessons"]}',
            f'{t["remaining"]}: {progress["remaining_lessons"]}',
            f'{t["completion"]}: {progress["completion_percent"]}%',
            "",
        ])

    await edit_or_send(
        callback,
        "\n".join(lines),
        back_keyboard(language),
    )


@router.message(Command("courses"))
async def command_courses(message: Message):
    language = language_for(message.from_user.id)
    await show_courses(message, language)


@router.message(Command("learn"))
async def command_learn(message: Message):
    language = language_for(message.from_user.id)
    await show_my_courses(message, language, message.from_user.id)


@router.message(Command("my_skills"))
async def command_my_skills(message: Message):
    language = language_for(message.from_user.id)
    courses = academy.get_enrolled_courses(message.from_user.id, language)

    if not courses:
        await message.answer(TEXT[language]["no_enrollments"])
        return

    lines = [f'<b>{TEXT[language]["progress"]}</b>', ""]
    for course in courses:
        progress = academy.get_course_progress(
            message.from_user.id,
            course["id"],
        )
        if progress:
            lines.append(
                f'<b>{course.get("title", "Course")}</b>\n'
                f'{progress["completed_lessons"]}/{progress["total_lessons"]} '
                f'({progress["completion_percent"]}%)'
            )

    await message.answer("\n\n".join(lines), parse_mode="HTML")


@router.message(F.text.in_([
    "🎓 Academy",
    "🎓 አካዳሚ",
    "🎓 Academy Barnootaa",
]))
async def academy_menu_button(message: Message):
    language = language_for(message.from_user.id)
    await show_home(message, language)


@router.callback_query(F.data == "ac:home")
async def academy_home(callback: CallbackQuery):
    language = language_for(callback.from_user.id)
    await safe_callback_answer(callback, )
    await edit_or_send(
        callback,
        f'{TEXT[language]["title"]}\n\n{TEXT[language]["intro"]}',
        home_keyboard(language),
    )


@router.callback_query(F.data == "ac:courses")
async def academy_courses(callback: CallbackQuery):
    language = language_for(callback.from_user.id)
    await safe_callback_answer(callback, )
    await show_courses(callback, language)


@router.callback_query(F.data == "ac:mine")
async def academy_mine(callback: CallbackQuery):
    language = language_for(callback.from_user.id)
    await safe_callback_answer(callback, )
    await show_my_courses(callback, language, callback.from_user.id)


@router.callback_query(F.data.startswith("ac:course:"))
async def academy_course_detail(callback: CallbackQuery):
    language = language_for(callback.from_user.id)
    try:
        course_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await safe_callback_answer(callback, TEXT[language]["not_found"], show_alert=True)
        return

    await safe_callback_answer(callback, )
    await show_course(callback, language, course_id)


@router.callback_query(F.data.startswith("ac:enroll:"))
async def academy_enroll(callback: CallbackQuery):
    language = language_for(callback.from_user.id)
    try:
        course_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await safe_callback_answer(callback, TEXT[language]["not_found"], show_alert=True)
        return

    try:
        enrolled = academy.enroll_user(callback.from_user.id, course_id)
    except PermissionError:
        await safe_callback_answer(
            callback,
            TEXT[language]["not_registered"],
            show_alert=True,
        )
        return
    except ValueError:
        await safe_callback_answer(callback, TEXT[language]["not_found"], show_alert=True)
        return

    if enrolled:
        await safe_callback_answer(callback, TEXT[language]["enrolled"], show_alert=True)
    else:
        await safe_callback_answer(callback, TEXT[language]["already"], show_alert=True)

    await show_course(callback, language, course_id)


@router.callback_query(F.data.startswith("ac:curr:"))
async def academy_curriculum(callback: CallbackQuery):
    language = language_for(callback.from_user.id)
    try:
        course_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await safe_callback_answer(callback, TEXT[language]["not_found"], show_alert=True)
        return

    await safe_callback_answer(callback, )
    try:
        await show_curriculum(callback, language, course_id)
    except PermissionError:
        await safe_callback_answer(
            callback,
            TEXT[language]["not_registered"],
            show_alert=True,
        )


@router.callback_query(F.data.startswith("ac:lesson:"))
async def academy_lesson(callback: CallbackQuery):
    language = language_for(callback.from_user.id)
    try:
        _, _, lesson_id, course_id = callback.data.split(":")
        lesson_id = int(lesson_id)
        course_id = int(course_id)
    except (ValueError, IndexError):
        await safe_callback_answer(callback, TEXT[language]["not_found"], show_alert=True)
        return

    await show_lesson(callback, language, lesson_id, course_id)


@router.callback_query(F.data.startswith("ac:done:"))
async def academy_complete_lesson(callback: CallbackQuery):
    language = language_for(callback.from_user.id)
    try:
        _, _, lesson_id, course_id = callback.data.split(":")
        lesson_id = int(lesson_id)
        course_id = int(course_id)
    except (ValueError, IndexError):
        await safe_callback_answer(callback, TEXT[language]["not_found"], show_alert=True)
        return

    try:
        result = academy.update_lesson_progress(
            callback.from_user.id,
            lesson_id,
            status="completed",
        )
    except PermissionError:
        await safe_callback_answer(
            callback,
            TEXT[language]["not_registered"],
            show_alert=True,
        )
        return

    if not result:
        await safe_callback_answer(callback, TEXT[language]["not_found"], show_alert=True)
        return

    await safe_callback_answer(callback, TEXT[language]["marked"], show_alert=True)
    try:
        await show_curriculum(callback, language, course_id)
    except PermissionError:
        await safe_callback_answer(
            callback,
            TEXT[language]["not_registered"],
            show_alert=True,
        )


@router.callback_query(F.data == "ac:progress")
async def academy_all_progress(callback: CallbackQuery):
    await safe_callback_answer(callback)
    language = language_for(callback.from_user.id)
    await show_progress(callback, language)


@router.callback_query(F.data.startswith("ac:oneprogress:"))
async def academy_course_progress(callback: CallbackQuery):
    language = language_for(callback.from_user.id)
    try:
        course_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await safe_callback_answer(callback, TEXT[language]["not_found"], show_alert=True)
        return

    await safe_callback_answer(callback, )
    await show_progress(callback, language, course_id)
