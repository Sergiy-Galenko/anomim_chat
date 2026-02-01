from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard(show_end: bool = False, is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🔍 Пошук співрозмовника")],
        [KeyboardButton(text="🎯 Інтереси")],
        [KeyboardButton(text="🧑‍💻 Мій профіль")],
        [KeyboardButton(text="❓ Правила")],
        [KeyboardButton(text="⚙️ Налаштування")],
        [KeyboardButton(text="🚨 Поскаржитись")],
    ]
    if show_end:
        keyboard.append([KeyboardButton(text="🛑 Завершити діалог")])
        if is_admin:
            keyboard.append([KeyboardButton(text="🧷 Адмін: інфо партнера")])
            keyboard.append([KeyboardButton(text="🚫 Адмін: бан партнера")])
    if is_admin:
        keyboard.append([KeyboardButton(text="🧰 Адмін-панель")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
