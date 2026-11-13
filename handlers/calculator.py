from aiogram import Router, F
from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database.db import get_language
from keyboards.menus import main_menu, calculator_menu
from services.calculator import (
    parse_numbers,
    format_money,
    calculate_profit,
    calculate_percentage,
    calculate_discount,
    calculate_expenses
)


router = Router()


class CalculatorStates(StatesGroup):
    waiting_for_values = State()


CALCULATOR_MENU_BUTTONS = {
    "am": "🧮 የሂሳብ አስሊ",
    "en": "🧮 Calculators",
    "om": "🧮 Herrega"
}


CALCULATOR_OPTIONS = {
    "am": {
        "💰 ትርፍ / ኪሳራ": "profit",
        "📊 መቶኛ": "percentage",
        "🏷️ ቅናሽ": "discount",
        "🧾 ወጪዎች": "expenses"
    },
    "en": {
        "💰 Profit / Loss": "profit",
        "📊 Percentage": "percentage",
        "🏷️ Discount": "discount",
        "🧾 Expenses": "expenses"
    },
    "om": {
        "💰 Bu'aa / Kasaaraa": "profit",
        "📊 Dhibbeentaa": "percentage",
        "🏷️ Hir'ina Gatii": "discount",
        "🧾 Baasii": "expenses"
    }
}


BACK_BUTTONS = {
    "⬅️ ወደ ዋና ምናሌ",
    "⬅️ Main Menu",
    "⬅️ Gara Menuu"
}


PROMPTS = {
    "am": {
        "profit": (
            "የግዢ ዋጋን እና የሽያጭ ዋጋን በቅደም ተከተል ያስገቡ።\n"
            "ምሳሌ፦ 1000 1250"
        ),
        "percentage": (
            "መጠኑን እና መቶኛውን ያስገቡ።\n"
            "ምሳሌ፦ 1000 15"
        ),
        "discount": (
            "የመጀመሪያ ዋጋን እና የቅናሽ መቶኛን ያስገቡ።\n"
            "ምሳሌ፦ 2000 10"
        ),
        "expenses": (
            "ወጪዎችዎን በክፍተት ይለዩ።\n"
            "ምሳሌ፦ 100 250 300 150"
        )
    },
    "en": {
        "profit": (
            "Enter purchase cost and selling price, in that order.\n"
            "Example: 1000 1250"
        ),
        "percentage": (
            "Enter amount and percentage.\n"
            "Example: 1000 15"
        ),
        "discount": (
            "Enter original price and discount percentage.\n"
            "Example: 2000 10"
        ),
        "expenses": (
            "Enter your expenses separated by spaces.\n"
            "Example: 100 250 300 150"
        )
    },
    "om": {
        "profit": (
            "Gatii bittaa fi gatii gurgurtaa tartiibaan galchi.\n"
            "Fakkeenya: 1000 1250"
        ),
        "percentage": (
            "Hamma fi dhibbeentaa galchi.\n"
            "Fakkeenya: 1000 15"
        ),
        "discount": (
            "Gatii jalqabaa fi dhibbeentaa hir'inaa galchi.\n"
            "Fakkeenya: 2000 10"
        ),
        "expenses": (
            "Baasii kee addaan qooduun galchi.\n"
            "Fakkeenya: 100 250 300 150"
        )
    }
}


ERROR_MESSAGES = {
    "am": "የተሳሳተ ግቤት ነው። እባክዎ ቁጥሮቹን እንደገና ያስገቡ።",
    "en": "Invalid input. Please enter the numbers again.",
    "om": "Galteen sirrii miti. Maaloo lakkoofsota irra deebi'ii galchi."
}


CANCEL_MESSAGES = {
    "am": "ወደ ዋናው ምናሌ ተመልሰዋል።",
    "en": "You have returned to the main menu.",
    "om": "Gara menuu isa guddaatti deebiteetta."
}


