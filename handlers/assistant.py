
import logging

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database.db import get_language
from keyboards.menus import main_menu
from services.ai_assistant import generate_reply, AIRateLimited
from services.telegram_formatting import format_telegram_html


logger = logging.getLogger(__name__)

router = Router()


class AssistantStates(StatesGroup):
    chatting = State()


ASSISTANT_BUTTONS = {
    "am": "🤖 የAI ረዳት",
    "en": "🤖 AI Assistant",
    "om": "🤖 Gargaaraa AI"
}


WELCOME_MESSAGES = {
    "am": (
        "🤖 ወደ EthioMate AI ረዳት እንኳን በደህና መጡ!\n\n"
        "ጥያቄዎን በአማርኛ ወይም በእንግሊዝኛ ይጠይቁ።\n"
        "ስለ ትምህርት፣ ቴክኖሎጂ፣ ንግድ እና ሌሎች ጉዳዮች "
        "ማውራት ይችላሉ።\n\n"
        "/newchat - አዲስ ውይይት\n"
        "/exit - ወደ ዋና ምናሌ ለመመለስ"
    ),
    "en": (
        "🤖 Welcome to EthioMate AI Assistant!\n\n"
        "Ask me questions about education, technology, business, "
        "programming and everyday life.\n"
        "You can communicate in English or Amharic.\n\n"
        "/newchat - Start a fresh conversation\n"
        "/exit - Return to the main menu"
    ),
    "om": (
        "🤖 Gara Gargaaraa AI EthioMate baga nagaan dhuftan!\n\n"
        "Waa'ee barnootaa, teeknooloojii, daldalaa fi jireenya "
        "guyyaa guyyaa na gaafachuu dandeessu.\n\n"
        "/newchat - Haasaa haaraa jalqabi\n"
        "/exit - Gara menuu isa guddaatti deebi'i"
    )
}


PROCESSING_MESSAGES = {
    "am": "⏳ ጥያቄዎን እያዘጋጀሁ ነው...",
    "en": "⏳ Thinking...",
    "om": "⏳ Deebii qopheessaa jira..."
}


ERROR_MESSAGES = {
    "am": (
        "ይቅርታ፣ አሁን ምላሽ ማግኘት አልቻልኩም። "
        "እባክዎ ትንሽ ቆይተው ይሞክሩ።"
    ),
    "en": (
        "Sorry, I couldn't generate a response right now. "
        "Please try again shortly."
    ),
    "om": (
        "Dhiifama, amma deebii kennuu hin dandeenye. "
        "Maaloo yeroo muraasa booda irra deebi'aa yaalaa."
    )
}


BUSY_MESSAGES = {
    "am": "የAI ጥያቄ ገደብ ለጊዜው ደርሷል። እባክዎ ትንሽ ቆይተው ይሞክሩ።",
    "en": "The AI request limit has been reached temporarily. Please wait a little and try again.",
    "om": "Daangaan gaaffii AI yeroo ammaa ga'ameera. Maaloo yeroo muraasa eeggadhuutii irra deebi'aa yaalaa."
}


EXIT_MESSAGES = {
    "am": "ወደ ዋናው ምናሌ ተመልሰዋል።",
    "en": "You have returned to the main menu.",
    "om": "Gara menuu isa guddaatti deebitaniittu."
}


def split_message(text, limit=4000):
    """Split long AI responses into Telegram-safe messages."""

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


@router.message(F.text.in_(list(ASSISTANT_BUTTONS.values())))
async def open_assistant(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)

    await state.clear()
    await state.set_state(AssistantStates.chatting)
    await state.update_data(history=[])

    await message.answer(WELCOME_MESSAGES[language])


@router.message(Command("newchat"))
async def new_chat(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)

    await state.set_state(AssistantStates.chatting)
    await state.update_data(history=[])

    messages = {
        "am": "አዲስ ውይይት ተጀምሯል። ጥያቄዎን ይጠይቁ።",
        "en": "A new conversation has started. Ask your question.",
        "om": "Haasaan haaraan jalqabameera. Gaaffii kee gaafadhu."
    }

    await message.answer(messages[language])


@router.message(Command("exit"))
async def exit_assistant(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)

    await state.clear()

    await message.answer(
        EXIT_MESSAGES[language],
        reply_markup=main_menu(language)
    )


@router.message(AssistantStates.chatting, F.text)
async def process_ai_message(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)

    question = message.text.strip()

    if not question:
        return

    data = await state.get_data()
    history = data.get("history", [])

    history.append({
        "role": "user",
        "parts": [{"text": question}]
    })

    status_message = await message.answer(
        PROCESSING_MESSAGES[language]
    )

    try:
        answer = await generate_reply(
            history=history,
            language=language
        )

        history.append({
            "role": "model",
            "parts": [{"text": answer}]
        })

        # Keep the most recent six conversation exchanges.
        history = history[-12:]

        await state.update_data(history=history)

        await status_message.delete()

        for chunk in split_message(answer):
            await message.answer(
                format_telegram_html(chunk),
                parse_mode=ParseMode.HTML
            )

    except AIRateLimited:
        logger.warning(
            "AI assistant rate limited for user %s",
            message.from_user.id
        )

        # FSM state and history are intentionally preserved so the user
        # can simply send their question again.
        await status_message.edit_text(BUSY_MESSAGES[language])

    except Exception:
        logger.exception(
            "AI assistant request failed for user %s",
            message.from_user.id
        )

        await status_message.edit_text(
            ERROR_MESSAGES[language]
        )


@router.message(AssistantStates.chatting)
async def unsupported_ai_message(message: Message):
    language = get_language(message.from_user.id)

    messages = {
        "am": "እባክዎ የጽሑፍ ጥያቄ ይላኩልኝ።",
        "en": "Please send your question as text.",
        "om": "Maaloo gaaffii kee barreeffamaan ergi."
    }

    await message.answer(messages[language])
