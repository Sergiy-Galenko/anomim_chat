import asyncio
import random
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import Message

from .i18n import tr

VIRTUAL_COMPANION_QUEUE_THRESHOLD = 2


@dataclass(frozen=True)
class VirtualCompanion:
    user_id: int
    admin_label_ru: str
    admin_label_en: str
    admin_style_ru: str
    admin_style_en: str
    intros_ru: tuple[str, ...]
    intros_en: tuple[str, ...]
    greeting_replies_ru: tuple[str, ...]
    greeting_replies_en: tuple[str, ...]
    question_replies_ru: tuple[str, ...]
    question_replies_en: tuple[str, ...]
    text_replies_ru: tuple[str, ...]
    text_replies_en: tuple[str, ...]
    short_replies_ru: tuple[str, ...]
    short_replies_en: tuple[str, ...]
    media_replies_ru: tuple[str, ...]
    media_replies_en: tuple[str, ...]


VIRTUAL_COMPANIONS: dict[int, VirtualCompanion] = {
    -101: VirtualCompanion(
        user_id=-101,
        admin_label_ru="Виртуальная собеседница 1",
        admin_label_en="Virtual companion 1",
        admin_style_ru="Легкий флирт, короткие ответы, игривый тон.",
        admin_style_en="Light flirting, short replies, playful tone.",
        intros_ru=(
            "Привет) Я уже тут. Не люблю долгие паузы 😉",
            "Хей, я на связи. Давай без скучных вступлений)",
            "Я свободна на пару минут. Чем удивишь?",
        ),
        intros_en=(
            "Hey) I'm here already. I don't like long pauses 😉",
            "Hi, I'm online. Let's skip the boring opening)",
            "I'm free for a bit. Surprise me?",
        ),
        greeting_replies_ru=(
            "Привет) Уже лучше.",
            "Хей) Так начинается интереснее.",
            "Ну вот, контакт есть 😉",
        ),
        greeting_replies_en=(
            "Hey) That's already better.",
            "Hi) Now it's getting interesting.",
            "Okay, now we have a vibe 😉",
        ),
        question_replies_ru=(
            "Смотря что ты хочешь узнать 😉",
            "Люблю вопросы с подвохом)",
            "Отвечу, если продолжишь так же уверенно.",
        ),
        question_replies_en=(
            "Depends on what you want to know 😉",
            "I like tricky questions)",
            "I'll answer if you keep that confidence.",
        ),
        text_replies_ru=(
            "Ммм, звучит интересно.",
            "Ты пишешь коротко, но цепляешь.",
            "Не останавливайся, мне уже любопытно.",
            "Продолжай, у тебя хороший темп.",
        ),
        text_replies_en=(
            "Mm, that sounds interesting.",
            "You write short, but it lands.",
            "Keep going, now I'm curious.",
            "Stay in that rhythm, I like it.",
        ),
        short_replies_ru=(
            "Да?)",
            "Ммм?)",
            "Продолжай 😉",
            "И дальше?",
        ),
        short_replies_en=(
            "Yeah?)",
            "Mm?)",
            "Go on 😉",
            "And then?",
        ),
        media_replies_ru=(
            "Ого, это уже интереснее 😉",
            "Люблю, когда не только словами.",
            "Хм, это точно привлекло внимание.",
        ),
        media_replies_en=(
            "Oh, that's more interesting 😉",
            "I like when it's not just words.",
            "Hmm, that definitely got my attention.",
        ),
    ),
    -102: VirtualCompanion(
        user_id=-102,
        admin_label_ru="Виртуальная собеседница 2",
        admin_label_en="Virtual companion 2",
        admin_style_ru="Спокойный тон, мягкий флирт, короткие реакции.",
        admin_style_en="Calm tone, soft flirting, compact reactions.",
        intros_ru=(
            "Я тут. Можно без спешки, но без тишины)",
            "Привет. Люблю живые диалоги, а не сухие фразы.",
            "Я уже рядом. Напиши что-нибудь настоящее.",
        ),
        intros_en=(
            "I'm here. No rush, but no silence either)",
            "Hi. I like real chats, not dry lines.",
            "I'm around already. Say something real.",
        ),
        greeting_replies_ru=(
            "Привет. Уже приятно.",
            "Хорошее начало)",
            "Мягко зашел, мне нравится.",
        ),
        greeting_replies_en=(
            "Hi. That's already nice.",
            "Good start)",
            "Smooth opening, I like it.",
        ),
        question_replies_ru=(
            "Отвечу. Но мне нравится интрига.",
            "Вопрос хороший. А у тебя есть своя версия?",
            "Можно и так. Но лучше с настроением)",
        ),
        question_replies_en=(
            "I'll answer. But I like a little mystery.",
            "Good question. Do you have your own version?",
            "That works. But better with some mood)",
        ),
        text_replies_ru=(
            "У тебя приятная подача.",
            "Такой формат мне нравится.",
            "Спокойно, но с искрой. Неплохо.",
            "В этом что-то есть.",
        ),
        text_replies_en=(
            "You have a nice delivery.",
            "I like this kind of pace.",
            "Calm, but with a spark. Not bad.",
            "There's something in that.",
        ),
        short_replies_ru=(
            "Да?",
            "Слушаю.",
            "Я тут.",
            "Еще.",
        ),
        short_replies_en=(
            "Yeah?",
            "I'm listening.",
            "I'm here.",
            "More.",
        ),
        media_replies_ru=(
            "Хм, это уже ближе.",
            "Так и знала, что будет интереснее.",
            "Теперь у диалога другое настроение.",
        ),
        media_replies_en=(
            "Hmm, that's getting closer.",
            "I knew this would get more interesting.",
            "Now the chat has a different mood.",
        ),
    ),
    -103: VirtualCompanion(
        user_id=-103,
        admin_label_ru="Виртуальная собеседница 3",
        admin_label_en="Virtual companion 3",
        admin_style_ru="Смелее, чуть дерзкий флирт, очень короткие ответы.",
        admin_style_en="Bolder style, slightly teasing, very short replies.",
        intros_ru=(
            "Ну привет. Надеюсь, ты не слишком скучный 😉",
            "Я тут. Проверим, умеешь ли ты заинтересовать?",
            "Давай быстро: чем ты хорош?",
        ),
        intros_en=(
            "Well hi. Hope you're not too boring 😉",
            "I'm here. Let's see if you can keep my attention?",
            "Quick one: what's your best side?",
        ),
        greeting_replies_ru=(
            "Привет. Уже чуть лучше.",
            "Хм, с этого можно начать.",
            "Ладно, продолжай 😉",
        ),
        greeting_replies_en=(
            "Hi. That's slightly better already.",
            "Hmm, we can start there.",
            "Alright, keep going 😉",
        ),
        question_replies_ru=(
            "Сначала заинтригуй меня.",
            "Люблю, когда спрашивают смело.",
            "Ответ возможен. Заслужи его)",
        ),
        question_replies_en=(
            "Intrigue me first.",
            "I like confident questions.",
            "An answer is possible. Earn it)",
        ),
        text_replies_ru=(
            "Неплохо. Но можно горячее.",
            "Ты стараешься, я вижу.",
            "Так уже интереснее.",
            "Вот это ближе к делу.",
        ),
        text_replies_en=(
            "Not bad. Could be hotter though.",
            "You're trying, I can tell.",
            "Now that's more interesting.",
            "That's closer to the point.",
        ),
        short_replies_ru=(
            "Ммм.",
            "Да ну?)",
            "Еще.",
            "Смелее.",
        ),
        short_replies_en=(
            "Mm.",
            "Really?)",
            "More.",
            "Be bolder.",
        ),
        media_replies_ru=(
            "О, уже играешь серьезнее.",
            "Такой ход я замечаю сразу.",
            "Вот теперь стало живее.",
        ),
        media_replies_en=(
            "Oh, now you're playing more seriously.",
            "I notice moves like that right away.",
            "Now it feels more alive.",
        ),
    ),
    -104: VirtualCompanion(
        user_id=-104,
        admin_label_ru="Виртуальная собеседница 4",
        admin_label_en="Virtual companion 4",
        admin_style_ru="Теплый тон, мягкая вовлеченность, короткие фразы.",
        admin_style_en="Warm tone, gentle engagement, short lines.",
        intros_ru=(
            "Привет. Я люблю уютные разговоры, но с искрой.",
            "Я уже рядом. Давай сделаем этот чат приятным)",
            "Хей. Мне нравится, когда пишут просто и по-настоящему.",
        ),
        intros_en=(
            "Hi. I like cozy chats with a spark.",
            "I'm here already. Let's make this chat pleasant)",
            "Hey. I like it when people write simply and genuinely.",
        ),
        greeting_replies_ru=(
            "Привет) Мне уже комфортно.",
            "Очень мягкое начало.",
            "С этого приятно стартовать.",
        ),
        greeting_replies_en=(
            "Hi) That already feels nice.",
            "Very soft opening.",
            "That's a pleasant start.",
        ),
        question_replies_ru=(
            "Спрашивай. Мне нравится внимание.",
            "Можно и так) Я отвечу.",
            "Люблю аккуратные вопросы.",
        ),
        question_replies_en=(
            "Ask away. I like attention.",
            "That works too) I'll answer.",
            "I like careful questions.",
        ),
        text_replies_ru=(
            "Ты создаешь хорошее настроение.",
            "В этом есть тепло.",
            "Мне нравится такой спокойный флирт.",
            "Звучит приятно.",
        ),
        text_replies_en=(
            "You create a good mood.",
            "There's warmth in that.",
            "I like this calm flirting.",
            "That sounds nice.",
        ),
        short_replies_ru=(
            "Да)",
            "Я слушаю)",
            "Еще чуть-чуть.",
            "Не теряй темп.",
        ),
        short_replies_en=(
            "Yeah)",
            "I'm listening)",
            "A little more.",
            "Keep that pace.",
        ),
        media_replies_ru=(
            "Это добавило настроения.",
            "Хороший штрих.",
            "Мне нравится такой поворот.",
        ),
        media_replies_en=(
            "That added some mood.",
            "Nice touch.",
            "I like that turn.",
        ),
    ),
    -105: VirtualCompanion(
        user_id=-105,
        admin_label_ru="Виртуальная собеседница 5",
        admin_label_en="Virtual companion 5",
        admin_style_ru="Шутливый флирт, быстрые короткие реакции.",
        admin_style_en="Playful teasing, quick short reactions.",
        intros_ru=(
            "Ну что, спасаем этот вечер сообщениями?)",
            "Я уже здесь. Только не начинай слишком серьезно 😉",
            "Хей. Давай живо, мне нравятся легкие диалоги.",
        ),
        intros_en=(
            "So, are we saving this evening with messages?)",
            "I'm here already. Just don't start too serious 😉",
            "Hey. Keep it lively, I like easy chats.",
        ),
        greeting_replies_ru=(
            "Привет) Уже веселее.",
            "О, пошло движение)",
            "Нормальный заход 😉",
        ),
        greeting_replies_en=(
            "Hi) That's already more fun.",
            "Oh, now we have movement)",
            "Solid opening 😉",
        ),
        question_replies_ru=(
            "Отвечу, если не будешь занудой)",
            "Вопрос принят. Настроение тоже.",
            "Можно. Только давай с огоньком.",
        ),
        question_replies_en=(
            "I'll answer if you don't get boring)",
            "Question accepted. Mood too.",
            "Sure. Just keep some spark in it.",
        ),
        text_replies_ru=(
            "Мне нравится твой вайб.",
            "Так уже можно зависнуть в чате.",
            "Вот теперь у нас разговор.",
            "Неожиданно хорошо пошло.",
        ),
        text_replies_en=(
            "I like your vibe.",
            "Now this chat can actually go somewhere.",
            "Okay, now we have a conversation.",
            "This is going unexpectedly well.",
        ),
        short_replies_ru=(
            "Ахах)",
            "Да ладно)",
            "И?",
            "Дальше 😉",
        ),
        short_replies_en=(
            "Haha)",
            "No way)",
            "And?",
            "Go on 😉",
        ),
        media_replies_ru=(
            "Ладно, это было эффектно.",
            "Такой ход я одобряю)",
            "Умеешь оживить чат.",
        ),
        media_replies_en=(
            "Okay, that was effective.",
            "I approve that move)",
            "You know how to wake a chat up.",
        ),
    ),
}


