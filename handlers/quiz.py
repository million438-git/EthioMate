import html
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from database.db import get_language, save_quiz_result
from aiogram.exceptions import TelegramBadRequest
from keyboards.menus import STUDY_QUIZ_BUTTONS, study_menu
from services.ai_assistant import AIRateLimited
from services.quiz_generator import generate_quiz


logger = logging.getLogger(__name__)
router = Router()


class QuizStates(StatesGroup):
    choosing_subject = State()
    entering_topic = State()
    choosing_difficulty = State()
    choosing_count = State()
    answering = State()


SUBJECTS = {
    "math": "Mathematics",
    "physics": "Physics",
    "chemistry": "Chemistry",
    "biology": "Biology",
    "english": "English",
    "computer": "Computer Science",
    "other": "Other",
}

SUBJECT_LABELS = {
    "am": {
        "math": "ሒሳብ",
        "physics": "ፊዚክስ",
        "chemistry": "ኬሚስትሪ",
        "biology": "ባዮሎጂ",
        "english": "እንግሊዝኛ",
        "computer": "ኮምፒውተር ሳይንስ",
        "other": "ሌላ",
    },
    "en": SUBJECTS,
    "om": {
        "math": "Herrega",
        "physics": "Fiiziksii",
        "chemistry": "Keemistirii",
        "biology": "Baayoloojii",
        "english": "Afaan Ingilizii",
        "computer": "Saayinsii Kompiitaraa",
        "other": "Kan biraa",
    },
}

TEXT = {
    "en": {
        "choose_subject": "Choose a subject:",
        "topic": "Enter the topic you want to practise. For example: Newton's Laws of Motion.",
        "difficulty_prompt": "Choose the difficulty:",
        "count": "How many questions would you like?",
        "generating": "⏳ Preparing your quiz. This may take a little while...",
        "error": "I couldn't prepare a valid quiz this time. Please try again.",
        "rate_limited": "The AI request limit has been reached temporarily. Please wait a little and pick a question count again.",
        "question": "Question",
        "correct": "Correct!",
        "incorrect": "Not quite.",
        "answer": "Correct answer",
        "score": "Quiz completed!",
        "saved": "Your result has been saved.",
        "cancel": "Quiz cancelled. You can start another one from Study & Learn.",
        "expired": "This quiz session has expired. Start a new quiz from Study & Learn.",
        "difficulty": {"beginner": "Beginner", "intermediate": "Intermediate", "advanced": "Advanced"},
    },
    "am": {
        "choose_subject": "የትምህርት ዘርፍ ይምረጡ፦",
        "topic": "ልምምድ ማድረግ የሚፈልጉትን ርዕስ ያስገቡ። ለምሳሌ፦ የኒውተን የእንቅስቃሴ ሕጎች።",
        "difficulty_prompt": "የጥያቄዎችን ደረጃ ይምረጡ፦",
        "count": "ስንት ጥያቄዎች ይፈልጋሉ?",
        "generating": "⏳ የፈተና ጥያቄዎችዎን እያዘጋጀሁ ነው...",
        "error": "በዚህ ጊዜ ጥያቄዎቹን ማዘጋጀት አልቻልኩም። እባክዎ እንደገና ይሞክሩ።",
        "rate_limited": "የAI ጥያቄ ገደብ ለጊዜው ደርሷል። እባክዎ ትንሽ ቆይተው የጥያቄዎች ቁጥር እንደገና ይምረጡ።",
        "question": "ጥያቄ",
        "correct": "ትክክል ነው!",
        "incorrect": "ትክክል አይደለም።",
        "answer": "ትክክለኛው መልስ",
        "score": "ፈተናው ተጠናቋል!",
        "saved": "ውጤትዎ ተቀምጧል።",
        "cancel": "ፈተናው ተሰርዟል። ከትምህርት ምናሌው እንደገና መጀመር ይችላሉ።",
        "expired": "የፈተና ክፍለ-ጊᜱ አብቅቷል። ከትምህርት ምናሌው አዲስ ፈተና ይጀምሩ።",
        "difficulty": {"beginner": "ጀማሪ", "intermediate": "መካከለኛ", "advanced": "ከፍተኛ"},
    },
    "om": {
        "choose_subject": "Mata duree filadhu:",
        "topic": "Mata duree shaakaluu barbaaddu galchi. Fakkeenyaaf: Seerota Sochii Newton.",
        "difficulty_prompt": "Sadarkaa rakkinaa filadhu:",
        "count": "Gaaffii meeqa barbaadda?",
        "generating": "⏳ Gaaffii qormaataa qopheessaa jira...",
        "error": "Yeroo kana qormaata qopheessuu hin dandeenye. Maaloo irra deebi'i.",
        "rate_limited": "Daangaan gaaffii AI yeroo ammaa ga'ameera. Maaloo yeroo muraasa eeggadhuutii lakkoofsa gaaffii irra deebi'aa filadhu.",
        "question": "Gaaffii",
        "correct": "Sirrii dha!",
        "incorrect": "Sirrii miti.",
        "answer": "Deebii sirrii",
        "score": "Qormaanni xumurame!",
        "saved": "Bu'aan kee olkaa'ameera.",
        "cancel": "Qormaanni haqameera. Menuu Barachuu fi Barnootaa irraa jalqabuu dandeessa.",
        "expired": "Sadarkaan qormaatichii dhumaate. Menuu barnootaa irraa qormaata haaraa jalqabi.",
        "difficulty": {"beginner": "Jalqabaa", "intermediate": "Giddugaleessa", "advanced": "Olaanaa"},
    },
}


