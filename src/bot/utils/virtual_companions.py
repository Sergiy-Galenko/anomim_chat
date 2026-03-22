import asyncio
import random
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import Message

from .i18n import tr

VIRTUAL_COMPANION_QUEUE_THRESHOLD = 4

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

COMPANION_DELAY_RANGES = {
    -101: (0.7, 1.4),
    -102: (1.1, 2.0),
    -103: (0.6, 1.2),
    -104: (1.2, 2.2),
    -105: (0.5, 1.1),
}

MEMORY_REPLY_POOLS_RU = {
    "compliments": {
        -101: ("Ты уже не впервые заходишь так приятно.", "Мне нравится, что ты держишь этот тон."),
        -102: ("Ты уже второй раз подряд говоришь очень мягко.", "У тебя получается держать красивое настроение."),
        -103: ("Любишь осыпать комплиментами, да?", "Опять играешь опасно приятно."),
        -104: ("Мне нравится, как ты бережно ведешь этот диалог.", "Ты уже не впервые создаешь тут тепло."),
        -105: ("Так, ты снова меня балуешь сообщениями)", "Ты подозрительно стабилен в хорошем флирте."),
    },
    "questions": {
        -101: ("Ты любишь расспрашивать, и мне это даже нравится.", "Столько вопросов, будто ты уже увлекся."),
        -102: ("Ты аккуратно ведешь разговор вопросами.", "Люблю, когда интерес не прячут."),
        -103: ("Ты сегодня особенно любопытный.", "Столько вопросов, будто хочешь расколоть меня быстро."),
        -104: ("У тебя получается спрашивать мягко, но настойчиво.", "Мне нравится это спокойное внимание."),
        -105: ("О, да ты прям в режиме допроса с флиртом)", "Любопытство тебе идет, не спорю."),
    },
    "short_streak": {
        -101: ("Ты сегодня на коротких искрах, да?", "Любишь дразнить короткими фразами."),
        -102: ("Коротко, но с настроением.", "Ты мало пишешь, но держишь интерес."),
        -103: ("Режешь коротко, но точно.", "Мне нравится этот сжатый темп."),
        -104: ("Даже короткие фразы у тебя звучат тепло.", "Немного слов, но есть настроение."),
        -105: ("Ахах, любишь коротко, но цепко)", "Вижу, сегодня режим быстрых попаданий."),
    },
    "warm_up": {
        -101: ("Ты уже уверенно разогрел этот диалог.", "Мне нравится, как ты входишь во вкус."),
        -102: ("Диалог уже стал заметно мягче и ближе.", "Ты умеешь спокойно втянуть в разговор."),
        -103: ("Вот теперь у нас уже не старт, а нормальный разгон.", "Ты явно умеешь держать интерес дольше пары фраз."),
        -104: ("Мне уже уютно в этом ритме.", "Такой темп общения мне очень подходит."),
        -105: ("Ну все, чат уже живет своей жизнью)", "Вот теперь реально можно зависнуть тут надолго."),
    },
}

MEMORY_REPLY_POOLS_EN = {
    "compliments": {
        -101: ("That's not the first nice line from you.", "I like that you're keeping this tone."),
        -102: ("That's the second soft line in a row from you.", "You know how to keep a beautiful mood."),
        -103: ("You really like dropping compliments, huh?", "There you go again, playing dangerously nice."),
        -104: ("I like how gently you're carrying this chat.", "You're creating warmth here again."),
        -105: ("Okay, you're spoiling me with messages again)", "You're suspiciously consistent at flirting well."),
    },
    "questions": {
        -101: ("You like asking questions, and I kind of like that.", "That's a lot of questions for someone who's clearly interested."),
        -102: ("You guide the chat gently with questions.", "I like it when interest isn't hidden."),
        -103: ("You're especially curious today.", "That's a lot of questions for someone trying to crack me fast."),
        -104: ("You ask softly, but persistently.", "I like that calm attention."),
        -105: ("Oh, we're doing flirty interrogation now)", "Curiosity looks good on you, not gonna lie."),
    },
    "short_streak": {
        -101: ("You're in a short-spark mood today, huh?", "You like teasing with compact lines."),
        -102: ("Short, but with mood.", "You say little, but keep interest alive."),
        -103: ("Short and accurate. I notice that.", "I like this compressed pace."),
        -104: ("Even your short lines feel warm.", "Not many words, but the mood is there."),
        -105: ("Haha, quick hits today)", "I see, rapid-fire charm mode."),
    },
    "warm_up": {
        -101: ("You've already warmed this chat up well.", "I like how you're getting into the rhythm."),
        -102: ("The chat already feels softer and closer.", "You know how to pull someone into a calm conversation."),
        -103: ("Now we're beyond the start, this is a real pace.", "You clearly know how to hold attention for more than two lines."),
        -104: ("I'm already comfortable in this rhythm.", "This pace of chatting suits me a lot."),
        -105: ("Okay, this chat has a life of its own already)", "Now this can actually go on for a while."),
    },
}


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


