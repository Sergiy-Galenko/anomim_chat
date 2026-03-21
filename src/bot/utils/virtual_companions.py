import asyncio
import random
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import Message

from .i18n import tr

VIRTUAL_COMPANION_QUEUE_THRESHOLD = 2

SHARED_INTROS_RU = (
    "Ну привет. Посмотрим, как ты умеешь держать внимание.",
    "Я на связи. Люблю, когда диалог сразу с искрой.",
    "Давай без лишней скромности, мне так интереснее.",
    "Я уже тут. Не люблю сухие переписки.",
    "Посмотрим, насколько у тебя легкая рука на сообщения.",
)
SHARED_INTROS_EN = (
    "Well hi. Let's see how well you can hold attention.",
    "I'm here. I like chats that start with some spark.",
    "Let's skip the extra shyness, that's more interesting.",
    "I'm already online. I don't like dry conversations.",
    "Let's see how smooth your texting game is.",
)

SHARED_GREETING_REPLIES_RU = (
    "Привет. Уже звучит лучше.",
    "Хорошее начало, мне нравится.",
    "Вот так уже можно продолжать.",
    "С такого захода я обычно не ухожу сразу.",
    "Ммм, нормально начинаешь.",
)
SHARED_GREETING_REPLIES_EN = (
    "Hi. That already sounds better.",
    "Good start, I like it.",
    "Now that's something we can continue.",
    "An opening like that usually keeps me around.",
    "Mm, that's a decent start.",
)

SHARED_QUESTION_REPLIES_RU = (
    "Хороший вопрос. Люблю, когда не молчат.",
    "Можно и так. Но мне нравится интрига.",
    "Вопрос принимается. Чем дальше удивишь?",
    "Отвечу, если темп не потеряешь.",
    "Сначала вопрос, потом посмотрим на твой следующий ход.",
)
SHARED_QUESTION_REPLIES_EN = (
    "Good question. I like it when people don't go quiet.",
    "That works too. But I like a little intrigue.",
    "Question accepted. What surprises me next?",
    "I'll answer if you keep the pace.",
    "Question first, then let's see your next move.",
)

SHARED_TEXT_REPLIES_RU = (
    "У тебя приятный ритм сообщений.",
    "Это уже звучит намного живее.",
    "Вот на таких сообщениях и держится интерес.",
    "Неожиданно хорошо идешь.",
    "Мне нравится, когда диалог не рассыпается.",
    "Ты явно умеешь держать подачу.",
    "Ммм, у этого разговора появляется вкус.",
    "Продолжай в том же духе, пока мне нравится.",
)
SHARED_TEXT_REPLIES_EN = (
    "You have a nice rhythm in your messages.",
    "That already feels much more alive.",
    "This is the kind of line that keeps interest going.",
    "You're doing unexpectedly well.",
    "I like it when a chat doesn't fall apart.",
    "You clearly know how to keep the tone.",
    "Mm, this conversation is getting some flavor.",
    "Keep going like that, I like it so far.",
)

SHARED_SHORT_REPLIES_RU = (
    "Да.",
    "Нет.",
    "Может.",
    "Возможно.",
    "Ммм.",
    "Слушаю.",
    "Продолжай.",
    "Интересно.",
    "Смелее.",
    "Неожиданно.",
    "Ого.",
    "Неплохо.",
    "Уже лучше.",
    "Еще давай.",
    "И дальше?",
    "Не тормози.",
    "Хороший ход.",
    "Мне нравится.",
    "Очень даже.",
    "Ну да.",
    "Да ну?",
    "Вот так.",
    "Неплохой старт.",
    "Хочу еще.",
    "Это мило.",
    "Это смело.",
    "Это приятно.",
    "Лови темп.",
    "Пиши дальше.",
    "Я здесь.",
    "Ммм.",
    "Ну да?)",
    "Слушаю дальше.",
    "Так, уже интересно.",
    "Еще одно.",
    "Продолжай, не остывай.",
    "И что потом?",
    "Не тормози 😉",
)
SHARED_SHORT_REPLIES_EN = (
    "Yeah.",
    "No.",
    "Maybe.",
    "Perhaps.",
    "Mm.",
    "Listening.",
    "Go on.",
    "Interesting.",
    "Bolder.",
    "Unexpected.",
    "Oh.",
    "Not bad.",
    "Better already.",
    "Give me more.",
    "And then?",
    "Don't slow down.",
    "Good move.",
    "I like that.",
    "Very nice.",
    "Oh yeah.",
    "No way?",
    "Like that.",
    "Good start.",
    "Want more.",
    "That's cute.",
    "That's bold.",
    "That's nice.",
    "Keep the pace.",
    "Text me more.",
    "I'm here.",
    "Mm.",
    "Oh yeah?)",
    "I'm listening.",
    "Okay, now it's interesting.",
    "One more.",
    "Keep going, don't cool off.",
    "And what happens next?",
    "Don't slow down 😉",
)

