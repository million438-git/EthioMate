
import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import BOT_TOKEN
from database.db import (
    init_db,
    register_user,
    set_language,
    get_language,
    get_user,
    get_total_users
)
from keyboards.menus import (
    language_keyboard,
    main_menu,
    language_menu,
    business_menu,
    BACK_BUTTONS
)
from handlers.calculator import router as calculator_router
from handlers.assistant import (
    router as assistant_router,
    ASSISTANT_BUTTONS,
    WELCOME_MESSAGES,
    AssistantStates
)
from handlers.translation import router as translation_router
from handlers.study import router as study_router
from handlers.quiz import router as quiz_router
from handlers.academy import router as academy_router
from keyboards.menus import study_menu, STUDY_BUTTONS
from handlers.commands import (
    router as commands_router,
    register_bot_commands,
)



logging.basicConfig(level=logging.INFO)

core_router = Router()
fallback_router = Router()


class UserActivityMiddleware(BaseMiddleware):
    """Automatically save user information on incoming messages and callback queries."""

    async def __call__(self, handler, event, data):
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user = event.from_user

            register_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name
            )

        return await handler(event, data)


@core_router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Welcome to EthioMate!\n\n"
        "ወደ EthioMate እንኳን በደህና መጡ!\n\n"
        "Choose your language / ቋንቋ ይምረጡ:",
        reply_markup=language_keyboard()
    )


@core_router.message(
    F.text.in_(["አማርኛ", "English", "Afaan Oromo"])
)
async def select_language(message: Message, state: FSMContext):
    languages = {
        "አማርኛ": "am",
        "English": "en",
        "Afaan Oromo": "om"
    }

    language = languages[message.text]

    await state.clear()

    set_language(
        message.from_user.id,
        language
    )

    greetings = {
        "am": (
            "ሰላም! ወደ EthioMate በደህና መጡ።\n"
            "ምን ልርዳዎት?"
        ),
        "en": (
            "Hello! Welcome to EthioMate.\n"
            "How can I help you?"
        ),
        "om": (
            "Akkam! Gara EthioMate dhuftan.\n"
            "Maal isin gargaaruu?"
        )
    }

    await message.answer(
        greetings[language],
        reply_markup=main_menu(language)
    )


@core_router.message(
    F.text.in_([
        "🌍 Change Language",
        "🌍 ቋንቋ ቀይር",
        "🌍 Afaan jijjiiri"
    ])
)
async def change_language(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Choose your language / ቋንቋ ይምረጡ:",
        reply_markup=language_keyboard()
    )


@core_router.message(F.text.in_(list(STUDY_BUTTONS.values())))
async def open_study_services(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)
    await state.clear()

    prompts = {
        "am": "የትምህርት አገልግሎት ይምረጡ።",
        "en": "Choose a learning service.",
        "om": "Tajaajila barnootaa filadhu."
    }

    await message.answer(
        prompts[language],
        reply_markup=study_menu(language)
    )


@core_router.message(F.text.in_(list(ASSISTANT_BUTTONS.values())))
async def open_assistant_from_menu(message: Message, state: FSMContext):
    """Open a fresh AI conversation from any active workflow."""
    language = get_language(message.from_user.id)

    await state.clear()
    await state.set_state(AssistantStates.chatting)
    await state.update_data(history=[])

    await message.answer(WELCOME_MESSAGES[language])


@core_router.message(Command("cancel"))
async def cancel_current_workflow(message: Message, state: FSMContext):
    """Return safely to the main menu from any active workflow.

    This is the single /cancel owner for every FSM state, including
    translation, calculator, assistant, study and quiz. State-specific
    /cancel handlers are intentionally absent.
    """
    language = get_language(message.from_user.id)
    await state.clear()

    messages = {
        "am": "ሂደቱ ተሰርዟል። ወደ ዋናው ምናሌ ተመልሰዋል።",
        "en": "The current operation was cancelled. You are back at the main menu.",
        "om": "Hojii amma jiru haqameera. Gara menuu isa guddaatti deebitaniittu."
    }

    await message.answer(
        messages[language],
        reply_markup=main_menu(language)
    )