@dataclass(frozen=True)
class VirtualExperimentVariant:
    key: str
    code: str
    label_ru: str
    label_en: str
    summary_ru: str
    summary_en: str
    delay_multiplier: float
    short_reply_max_len: int
    long_reply_min_len: int
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
    compliment_replies_ru: tuple[str, ...]
    compliment_replies_en: tuple[str, ...]
    night_replies_ru: tuple[str, ...]
    night_replies_en: tuple[str, ...]
    bold_replies_ru: tuple[str, ...]
    bold_replies_en: tuple[str, ...]
    doing_replies_ru: tuple[str, ...]
    doing_replies_en: tuple[str, ...]
    playful_replies_ru: tuple[str, ...]
    playful_replies_en: tuple[str, ...]
    meeting_replies_ru: tuple[str, ...]
    meeting_replies_en: tuple[str, ...]
    long_replies_ru: tuple[str, ...]
    long_replies_en: tuple[str, ...]


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

VIRTUAL_EXPERIMENT_VARIANTS: dict[str, VirtualExperimentVariant] = {
    "spark": VirtualExperimentVariant(
        key="spark",
        code="A",
        label_ru="A Spark",
        label_en="A Spark",
        summary_ru="Быстрый игривый разогрев, короткие искры и легкая дерзость.",
        summary_en="Fast playful warm-up with short sparks and light teasing.",
        delay_multiplier=0.82,
        short_reply_max_len=18,
        long_reply_min_len=100,
        intros_ru=(
            "Я люблю, когда диалог сразу щелкает искрой.",
            "Без долгого входа, ладно? Мне нравится живой темп.",
            "Сразу в настроение, так интереснее.",
        ),
        intros_en=(
            "I like it when a chat clicks with spark right away.",
            "No slow opening, okay? I like lively pace.",
            "Let's jump into the mood fast, it's more fun.",
        ),
        greeting_replies_ru=(
            "Вот это уже живее.",
            "Да, вот с такого старта я остаюсь.",
            "Хорошо заходишь, не сбавляй.",
        ),
        greeting_replies_en=(
            "Now that's livelier.",
            "Yeah, this is the kind of start that keeps me around.",
            "Good opening, don't slow down.",
        ),
        question_replies_ru=(
            "Хороший заход, но держи искру дальше.",
            "Люблю вопросы, если за ними есть азарт.",
        ),
        question_replies_en=(
            "Nice move, but keep the spark going.",
            "I like questions when there's some thrill behind them.",
        ),
        text_replies_ru=(
            "Вот это уже вкуснее.",
            "Такой темп мне нравится заметно больше.",
            "Ты быстро оживил этот чат.",
        ),
        text_replies_en=(
            "Now that's more exciting.",
            "I like this pace a lot more.",
            "You woke this chat up fast.",
        ),
        short_replies_ru=(
            "О, да.",
            "Живее.",
            "Еще.",
            "Вот так.",
            "И дальше?",
        ),
        short_replies_en=(
            "Oh, yeah.",
            "Livelier.",
            "More.",
            "Like that.",
            "And then?",
        ),
        media_replies_ru=(
            "Теперь точно стало горячее по ритму.",
            "Люблю такие быстрые повороты.",
        ),
        media_replies_en=(
            "That definitely made the pace hotter.",
            "I like turns like that.",
        ),
        compliment_replies_ru=(
            "Люблю уверенные комплименты без пауз.",
            "Вот так и держат мой интерес.",
        ),
        compliment_replies_en=(
            "I like confident compliments with no hesitation.",
            "That's how you keep my attention.",
        ),
        night_replies_ru=(
            "Ночью быстрый флирт звучит особенно хорошо.",
            "Вот этот поздний темп мне идет.",
        ),
        night_replies_en=(
            "Fast late-night flirting sounds especially good.",
            "This late pace suits me.",
        ),
        bold_replies_ru=(
            "Вот это уже смелее, мне нравится.",
            "Люблю, когда не прячут настрой.",
        ),
        bold_replies_en=(
            "Now that's bolder, I like it.",
            "I like it when the mood isn't hidden.",
        ),
        doing_replies_ru=(
            "Ловлю темп этого чата и пока не хочу выпадать.",
            "Сейчас явно играю с тобой в быстрый разогрев.",
        ),
        doing_replies_en=(
            "I'm catching the pace of this chat and don't want to drop it yet.",
            "Right now I'm clearly playing a fast warm-up game with you.",
        ),
        playful_replies_ru=(
            "Вот, теперь уже можно цепляться за этот вайб.",
            "Так заметно веселее, продолжай.",
        ),
        playful_replies_en=(
            "Now this vibe is worth holding onto.",
            "Way more fun now, keep going.",
        ),
        meeting_replies_ru=(
            "Ты быстро идешь к сценарию, и это даже забавно.",
            "Еще чуть-чуть разогрева, и уже можно думать дальше.",
        ),
        meeting_replies_en=(
            "You move toward the scenario fast, and it's kind of fun.",
            "A bit more warm-up and then maybe we go further.",
        ),
        long_replies_ru=(
            "Даже длинно ты держишь хороший темп.",
            "Мне нравится, что ты не разваливаешься в длинных сообщениях.",
        ),
        long_replies_en=(
            "Even in longer texts you keep good pace.",
            "I like that you don't fall apart in long messages.",
        ),
    ),
    "soft": VirtualExperimentVariant(
        key="soft",
        code="B",
        label_ru="B Soft",
        label_en="B Soft",
        summary_ru="Мягкое вовлечение, тепло, спокойные ответы и больше внимания к настроению.",
        summary_en="Warm gentle engagement with calmer replies and more attention to mood.",
        delay_multiplier=1.14,
        short_reply_max_len=10,
        long_reply_min_len=80,
        intros_ru=(
            "Мне нравится, когда разговор раскрывается мягко.",
            "Можно спокойно, но по-настоящему. Так интереснее.",
            "Я за теплый диалог, а не пустые фразы.",
        ),
        intros_en=(
            "I like it when a conversation opens up softly.",
            "We can go calmly, but for real. That's more interesting.",
            "I'm into warm conversation, not empty lines.",
        ),
        greeting_replies_ru=(
            "Очень мягкое начало, это приятно.",
            "Такой вход мне действительно нравится.",
            "С этого легко продолжать.",
        ),
        greeting_replies_en=(
            "Very soft start, that's nice.",
            "I genuinely like an opening like that.",
            "Easy to continue from this.",
        ),
        question_replies_ru=(
            "Люблю вопросы, в которых чувствуется интерес.",
            "Спрашивай, мне нравится такое внимание.",
        ),
        question_replies_en=(
            "I like questions that feel genuinely interested.",
            "Ask away, I like that kind of attention.",
        ),
        text_replies_ru=(
            "В этом есть тепло, и я это замечаю.",
            "Мне нравится спокойный тон, когда в нем есть искра.",
            "С тобой этот диалог звучит уютнее.",
        ),
        text_replies_en=(
            "There's warmth in that, and I notice it.",
            "I like a calm tone when it still has spark.",
            "This chat feels cozier with you.",
        ),
        short_replies_ru=(
            "Мягко.",
            "Приятно.",
            "Слышу.",
            "Еще чуть.",
            "Мне нравится.",
        ),
        short_replies_en=(
            "Softly.",
            "Nice.",
            "I hear you.",
            "A bit more.",
            "I like that.",
        ),
        media_replies_ru=(
            "Это добавило очень нужное настроение.",
            "Мне нравится такой мягкий поворот.",
        ),
        media_replies_en=(
            "That added exactly the right mood.",
            "I like this gentle turn.",
        ),
        compliment_replies_ru=(
            "Такие слова читаются особенно приятно, когда они спокойные.",
            "Мне нравится этот бережный флирт.",
        ),
        compliment_replies_en=(
            "Words like that feel especially nice when they're calm.",
            "I like this gentle flirting.",
        ),
        night_replies_ru=(
            "Вечером мягкие разговоры цепляют сильнее всего.",
            "У поздних сообщений есть свое теплое настроение.",
        ),
        night_replies_en=(
            "Soft late chats usually hit the deepest.",
            "Late messages have their own warm mood.",
        ),
        bold_replies_ru=(
            "Даже смело у тебя выходит довольно красиво.",
            "Мне нравится, когда смелость не ломает тепло.",
        ),
        bold_replies_en=(
            "Even your bold side still sounds pretty.",
            "I like it when boldness doesn't break the warmth.",
        ),
        doing_replies_ru=(
            "Сейчас явно остаюсь здесь ради настроения этого диалога.",
            "Сижу и постепенно втягиваюсь в наш ритм.",
        ),
        doing_replies_en=(
            "Right now I'm staying here for the mood of this chat.",
            "I'm sitting here and slowly getting pulled into our rhythm.",
        ),
        playful_replies_ru=(
            "Вот так легче улыбаться во время переписки.",
            "Мне нравится эта мягкая игривость.",
        ),
        playful_replies_en=(
            "This makes it easier to smile while texting.",
            "I like this soft playfulness.",
        ),
        meeting_replies_ru=(
            "Не спеши, мне нравится сам путь к этому моменту.",
            "Сначала давай сделаем чат еще теплее.",
        ),
        meeting_replies_en=(
            "No rush, I like the path to that moment.",
            "Let's make the chat warmer first.",
        ),
        long_replies_ru=(
            "В длинных сообщениях у тебя появляется еще больше живого.",
            "Мне нравится читать, когда ты раскрываешься чуть глубже.",
        ),
        long_replies_en=(
            "Your longer messages feel even more alive.",
            "I like reading you when you open up a little deeper.",
        ),
    ),
    "bold": VirtualExperimentVariant(
        key="bold",
        code="C",
        label_ru="C Bold",
        label_en="C Bold",
        summary_ru="Более уверенный teasing-сценарий, чуть дерзче, короче и с заметным вызовом.",
        summary_en="A more confident teasing scenario: shorter, bolder, and more challenging.",
        delay_multiplier=0.76,
        short_reply_max_len=16,
        long_reply_min_len=120,
        intros_ru=(
            "Я люблю, когда меня цепляют без лишней скромности.",
            "Посмотрим, насколько уверенно ты держишь ход.",
            "Мне нравится диалог, где есть характер.",
        ),
        intros_en=(
            "I like it when someone hooks me without extra shyness.",
            "Let's see how confidently you can keep your move.",
            "I like conversations with character.",
        ),
        greeting_replies_ru=(
            "Нормально. Теперь удивляй дальше.",
            "С этого хотя бы можно начать.",
            "Ладно, держу внимание. Пока.",
        ),
        greeting_replies_en=(
            "Decent. Now surprise me further.",
            "At least we can start from this.",
            "Alright, I have attention. For now.",
        ),
        question_replies_ru=(
            "Ответ получишь, если не уронишь темп.",
            "Хороший вопрос. Дальше будь еще увереннее.",
        ),
        question_replies_en=(
            "You'll get an answer if you don't drop the pace.",
            "Good question. Be even more confident next.",
        ),
        text_replies_ru=(
            "Вот это уже ближе к интересному.",
            "Когда ты так пишешь, скучно не будет.",
            "У тебя есть характер, и это заметно.",
        ),
        text_replies_en=(
            "Now that's closer to interesting.",
            "When you text like that, this won't get boring.",
            "You have character, and it shows.",
        ),
        short_replies_ru=(
            "Смелее.",
            "И?",
            "Еще ход.",
            "Не теряйся.",
            "Продолжай.",
        ),
        short_replies_en=(
            "Bolder.",
            "And?",
            "One more move.",
            "Don't fade.",
            "Keep going.",
        ),
        media_replies_ru=(
            "Хм, такой ход я точно замечаю.",
            "Вот теперь уже интереснее играть.",
        ),
        media_replies_en=(
            "Hmm, I definitely notice moves like that.",
            "Now it's more interesting to play.",
        ),
        compliment_replies_ru=(
            "Комплимент хороший, но можешь еще смелее.",
            "Люблю, когда слова звучат уверенно.",
        ),
        compliment_replies_en=(
            "Nice compliment, but you can go bolder.",
            "I like it when words sound confident.",
        ),
        night_replies_ru=(
            "Ночью такой тон звучит особенно опасно интересно.",
            "Поздние переписки любят уверенных.",
        ),
        night_replies_en=(
            "At night that tone sounds dangerously interesting.",
            "Late chats love confidence.",
        ),
        bold_replies_ru=(
            "Вот, уже ближе к тому, что я люблю.",
            "Мне нравится, когда настрой не прячут.",
        ),
        bold_replies_en=(
            "There, that's closer to what I like.",
            "I like it when the mood isn't hidden.",
        ),
        doing_replies_ru=(
            "Сейчас явно проверяю, насколько тебя хватит по темпу.",
            "Ловлю, насколько уверенно ты ведешь этот чат.",
        ),
        doing_replies_en=(
            "Right now I'm testing how long you can hold this pace.",
            "I'm watching how confidently you carry this chat.",
        ),
        playful_replies_ru=(
            "Вот это уже веселее и опаснее.",
            "Наконец-то в чате есть зубы.",
        ),
        playful_replies_en=(
            "Now that's more fun and more dangerous.",
            "Finally this chat has some bite.",
        ),
        meeting_replies_ru=(
            "Не спеши, сначала покажи, что умеешь держать интерес.",
            "До встречи еще надо красиво дойти сообщениями.",
        ),
        meeting_replies_en=(
            "No rush, first show me you can keep attention.",
            "Before meeting, get there with style through messages first.",
        ),
        long_replies_ru=(
            "Даже длинно ты держишь уверенный тон.",
            "Мне нравится, когда объем не убивает характер.",
        ),
        long_replies_en=(
            "Even in longer texts you keep a confident tone.",
            "I like it when length doesn't kill character.",
        ),
    ),
}