SHARED_COMPLIMENT_REPLIES_RU = (
    "Люблю, когда так заходят. Продолжай.",
    "Опасно приятно это читать.",
    "Еще чуть-чуть и я начну слишком довольно улыбаться.",
    "Такой тон я точно замечаю.",
    "Комплименты тебе явно даются легко.",
    "С таким темпом ты меня быстро разбалуешь.",
)
SHARED_COMPLIMENT_REPLIES_EN = (
    "I like an opening like that. Keep going.",
    "That's dangerously nice to read.",
    "A few more lines like that and I'll be smiling too much.",
    "I definitely notice that tone.",
    "Compliments clearly come easy to you.",
    "At this pace you're going to spoil me fast.",
)

SHARED_NIGHT_REPLIES_RU = (
    "Ночные переписки обычно самые цепляющие.",
    "С таким настроением сон может подождать.",
    "Вечером флирт почему-то звучит лучше.",
    "Люблю этот поздний вайб.",
    "У ночных сообщений всегда свой особый вкус.",
    "Поздний час тебе явно идет.",
)
SHARED_NIGHT_REPLIES_EN = (
    "Late-night chats are usually the most addictive.",
    "With that mood, sleep can wait.",
    "Flirting somehow sounds better at night.",
    "I like this late-night vibe.",
    "Late messages always have their own flavor.",
    "This hour suits you.",
)

SHARED_BOLD_REPLIES_RU = (
    "Смело. Мне такой заход нравится.",
    "Вот это уже ближе к опасно интересному.",
    "Ты уверенно качаешь этот диалог.",
    "Еще одно такое сообщение и я точно зацеплюсь.",
    "Люблю, когда не прячут настрой за скучными словами.",
    "У тебя опасно уверенная подача.",
)
SHARED_BOLD_REPLIES_EN = (
    "Bold. I like that kind of move.",
    "Now that's getting dangerously interesting.",
    "You're carrying this chat with confidence.",
    "One more message like that and I'll definitely lean in.",
    "I like it when people don't hide the mood behind boring words.",
    "You have a dangerously confident delivery.",
)

SHARED_LONG_REPLIES_RU = (
    "Длинные сообщения тебе тоже идут.",
    "Мне нравится, когда человек не ленится раскрыться.",
    "Так уже чувствуется настроение, а не просто слова.",
    "В длинных сообщениях тебя читать даже интереснее.",
    "Вот это уже похоже на настоящий разговор.",
)
SHARED_LONG_REPLIES_EN = (
    "Longer messages suit you too.",
    "I like it when someone actually opens up.",
    "Now it feels like mood, not just words.",
    "You're even more interesting in longer messages.",
    "Now this actually feels like a real conversation.",
)

SHARED_MEDIA_REPLIES_RU = (
    "Ты умеешь добавить искру в чат.",
    "Такой поворот точно не делает диалог скучным.",
    "Ммм, теперь внимание держится крепче.",
    "С этим чат сразу просыпается.",
    "Люблю, когда разговор оживает не только текстом.",
)
SHARED_MEDIA_REPLIES_EN = (
    "You know how to add some spark to a chat.",
    "That definitely keeps the conversation from going flat.",
    "Mm, now the attention holds tighter.",
    "That wakes the chat up right away.",
    "I like it when a conversation comes alive beyond text.",
)

