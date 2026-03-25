STATE_IDLE = "idle"
STATE_SEARCHING = "searching"
STATE_CHATTING = "chatting"

RULES_TEXT_RU = (
    "Не передавайте личные данные, не угрожайте, без спама, "
    "18+ запрещено, жалобы модерируются."
)
RULES_TEXT_UK = (
    "Не передавайте особисті дані, не погрожуйте, без спаму, "
    "18+ заборонено, скарги модеруються."
)
RULES_TEXT_EN = (
    "Do not share personal data, do not threaten, no spam, "
    "18+ content is prohibited, reports are moderated."
)
RULES_TEXT_DE = (
    "Gib keine persönlichen Daten weiter, drohe nicht, kein Spam, "
    "18+-Inhalte sind verboten, Meldungen werden moderiert."
)
RULES_TEXT = RULES_TEXT_RU

SKIP_COOLDOWN_SECONDS = 30
MATCH_SOFT_EXPAND_SECONDS = 45
PREMIUM_PRICE_BY_DAYS = {7: 29, 30: 99, 90: 249}

PREMIUM_INFO_TEXT_RU = (
    "⭐ Premium\n"
    "Преимущества:\n"
    "- несколько интересов в поиске\n"
    "- режим \"только с интересом\"\n"
    "\n"
    "Цены (Telegram Stars):\n"
    "- 99 Stars / 30 дней\n"
    "- 29 Stars / 7 дней\n"
    "- 249 Stars / 90 дней\n"
    "\n"
    "Дополнительно:\n"
    "- пробный период (1 раз)\n"
    "- промокоды\n"
)
PREMIUM_INFO_TEXT_UK = (
    "⭐ Premium\n"
    "Переваги:\n"
    "- кілька інтересів у пошуку\n"
    "- режим \"тільки за інтересом\"\n"
    "\n"
    "Ціни (Telegram Stars):\n"
    "- 99 Stars / 30 днів\n"
    "- 29 Stars / 7 днів\n"
    "- 249 Stars / 90 днів\n"
    "\n"
    "Додатково:\n"
    "- пробний період (1 раз)\n"
    "- промокоди\n"
)
PREMIUM_INFO_TEXT_EN = (
    "⭐ Premium\n"
    "Benefits:\n"
    "- multiple interests in matchmaking\n"
    "- \"interest-only\" mode\n"
    "\n"
    "Prices (Telegram Stars):\n"
    "- 99 Stars / 30 days\n"
    "- 29 Stars / 7 days\n"
    "- 249 Stars / 90 days\n"
    "\n"
    "Also:\n"
    "- trial period (one-time)\n"
    "- promo codes\n"
)
PREMIUM_INFO_TEXT_DE = (
    "⭐ Premium\n"
    "Vorteile:\n"
    "- mehrere Interessen bei der Suche\n"
    "- Modus \"nur nach Interesse\"\n"
    "\n"
    "Preise (Telegram Stars):\n"
    "- 99 Stars / 30 Tage\n"
    "- 29 Stars / 7 Tage\n"
    "- 249 Stars / 90 Tage\n"
    "\n"
    "Zusätzlich:\n"
    "- Testzeitraum (einmalig)\n"
    "- Promo-Codes\n"
)
PREMIUM_INFO_TEXT = PREMIUM_INFO_TEXT_RU


def rules_text(lang: str) -> str:
    normalized = (lang or "").strip().lower()
    if normalized == "en":
        return RULES_TEXT_EN
    if normalized == "uk":
        return RULES_TEXT_UK
    if normalized == "de":
        return RULES_TEXT_DE
    return RULES_TEXT_RU


def premium_info_text(lang: str) -> str:
    normalized = (lang or "").strip().lower()
    if normalized == "en":
        return PREMIUM_INFO_TEXT_EN
    if normalized == "uk":
        return PREMIUM_INFO_TEXT_UK
    if normalized == "de":
        return PREMIUM_INFO_TEXT_DE
    return PREMIUM_INFO_TEXT_RU