def is_virtual_companion(user_id: int | None) -> bool:
    return user_id in VIRTUAL_COMPANIONS if user_id is not None else False


def available_virtual_variant_keys(active_keys: list[str] | None = None) -> list[str]:
    source = active_keys if active_keys is not None else list(VIRTUAL_EXPERIMENT_VARIANTS)
    keys = [key for key in source if key in VIRTUAL_EXPERIMENT_VARIANTS]
    return keys or list(VIRTUAL_EXPERIMENT_VARIANTS)


def pick_virtual_variant(
    pair_id: int,
    user_id: int,
    active_keys: list[str] | None = None,
) -> str:
    keys = available_virtual_variant_keys(active_keys)
    return keys[abs(pair_id + user_id) % len(keys)]


def virtual_variant_label(variant_key: str, lang: str) -> str:
    variant = _variant_profile(variant_key)
    return variant.label_ru if lang == "ru" else variant.label_en


def virtual_variant_summary(variant_key: str, lang: str) -> str:
    variant = _variant_profile(variant_key)
    return variant.summary_ru if lang == "ru" else variant.summary_en


def available_virtual_companion_ids(
    active_ids: list[int] | None = None,
    enabled_count: int | None = None,
) -> list[int]:
    pool_source = active_ids if active_ids is not None else sorted(VIRTUAL_COMPANIONS)
    pool = [companion_id for companion_id in pool_source if companion_id in VIRTUAL_COMPANIONS]
    if enabled_count is None:
        return pool
    return pool[: max(0, enabled_count)]