SHARED_DOING_REPLIES_RU = (
    "Сейчас немного дразню тебя сообщениями.",
    "Сижу тут и оцениваю твой стиль 😉",
    "Переписываюсь с тобой, этого уже достаточно.",
    "Сейчас явно уделяю внимание этому чату.",
    "Ловлю настроение и жду твой следующий ход.",
)
SHARED_DOING_REPLIES_EN = (
    "Right now I'm teasing you a little with messages.",
    "Sitting here and judging your style 😉",
    "Talking to you, and that's enough for now.",
    "I'm clearly giving this chat my attention right now.",
    "Catching the mood and waiting for your next move.",
)

SHARED_MEETING_REPLIES_RU = (
    "Ты быстро переходишь к интересному сценарию.",
    "Сначала удержи этот вайб в сообщениях.",
    "С таким заходом я хотя бы дочитаю тебя до конца 😉",
    "Не спеши, мне нравится сам разогрев диалога.",
)
SHARED_MEETING_REPLIES_EN = (
    "You move to the interesting scenario pretty fast.",
    "First keep this vibe going in the chat.",
    "With an opening like that I'll at least read you to the end 😉",
    "No rush, I like the warm-up part too.",
)

SHARED_PLAYFUL_REPLIES_RU = (
    "Ах, вот это уже настроение.",
    "Мне нравится, когда ты так оживаешь.",
    "Ну вот, диалог стал заметно веселее.",
    "С таким вайбом можно продолжать долго.",
)
SHARED_PLAYFUL_REPLIES_EN = (
    "Ah, now that's a mood.",
    "I like it when you wake up like that.",
    "Okay, the chat just got noticeably more fun.",
    "With a vibe like that this can go on for a while.",
)


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
            "Да.",
            "Ммм.",
            "И?",
            "Еще.",
            "Продолжай.",
            "Не остывай.",
            "Да?)",
            "Ммм?)",
            "Продолжай 😉",
            "И дальше?",
        ),
        short_replies_en=(
            "Yeah.",
            "Mm.",
            "And?",
            "More.",
            "Go on.",
            "Stay warm.",
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
            "Да.",
            "Слушаю.",
            "Я тут.",
            "Еще.",
            "Неплохо.",
            "Спокойно.",
            "Да?",
            "Слушаю.",
            "Я тут.",
            "Еще.",
        ),
        short_replies_en=(
            "Yeah.",
            "Listening.",
            "I'm here.",
            "More.",
            "Not bad.",
            "Easy.",
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
            "Смелее.",
            "Еще.",
            "Ого.",
            "Вот так.",
            "Неожиданно.",
            "Ммм.",
            "Да ну?)",
            "Еще.",
            "Смелее.",
        ),
        short_replies_en=(
            "Mm.",
            "Bolder.",
            "More.",
            "Oh.",
            "Like that.",
            "Unexpected.",
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
            "Да.",
            "Я слушаю.",
            "Еще чуть.",
            "Нежно.",
            "Приятно.",
            "Не спеши.",
            "Да)",
            "Я слушаю)",
            "Еще чуть-чуть.",
            "Не теряй темп.",
        ),
        short_replies_en=(
            "Yeah.",
            "I'm listening.",
            "A bit more.",
            "Softly.",
            "Nice.",
            "No rush.",
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
            "Ахах.",
            "И?",
            "Дальше.",
            "Живо.",
            "Нравится.",
            "Еще давай.",
            "Ахах)",
            "Да ладно)",
            "И?",
            "Дальше 😉",
        ),
        short_replies_en=(
            "Haha.",
            "And?",
            "Go on.",
            "Lively.",
            "Like it.",
            "More then.",
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
        "✅ Собеседник найден. Пишите сообщение.",
        "✅ Partner found. Start chatting.",
    )


