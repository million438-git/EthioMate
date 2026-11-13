import html
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    BotCommandScopeDefault,
)

from config import ADMIN_IDS
from database.db import (
    get_language,
    get_quiz_history,
    save_feedback,
    get_open_feedback,
    mark_feedback_reviewed,
)
from keyboards.menus import (
    main_menu,
    language_keyboard,
    study_menu,
)
from handlers.assistant import open_assistant, new_chat
from handlers.translation import open_translation
from handlers.calculator import open_calculator
from handlers.quiz import start_quiz

logger = logging.getLogger(__name__)
router = Router()


class FeedbackStates(StatesGroup):
    waiting_for_submission = State()


FEEDBACK_TYPES = {
    "feedback": {
        "en": ("Send your feedback in one message.", "Feedback"),
        "am": ("አስተያየትዎን በአንድ መልዕክት ይላኩ።", "አስተያየት"),
        "om": ("Yaada kee ergaa tokkoon ergi.", "Yaada"),
    },
    "report": {
        "en": ("Describe the problem or bug you found.", "Bug report"),
        "am": ("ያገኙትን ችግር ወይም ስህተት ይግለጹ።", "የስህተት ሪፖርት"),
        "om": ("Rakkoo ykn dogoggora argite ibsi.", "Gabaasa dogoggoraa"),
    },
    "suggest": {
        "en": ("Describe your suggestion.", "Suggestion"),
        "am": ("ሃሳብዎን ይግለጹ።", "ጥቆማ"),
        "om": ("Yaada kee ibsi.", "Yaada fooyya'iinsaa"),
    },
    "request": {
        "en": ("Describe the feature or service you would like us to add.", "Feature request"),
        "am": ("እንዲጨመር የሚፈልጉትን ባህሪ ወይም አገልግሎት ይግለጹ።", "የአዲስ ባህሪ ጥያቄ"),
        "om": ("Amala ykn tajaajila akka dabalamuu barbaaddu ibsi.", "Gaaffii amala haaraa"),
    },
}


@router.message(Command("menu"))
async def command_menu(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)
    await state.clear()
    await message.answer(
        "Main menu / ዋና ምናሌ",
        reply_markup=main_menu(language),
    )


@router.message(Command("help"))
async def command_help(message: Message):
    language = get_language(message.from_user.id)

    help_text = {
        "en": (
            "<b>EthioMate Commands</b>\n\n"
            "/start — Start the bot\n"
            "/menu — Open the main menu\n"
            "/study — Study services\n"
            "/quiz — Generate a practice quiz\n"
            "/ask — Ask the AI Assistant\n"
            "/new — Start a fresh AI conversation\n"
            "/translate — Translate text\n"
            "/calculate — Open calculators\n"
            "/history — View recent quiz results\n"
            "/progress — View your quiz progress\n"
            "/feedback — Send feedback\n"
            "/report — Report a problem\n"
            "/suggest — Suggest an improvement\n"
            "/request — Request a new feature\n"
            "/settings — View your account settings\n"
            "/language — Change your language\n"
            "/profile — View your account\n"
            "/cancel — Cancel the current operation\n"
            "/about — About EthioMate\n"
            "/privacy — Privacy information\n"
            "/support — Get support\n\n"
            "Existing commands: /newchat, /exit, /studyexit."
        ),
        "am": (
            "<b>የEthioMate ትዕዛዞች</b>\n\n"
            "/start — ቦቱን ጀምር\n"
            "/menu — ዋና ምናሌ\n"
            "/study — የትምህርት አገልግሎቶች\n"
            "/quiz — የልምምድ ፈተና\n"
            "/ask — AI አስተዳዳሪን ጠይቅ\n"
            "/new — አዲስ AI ውይይት\n"
            "/translate — ትርጉም\n"
            "/calculate — የሂሳብ ማስያዎች\n"
            "/history — የፈተና ታሪክ\n"
            "/progress — የትምህርት እድገት\n"
            "/feedback — አስተያየት\n"
            "/report — ችግር ሪፖርት\n"
            "/suggest — ማሻሻያ ጥቆማ\n"
            "/request — አዲስ ባህሪ ጥያቄ\n"
            "/settings — የመለያ ቅንብሮች\n"
            "/language — ቋንቋ ቀይር\n"
            "/profile — መለያዎን ይመልከቱ\n"
            "/cancel — አሁኑን ሂደት ሰርዝ\n"
            "/about — ስለ EthioMate\n"
            "/privacy — የግላዊነት መረጃ\n"
            "/support — እገዛ"
        ),
        "om": (
            "<b>Ajajoota EthioMate</b>\n\n"
            "/start — Bot jalqabi\n"
            "/menu — Menuu guddaa bani\n"
            "/study — Tajaajila barnootaa\n"
            "/quiz — Qormaata shaakalaa\n"
            "/ask — Gargaaraa AI gaafadhu\n"
            "/new — Haasaa AI haaraa jalqabi\n"
            "/translate — Hiikkaa\n"
            "/calculate — Herrega\n"
            "/history — Seenaa qormaataa\n"
            "/progress — Guddina barnootaa\n"
            "/feedback — Yaada ergi\n"
            "/report — Rakkoo gabaasi\n"
            "/suggest — Fooyya'iinsa yaadi\n"
            "/request — Amala haaraa gaafadhu\n"
            "/settings — Qindaa'ina herregaa\n"
            "/language — Afaan jijjiiri\n"
            "/profile — Herrega ilaali\n"
            "/cancel — Hojii amma jiru haqi\n"
            "/about — Waa'ee EthioMate\n"
            "/privacy — Odeeffannoo iccitii\n"
            "/support — Gargaarsa"
        ),
    }

    await message.answer(
        help_text.get(language, help_text["en"]),
        parse_mode="HTML",
    )