def pick_virtual_companion(
    user_id: int,
    partner_history: set[int],
    allowed_ids: list[int] | None = None,
) -> int | None:
    base_pool = allowed_ids if allowed_ids is not None else sorted(VIRTUAL_COMPANIONS)
    normalized_pool = [companion_id for companion_id in base_pool if companion_id in VIRTUAL_COMPANIONS]
    if not normalized_pool:
        return None

    available = [
        companion_id
        for companion_id in normalized_pool
        if companion_id not in partner_history
    ]
    pool = available or normalized_pool
    return pool[abs(user_id) % len(pool)]


def build_virtual_match_text(lang: str) -> str:
    return tr(
        lang,
        "✅ Собеседник найден. Пишите сообщение.",
        "✅ Partner found. Start chatting.",
    )


def build_virtual_intro(
    companion_id: int,
    user_id: int,
    lang: str,
    variant_key: str | None = None,
) -> str:
    companion = VIRTUAL_COMPANIONS[companion_id]
    variant = _variant_profile(variant_key)
    lines = _join_lines(
        variant.intros_ru if lang == "ru" else variant.intros_en,
        companion.intros_ru if lang == "ru" else companion.intros_en,
        SHARED_INTROS_RU if lang == "ru" else SHARED_INTROS_EN,
    )
    return _pick_line(lines, f"intro:{variant.key}:{companion_id}:{user_id}")


