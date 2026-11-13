import unittest

from keyboards.menus import (
    MAIN_BUTTONS,
    LANGUAGE_MENU_BUTTONS,
    BUSINESS_MENU_BUTTONS,
    CALCULATOR_BUTTONS,
    main_menu,
    language_menu,
    business_menu,
    calculator_menu,
)


class TestEthioMateNavigation(unittest.TestCase):

    def get_keyboard_texts(self, markup):
        return {
            button.text
            for row in markup.keyboard
            for button in row
        }

    def test_main_menu_has_active_categories_in_all_languages(self):
        expected = {
            "am": {"🤖 የAI ረዳት", "🌐 ቋንቋዎች", "💼 ንግድ እና ገንዘብ"},
            "en": {"🤖 AI Assistant", "🌐 Languages", "💼 Business & Money"},
            "om": {"🤖 Gargaaraa AI", "🌐 Afaanota", "💼 Daldalaa fi Maallaqa"},
        }

        for language, required in expected.items():
            with self.subTest(language=language):
                actual = self.get_keyboard_texts(main_menu(language))
                self.assertTrue(required.issubset(actual))

    def test_language_submenu_keeps_translation_entry(self):
        for language in ("am", "en", "om"):
            with self.subTest(language=language):
                markup = language_menu(language)
                actual = self.get_keyboard_texts(markup)
                expected = {
                    button
                    for row in LANGUAGE_MENU_BUTTONS[language]
                    for button in row
                }
                self.assertEqual(actual, expected)

    def test_business_submenu_keeps_calculator_entry(self):
        for language in ("am", "en", "om"):
            with self.subTest(language=language):
                markup = business_menu(language)
                actual = self.get_keyboard_texts(markup)
                expected = {
                    button
                    for row in BUSINESS_MENU_BUTTONS[language]
                    for button in row
                }
                self.assertEqual(actual, expected)

    def test_calculator_options_are_preserved(self):
        for language in ("am", "en", "om"):
            with self.subTest(language=language):
                markup = calculator_menu(language)
                actual = self.get_keyboard_texts(markup)
                expected = {
                    button
                    for row in CALCULATOR_BUTTONS[language]
                    for button in row
                }
                self.assertEqual(actual, expected)

    def test_existing_main_menu_language_definitions(self):
        self.assertEqual(set(MAIN_BUTTONS), {"am", "en", "om"})


if __name__ == "__main__":
    unittest.main()