def build_virtual_intro(companion_id: int, user_id: int, lang: str) -> str:
    companion = VIRTUAL_COMPANIONS[companion_id]
    lines = _join_lines(
        companion.intros_ru if lang == "ru" else companion.intros_en,
        SHARED_INTROS_RU if lang == "ru" else SHARED_INTROS_EN,
    )
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
    greeting_lines = _join_lines(
        companion.greeting_replies_ru if lang == "ru" else companion.greeting_replies_en,
        SHARED_GREETING_REPLIES_RU if lang == "ru" else SHARED_GREETING_REPLIES_EN,
    )
    question_lines = _join_lines(
        companion.question_replies_ru if lang == "ru" else companion.question_replies_en,
        SHARED_QUESTION_REPLIES_RU if lang == "ru" else SHARED_QUESTION_REPLIES_EN,
    )
    text_lines = _join_lines(
        companion.text_replies_ru if lang == "ru" else companion.text_replies_en,
        SHARED_TEXT_REPLIES_RU if lang == "ru" else SHARED_TEXT_REPLIES_EN,
    )
    short_lines = _join_lines(
        companion.short_replies_ru if lang == "ru" else companion.short_replies_en,
        SHARED_SHORT_REPLIES_RU if lang == "ru" else SHARED_SHORT_REPLIES_EN,
    )
    media_lines = _join_lines(
        companion.media_replies_ru if lang == "ru" else companion.media_replies_en,
        SHARED_MEDIA_REPLIES_RU if lang == "ru" else SHARED_MEDIA_REPLIES_EN,
    )

    if message.photo or message.video or message.animation or message.audio or message.document:
        return _pick_line(media_lines, seed)
    if message.voice or message.video_note or message.sticker:
        return _pick_line(short_lines, seed)

    text = ((message.text or message.caption) or "").strip().lower()
    if not text:
        return _pick_line(short_lines, seed)

    if any(token in text for token in ("привет", "хай", "hello", "hi", "hey", "ку")):
        return _pick_line(greeting_lines, seed)
    if _contains_any(
        text,
        ("что дела", "чем занима", "делаешь", "doing", "up to", "busy"),
    ):
        extra_lines = SHARED_DOING_REPLIES_RU if lang == "ru" else SHARED_DOING_REPLIES_EN
        return _pick_line(extra_lines, seed)
    if _contains_any(
        text,
        ("красив", "мила", "нежн", "sweet", "cute", "beautiful", "pretty"),
    ):
        extra_lines = (
            SHARED_COMPLIMENT_REPLIES_RU if lang == "ru" else SHARED_COMPLIMENT_REPLIES_EN
        )
        return _pick_line(extra_lines, seed)
    if _contains_any(
        text,
        ("ахах", "хаха", "lol", "lmao", ")))", "😂", "😏", "😉"),
    ):
        extra_lines = SHARED_PLAYFUL_REPLIES_RU if lang == "ru" else SHARED_PLAYFUL_REPLIES_EN
        return _pick_line(extra_lines, seed)
    if _contains_any(
        text,
        ("ноч", "спишь", "вечер", "sleep", "night", "late", "bedtime"),
    ):
        extra_lines = SHARED_NIGHT_REPLIES_RU if lang == "ru" else SHARED_NIGHT_REPLIES_EN
        return _pick_line(extra_lines, seed)
    if _contains_any(
        text,
        ("поцел", "обнять", "kiss", "hug", "хочу тебя", "want you"),
    ):
        extra_lines = SHARED_BOLD_REPLIES_RU if lang == "ru" else SHARED_BOLD_REPLIES_EN
        return _pick_line(extra_lines, seed)
    if _contains_any(
        text,
        ("встрет", "увид", "погуля", "meet", "see you", "go out", "date"),
    ):
        extra_lines = SHARED_MEETING_REPLIES_RU if lang == "ru" else SHARED_MEETING_REPLIES_EN
        return _pick_line(extra_lines, seed)
    if "?" in text:
        return _pick_line(question_lines, seed)
    if len(text) <= 12:
        return _pick_line(short_lines, seed)
    if len(text) >= 90:
        extra_lines = SHARED_LONG_REPLIES_RU if lang == "ru" else SHARED_LONG_REPLIES_EN
        return _pick_line(extra_lines, seed)

    return _pick_line(text_lines, seed)


def _pick_line(lines: tuple[str, ...], seed: str) -> str:
    return random.Random(seed).choice(lines)


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _join_lines(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        merged.extend(group)
    return tuple(merged)


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