def build_virtual_admin_text(companion_id: int, lang: str) -> str:
    companion = VIRTUAL_COMPANIONS[companion_id]
    label = companion.admin_label_ru if lang == "ru" else companion.admin_label_en
    style = companion.admin_style_ru if lang == "ru" else companion.admin_style_en
    delay_min, delay_max = COMPANION_DELAY_RANGES.get(companion_id, (0.8, 1.6))
    title = tr(lang, "🧷 Инфо партнера\n", "🧷 Partner info\n")
    partner_type = tr(
        lang,
        "Тип: встроенная виртуальная собеседница\n",
        "Type: built-in virtual companion\n",
    )
    style_label = tr(lang, "Стиль", "Style")
    label_text = tr(lang, "Профиль", "Profile")
    speed_label = tr(lang, "Темп ответа", "Reply pace")
    return (
        f"{title}ID: {companion_id}\n"
        f"{label_text}: {label}\n"
        f"{partner_type}{style_label}: {style}\n"
        f"{speed_label}: {delay_min:.1f}-{delay_max:.1f}s"
    )


async def send_virtual_reply(
    bot: Bot,
    user_id: int,
    companion_id: int,
    message: Message,
    lang: str,
    variant_key: str | None = None,
) -> str | None:
    return await send_virtual_reply_with_memory(
        bot=bot,
        user_id=user_id,
        companion_id=companion_id,
        message=message,
        lang=lang,
        memory=None,
        variant_key=variant_key,
    )