def localized_language(user_id):
    language = get_language(user_id)
    return language if language in TEXT else "en"


def subject_keyboard(language):
    labels = SUBJECT_LABELS[language]
    keys = list(SUBJECTS)
    rows = []

    for index in range(0, len(keys), 2):
        rows.append([
            InlineKeyboardButton(
                text=labels[key],
                callback_data=f"qz:subject:{key}",
            )
            for key in keys[index:index + 2]
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def difficulty_keyboard(language):
    labels = TEXT[language]["difficulty"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=labels[key],
                callback_data=f"qz:difficulty:{key}",
            )
        ]
        for key in ("beginner", "intermediate", "advanced")
    ])


def count_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=str(count), callback_data=f"qz:count:{count}")
            for count in (5, 10, 15)
        ]
    ])


def question_keyboard(question):
    letters = ("A", "B", "C", "D")
    rows = []

    for index, option in enumerate(question["options_en"]):
        label = f"{letters[index]}. {option}"
        rows.append([
            InlineKeyboardButton(
                text=label[:60],
                callback_data=f"qz:answer:{index}",
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_question(question, number, total):
    return (
        f"<b>Question {number}/{total}</b>\n\n"
        f"<b>{html.escape(question['question_en'])}</b>\n\n"
        f"<i>{html.escape(question['question_am'])}</i>\n\n"
        "<b>Choose your answer:</b>"
    )


def render_feedback(question, selected_index, language):
    letters = ("A", "B", "C", "D")
    correct_index = question["correct_index"]
    result = TEXT[language]["correct"] if selected_index == correct_index else TEXT[language]["incorrect"]

    return (
        f"<b>{result}</b>\n\n"
        f"<b>{TEXT[language]['answer']}: "
        f"{letters[correct_index]}. {html.escape(question['options_en'][correct_index])}</b>\n\n"
        f"<b>Explanation:</b>\n{html.escape(question['explanation_en'])}\n\n"
        f"<b>ማብራሪያ:</b>\n{html.escape(question['explanation_am'])}"
    )


async def show_question(message, state, language):
    data = await state.get_data()
    index = data["current_index"]
    questions = data["questions"]
    question = questions[index]

    await state.update_data(answered=False)

    await message.answer(
        render_question(question, index + 1, len(questions)),
        reply_markup=question_keyboard(question),
        parse_mode="HTML",
    )


async def finish_quiz(message, state, language, telegram_id):
    data = await state.get_data()
    total = data["current_index"] + 1
    correct = data["correct_answers"]

    save_quiz_result(
        telegram_id=telegram_id,
        subject=data["subject"],
        topic=data["topic"],
        difficulty=data["difficulty"],
        total_questions=total,
        correct_answers=correct,
    )

    percentage = round(correct / total * 100, 1)

    await message.answer(
        f"<b>{TEXT[language]['score']}</b>\n\n"
        f"Score: <b>{correct}/{total}</b> ({percentage}%)\n"
        f"{TEXT[language]['saved']}",
        parse_mode="HTML",
        reply_markup=study_menu(language),
    )
    await state.clear()


@router.message(F.text.in_(list(STUDY_QUIZ_BUTTONS.values())))
async def start_quiz(message: Message, state: FSMContext):
    language = localized_language(message.from_user.id)
    await state.clear()
    await state.set_state(QuizStates.choosing_subject)

    await message.answer(
        TEXT[language]["choose_subject"],
        reply_markup=subject_keyboard(language),
    )


@router.callback_query(
    QuizStates.choosing_subject,
    F.data.startswith("qz:subject:"),
)
async def select_subject(callback: CallbackQuery, state: FSMContext):
    language = localized_language(callback.from_user.id)
    subject_key = callback.data.rsplit(":", 1)[-1]

    if subject_key not in SUBJECTS:
        await callback.answer("Invalid subject.", show_alert=True)
        return

    await state.update_data(subject=SUBJECTS[subject_key])
    await state.set_state(QuizStates.entering_topic)

    await callback.answer()
    await callback.message.answer(TEXT[language]["topic"])


@router.message(QuizStates.entering_topic, F.text)
async def receive_topic(message: Message, state: FSMContext):
    language = localized_language(message.from_user.id)
    topic = message.text.strip()

    if not topic or len(topic) > 150:
        await message.answer("Please enter a topic between 1 and 150 characters.")
        return

    await state.update_data(topic=topic)
    await state.set_state(QuizStates.choosing_difficulty)

    await message.answer(
        TEXT[language]["difficulty_prompt"],
        reply_markup=difficulty_keyboard(language),
    )


@router.callback_query(
    QuizStates.choosing_difficulty,
    F.data.startswith("qz:difficulty:"),
)
async def select_difficulty(callback: CallbackQuery, state: FSMContext):
    language = localized_language(callback.from_user.id)
    difficulty = callback.data.rsplit(":", 1)[-1]

    if difficulty not in ("beginner", "intermediate", "advanced"):
        await callback.answer("Invalid difficulty.", show_alert=True)
        return

    await state.update_data(difficulty=difficulty)
    await state.set_state(QuizStates.choosing_count)

    await callback.answer()
    await callback.message.answer(
        TEXT[language]["count"],
        reply_markup=count_keyboard(),
    )


@router.callback_query(
    QuizStates.choosing_count,
    F.data.startswith("qz:count:"),
)
async def select_count(callback: CallbackQuery, state: FSMContext):
    language = localized_language(callback.from_user.id)

    try:
        count = int(callback.data.rsplit(":", 1)[-1])
    except ValueError:
        await callback.answer("Invalid question count.", show_alert=True)
        return

    if count not in (5, 10, 15):
        await callback.answer("Invalid question count.", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(TEXT[language]["generating"])

    data = await state.get_data()

    try:
        questions = await generate_quiz(
            subject=data["subject"],
            topic=data["topic"],
            difficulty=data["difficulty"],
            count=count,
        )
    except AIRateLimited:
        # FSM state is preserved so the user can pick a count again
        # once the temporary limit clears.
        logger.warning(
            "Quiz generation rate limited for user %s",
            callback.from_user.id
        )
        await callback.message.answer(TEXT[language]["rate_limited"])
        return
    except Exception:
        logger.exception("Quiz generation failed for user %s", callback.from_user.id)
        await state.clear()
        await callback.message.answer(
            TEXT[language]["error"],
            reply_markup=study_menu(language),
        )
        return

    await state.update_data(
        questions=questions,
        current_index=0,
        correct_answers=0,
        answered=False,
    )
    await state.set_state(QuizStates.answering)

    await show_question(callback.message, state, language)


@router.callback_query(
    QuizStates.answering,
    F.data.startswith("qz:answer:"),
)
async def answer_question(callback: CallbackQuery, state: FSMContext):
    language = localized_language(callback.from_user.id)
    data = await state.get_data()

    if data.get("answered"):
        await callback.answer("You have already answered this question.")
        return

    try:
        selected = int(callback.data.rsplit(":", 1)[-1])
    except ValueError:
        await callback.answer("Invalid answer.", show_alert=True)
        return

    if selected not in range(4):
        await callback.answer("Invalid answer.", show_alert=True)
        return

    index = data["current_index"]
    question = data["questions"][index]
    correct = data["correct_answers"]

    if selected == question["correct_index"]:
        correct += 1

    await state.update_data(
        answered=True,
        correct_answers=correct,
    )

    await callback.answer()

    feedback = render_feedback(question, selected, language)
    total = len(data["questions"])

    if index + 1 < total:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="Next question ➡️",
                callback_data="qz:next",
            )
        ]])
    else:
        keyboard = None

    try:
        await callback.message.edit_text(
            feedback,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        # The feedback edit can fail (e.g. the message was deleted or the
        # content is unchanged). Scoring must still complete, so the
        # failure is swallowed and finish_quiz runs either way.
        logger.info(
            "Quiz feedback edit skipped for user %s",
            callback.from_user.id
        )

    if index + 1 == total:
        await finish_quiz(callback.message, state, language, callback.from_user.id)


@router.callback_query(
    QuizStates.answering,
    F.data == "qz:next",
)
async def next_question(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if not data.get("answered"):
        await callback.answer("Answer the current question first.")
        return

    next_index = data["current_index"] + 1

    if next_index >= len(data["questions"]):
        await callback.answer()
        return

    await state.update_data(
        current_index=next_index,
        answered=False,
    )

    await callback.answer()
    await show_question(callback.message, state, localized_language(callback.from_user.id))


@router.callback_query(F.data.startswith("qz:"))
async def stale_quiz_callback(callback: CallbackQuery, state: FSMContext):
    """Answer quiz callbacks whose session no longer exists.

    Registered last so every state-specific handler keeps priority.
    Only fires when no active quiz handler matched (state cleared/none).
    """
    data = await state.get_data()

    if data.get("questions"):
        # An active quiz exists; do not mask it with the expiry message.
        await callback.answer()
        return

    language = localized_language(callback.from_user.id)
    await callback.answer(TEXT[language]["expired"], show_alert=True)