@router.message(Command("language"))
async def command_language(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Choose your language / ቋንቋ ይምረጡ:",
        reply_markup=language_keyboard(),
    )


@router.message(Command("study"))
async def command_study(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)
    await state.clear()
    await message.answer(
        {
            "en": "Choose a learning service.",
            "am": "የትምህርት አገልግሎት ይምረጡ።",
            "om": "Tajaajila barnootaa filadhu.",
        }[language],
        reply_markup=study_menu(language),
    )


@router.message(Command("quiz"))
async def command_quiz(message: Message, state: FSMContext):
    await start_quiz(message, state)


@router.message(Command("ask"))
async def command_ask(message: Message, state: FSMContext):
    await open_assistant(message, state)


@router.message(Command("new"))
async def command_new(message: Message, state: FSMContext):
    await new_chat(message, state)


@router.message(Command("translate"))
async def command_translate(message: Message, state: FSMContext):
    await open_translation(message, state)


@router.message(Command("calculate"))
async def command_calculate(message: Message, state: FSMContext):
    await open_calculator(message, state)


@router.message(Command("history"))
async def command_history(message: Message):
    language = get_language(message.from_user.id)
    records = get_quiz_history(message.from_user.id, limit=10)

    if not records:
        text = {
            "en": "You have no completed quizzes yet. Use /quiz to begin.",
            "am": "እስካሁን የተጠናቀቀ ፈተና የለዎትም። /quiz በመጠቀም ይጀምሩ።",
            "om": "Hanga ammaatti qormaata hin xumurre. /quiz fayyadamuun jalqabi.",
        }[language]
        await message.answer(text)
        return

    lines = ["<b>Recent quiz history</b>\n"]
    for item in records:
        lines.append(
            f"• {item['subject']} — {item['topic']}\n"
            f"  {item['correct_answers']}/{item['total_questions']} "
            f"({item['score_percent']}%)"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("progress"))
async def command_progress(message: Message):
    language = get_language(message.from_user.id)
    records = get_quiz_history(message.from_user.id, limit=1000)

    if not records:
        await message.answer({
            "en": "Complete your first quiz to see your progress.",
            "am": "እድገትዎን ለማየት የመጀመሪያ ፈተናዎን ያጠናቅቁ።",
            "om": "Qormaata jalqabaa xumuri; guddina kee ni argita.",
        }[language])
        return

    total_questions = sum(item["total_questions"] for item in records)
    correct = sum(item["correct_answers"] for item in records)
    average = round(correct / total_questions * 100, 1)

    await message.answer(
        f"<b>Your quiz progress</b>\n\n"
        f"Completed quizzes: {len(records)}\n"
        f"Questions answered: {total_questions}\n"
        f"Correct answers: {correct}\n"
        f"Overall accuracy: {average}%",
        parse_mode="HTML",
    )


