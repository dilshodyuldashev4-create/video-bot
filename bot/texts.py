"""All user-facing strings, in Russian and Uzbek."""

LINE = "━━━━━━━━━━━━━━━"

TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "start": (
            "⚡️ <b>Йо, {name}!</b> Ты в самом быстром музыкальном боте 🔥\n"
            f"{LINE}\n"
            "🎧 <b>Музыка</b> — напиши название или артиста\n"
            "📥 <b>Видео</b> — кинь ссылку YouTube · Instagram · TikTok\n"
            "🔍 <b>Shazam</b> — скинь видео, аудио, голосовое или кружок, узнаю трек\n"
            "🔥 <b>Топ недели</b> · 🇺🇿 <b>UZ</b> · 🇷🇺 <b>RU</b> — свежие чарты в меню\n"
            "⚡ <b>Speed up</b> · 🌙 <b>Slowed + reverb</b> — любая песня в один клик\n"
            "❤️ <b>Моя музыка</b> — лайкай треки и собирай свой плейлист\n"
            f"{LINE}\n"
            "👇 Попробуй прямо сейчас: <code>Pop Smoke Dior</code>"
        ),
        "help": (
            "📖 <b>Как это работает</b>\n"
            f"{LINE}\n"
            "🎧 Пишешь <code>Dior</code> → выбираешь номер → MP3 у тебя\n"
            "📥 Кидаешь ссылку → видео в HD без водяного знака\n"
            "🎵 Под видео жмёшь «Скачать песню» → бот найдёт трек из видео\n"
            "🔍 Скидываешь видео / аудио / голосовое → Shazam узнаёт песню\n"
            "❤️ Жмёшь «В избранное» → трек в твоём плейлисте /mymusic\n"
            "⚡ / 🌙 Под любым MP3 → speed up или slowed + reverb версия\n"
            "🔥 Меню → топ недели, топ Узбекистана и России (/top)\n"
            f"{LINE}\n"
            "👥 Добавь бота в группу, и он будет качать ссылки прямо в чат"
        ),
        "choose_lang": "🌐 Выбери язык:",
        "lang_set": "✅ Язык: Русский",
        "searching": "🔎",
        "nothing_found": "🙈 По запросу «<b>{q}</b>» ничего нет. Попробуй написать по-другому.",
        "results_header": "🎧 <b>{q}</b>\n<i>Выбирай номер 👇</i> · стр. {page}/{pages}\n" + LINE,
        "search_expired": "⌛️ Поиск устарел, отправь запрос ещё раз.",
        "downloading": "⏳",
        "audio_footer": "⚡️ @{bot} — музыка за секунду",
        "video_caption": "{icon} <b>Готово!</b> Видео из {platform}\n" + LINE + "\n⚡️ Скачано через @{bot}",
        "btn_get_song": "🎵 Скачать песню из видео",
        "btn_add_group": "➕ В группу",
        "btn_share": "🔗 Поделиться",
        "btn_like": "❤️ В избранное",
        "btn_liked": "💖 В избранном",
        "btn_shazam": "🔍 Открыть в Shazam",
        "share_text": "🔥 Качаю музыку и видео из YouTube, Instagram и TikTok + Shazam прямо в Telegram",
        "liked": "💖 Добавлено в «Моя музыка»",
        "unliked": "💔 Убрано из «Моя музыка»",
        "my_music_header": "❤️ <b>Моя музыка</b> · {n} треков\n<i>Выбирай номер 👇</i> · стр. {page}/{pages}\n" + LINE,
        "my_music_empty": "❤️ <b>Моя музыка</b> пока пусто.\nЖми «❤️ В избранное» под любым треком, и он появится здесь.",
        "menu_top_world": "🔥 Топ недели",
        "menu_top_uz": "🇺🇿 Топ UZ",
        "menu_top_ru": "🇷🇺 Топ RU",
        "chart_world_header": "🔥 <b>Топ недели</b> · то, что все шазамят и крутят в TikTok\n<i>Выбирай номер 👇</i> · стр. {page}/{pages}\n" + LINE,
        "chart_uz_header": "🇺🇿 <b>Топ Узбекистана</b>\n<i>Выбирай номер 👇</i> · стр. {page}/{pages}\n" + LINE,
        "chart_ru_header": "🇷🇺 <b>Топ России</b>\n<i>Выбирай номер 👇</i> · стр. {page}/{pages}\n" + LINE,
        "chart_failed": "😔 Чарт сейчас не загрузился. Попробуй через минуту.",
        "btn_up": "⚡ Speed up",
        "btn_slow": "🌙 Slowed + reverb",
        "fx_header_up": "⚡ <b>Speed up</b> версия",
        "fx_header_slow": "🌙 <b>Slowed + reverb</b> версия",
        "menu_my_music": "❤️ Моя музыка",
        "menu_help": "❓ Помощь",
        "menu_lang": "🌐 Язык",
        "recognizing": "🎧",
        "not_recognized": "🙉 Не смог узнать трек. Скинь отрывок, где музыку слышно чётче (10–20 сек).",
        "recognized_card": "🔍 <b>Shazam нашёл!</b>\n" + LINE + "\n🎵 <b>{title}</b>\n👤 {artist}\n" + LINE + "\n⏬ Качаю MP3…",
        "recognized_header": "🔍 Найдено по звуку",
        "song_not_found_dl": "🎵 Это <b>{title}</b> — {artist}, но MP3 найти не удалось. Попробуй поиск по названию.",
        "unsupported_link": "🤔 Такую ссылку не знаю. Кидай YouTube, Instagram или TikTok.",
        "track_failed": "😔 Этот трек сейчас не качается. Попробуй другой номер из списка.",
        "dl_failed": "😔 Не получилось скачать. Возможно, видео приватное, удалено или доступно только после входа.",
        "too_big": "📦 Видео слишком тяжёлое для Telegram даже в низком качестве.",
        "file_too_big": "📦 Файл слишком большой. Скинь отрывок покороче (до 20 МБ).",
        "busy": "⏳ Секунду, ещё делаю твой прошлый запрос.",
        "error": "⚠️ Что-то пошло не так. Попробуй ещё раз.",
        "stats": "📊 <b>Статистика</b>\n" + LINE + "\n👥 Пользователей: <b>{users}</b>\n📥 Скачиваний: <b>{downloads}</b>\n🔍 Распознаваний: <b>{recognitions}</b>",
    },
    "uz": {
        "start": (
            "⚡️ <b>Salom, {name}!</b> Eng tezkor musiqa botiga xush kelibsiz 🔥\n"
            f"{LINE}\n"
            "🎧 <b>Musiqa</b> — qo'shiq nomi yoki ijrochini yozing\n"
            "📥 <b>Video</b> — YouTube · Instagram · TikTok havolasini yuboring\n"
            "🔍 <b>Shazam</b> — video, audio, ovozli xabar yoki dumaloq video yuboring, qo'shiqni topaman\n"
            "🔥 <b>Hafta topi</b> · 🇺🇿 <b>UZ</b> · 🇷🇺 <b>RU</b> — yangi chartlar menyuda\n"
            "⚡ <b>Speed up</b> · 🌙 <b>Slowed + reverb</b> — istalgan qo'shiq bir bosishda\n"
            "❤️ <b>Mening musiqam</b> — treklarni yoqtiring va pleylist yig'ing\n"
            f"{LINE}\n"
            "👇 Hoziroq sinab ko'ring: <code>Pop Smoke Dior</code>"
        ),
        "help": (
            "📖 <b>Qanday ishlaydi</b>\n"
            f"{LINE}\n"
            "🎧 <code>Dior</code> deb yozing → raqamni tanlang → MP3 sizda\n"
            "📥 Havola yuboring → HD video, suv belgisiz\n"
            "🎵 Video ostidagi «Qo'shiqni yuklab olish» → videodagi trekni topadi\n"
            "🔍 Video / audio / ovozli xabar yuboring → Shazam qo'shiqni aniqlaydi\n"
            "❤️ «Sevimlilarga» bosing → trek /mymusic pleylistingizda\n"
            "⚡ / 🌙 Istalgan MP3 ostida → speed up yoki slowed + reverb versiya\n"
            "🔥 Menyu → hafta topi, O'zbekiston va Rossiya topi (/top)\n"
            f"{LINE}\n"
            "👥 Botni guruhga qo'shing — havolalarni to'g'ridan-to'g'ri chatga yuklaydi"
        ),
        "choose_lang": "🌐 Tilni tanlang:",
        "lang_set": "✅ Til: O'zbekcha",
        "searching": "🔎",
        "nothing_found": "🙈 «<b>{q}</b>» bo'yicha hech narsa topilmadi. Boshqacha yozib ko'ring.",
        "results_header": "🎧 <b>{q}</b>\n<i>Raqamni tanlang 👇</i> · {page}/{pages}-sahifa\n" + LINE,
        "search_expired": "⌛️ Qidiruv eskirdi, so'rovni qayta yuboring.",
        "downloading": "⏳",
        "audio_footer": "⚡️ @{bot} orqali istagan musiqangizni tez va oson toping!",
        "video_caption": "{icon} <b>Tayyor!</b> {platform} videosi\n" + LINE + "\n⚡️ @{bot} orqali yuklab olindi",
        "btn_get_song": "🎵 Qo'shiqni yuklab olish",
        "btn_add_group": "➕ Guruhga qo'shish",
        "btn_share": "🔗 Ulashish",
        "btn_like": "❤️ Sevimlilarga",
        "btn_liked": "💖 Sevimlilarda",
        "btn_shazam": "🔍 Shazam'da ochish",
        "share_text": "🔥 YouTube, Instagram va TikTok'dan musiqa va video yuklash + Shazam to'g'ridan-to'g'ri Telegram'da",
        "liked": "💖 «Mening musiqam»ga qo'shildi",
        "unliked": "💔 «Mening musiqam»dan olib tashlandi",
        "my_music_header": "❤️ <b>Mening musiqam</b> · {n} ta trek\n<i>Raqamni tanlang 👇</i> · {page}/{pages}-sahifa\n" + LINE,
        "my_music_empty": "❤️ <b>Mening musiqam</b> hozircha bo'sh.\nIstalgan trek ostidagi «❤️ Sevimlilarga» tugmasini bosing.",
        "menu_top_world": "🔥 Hafta topi",
        "menu_top_uz": "🇺🇿 Top UZ",
        "menu_top_ru": "🇷🇺 Top RU",
        "chart_world_header": "🔥 <b>Hafta topi</b> · hamma shazam qilayotgan va TikTok'dagi treklar\n<i>Raqamni tanlang 👇</i> · {page}/{pages}-sahifa\n" + LINE,
        "chart_uz_header": "🇺🇿 <b>O'zbekiston topi</b>\n<i>Raqamni tanlang 👇</i> · {page}/{pages}-sahifa\n" + LINE,
        "chart_ru_header": "🇷🇺 <b>Rossiya topi</b>\n<i>Raqamni tanlang 👇</i> · {page}/{pages}-sahifa\n" + LINE,
        "chart_failed": "😔 Chart hozir yuklanmadi. Bir daqiqadan so'ng urinib ko'ring.",
        "btn_up": "⚡ Speed up",
        "btn_slow": "🌙 Slowed + reverb",
        "fx_header_up": "⚡ <b>Speed up</b> versiya",
        "fx_header_slow": "🌙 <b>Slowed + reverb</b> versiya",
        "menu_my_music": "❤️ Mening musiqam",
        "menu_help": "❓ Yordam",
        "menu_lang": "🌐 Til",
        "recognizing": "🎧",
        "not_recognized": "🙉 Qo'shiqni aniqlab bo'lmadi. Musiqa aniqroq eshitiladigan qismini yuboring (10–20 soniya).",
        "recognized_card": "🔍 <b>Shazam topdi!</b>\n" + LINE + "\n🎵 <b>{title}</b>\n👤 {artist}\n" + LINE + "\n⏬ MP3 yuklanmoqda…",
        "recognized_header": "🔍 Ovoz bo'yicha topildi",
        "song_not_found_dl": "🎵 Bu <b>{title}</b> — {artist}, lekin MP3 topilmadi. Nomi bo'yicha qidirib ko'ring.",
        "unsupported_link": "🤔 Bu havolani bilmayman. YouTube, Instagram yoki TikTok yuboring.",
        "track_failed": "😔 Bu trek hozir yuklanmayapti. Ro'yxatdan boshqa raqamni tanlang.",
        "dl_failed": "😔 Yuklab bo'lmadi. Video yopiq, o'chirilgan yoki faqat kirish orqali ochiladi.",
        "too_big": "📦 Video Telegram uchun juda og'ir, hatto past sifatda ham.",
        "file_too_big": "📦 Fayl juda katta. Qisqaroq qism yuboring (20 MB gacha).",
        "busy": "⏳ Bir soniya, oldingi so'rovingizni bajaryapman.",
        "error": "⚠️ Nimadir xato ketdi. Qayta urinib ko'ring.",
        "stats": "📊 <b>Statistika</b>\n" + LINE + "\n👥 Foydalanuvchilar: <b>{users}</b>\n📥 Yuklashlar: <b>{downloads}</b>\n🔍 Aniqlashlar: <b>{recognitions}</b>",
    },
}

PLATFORM_ICONS = {"youtube": ("▶️", "YouTube"), "instagram": ("📸", "Instagram"), "tiktok": ("🎵", "TikTok")}

LANGS = {"ru": "🇷🇺 Русский", "uz": "🇺🇿 O'zbekcha"}
DEFAULT_LANG = "ru"


def t(lang: str | None, key: str, **kw) -> str:
    table = TEXTS.get(lang or DEFAULT_LANG, TEXTS[DEFAULT_LANG])
    text = table.get(key) or TEXTS[DEFAULT_LANG][key]
    return text.format(**kw) if kw else text


def guess_lang(language_code: str | None) -> str:
    return "uz" if (language_code or "").lower().startswith("uz") else DEFAULT_LANG


def menu_labels(key: str) -> set[str]:
    """All language variants of a reply-keyboard button (so any language works)."""
    return {table[key] for table in TEXTS.values()}