def result_text(language, calculator, values):
    """Create a localized calculation result."""

    if language == "am":
        if calculator == "profit":
            result = calculate_profit(*values)

            labels = {
                "profit": "ትርፍ",
                "loss": "ኪሳራ",
                "break_even": "ትርፍም ኪሳራም የለም"
            }

            return (
                f"📊 የሂሳብ ውጤት\n\n"
                f"ውጤት: {labels[result['status']]}\n"
                f"መጠን: {format_money(abs(result['difference']))}\n"
                f"የትርፍ ህዳግ: {result['margin']:.2f}%\n"
                f"Markup: {result['markup']:.2f}%"
            )

        if calculator == "percentage":
            value = calculate_percentage(*values)
            return (
                f"📊 የመቶኛ ውጤት\n\n"
                f"ውጤት: {format_money(value)}"
            )

        if calculator == "discount":
            result = calculate_discount(*values)
            return (
                f"🏷️ የቅናሽ ውጤት\n\n"
                f"የቅናሽ መጠን: {format_money(result['savings'])}\n"
                f"የመጨረሻ ዋጋ: {format_money(result['final_price'])}"
            )

        if calculator == "expenses":
            result = calculate_expenses(values)
            return (
                f"🧾 የወጪ ሪፖርት\n\n"
                f"ጠቅላላ ወጪ: {format_money(result['total'])}\n"
                f"አማካይ ወጪ: {format_money(result['average'])}\n"
                f"የወጪ ብዛት: {result['count']}"
            )

    elif language == "om":
        if calculator == "profit":
            result = calculate_profit(*values)

            labels = {
                "profit": "Bu'aa",
                "loss": "Kasaaraa",
                "break_even": "Bu'aa fi kasaaraa hin qabu"
            }

            return (
                f"📊 Bu'aa Herregaa\n\n"
                f"Haala: {labels[result['status']]}\n"
                f"Hammi: {format_money(abs(result['difference']))}\n"
                f'Profit margin: {result["margin"]:.2f}%\n'
                f'Markup: {result["markup"]:.2f}%'
            )

        if calculator == "percentage":
            value = calculate_percentage(*values)
            return f"📊 Bu'aan: {format_money(value)}"

        if calculator == "discount":
            result = calculate_discount(*values)
            return (
                f"🏷️ Bu'aa Hir'ina Gatii\n\n"
                f"Hir'inni: {format_money(result['savings'])}\n"
                f"Gatiin dhumaa: {format_money(result['final_price'])}"
            )

        if calculator == "expenses":
            result = calculate_expenses(values)
            return (
                f"🧾 Gabaasa Baasii\n\n"
                f"Ida'ama: {format_money(result['total'])}\n"
                f"Giddugaleessa: {format_money(result['average'])}\n"
                f"Baay'ina: {result['count']}"
            )

    else:
        if calculator == "profit":
            result = calculate_profit(*values)

            labels = {
                "profit": "Profit",
                "loss": "Loss",
                "break_even": "Break-even"
            }

            return (
                f"📊 Calculation Result\n\n"
                f"Status: {labels[result['status']]}\n"
                f"Amount: {format_money(abs(result['difference']))}\n"
                f"Profit margin: {result['margin']:.2f}%\n"
                f"Markup: {result['markup']:.2f}%"
            )

        if calculator == "percentage":
            value = calculate_percentage(*values)
            return (
                f"📊 Percentage Result\n\n"
                f"Result: {format_money(value)}"
            )

        if calculator == "discount":
            result = calculate_discount(*values)
            return (
                f"🏷️ Discount Result\n\n"
                f"Money saved: {format_money(result['savings'])}\n"
                f"Final price: {format_money(result['final_price'])}"
            )

        if calculator == "expenses":
            result = calculate_expenses(values)
            return (
                f"🧾 Expense Report\n\n"
                f"Total expenses: {format_money(result['total'])}\n"
                f"Average expense: {format_money(result['average'])}\n"
                f"Number of expenses: {result['count']}"
            )

    raise ValueError("Unknown calculator")


@router.message(F.text.in_(list(CALCULATOR_MENU_BUTTONS.values())))
async def open_calculator(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)

    await state.clear()

    await message.answer(
        {
            "am": "የሚፈልጉትን የሂሳብ አገልግሎት ይምረጡ።",
            "en": "Choose a calculator service.",
            "om": "Tajaajila herregaa filadhu."
        }[language],
        reply_markup=calculator_menu(language)
    )


@router.message(
    F.text.in_([
        label
        for options in CALCULATOR_OPTIONS.values()
        for label in options
    ])
)
async def select_calculator(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)

    calculator = CALCULATOR_OPTIONS[language].get(message.text)

    if not calculator:
        return

    await state.update_data(calculator=calculator)
    await state.set_state(CalculatorStates.waiting_for_values)

    await message.answer(
        PROMPTS[language][calculator]
    )


@router.message(CalculatorStates.waiting_for_values)
async def process_calculation(message: Message, state: FSMContext):
    language = get_language(message.from_user.id)

    if message.text in BACK_BUTTONS:
        await state.clear()

        await message.answer(
            CANCEL_MESSAGES[language],
            reply_markup=main_menu(language)
        )
        return

    if not message.text:
        await message.answer(ERROR_MESSAGES[language])
        return

    data = await state.get_data()
    calculator = data.get("calculator")

    try:
        if calculator in ("profit", "percentage", "discount"):
            values = parse_numbers(
                message.text,
                minimum=2,
                maximum=2
            )
        elif calculator == "expenses":
            values = parse_numbers(
                message.text,
                minimum=1,
                maximum=50
            )
        else:
            raise ValueError("Unknown calculator")

        if calculator in ("profit", "percentage", "discount"):
            if any(value < 0 for value in values):
                raise ValueError("Values cannot be negative.")

        response = result_text(
            language,
            calculator,
            values
        )

    except (ValueError, ArithmeticError):
        await message.answer(
            ERROR_MESSAGES[language]
        )
        return

    await state.clear()

    await message.answer(
        response,
        reply_markup=main_menu(language)
    )