@router.message(Command("settings"))
async def command_settings(message: Message):
    language = get_language(message.from_user.id)
    await message.answer({
        "en": "Account settings\n\nUse /language to change your language or /profile to view your account.",
        "am": "የመለያ ቅንብሮች\n\nቋንቋዎን ለመቀየር /language ወይም መለያዎን ለማየት /profile ይጠቀሙ።",
        "om": "Qindaa'ina herregaa\n\nAfaan jijjiiruuf /language ykn herrega ilaaluuf /profile fayyadami.",
    }[language])


@router.message(Command("about"))
async def command_about(message: Message):
    await message.answer(
        "EthioMate is a multilingual learning and productivity assistant "
        "for English, Amharic and Afaan Oromo users."
    )


@router.message(Command("privacy"))
async def command_privacy(message: Message):
    await message.answer(
        "EthioMate stores basic Telegram profile details, language preferences, "
        "quiz results and any feedback or reports you choose to submit. "
        "Do not send passwords, payment credentials or other sensitive information."
    )


@router.message(Command("support"))
async def command_support(message: Message):
    await message.answer(
        "For help, use /feedback to share general feedback or /report to report "
        "a problem. Use /help to see available commands."
    )


@router.message(Command("feedback", "report", "suggest", "request"))
async def start_feedback(message: Message, state: FSMContext):
    command = message.text.split()[0].split("@")[0].lstrip("/").lower()
    language = get_language(message.from_user.id)

    await state.clear()
    await state.update_data(submission_type=command)
    await state.set_state(FeedbackStates.waiting_for_submission)

    prompt, label = FEEDBACK_TYPES[command][language]
    await message.answer(
        f"{label}\n\n{prompt}\n\n"
        "Send /cancel if you want to stop."
    )


@router.message(FeedbackStates.waiting_for_submission, F.text)
async def receive_feedback(message: Message, state: FSMContext):
    content = message.text.strip()

    if content.startswith("/cancel"):
        await state.clear()
        await message.answer("Submission cancelled.")
        return

    if len(content) < 5 or len(content) > 3000:
        await message.answer("Please send between 5 and 3000 characters.")
        return

    data = await state.get_data()
    submission_type = data.get("submission_type", "feedback")

    submission_id = save_feedback(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        submission_type=submission_type,
        content=content,
    )

    await state.clear()
    await message.answer(
        f"Thank you. Your submission has been saved.\n"
        f"Reference: #{submission_id}"
    )

    admin_message = (
        f"New EthioMate {submission_type}\n"
        f"Reference: #{submission_id}\n"
        f"User: {message.from_user.full_name}\n"
        f"Telegram ID: {message.from_user.id}\n\n"
        f"{content}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, admin_message)
        except Exception:
            logger.exception("Could not notify admin %s", admin_id)


@router.message(Command("admin_feedback"))
async def admin_feedback(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("You are not authorized to use this command.")
        return

    submissions = get_open_feedback(limit=20)

    if not submissions:
        await message.answer("There are no pending submissions.")
        return

    for item in submissions:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="Mark reviewed",
                    callback_data=f"feedback:review:{item['id']}",
                )
            ]]
        )

        safe_type = html.escape(str(item["submission_type"]))
        safe_name = html.escape(str(item["first_name"]))
        safe_username = html.escape(str(item["username"] or "not set"))
        safe_content = html.escape(str(item["content"]))
        safe_date = html.escape(str(item["created_at"]))

        await message.answer(
            f"<b>#{item['id']} — {safe_type}</b>\n"
            f"User: {safe_name} (@{safe_username})\n"
            f"Telegram ID: <code>{item['telegram_id']}</code>\n"
            f"Date: {safe_date}\n\n"
            f"{safe_content}",
            parse_mode="HTML",
            reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("feedback:review:"))
async def review_feedback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Not authorized.", show_alert=True)
        return

    try:
        submission_id = int(callback.data.rsplit(":", 1)[-1])
    except ValueError:
        await callback.answer("Invalid submission.", show_alert=True)
        return

    updated = mark_feedback_reviewed(submission_id, callback.from_user.id)

    if updated:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Submission marked as reviewed.")
    else:
        await callback.answer("Submission was already reviewed or not found.", show_alert=True)


