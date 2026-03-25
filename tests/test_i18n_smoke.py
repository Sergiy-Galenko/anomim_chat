import unittest

from src.bot.keyboards.report_menu import parse_report_reason, report_reason_label
from src.bot.keyboards.settings_menu import settings_keyboard
from src.bot.utils.constants import premium_info_text, rules_text
from src.bot.utils.i18n import button_text, normalize_lang, tr, yes_no
from src.bot.utils.interests import interest_label
from src.bot.utils.virtual_companions import (
    build_virtual_match_text,
    virtual_variant_label,
)


class I18nSmokeTests(unittest.TestCase):
    def test_language_normalization_and_translation(self) -> None:
        self.assertEqual(normalize_lang("uk"), "uk")
        self.assertEqual(normalize_lang("de"), "de")
        self.assertEqual(normalize_lang("es"), "ru")
        self.assertEqual(tr("uk", "ru", "en", "uk", "de"), "uk")
        self.assertEqual(tr("de", "ru", "en", "uk", "de"), "de")
        self.assertEqual(yes_no("uk", True), "Так")
        self.assertEqual(yes_no("de", False), "Nein")

    def test_settings_keyboard_contains_new_languages(self) -> None:
        keyboard = settings_keyboard(auto_search=True, content_filter=False, lang="uk")
        texts = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("🇺🇦 Українська ✅", texts)
        self.assertIn("🇩🇪 Deutsch", texts)
        self.assertIn("✅ Готово", texts)

    def test_labels_and_virtual_fallbacks(self) -> None:
        self.assertEqual(button_text("settings", "de"), "⚙️ Einstellungen")
        self.assertEqual(interest_label("movies", "uk"), "Кіно")
        self.assertEqual(report_reason_label("abuse", "de"), "Beleidigung")
        self.assertEqual(parse_report_reason("Інше"), "other")
        self.assertEqual(parse_report_reason("Beleidigung"), "abuse")
        self.assertIn("скарги", rules_text("uk").lower())
        self.assertIn("promo-codes", premium_info_text("de").lower())
        self.assertIn("Gesprächspartner", build_virtual_match_text("de"))
        self.assertEqual(virtual_variant_label("spark", "uk"), virtual_variant_label("spark", "ru"))
        self.assertEqual(virtual_variant_label("spark", "de"), virtual_variant_label("spark", "en"))
