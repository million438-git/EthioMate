from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


LANGUAGE_NAMES = {
    "am": "አማርኛ",
    "en": "English",
    "om": "Afaan Oromo"
}


# Only categories backed by existing working functionality are active.
MAIN_BUTTONS = {
    "am": [
        ["🤖 የAI ረዳት"],
        ["📚 ትምህርት እና መማር"],
        ["🌐 ቋንቋዎች", "💼 ንግድ እና ገንዘብ"],
        ["👤 የእኔ መለያ", "🌍 ቋንቋ ቀይር"]
    ],
    "en": [
        ["🤖 AI Assistant"],
        ["📚 Study & Learn"],
        ["🌐 Languages", "💼 Business & Money"],
        ["👤 My Account", "🌍 Change Language"]
    ],
    "om": [
        ["🤖 Gargaaraa AI"],
        ["📚 Barachuu fi Barnoota"],
        ["🌐 Afaanota", "💼 Daldalaa fi Maallaqa"],
        ["👤 Herrega Koo", "🌍 Afaan jijjiiri"]
    ]
}


LANGUAGE_MENU_BUTTONS = {
    "am": [
        ["🌐 ቋንቋ ተርጉም"],
        ["⬅️ ወደ ዋና ምናሌ"]
    ],
    "en": [
        ["🌐 Translation"],
        ["⬅️ Main Menu"]
    ],
    "om": [
        ["🌐 Hiikkaa"],
        ["⬅️ Gara Menuu"]
    ]
}


BUSINESS_MENU_BUTTONS = {
    "am": [
        ["🧮 የሂሳብ አስሊ"],
        ["⬅️ ወደ ዋና ምናሌ"]
    ],
    "en": [
        ["🧮 Calculators"],
        ["⬅️ Main Menu"]
    ],
    "om": [
        ["🧮 Herrega"],
        ["⬅️ Gara Menuu"]
    ]
}


CALCULATOR_BUTTONS = {
    "am": [
        ["💰 ትርፍ / ኪሳራ", "📊 መቶኛ"],
        ["🏷️ ቅናሽ", "🧾 ወጪዎች"],
        ["⬅️ ወደ ዋና ምናሌ"]
    ],
    "en": [
        ["💰 Profit / Loss", "📊 Percentage"],
        ["🏷️ Discount", "🧾 Expenses"],
        ["⬅️ Main Menu"]
    ],
    "om": [
        ["💰 Bu'aa / Kasaaraa", "📊 Dhibbeentaa"],
        ["🏷️ Hir'ina Gatii", "🧾 Baasii"],
        ["⬅️ Gara Menuu"]
    ]
}


BACK_BUTTONS = {
    "am": "⬅️ ወደ ዋና ምናሌ",
    "en": "⬅️ Main Menu",
    "om": "⬅️ Gara Menuu"
}


def build_keyboard(buttons):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=text) for text in row]
            for row in buttons
        ],
        resize_keyboard=True,
        is_persistent=True
    )


def language_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="አማርኛ"),
                KeyboardButton(text="English")
            ],
            [KeyboardButton(text="Afaan Oromo")]
        ],
        resize_keyboard=True
    )


def main_menu(language="en"):
    return build_keyboard(
        MAIN_BUTTONS.get(language, MAIN_BUTTONS["en"])
    )


def language_menu(language="en"):
    return build_keyboard(
        LANGUAGE_MENU_BUTTONS.get(
            language, LANGUAGE_MENU_BUTTONS["en"]
        )
    )


def business_menu(language="en"):
    return build_keyboard(
        BUSINESS_MENU_BUTTONS.get(
            language, BUSINESS_MENU_BUTTONS["en"]
        )
    )


def calculator_menu(language="en"):
    return build_keyboard(
        CALCULATOR_BUTTONS.get(
            language, CALCULATOR_BUTTONS["en"]
        )
    )


# Navigation labels are centralized so active workflows can return home.
MAIN_MENU_NAV_LABELS = {
    button
    for rows in MAIN_BUTTONS.values()
    for row in rows
    for button in row
}

MAIN_MENU_NAV_LABELS.update(
    button
    for language, rows in LANGUAGE_MENU_BUTTONS.items()
    for row in rows
    for button in row
    if button == BACK_BUTTONS[language]
)

MAIN_MENU_NAV_LABELS.update(
    button
    for language, rows in BUSINESS_MENU_BUTTONS.items()
    for row in rows
    for button in row
    if button == BACK_BUTTONS[language]
)


STUDY_MENU_BUTTONS = {
    "am": [
        ["🎓 አካዳሚ"],
        ["📖 AI አስተማሪ"],
        ["📝 የፈተና ጥያቄ ፈጣሪ"],
        ["⬅️ ወደ ዋና ምናሌ"]
    ],
    "en": [
        ["🎓 Academy"],
        ["📖 AI Tutor"],
        ["📝 Quiz Generator"],
        ["⬅️ Main Menu"]
    ],
    "om": [
        ["🎓 Academy Barnootaa"],
        ["📖 Barsiisaa AI"],
        ["📝 Uumaa Gaaffii Qormaataa"],
        ["⬅️ Gara Menuu"]
    ]
}


STUDY_ACADEMY_BUTTONS = {
    "am": "🎓 አካዳሚ",
    "en": "🎓 Academy",
    "om": "🎓 Academy Barnootaa"
}


STUDY_BUTTONS = {
    "am": "📚 ትምህርት እና መማር",
    "en": "📚 Study & Learn",
    "om": "📚 Barachuu fi Barnoota"
}


STUDY_TUTOR_BUTTONS = {
    "am": "📖 AI አስተማሪ",
    "en": "📖 AI Tutor",
    "om": "📖 Barsiisaa AI"
}



STUDY_QUIZ_BUTTONS = {
    "am": "📝 የፈተና ጥያቄ ፈጣሪ",
    "en": "📝 Quiz Generator",
    "om": "📝 Uumaa Gaaffii Qormaataa"
}


def study_menu(language="en"):
    return build_keyboard(
        STUDY_MENU_BUTTONS.get(
            language, STUDY_MENU_BUTTONS["en"]
        )
    )