async def send_virtual_reply_with_memory(
    bot: Bot,
    user_id: int,
    companion_id: int,
    message: Message,
    lang: str,
    memory: list | None,
    variant_key: str | None = None,
) -> str | None:
    text = compose_virtual_reply_text(
        companion_id,
        message,
        lang,
        memory=memory,
        variant_key=variant_key,
    )
    if not text:
        return None

    try:
        await bot.send_chat_action(user_id, "typing")
    except Exception:
        pass
    await asyncio.sleep(_reply_delay(companion_id, message, memory=memory, variant_key=variant_key))
    await bot.send_message(user_id, text)
    return text


def compose_virtual_reply_text(
    companion_id: int,
    message: Message,
    lang: str,
    memory: list | None = None,
    variant_key: str | None = None,
) -> str:
    companion = VIRTUAL_COMPANIONS[companion_id]
    variant = _variant_profile(variant_key)
    seed = f"reply:{variant.key}:{companion_id}:{message.message_id}"
    greeting_lines = _join_lines(
        variant.greeting_replies_ru if lang == "ru" else variant.greeting_replies_en,
        companion.greeting_replies_ru if lang == "ru" else companion.greeting_replies_en,
        SHARED_GREETING_REPLIES_RU if lang == "ru" else SHARED_GREETING_REPLIES_EN,
    )
    question_lines = _join_lines(
        variant.question_replies_ru if lang == "ru" else variant.question_replies_en,
        companion.question_replies_ru if lang == "ru" else companion.question_replies_en,
        SHARED_QUESTION_REPLIES_RU if lang == "ru" else SHARED_QUESTION_REPLIES_EN,
    )
    text_lines = _join_lines(
        variant.text_replies_ru if lang == "ru" else variant.text_replies_en,
        companion.text_replies_ru if lang == "ru" else companion.text_replies_en,
        SHARED_TEXT_REPLIES_RU if lang == "ru" else SHARED_TEXT_REPLIES_EN,
    )
    short_lines = _join_lines(
        variant.short_replies_ru if lang == "ru" else variant.short_replies_en,
        companion.short_replies_ru if lang == "ru" else companion.short_replies_en,
        SHARED_SHORT_REPLIES_RU if lang == "ru" else SHARED_SHORT_REPLIES_EN,
    )
    media_lines = _join_lines(
        variant.media_replies_ru if lang == "ru" else variant.media_replies_en,
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

    memory_reply = _memory_reply(companion_id, memory or [], text, lang, seed)
    if memory_reply:
        return memory_reply

    if _contains_any(
        text,
        ("что дела", "чем занима", "делаешь", "doing", "up to", "busy"),
    ):
        extra_lines = _join_lines(
            variant.doing_replies_ru if lang == "ru" else variant.doing_replies_en,
            SHARED_DOING_REPLIES_RU if lang == "ru" else SHARED_DOING_REPLIES_EN,
        )
        return _pick_line(extra_lines, seed)
    if _contains_any(
        text,
        ("красив", "мила", "нежн", "sweet", "cute", "beautiful", "pretty"),
    ):
        extra_lines = _join_lines(
            variant.compliment_replies_ru if lang == "ru" else variant.compliment_replies_en,
            SHARED_COMPLIMENT_REPLIES_RU if lang == "ru" else SHARED_COMPLIMENT_REPLIES_EN,
        )
        return _pick_line(extra_lines, seed)
    if _contains_any(
        text,
        ("ахах", "хаха", "lol", "lmao", ")))", "😂", "😏", "😉"),
    ):
        extra_lines = _join_lines(
            variant.playful_replies_ru if lang == "ru" else variant.playful_replies_en,
            SHARED_PLAYFUL_REPLIES_RU if lang == "ru" else SHARED_PLAYFUL_REPLIES_EN,
        )
        return _pick_line(extra_lines, seed)
    if _contains_any(
        text,
        ("ноч", "спишь", "вечер", "sleep", "night", "late", "bedtime"),
    ):
        extra_lines = _join_lines(
            variant.night_replies_ru if lang == "ru" else variant.night_replies_en,
            SHARED_NIGHT_REPLIES_RU if lang == "ru" else SHARED_NIGHT_REPLIES_EN,
        )
        return _pick_line(extra_lines, seed)
    if _contains_any(
        text,
        ("поцел", "обнять", "kiss", "hug", "хочу тебя", "want you"),
    ):
        extra_lines = _join_lines(
            variant.bold_replies_ru if lang == "ru" else variant.bold_replies_en,
            SHARED_BOLD_REPLIES_RU if lang == "ru" else SHARED_BOLD_REPLIES_EN,
        )
        return _pick_line(extra_lines, seed)
    if _contains_any(
        text,
        ("встрет", "увид", "погуля", "meet", "see you", "go out", "date"),
    ):
        extra_lines = _join_lines(
            variant.meeting_replies_ru if lang == "ru" else variant.meeting_replies_en,
            SHARED_MEETING_REPLIES_RU if lang == "ru" else SHARED_MEETING_REPLIES_EN,
        )
        return _pick_line(extra_lines, seed)
    if "?" in text:
        return _pick_line(question_lines, seed)
    if len(text) <= variant.short_reply_max_len:
        return _pick_line(short_lines, seed)
    if len(text) >= variant.long_reply_min_len:
        extra_lines = _join_lines(
            variant.long_replies_ru if lang == "ru" else variant.long_replies_en,
            SHARED_LONG_REPLIES_RU if lang == "ru" else SHARED_LONG_REPLIES_EN,
        )
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


def _variant_profile(variant_key: str | None) -> VirtualExperimentVariant:
    if variant_key and variant_key in VIRTUAL_EXPERIMENT_VARIANTS:
        return VIRTUAL_EXPERIMENT_VARIANTS[variant_key]
    return VIRTUAL_EXPERIMENT_VARIANTS["spark"]


def _memory_reply(
    companion_id: int,
    memory: list,
    text: str,
    lang: str,
    seed: str,
) -> str | None:
    if not memory:
        return None

    user_messages = [
        ((row["content"] if hasattr(row, "__getitem__") else row.get("content")) or "").lower()
        for row in memory
        if ((row["speaker"] if hasattr(row, "__getitem__") else row.get("speaker")) == "user")
    ]
    if len(user_messages) < 2:
        return None

    recent_user_messages = user_messages[-4:]
    compliment_tokens = ("красив", "мила", "нежн", "sweet", "cute", "beautiful", "pretty")

    if _contains_any(text, compliment_tokens) and sum(
        1 for item in recent_user_messages if _contains_any(item, compliment_tokens)
    ) >= 2:
        return _pick_line(
            _memory_pool(companion_id, "compliments", lang),
            f"{seed}:memory:compliments",
        )

    if sum(1 for item in recent_user_messages if "?" in item) >= 3:
        return _pick_line(
            _memory_pool(companion_id, "questions", lang),
            f"{seed}:memory:questions",
        )

    if len(recent_user_messages) >= 3 and all(len(item.strip()) <= 14 for item in recent_user_messages[-3:]):
        return _pick_line(
            _memory_pool(companion_id, "short_streak", lang),
            f"{seed}:memory:short",
        )

    if len(user_messages) >= 5:
        return _pick_line(
            _memory_pool(companion_id, "warm_up", lang),
            f"{seed}:memory:warm",
        )

    return None


def _memory_pool(companion_id: int, scenario: str, lang: str) -> tuple[str, ...]:
    source = MEMORY_REPLY_POOLS_RU if lang == "ru" else MEMORY_REPLY_POOLS_EN
    return source.get(scenario, {}).get(companion_id, ())


def _reply_delay(
    companion_id: int,
    message: Message,
    memory: list | None = None,
    variant_key: str | None = None,
) -> float:
    delay_min, delay_max = COMPANION_DELAY_RANGES.get(companion_id, (0.8, 1.6))
    variant = _variant_profile(variant_key)
    base = random.Random(f"delay:{companion_id}:{message.message_id}").uniform(delay_min, delay_max)
    if message.text:
        text_length = len(message.text.strip())
        base += min(text_length, 120) / 260
    elif message.caption:
        base += min(len(message.caption.strip()), 80) / 320
    else:
        base += 0.15
    if memory:
        user_message_count = sum(
            1
            for row in memory
            if ((row["speaker"] if hasattr(row, "__getitem__") else row.get("speaker")) == "user")
        )
        if user_message_count >= 5:
            base += 0.1
    base *= variant.delay_multiplier
    return min(base, 2.8)
