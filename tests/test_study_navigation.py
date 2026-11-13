import unittest

from keyboards.menus import (
    MAIN_BUTTONS,
    STUDY_BUTTONS,
    STUDY_TUTOR_BUTTONS,
    STUDY_MENU_BUTTONS,
    main_menu,
    study_menu,
)


class TestStudyNavigation(unittest.TestCase):

    def get_keyboard_texts(self, markup):
        return {
            button.text
            for row in markup.keyboard
            for button in row
        }

    def test_study_category_exists_in_all_languages(self):
        for language in ("am", "en", "om"):
            with self.subTest(language=language):
                self.assertIn(
                    STUDY_BUTTONS[language],
                    self.get_keyboard_texts(main_menu(language))
                )

    def test_tutor_and_back_buttons_exist_in_all_languages(self):
        for language in ("am", "en", "om"):
            with self.subTest(language=language):
                actual = self.get_keyboard_texts(study_menu(language))
                self.assertEqual(
                    actual,
                    {
                        button
                        for row in STUDY_MENU_BUTTONS[language]
                        for button in row
                    }
                )
                self.assertIn(STUDY_TUTOR_BUTTONS[language], actual)

    def test_existing_main_menu_languages_are_preserved(self):
        self.assertEqual(set(MAIN_BUTTONS), {"am", "en", "om"})


if __name__ == "__main__":
    unittest.main()
