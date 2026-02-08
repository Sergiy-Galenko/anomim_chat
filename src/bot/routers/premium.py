from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..keyboards.premium_menu import premium_keyboard
from ..utils.admin import is_admin
from ..utils.constants import PREMIUM_INFO_TEXT_EN, PREMIUM_INFO_TEXT_RU, STATE_CHATTING
from ..utils.i18n import button_variants, tr
from ..utils.premium import add_premium_days
from ..utils.users import ensure_user, get_state, is_banned

router = Router()

STAR_CURRENCY = "XTR"
PRICE_BY_DAYS = {7: 29, 30: 99, 90: 249}


@router.message(F.text.in_(button_variants("premium")))
async def premium_info(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    lang = await db.get_lang(user_id)

    if await is_banned(db, user_id):
        await message.answer(
            tr(
                lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
            )
        )
        return

    state = await get_state(db, user_id)
    await message.answer(
        PREMIUM_INFO_TEXT_EN if lang == "en" else PREMIUM_INFO_TEXT_RU,
        reply_markup=premium_keyboard(lang),
    )
    await message.answer(
        tr(
            lang,
            "Выберите действие ниже или вернитесь в меню.",
            "Choose an action below or return to the menu.",
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
    lang = await db.get_lang(user_id)

    if await is_banned(db, user_id):
        await callback.answer(
            tr(lang, "Доступ запрещен.", "Access denied."),
            show_alert=True,
        )
        return

    try:
        days = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer(
            tr(lang, "Неверный тариф.", "Invalid plan."),
            show_alert=True,
        )
        return

    if days not in PRICE_BY_DAYS:
        await callback.answer(
            tr(lang, "Неверный тариф.", "Invalid plan."),
            show_alert=True,
        )
        return

    price = PRICE_BY_DAYS[days]
    await callback.bot.send_invoice(
        chat_id=user_id,
        title=tr(lang, f"Premium {days} дней", f"Premium {days} days"),
        description=tr(lang, "Premium в ghostchat_bot", "Premium in ghostchat_bot"),
        payload=f"premium_{days}",
        currency=STAR_CURRENCY,
        prices=[LabeledPrice(label=tr(lang, f"Premium {days} дней", f"Premium {days} days"), amount=price)],
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

    current_until = await db.get_premium_until(message.from_user.id)
    new_until = add_premium_days(current_until, days)
    await db.set_premium_until(message.from_user.id, new_until)
    await db.add_incident(message.from_user.id, None, "payment", payload)
    lang = await db.get_lang(message.from_user.id)

    await message.answer(
        tr(
            lang,
            f"✅ Premium активирован на {days} дней.\nДействует до: {new_until}",
            f"✅ Premium activated for {days} days.\nValid until: {new_until}",
        )
    )


@router.callback_query(F.data == "premium:trial")
async def premium_trial(callback: CallbackQuery, db: Database, config: Config) -> None:
    user_id = callback.from_user.id
    await ensure_user(db, user_id)
    lang = await db.get_lang(user_id)

    if await is_banned(db, user_id):
        await callback.answer(tr(lang, "Доступ запрещен.", "Access denied."), show_alert=True)
        return

    if await db.get_trial_used(user_id):
        await callback.answer(
            tr(lang, "Пробный период уже использован.", "Trial period already used."),
            show_alert=True,
        )
        return

    days = config.trial_days
    current_until = await db.get_premium_until(user_id)
    new_until = add_premium_days(current_until, days)
    await db.set_premium_until(user_id, new_until)
    await db.set_trial_used(user_id, True)
    await db.add_incident(user_id, None, "trial", f"{days}d")

    await callback.message.answer(
        tr(
            lang,
            f"🎁 Пробный период активирован на {days} дней.\nДействует до: {new_until}",
            f"🎁 Trial period activated for {days} days.\nValid until: {new_until}",
        )
    )
    await callback.answer()


@router.message(Command("trial"))
async def premium_trial_command(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    lang = await db.get_lang(user_id)

    if await is_banned(db, user_id):
        await message.answer(
            tr(
                lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
            )
        )
        return

    if await db.get_trial_used(user_id):
        await message.answer(
            tr(lang, "Пробный период уже использован.", "Trial period already used.")
        )
        return

    days = config.trial_days
    current_until = await db.get_premium_until(user_id)
    new_until = add_premium_days(current_until, days)
    await db.set_premium_until(user_id, new_until)
    await db.set_trial_used(user_id, True)
    await db.add_incident(user_id, None, "trial", f"{days}d")

    await message.answer(
        tr(
            lang,
            f"🎁 Пробный период активирован на {days} дней. Действует до: {new_until}",
            f"🎁 Trial period activated for {days} days. Valid until: {new_until}",
        )
    )


@router.callback_query(F.data == "premium:promo")
async def premium_promo_hint(callback: CallbackQuery, db: Database) -> None:
    lang = await db.get_lang(callback.from_user.id)
    await callback.message.answer(tr(lang, "Введите: /promo CODE", "Enter: /promo CODE"))
    await callback.answer()


@router.message(Command("promo"))
async def promo_command(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    lang = await db.get_lang(user_id)

    if await is_banned(db, user_id):
        await message.answer(
            tr(
                lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
            )
        )
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(tr(lang, "Использование: /promo CODE", "Usage: /promo CODE"))
        return

    code = parts[1].strip().upper()
    days = config.promo_codes.get(code)
    if not days:
        await message.answer(tr(lang, "Неверный промокод.", "Invalid promo code."))
        return

    if await db.has_used_promo(user_id, code):
        await message.answer(
            tr(lang, "Этот промокод уже использован.", "This promo code has already been used.")
        )
        return

    current_until = await db.get_premium_until(user_id)
    new_until = add_premium_days(current_until, days)
    await db.set_premium_until(user_id, new_until)
    await db.add_promo_use(user_id, code)
    await db.add_incident(user_id, None, "promo", code)

    await message.answer(
        tr(
            lang,
            f"✅ Промокод активирован на {days} дней. Действует до: {new_until}",
            f"✅ Promo code activated for {days} days. Valid until: {new_until}",
        )
    )