@core_router.message(F.text.in_(list(BACK_BUTTONS.values())))
async def return_to_main_menu(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)
    await state.clear()

    messages = {
        "am": "ወደ ዋናው ምናሌ ተመልሰዋል።",
        "en": "You are back at the main menu.",
        "om": "Gara menuu isa guddaatti deebitaniittu."
    }

    await message.answer(
        messages[language],
        reply_markup=main_menu(language)
    )


@core_router.message(
    F.text.in_([
        "🌐 Languages",
        "🌐 ቋንቋዎች",
        "🌐 Afaanota"
    ])
)
async def open_language_services(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)
    await state.clear()

    prompts = {
        "am": "የቋንቋ አገልግሎት ይምረጡ።",
        "en": "Choose a language service.",
        "om": "Tajaajila afaanii filadhu."
    }

    await message.answer(
        prompts[language],
        reply_markup=language_menu(language)
    )


@core_router.message(
    F.text.in_([
        "💼 Business & Money",
        "💼 ንግድ እና ገንዘብ",
        "💼 Daldalaa fi Maallaqa"
    ])
)
async def open_business_services(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)
    await state.clear()

    prompts = {
        "am": "የንግድ እና የገንዘብ ስሌት አገልግሎት ይምረጡ።",
        "en": "Choose a business and finance tool.",
        "om": "Meeshaa daldalaa fi maallaqaa filadhu."
    }

    await message.answer(
        prompts[language],
        reply_markup=business_menu(language)
    )


@core_router.message(Command("profile"))
@core_router.message(
    F.text.in_([
        "👤 My Account",
        "👤 የእኔ መለያ",
        "👤 Herrega Koo"
    ])
)
async def show_profile(message: Message):
    user = get_user(message.from_user.id)
    language = get_language(message.from_user.id)

    if not user:
        await message.answer("Please use /start first.")
        return

    language_names = {
        "am": "አማርኛ",
        "en": "English",
        "om": "Afaan Oromo"
    }

    username = (
        f"@{user['username']}"
        if user["username"]
        else "Not set"
    )

    if language == "am":
        response = (
            "👤 የእኔ መለያ\n\n"
            f"ስም: {user['first_name']}\n"
            f"የቴሌግራም ስም: {username}\n"
            f"የተመረጠ ቋንቋ: {language_names[language]}\n"
            f"የተመዘገቡበት: {user['created_at'][:10]}\n"
        )

    elif language == "om":
        response = (
            "👤 Herrega Koo\n\n"
            f"Maqaa: {user['first_name']}\n"
            f"Username: {username}\n"
            f"Afaan: {language_names[language]}\n"
            f"Guyyaa galmee: {user['created_at'][:10]}"
        )

    else:
        response = (
            "👤 My Account\n\n"
            f"Name: {user['first_name']}\n"
            f"Username: {username}\n"
            f"Preferred language: {language_names[language]}\n"
            f"Registration date: {user['created_at'][:10]}"
        )

    await message.answer(
        response,
        reply_markup=main_menu(language)
    )


@fallback_router.message()
async def unknown_message(message: Message):
    language = get_language(message.from_user.id)

    responses = {
        "am": (
            "እባክዎ ከሚታዩት የምናሌ አማራጮች አንዱን ይምረጡ።"
        ),
        "en": (
            "Please select one of the available menu options."
        ),
        "om": (
            "Maaloo filannoo menuu keessaa tokko filadhaa."
        )
    }

    await message.answer(responses[language])


async def main():
    init_db()

    bot = Bot(token=BOT_TOKEN)

    try:
        await register_bot_commands(bot)
        print("Telegram command menu registered.")
    except Exception:
        logging.exception("Could not register Telegram command menu.")

    dp = Dispatcher()

    dp.message.middleware(UserActivityMiddleware())
    dp.callback_query.middleware(UserActivityMiddleware())

    dp.include_router(core_router)
    dp.include_router(commands_router)
    dp.include_router(translation_router)
    dp.include_router(calculator_router)
    dp.include_router(assistant_router)
    dp.include_router(quiz_router)
    dp.include_router(academy_router)
    dp.include_router(study_router)
    dp.include_router(fallback_router)

    print("EthioMate is starting...")
    print("SQLite database initialized.")
    print("User account system enabled.")
    print("Calculator services enabled.")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