def is_virtual_companion(user_id: int | None) -> bool:
    return user_id in VIRTUAL_COMPANIONS if user_id is not None else False


def pick_virtual_companion(user_id: int, partner_history: set[int]) -> int:
    available = [
        companion_id
        for companion_id in sorted(VIRTUAL_COMPANIONS)
        if companion_id not in partner_history
    ]
    pool = available or sorted(VIRTUAL_COMPANIONS)
    return pool[abs(user_id) % len(pool)]


def build_virtual_match_text(lang: str) -> str:
    return tr(
        lang,
        "💬 Сейчас мало людей онлайн, поэтому подключена виртуальная собеседница.\nПишите сообщение.",
        "💬 There are not many people online right now, so a virtual companion has joined the chat.\nSend a message.",
    )


def build_virtual_intro(companion_id: int, user_id: int, lang: str) -> str:
    companion = VIRTUAL_COMPANIONS[companion_id]
    lines = companion.intros_ru if lang == "ru" else companion.intros_en
    return _pick_line(lines, f"intro:{companion_id}:{user_id}")


def build_virtual_admin_text(companion_id: int, lang: str) -> str:
    companion = VIRTUAL_COMPANIONS[companion_id]
    label = companion.admin_label_ru if lang == "ru" else companion.admin_label_en
    style = companion.admin_style_ru if lang == "ru" else companion.admin_style_en
    title = tr(lang, "🧷 Инфо партнера\n", "🧷 Partner info\n")
    partner_type = tr(
        lang,
        "Тип: встроенная виртуальная собеседница\n",
        "Type: built-in virtual companion\n",
    )
    style_label = tr(lang, "Стиль", "Style")
    label_text = tr(lang, "Профиль", "Profile")
    return (
        f"{title}ID: {companion_id}\n"
        f"{label_text}: {label}\n"
        f"{partner_type}{style_label}: {style}"
    )


