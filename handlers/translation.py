import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from database.db import get_language
from keyboards.menus import MAIN_BUTTONS, main_menu
from services.translation import translate_text
from services.ai_assistant import AIRateLimited, AITransient
from google.genai.errors import ClientError, ServerError


logger = logging.getLogger(__name__)

router = Router()


class TranslationStates(StatesGroup):
    choosing_target = State()
    waiting_for_text = State()


TRANSLATION_BUTTONS = {
    "am": "🌐 ቋንቋ ተርጉም",
    "en": "🌐 Translation",
    "om": "🌐 Hiikkaa"
}


TARGET_MESSAGES = {
    "am": "ወደ የትኛው ቋንቋ መተርጎም ይፈልጋሉ?",
    "en": "Which language would you like to translate into?",
    "om": "Gara afaan kamiitti hiikuu barbaadda?"
}


LANGUAGE_LABELS = {
    "am": {
        "am": "አማርኛ",
        "en": "እንግሊዝኛ",
        "om": "አፋን ኦሮሞ"
    },
    "en": {
        "am": "Amharic",
        "en": "English",
        "om": "Afaan Oromo"
    },
    "om": {
        "am": "Afaan Amaaraa",
        "en": "English",
        "om": "Afaan Oromo"
    }
}


INPUT_PROMPTS = {
    "am": "እባክዎ ሊተረጉሙት የሚፈልጉትን ጽሑፍ ይላኩ።\n/cancel - ለመውጣት",
    "en": "Send the text you want translated.\n/cancel - Cancel translation",
    "om": "Maaloo barruu hiikuu barbaaddu ergi.\n/cancel - Haquuf"
}


ERROR_MESSAGES = {
    "am": "ይቅርታ፣ ትርጉሙን ማግኘት አልቻልኩም። እባክዎ እንደገና ይሞክሩ።",
    "en": "Sorry, translation failed. Please try again.",
    "om": "Dhiifama, hiikkaan hin milkoofne. Maaloo irra deebi'ii yaali."
}


TEMPORARY_ERROR_MESSAGES = {
    "am": "የትርጉም አገልግሎቱ ለጊዜው በሥራ መጨናነቅ ምክንያት አይገኝም። እባክዎ ትንሽ ቆይተው ይሞክሩ።",
    "en": "The translation service is temporarily busy or unavailable. Please try again shortly.",
    "om": "Tajaajilli hiikkaa yeroo ammaa hojii baay'een qabameera ykn hin jiru. Maaloo yeroo muraasa booda irra deebi'ii yaali."
}


RATE_LIMIT_MESSAGES = {
    "am": "የAI ጥያቄ ገደብ ለጊዜው ደርሷል። እባክዎ ትንሽ ቆይተው ይሞክሩ።",
    "en": "The AI request limit has been reached temporarily. Please wait a little and try again.",
    "om": "Daangaan gaaffii AI yeroo ammaa ga'ameera. Maaloo yeroo muraasa eeggadhuutii irra deebi'ii yaali."
}


PROCESSING_MESSAGES = {
    "am": "⏳ ጽሑፉን እየተረጎምኩ ነው...",
    "en": "⏳ Translating your text...",
    "om": "⏳ Barruu hiikaa jira..."
}


MAIN_MENU_LABELS = {
    button
    for rows in MAIN_BUTTONS.values()
    for row in rows
    for button in row
}


def build_target_keyboard(language):
    labels = LANGUAGE_LABELS[language]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=labels["am"],
                    callback_data="translation:am"
                )
            ],
            [
                InlineKeyboardButton(
                    text=labels["en"],
                    callback_data="translation:en"
                )
            ],
            [
                InlineKeyboardButton(
                    text=labels["om"],
                    callback_data="translation:om"
                )
            ]
        ]
    )


def split_message(text, limit=4000):
    chunks = []

    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)

        if split_at < limit // 2:
            split_at = text.rfind(" ", 0, limit)

        if split_at < 1:
            split_at = limit

        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()

    if text:
        chunks.append(text)

    return chunks


@router.message(F.text.in_(list(TRANSLATION_BUTTONS.values())))
async def open_translation(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)

    await state.clear()
    await state.set_state(TranslationStates.choosing_target)

    await message.answer(
        TARGET_MESSAGES[language],
        reply_markup=build_target_keyboard(language)
    )


@router.callback_query(
    TranslationStates.choosing_target,
    F.data.startswith("translation:")
)
async def choose_target(callback: CallbackQuery, state: FSMContext):
    language = get_language(callback.from_user.id)
    target_language = callback.data.split(":", 1)[1]

    if target_language not in LANGUAGE_LABELS["en"]:
        await callback.answer("Unsupported language.", show_alert=True)
        return

    await state.update_data(target_language=target_language)
    await state.set_state(TranslationStates.waiting_for_text)

    await callback.answer()

    await callback.message.answer(
        INPUT_PROMPTS[language]
    )


@router.message(TranslationStates.waiting_for_text, F.text)
async def process_translation(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)

    if message.text in MAIN_MENU_LABELS:
        await state.clear()

        await message.answer(
            "Please select the menu option again.",
            reply_markup=main_menu(language)
        )
        return

    text = message.text.strip()

    if not text:
        return

    data = await state.get_data()
    target_language = data.get("target_language")

    status = await message.answer(
        PROCESSING_MESSAGES[language]
    )

    try:
        result = await translate_text(
            text=text,
            target_language=target_language
        )

        await state.set_state(TranslationStates.waiting_for_text)

        try:
            await status.delete()
        except Exception:
            logger.warning("Could not delete translation status message.")

        for chunk in split_message(result):
            await message.answer(chunk)

        await message.answer(
            {
                "am": "ሌላ ጽሑፍ ለመተርጎም ይላኩ። /cancel - ወደ ምናሌ",
                "en": "Send another text to translate. /cancel - Main menu",
                "om": "Barruu biraa ergi. /cancel - Menuu"
            }[language],
            reply_markup=main_menu(language)
        )

    except AIRateLimited:
        logger.warning(
            "Translation rate limited for user %s",
            message.from_user.id
        )
        await status.edit_text(RATE_LIMIT_MESSAGES[language])

    except AITransient:
        logger.warning(
            "Translation service unavailable for user %s (after retry)",
            message.from_user.id
        )
        await status.edit_text(TEMPORARY_ERROR_MESSAGES[language])

    except ServerError as exc:
        logger.warning(
            "Gemini server error during translation for user %s: HTTP %s",
            message.from_user.id,
            getattr(exc, "status", "unknown")
        )
        await status.edit_text(TEMPORARY_ERROR_MESSAGES[language])

    except ClientError as exc:
        status_code = getattr(exc, "status", None)

        logger.warning(
            "Gemini client error during translation for user %s: HTTP %s",
            message.from_user.id,
            status_code
        )

        if status_code == 429:
            await status.edit_text(RATE_LIMIT_MESSAGES[language])
        else:
            await status.edit_text(ERROR_MESSAGES[language])

    except Exception:
        logger.exception(
            "Translation failed for user %s",
            message.from_user.id
        )

        await status.edit_text(ERROR_MESSAGES[language])


@router.message(TranslationStates.waiting_for_text)
async def unsupported_translation_input(message: Message):
    language = get_language(message.from_user.id)

    await message.answer(
        {
            "am": "እባክዎ ጽሑፍ ይላኩ።",
            "en": "Please send text to translate.",
            "om": "Maaloo barruu ergi."
        }[language]
    )