async def register_bot_commands(bot):
    english = [
        ("start", "Start EthioMate"),
        ("menu", "Open the main menu"),
        ("help", "Show all commands"),
        ("study", "Open learning services"),
        ("courses", "Browse Academy courses"),
        ("learn", "Open your enrolled courses"),
        ("my_skills", "View Academy learning progress"),
        ("quiz", "Generate a practice quiz"),
        ("ask", "Ask the AI assistant"),
        ("new", "Start a new AI conversation"),
        ("translate", "Translate text"),
        ("calculate", "Open calculators"),
        ("history", "View quiz history"),
        ("progress", "View learning progress"),
        ("feedback", "Send feedback"),
        ("report", "Report a problem"),
        ("suggest", "Suggest an improvement"),
        ("request", "Request a new feature"),
        ("settings", "View account settings"),
        ("language", "Change language"),
        ("profile", "View your profile"),
        ("cancel", "Cancel current operation"),
        ("about", "About EthioMate"),
        ("privacy", "Privacy information"),
        ("support", "Get support"),
    ]

    amharic = [
        ("start", "EthioMate ጀምር"),
        ("menu", "ዋና ምናሌ"),
        ("help", "ሁሉንም ትዕዛዞች አሳይ"),
        ("study", "የትምህርት አገልግሎቶች"),
        ("courses", "ኮርሶችን ይመልከቱ"),
        ("learn", "የእኔ ኮርሶች"),
        ("my_skills", "የትምህርት እድገቴ"),
        ("quiz", "የልምምድ ፈተና"),
        ("ask", "AI አስተዳዳሪን ጠይቅ"),
        ("new", "አዲስ AI ውይይት"),
        ("translate", "ጽሑፍ ተርጉም"),
        ("calculate", "የሂሳብ ማስያዎች"),
        ("history", "የፈተና ታሪክ"),
        ("progress", "የትምህርት እድገት"),
        ("feedback", "አስተያየት ላክ"),
        ("report", "ችግር ሪፖርት"),
        ("suggest", "ማሻሻያ ጠቁም"),
        ("request", "አዲስ ባህሪ ጠይቅ"),
        ("settings", "የመለያ ቅንብሮች"),
        ("language", "ቋንቋ ቀይር"),
        ("profile", "መለያ አሳይ"),
        ("cancel", "ሂደት ሰርዝ"),
        ("about", "ስለ EthioMate"),
        ("privacy", "የግላዊነት መረጃ"),
        ("support", "እገዛ"),
    ]

    oromo = [
        ("start", "EthioMate jalqabi"),
        ("menu", "Menuu guddaa bani"),
        ("help", "Ajajoota hunda agarsiisi"),
        ("study", "Tajaajila barnootaa"),
        ("courses", "Koorsii barnootaa ilaali"),
        ("learn", "Koorsii koo bani"),
        ("my_skills", "Guddina barnootaa koo ilaali"),
        ("quiz", "Qormaata shaakalaa"),
        ("ask", "Gargaaraa AI gaafadhu"),
        ("new", "Haasaa AI haaraa"),
        ("translate", "Barruu hiiki"),
        ("calculate", "Meeshaalee herregaa"),
        ("history", "Seenaa qormaataa"),
        ("progress", "Guddina barnootaa"),
        ("feedback", "Yaada ergi"),
        ("report", "Rakkoo gabaasi"),
        ("suggest", "Fooyya'iinsa yaadi"),
        ("request", "Amala haaraa gaafadhu"),
        ("settings", "Qindaa'ina herregaa"),
        ("language", "Afaan jijjiiri"),
        ("profile", "Herrega ilaali"),
        ("cancel", "Hojii haqi"),
        ("about", "Waa'ee EthioMate"),
        ("privacy", "Odeeffannoo iccitii"),
        ("support", "Gargaarsa"),
    ]

    await bot.set_my_commands(
        [BotCommand(command=name, description=description) for name, description in english],
        scope=BotCommandScopeDefault(),
    )

    for code, entries in (("am", amharic), ("om", oromo)):
        await bot.set_my_commands(
            [BotCommand(command=name, description=description) for name, description in entries],
            scope=BotCommandScopeDefault(),
            language_code=code,
        )