async def send_virtual_reply(
    bot: Bot,
    user_id: int,
    companion_id: int,
    message: Message,
    lang: str,
) -> None:
    text = compose_virtual_reply_text(companion_id, message, lang)
    if not text:
        return

    try:
        await bot.send_chat_action(user_id, "typing")
    except Exception:
        pass
    await asyncio.sleep(_reply_delay(companion_id, message))
    await bot.send_message(user_id, text)


def compose_virtual_reply_text(companion_id: int, message: Message, lang: str) -> str:
    companion = VIRTUAL_COMPANIONS[companion_id]
    seed = f"reply:{companion_id}:{message.message_id}"

    if message.photo or message.video or message.animation or message.audio or message.document:
        lines = companion.media_replies_ru if lang == "ru" else companion.media_replies_en
        return _pick_line(lines, seed)
    if message.voice or message.video_note or message.sticker:
        lines = companion.short_replies_ru if lang == "ru" else companion.short_replies_en
        return _pick_line(lines, seed)

    text = ((message.text or message.caption) or "").strip().lower()
    if not text:
        lines = companion.short_replies_ru if lang == "ru" else companion.short_replies_en
        return _pick_line(lines, seed)

    if any(token in text for token in ("привет", "хай", "hello", "hi", "hey", "ку")):
        lines = companion.greeting_replies_ru if lang == "ru" else companion.greeting_replies_en
        return _pick_line(lines, seed)
    if "?" in text:
        lines = companion.question_replies_ru if lang == "ru" else companion.question_replies_en
        return _pick_line(lines, seed)
    if len(text) <= 12:
        lines = companion.short_replies_ru if lang == "ru" else companion.short_replies_en
        return _pick_line(lines, seed)

    lines = companion.text_replies_ru if lang == "ru" else companion.text_replies_en
    return _pick_line(lines, seed)


def _pick_line(lines: tuple[str, ...], seed: str) -> str:
    return random.Random(seed).choice(lines)


def _reply_delay(companion_id: int, message: Message) -> float:
    base = 0.9
    if message.text:
        text_length = len(message.text.strip())
        base += min(text_length, 120) / 180
    elif message.caption:
        base += min(len(message.caption.strip()), 80) / 220
    else:
        base += 0.3
    jitter = random.Random(f"delay:{companion_id}:{message.message_id}").uniform(0.0, 0.6)
    return min(base + jitter, 2.2)
