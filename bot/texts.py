"""All user-facing strings, in Russian and Uzbek."""

TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "start": (
            "👋 Привет, {name}!\n\n"
            "Я помогу:\n"
            "🔎 <b>Найти музыку</b> — напиши название песни или имя исполнителя.\n"
            "📥 <b>Скачать видео</b> — пришли ссылку на YouTube, Instagram или TikTok.\n"
            "🎧 <b>Узнать песню</b> — пришли видео, аудио, голосовое или кружочек, "
            "и я найду, что за музыка играет (как Shazam).\n\n"
            "🌐 Язык: /lang"
        ),
        "help": (
            "📖 <b>Как пользоваться</b>\n\n"
            "• Напиши <i>Dior</i> или <i>Pop Smoke Dior</i> — получишь список, нажми номер и получишь MP3.\n"
            "• Пришли ссылку — получишь видео в хорошем качестве. Кнопка «🎵 Скачать песню» найдёт музыку из видео.\n"
            "• Пришли видео / аудио / голосовое — я распознаю песню.\n\n"
            "В группе: добавь меня и присылай ссылки — я буду скачивать их прямо в чат."
        ),
        "choose_lang": "🌐 Выберите язык:",
        "lang_set": "✅ Язык: Русский",
        "searching": "🔎 Ищу…",
        "nothing_found": "😔 Ничего не нашёл по запросу «{q}». Попробуй написать по-другому.",
        "results_header": "🔎 <b>{q}</b>\n\n",
        "search_expired": "Поиск устарел, отправь запрос ещё раз.",
        "downloading": "⏳",
        "audio_caption": "🎧 Найдено через @{bot}",
        "video_caption": "📥 Скачано через @{bot}",
        "btn_get_song": "🎵 Скачать песню",
        "btn_add_group": "➕ Добавить в группу",
        "recognizing": "🎧 Слушаю…",
        "not_recognized": "😔 Не удалось распознать музыку. Попробуй прислать отрывок, где песня слышна чётче (10–20 секунд).",
        "recognized": "🎵 <b>{title}</b> — {artist}",
        "song_not_found_dl": "🎵 Это <b>{title}</b> — {artist}, но MP3 найти не удалось. Попробуй поиск по названию.",
        "unsupported_link": "🤔 Эту ссылку я не поддерживаю. Пришли ссылку на YouTube, Instagram или TikTok.",
        "dl_failed": "😔 Не получилось скачать. Возможно, видео приватное, удалено или доступно только после входа.",
        "too_big": "📦 Видео слишком большое для отправки в Telegram даже в низком качестве.",
        "file_too_big": "📦 Файл слишком большой. Пришли отрывок короче (до 20 МБ).",
        "busy": "⏳ Подожди, я ещё обрабатываю твой прошлый запрос.",
        "error": "⚠️ Что-то пошло не так. Попробуй ещё раз.",
        "stats": "👥 Пользователей: {users}\n📥 Скачиваний: {downloads}\n🎧 Распознаваний: {recognitions}",
    },
    "uz": {
        "start": (
            "👋 Salom, {name}!\n\n"
            "Men yordam beraman:\n"
            "🔎 <b>Musiqa topish</b> — qo'shiq nomi yoki ijrochi ismini yozing.\n"
            "📥 <b>Video yuklash</b> — YouTube, Instagram yoki TikTok havolasini yuboring.\n"
            "🎧 <b>Qo'shiqni aniqlash</b> — video, audio, ovozli xabar yoki dumaloq video yuboring, "
            "qaysi musiqa ekanini topaman (Shazam kabi).\n\n"
            "🌐 Til: /lang"
        ),
        "help": (
            "📖 <b>Qanday foydalanish</b>\n\n"
            "• <i>Dior</i> yoki <i>Pop Smoke Dior</i> deb yozing — ro'yxat chiqadi, raqamni bosing va MP3 oling.\n"
            "• Havola yuboring — videoni yaxshi sifatda olasiz. «🎵 Qo'shiqni yuklab olish» tugmasi videodagi musiqani topadi.\n"
            "• Video / audio / ovozli xabar yuboring — qo'shiqni aniqlayman.\n\n"
            "Guruhda: meni qo'shing va havolalarni yuboring — to'g'ridan-to'g'ri chatga yuklayman."
        ),
        "choose_lang": "🌐 Tilni tanlang:",
        "lang_set": "✅ Til: O'zbekcha",
        "searching": "🔎 Qidiryapman…",
        "nothing_found": "😔 «{q}» bo'yicha hech narsa topilmadi. Boshqacha yozib ko'ring.",
        "results_header": "🔎 <b>{q}</b>\n\n",
        "search_expired": "Qidiruv eskirdi, so'rovni qayta yuboring.",
        "downloading": "⏳",
        "audio_caption": "🎧 @{bot} orqali istagan musiqangizni tez va oson toping!",
        "video_caption": "📥 @{bot} orqali yuklab olindi",
        "btn_get_song": "🎵 Qo'shiqni yuklab olish",
        "btn_add_group": "➕ Guruhga qo'shish",
        "recognizing": "🎧 Tinglayapman…",
        "not_recognized": "😔 Musiqani aniqlab bo'lmadi. Qo'shiq aniqroq eshitiladigan qismini yuboring (10–20 soniya).",
        "recognized": "🎵 <b>{title}</b> — {artist}",
        "song_not_found_dl": "🎵 Bu <b>{title}</b> — {artist}, lekin MP3 topilmadi. Nomi bo'yicha qidirib ko'ring.",
        "unsupported_link": "🤔 Bu havolani qo'llab-quvvatlamayman. YouTube, Instagram yoki TikTok havolasini yuboring.",
        "dl_failed": "😔 Yuklab bo'lmadi. Video yopiq, o'chirilgan yoki faqat kirish orqali ochiladi.",
        "too_big": "📦 Video Telegram uchun juda katta, hatto past sifatda ham.",
        "file_too_big": "📦 Fayl juda katta. Qisqaroq qism yuboring (20 MB gacha).",
        "busy": "⏳ Kuting, oldingi so'rovingizni hali bajaryapman.",
        "error": "⚠️ Nimadir xato ketdi. Qayta urinib ko'ring.",
        "stats": "👥 Foydalanuvchilar: {users}\n📥 Yuklashlar: {downloads}\n🎧 Aniqlashlar: {recognitions}",
    },
}

LANGS = {"ru": "🇷🇺 Русский", "uz": "🇺🇿 O'zbekcha"}
DEFAULT_LANG = "ru"


def t(lang: str | None, key: str, **kw) -> str:
    table = TEXTS.get(lang or DEFAULT_LANG, TEXTS[DEFAULT_LANG])
    text = table.get(key) or TEXTS[DEFAULT_LANG][key]
    return text.format(**kw) if kw else text


def guess_lang(language_code: str | None) -> str:
    return "uz" if (language_code or "").lower().startswith("uz") else DEFAULT_LANG
