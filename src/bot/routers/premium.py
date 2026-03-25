from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..keyboards.premium_menu import premium_keyboard
from ..utils.admin import is_admin
from ..utils.constants import (
    PREMIUM_PRICE_BY_DAYS,
    STATE_CHATTING,
    premium_info_text,
)
from ..utils.i18n import button_variants, tr
from ..utils.users import (
    ensure_user,
    get_lang_from_snapshot,
    get_state_from_snapshot,
    get_user_snapshot,
    is_banned_from_snapshot,
)

router = Router()

STAR_CURRENCY = "XTR"
PRICE_BY_DAYS = PREMIUM_PRICE_BY_DAYS


@router.message(F.text.in_(button_variants("premium")))
async def premium_info(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    user = await get_user_snapshot(db, user_id)
    lang = get_lang_from_snapshot(user)

    if is_banned_from_snapshot(user):
        await message.answer(
            tr(
                lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
                "Ваш акаунт заблоковано адміністрацією.",
                "Dein Konto wurde von der Administration gesperrt.",
            )
        )
        return

    state = get_state_from_snapshot(user)
    await message.answer(
        premium_info_text(lang),
        reply_markup=premium_keyboard(lang),
    )
    await message.answer(
        tr(
            lang,
            "Выберите действие ниже или вернитесь в меню.",
            "Choose an action below or return to the menu.",
            "Оберіть дію нижче або поверніться в меню.",
            "Wähle unten eine Aktion oder kehre ins Menü zurück.",
        ),
        reply_markup=main_menu_keyboard(
            show_end=state == STATE_CHATTING,
            is_admin=is_admin(user_id, config),
            lang=lang,
        ),
    )


@router.callback_query(F.data.startswith("premium:buy:"))
async def premium_buy(callback: CallbackQuery, db: Database, config: Config) -> None:
    user_id = callback.from_user.id
    await ensure_user(db, user_id)
    user = await get_user_snapshot(db, user_id)
    lang = get_lang_from_snapshot(user)

    if is_banned_from_snapshot(user):
        await callback.answer(
            tr(lang, "Доступ запрещен.", "Access denied.", "Доступ заборонено.", "Zugriff verweigert."),
            show_alert=True,
        )
        return

    try:
        days = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer(
            tr(lang, "Неверный тариф.", "Invalid plan.", "Неправильний тариф.", "Ungültiger Tarif."),
            show_alert=True,
        )
        return

    if days not in PRICE_BY_DAYS:
        await callback.answer(
            tr(lang, "Неверный тариф.", "Invalid plan.", "Неправильний тариф.", "Ungültiger Tarif."),
            show_alert=True,
        )
        return

    price = PRICE_BY_DAYS[days]
    await callback.bot.send_invoice(
        chat_id=user_id,
        title=tr(lang, f"Premium {days} дней", f"Premium {days} days", f"Premium {days} днів", f"Premium {days} Tage"),
        description=tr(lang, "Premium в ghostchat_bot", "Premium in ghostchat_bot", "Premium у ghostchat_bot", "Premium in ghostchat_bot"),
        payload=f"premium_{days}",
        currency=STAR_CURRENCY,
        prices=[
            LabeledPrice(
                label=tr(lang, f"Premium {days} дней", f"Premium {days} days", f"Premium {days} днів", f"Premium {days} Tage"),
                amount=price,
            )
        ],
        provider_token="",
        start_parameter="premium",
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, db: Database) -> None:
    payment = message.successful_payment
    payload = payment.invoice_payload or ""
    if not payload.startswith("premium_"):
        return

    try:
        days = int(payload.split("_", 1)[1])
    except (IndexError, ValueError):
        return

    new_until = await db.grant_paid_premium(
        message.from_user.id,
        days,
        f"{payload}|{payment.total_amount}|{payment.currency}",
    )
    lang = await db.get_lang(message.from_user.id)

    await message.answer(
        tr(
            lang,
            f"✅ Premium активирован на {days} дней.\nДействует до: {new_until}",
            f"✅ Premium activated for {days} days.\nValid until: {new_until}",
            f"✅ Premium активовано на {days} днів.\nДіє до: {new_until}",
            f"✅ Premium wurde für {days} Tage aktiviert.\nGültig bis: {new_until}",
        )
    )


@router.callback_query(F.data == "premium:trial")
async def premium_trial(callback: CallbackQuery, db: Database, config: Config) -> None:
    user_id = callback.from_user.id
    await ensure_user(db, user_id)
    user = await get_user_snapshot(db, user_id)
    lang = get_lang_from_snapshot(user)

    if is_banned_from_snapshot(user):
        await callback.answer(
            tr(lang, "Доступ запрещен.", "Access denied.", "Доступ заборонено.", "Zugriff verweigert."),
            show_alert=True,
        )
        return

    days = config.trial_days
    result = await db.activate_trial(user_id, days)
    if result.status == "used":
        await callback.answer(
            tr(lang, "Пробный период уже использован.", "Trial period already used.", "Пробний період уже використано.", "Testzeitraum wurde bereits verwendet."),
            show_alert=True,
        )
        return

    await callback.message.answer(
        tr(
            lang,
            f"🎁 Пробный период активирован на {days} дней.\nДействует до: {result.premium_until}",
            f"🎁 Trial period activated for {days} days.\nValid until: {result.premium_until}",
            f"🎁 Пробний період активовано на {days} днів.\nДіє до: {result.premium_until}",
            f"🎁 Testzeitraum für {days} Tage aktiviert.\nGültig bis: {result.premium_until}",
        )
    )
    await callback.answer()


@router.message(Command("trial"))
async def premium_trial_command(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    user = await get_user_snapshot(db, user_id)
    lang = get_lang_from_snapshot(user)

    if is_banned_from_snapshot(user):
        await message.answer(
            tr(
                lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
                "Ваш акаунт заблоковано адміністрацією.",
                "Dein Konto wurde von der Administration gesperrt.",
            )
        )
        return

    days = config.trial_days
    result = await db.activate_trial(user_id, days)
    if result.status == "used":
        await message.answer(
            tr(lang, "Пробный период уже использован.", "Trial period already used.", "Пробний період уже використано.", "Testzeitraum wurde bereits verwendet.")
        )
        return

    await message.answer(
        tr(
            lang,
            f"🎁 Пробный период активирован на {days} дней. Действует до: {result.premium_until}",
            f"🎁 Trial period activated for {days} days. Valid until: {result.premium_until}",
            f"🎁 Пробний період активовано на {days} днів. Діє до: {result.premium_until}",
            f"🎁 Testzeitraum für {days} Tage aktiviert. Gültig bis: {result.premium_until}",
        )
    )


@router.callback_query(F.data == "premium:promo")
async def premium_promo_hint(callback: CallbackQuery, db: Database) -> None:
    lang = await db.get_lang(callback.from_user.id)
    await callback.message.answer(
        tr(lang, "Введите: /promo CODE", "Enter: /promo CODE", "Введіть: /promo CODE", "Eingeben: /promo CODE")
    )
    await callback.answer()


@router.message(Command("promo"))
async def promo_command(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    user = await get_user_snapshot(db, user_id)
    lang = get_lang_from_snapshot(user)

    if is_banned_from_snapshot(user):
        await message.answer(
            tr(
                lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
                "Ваш акаунт заблоковано адміністрацією.",
                "Dein Konto wurde von der Administration gesperrt.",
            )
        )
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            tr(lang, "Использование: /promo CODE", "Usage: /promo CODE", "Використання: /promo CODE", "Verwendung: /promo CODE")
        )
        return

    code = parts[1].strip().upper()
    managed_promo = await db.get_managed_promo_code(code)
    if managed_promo is not None:
        result = await db.redeem_managed_promo_code(user_id, code)
        if result.status == "used":
            await message.answer(
                tr(lang, "Этот промокод уже использован.", "This promo code has already been used.", "Цей промокод уже використано.", "Dieser Promo-Code wurde bereits verwendet.")
            )
            return
        if result.status in {"exhausted", "inactive"}:
            await message.answer(
                tr(
                    lang,
                    "Промокод больше недоступен.",
                    "This promo code is no longer available.",
                    "Промокод більше недоступний.",
                    "Dieser Promo-Code ist nicht mehr verfügbar.",
                )
            )
            return
        if result.status != "ok":
            await message.answer(
                tr(lang, "Неверный промокод.", "Invalid promo code.", "Неправильний промокод.", "Ungültiger Promo-Code.")
            )
            return
    else:
        days = config.promo_codes.get(code)
        if not days:
            await message.answer(
                tr(lang, "Неверный промокод.", "Invalid promo code.", "Неправильний промокод.", "Ungültiger Promo-Code.")
            )
            return
        result = await db.redeem_static_promo_code(user_id, code, days)
        if result.status == "used":
            await message.answer(
                tr(lang, "Этот промокод уже использован.", "This promo code has already been used.", "Цей промокод уже використано.", "Dieser Promo-Code wurde bereits verwendet.")
            )
            return

    await message.answer(
        tr(
            lang,
            f"✅ Промокод активирован на {result.days} дней. Действует до: {result.premium_until}",
            f"✅ Promo code activated for {result.days} days. Valid until: {result.premium_until}",
            f"✅ Промокод активовано на {result.days} днів. Діє до: {result.premium_until}",
            f"✅ Promo-Code für {result.days} Tage aktiviert. Gültig bis: {result.premium_until}",
        )
    )
