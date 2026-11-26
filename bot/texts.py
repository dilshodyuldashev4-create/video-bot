"""All user-facing strings: Uzbek, Russian, English."""

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
            "⚡ / 🌙 / 🎧 / 🔊 Под любым MP3 → speed up, slowed, 8D или bass boost\n"
            "🎤 Минус → песня без голоса · 🔔 Рингтон для iPhone и Android\n"
            "⭕ Видео → кружок или голосовое · 📝 Текст песни\n"
            "🎧 Настроение → подборка под вайб · 📊 Мой год → итоги (/wrapped)\n"
            "🎵 Похожие · 📂 Плейлисты (/playlists) · 🔔 Следить за артистом (/follows)\n"
            "🎬 Клип для сторис · 🎧 Плеер в Telegram (/app)\n"
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
        "link_choice": "{icon} <b>{platform}</b>\n" + LINE + "\nЧто скачать? Выбирай 👇",
        "btn_dl_video": "🎬 Видео в HD",
        "btn_dl_audio": "🎵 Аудио MP3",
        "btn_dl_shazam": "🔍 Найти музыку (Shazam)",
        "link_expired": "⌛ Ссылка устарела, отправь её ещё раз.",
        "lib_added": "✅ <b>{name}</b> добавлен в базу бота. Теперь его найдут через поиск 🔎",
        "btn_lyrics": "📝 Текст песни",
        "lyrics_title": "📝 <b>{name}</b>",
        "lyrics_none": "😔 Текст песни «{name}» не нашёл.",
        "inline_loading": "⏳ Загружаю…",
        "inline_open": "🎧 Открыть бота",
        "inline_hint": "Напиши название песни или исполнителя",
        "btn_8d": "🎧 8D",
        "btn_bass": "🔊 Bass boost",
        "btn_minus": "🎤 Минусовка",
        "btn_ringtone": "🔔 Рингтон",
        "fx_header_8d": "🎧 <b>8D</b> версия (слушай в наушниках)",
        "fx_header_bass": "🔊 <b>Bass boost</b> версия",
        "fx_header_minus": "🎤 <b>Минусовка</b> (караоке-версия)",
        "minus_mono": "😔 Этот трек записан в моно, голос отделить не получится.",
        "ringtone_caption": "🔔 <b>Рингтон</b>: {name}\n" + LINE + "\n📱 iPhone: файл .m4r → Поделиться → GarageBand → Рингтон\n🤖 Android: файл .mp3 → Настройки → Звук → Рингтон",
        "btn_note": "⭕ В кружок",
        "btn_voice": "🎙 В голосовое",
        "video_more": "🎬 Ещё можно сделать из этого видео 👇",
        "menu_mood": "🎧 Настроение",
        "mood_pick": "🎧 <b>Музыка по настроению</b>\n" + LINE + "\nВыбери, что сейчас нужно 👇",
        "mood_sad": "😢 Грустное", "mood_car": "🚗 Для машины", "mood_gym": "🏋️ Для зала",
        "mood_toy": "💃 Для тоя", "mood_chill": "😌 Спокойное", "mood_love": "❤️ Про любовь",
        "menu_wrapped": "📊 Мой {year}",
        "btn_similar": '🎵 Похожие',
        "btn_playlist": '📂 В плейлист',
        "btn_follow": '🔔 Следить за артистом',
        "btn_story": '🎬 Для сторис',
        "btn_more": '🎛 Эффекты и рингтон',
        "btn_back": '⬅️ Назад',
        "similar_header": '🎵 <b>Похоже на «{q}»</b>\n<i>Выбирай номер 👇</i> · стр. {page}/{pages}\n' + LINE + '',
        "similar_none": '😔 Не нашёл похожих треков.',
        "follow_on": '🔔 Теперь слежу за {name}! Напишу, когда выйдет новая песня.',
        "follow_off": '🔕 Больше не слежу за {name}.',
        "follow_none": '😔 Не нашёл этого исполнителя.',
        "follows_header": '🔔 <b>Ты следишь за:</b>\n' + LINE + '\nНажми на имя, чтобы отписаться 👇',
        "follows_empty": '🔔 Ты пока ни за кем не следишь. Нажми «🔔 Следить за артистом» под любым треком.',
        "new_release": '🔥 <b>Новый релиз!</b>\n👤 {artist}\n🎧 {title}\n' + LINE + '\nЖми кнопку и слушай первым 👇',
        "btn_listen": '🎧 Слушать',
        "pl_choose": '📂 В какой плейлист добавить?',
        "btn_pl_new": '➕ Новый плейлист',
        "pl_ask_name": '✍️ Напиши название нового плейлиста:',
        "pl_added": '✅ Добавил в «{name}»',
        "pl_exists": 'Уже есть в «{name}»',
        "playlists_header": '📂 <b>Мои плейлисты</b>\n' + LINE + '\nВыбери плейлист 👇',
        "playlists_empty": '📂 Плейлистов пока нет. Нажми «📂 В плейлист» под любым треком.',
        "playlist_header": '📂 <b>{q}</b>\n<i>Выбирай номер 👇</i> · стр. {page}/{pages}\n' + LINE + '',
        "playlist_empty": '📂 В плейлисте пока пусто.',
        "btn_pl_share": '📤 Поделиться',
        "btn_pl_delete": '🗑 Удалить',
        "btn_pl_save": '💾 Сохранить себе',
        "pl_deleted": '🗑 Плейлист удалён',
        "pl_saved": '✅ Плейлист сохранён: «{name}»',
        "pl_share_text": '🎧 Мой плейлист «{name}»',
        "menu_playlists": '📂 Плейлисты',
        "story_caption": '🎬 <b>Клип для сторис</b>\n' + LINE + '\nСохрани и выложи в сторис 🔥',
        "btn_app": '🎧 Открыть плеер',
        "app_text": '🎧 <b>Плеер</b>: поиск, избранное и плейлисты прямо в Telegram 👇',
        "app_off": '🎧 Плеер сейчас недоступен, попробуй чуть позже.',
        "app_menu": '🎧 Плеер',
        "wrapped_empty": "📊 Пока мало данных. Скачай несколько песен, и я соберу твои итоги года!",
        "wrapped_caption": "📊 <b>Твой {year}</b> с @{bot}\n" + LINE + "\nПоделись с друзьями 👇",
        "wr_title": "Твой {year}", "wr_tracks": "треков скачано", "wr_artists": "Любимые исполнители",
        "wr_songs": "Топ песни", "wr_days": "дней с музыкой",
        "btn_add_group": "➕ В группу",
        "btn_share": "🔗 Поделиться",
        "btn_like": "❤️ В избранное",
        "btn_liked": "💖 В избранном",
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
        "yt_video_blocked": "🎬 YouTube сейчас не отдаёт это видео нашему серверу. Присылаю песню из него 🎵",
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
            "⚡ / 🌙 / 🎧 / 🔊 Istalgan MP3 ostida → speed up, slowed, 8D yoki bass boost\n"
            "🎤 Minus → ovozsiz qo'shiq · 🔔 iPhone va Android uchun rington\n"
            "⭕ Video → dumaloq video yoki ovozli xabar · 📝 Qo'shiq matni\n"
            "🎧 Kayfiyat → vaybga mos tanlov · 📊 Mening yilim → yakunlar (/wrapped)\n"
            "🎵 O'xshashlari · 📂 Pleylistlar (/playlists) · 🔔 Ijrochini kuzatish (/follows)\n"
            "🎬 Storis uchun klip · 🎧 Telegram ichida pleyer (/app)\n"
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
        "link_choice": "{icon} <b>{platform}</b>\n" + LINE + "\nNimani yuklab olamiz? Tanlang 👇",
        "btn_dl_video": "🎬 HD video",
        "btn_dl_audio": "🎵 Audio MP3",
        "btn_dl_shazam": "🔍 Musiqani topish (Shazam)",
        "link_expired": "⌛ Havola eskirdi, uni qayta yuboring.",
        "lib_added": "✅ <b>{name}</b> bot bazasiga qo'shildi. Endi uni qidiruv orqali topishadi 🔎",
        "btn_lyrics": "📝 Qo'shiq matni",
        "lyrics_title": "📝 <b>{name}</b>",
        "lyrics_none": "😔 «{name}» qo'shig'ining matni topilmadi.",
        "inline_loading": "⏳ Yuklanmoqda…",
        "inline_open": "🎧 Botni ochish",
        "inline_hint": "Qo'shiq yoki ijrochi nomini yozing",
        "btn_8d": "🎧 8D",
        "btn_bass": "🔊 Bass boost",
        "btn_minus": "🎤 Minus",
        "btn_ringtone": "🔔 Rington",
        "fx_header_8d": "🎧 <b>8D</b> versiya (quloqchinda tinglang)",
        "fx_header_bass": "🔊 <b>Bass boost</b> versiya",
        "fx_header_minus": "🎤 <b>Minus</b> (karaoke versiya)",
        "minus_mono": "😔 Bu trek mono yozilgan, ovozni ajratib bo'lmaydi.",
        "ringtone_caption": "🔔 <b>Rington</b>: {name}\n" + LINE + "\n📱 iPhone: .m4r fayl → Ulashish → GarageBand → Rington\n🤖 Android: .mp3 fayl → Sozlamalar → Ovoz → Rington",
        "btn_note": "⭕ Dumaloq video",
        "btn_voice": "🎙 Ovozli xabar",
        "video_more": "🎬 Bu videodan yana nima qilamiz 👇",
        "menu_mood": "🎧 Kayfiyat",
        "mood_pick": "🎧 <b>Kayfiyatga mos musiqa</b>\n" + LINE + "\nHozir nima kerak, tanlang 👇",
        "mood_sad": "😢 G'amgin", "mood_car": "🚗 Mashinaga", "mood_gym": "🏋️ Sport zalga",
        "mood_toy": "💃 To'yga", "mood_chill": "😌 Sokin", "mood_love": "❤️ Sevgi haqida",
        "menu_wrapped": "📊 Mening {year}",
        "btn_similar": "🎵 O'xshashlari",
        "btn_playlist": '📂 Pleylistga',
        "btn_follow": '🔔 Ijrochini kuzatish',
        "btn_story": '🎬 Storis uchun',
        "btn_more": '🎛 Effektlar va rington',
        "btn_back": '⬅️ Orqaga',
        "similar_header": "🎵 <b>«{q}» ga o'xshash</b>\n<i>Raqamni tanlang 👇</i> · {page}/{pages}-sahifa\n" + LINE + '',
        "similar_none": "😔 O'xshash treklar topilmadi.",
        "follow_on": "🔔 Endi {name} ni kuzataman! Yangi qo'shiq chiqsa, yozaman.",
        "follow_off": '🔕 {name} endi kuzatilmaydi.',
        "follow_none": '😔 Bu ijrochi topilmadi.',
        "follows_header": '🔔 <b>Siz kuzatayotganlar:</b>\n' + LINE + '\nObunani bekor qilish uchun ismni bosing 👇',
        "follows_empty": '🔔 Hozircha hech kimni kuzatmayapsiz. Istalgan trek ostida «🔔 Ijrochini kuzatish» ni bosing.',
        "new_release": '🔥 <b>Yangi reliz!</b>\n👤 {artist}\n🎧 {title}\n' + LINE + "\nTugmani bosing va birinchi bo'lib tinglang 👇",
        "btn_listen": '🎧 Tinglash',
        "pl_choose": "📂 Qaysi pleylistga qo'shamiz?",
        "btn_pl_new": '➕ Yangi pleylist',
        "pl_ask_name": '✍️ Yangi pleylist nomini yozing:',
        "pl_added": "✅ «{name}» ga qo'shildi",
        "pl_exists": '«{name}» da allaqachon bor',
        "playlists_header": '📂 <b>Mening pleylistlarim</b>\n' + LINE + '\nPleylistni tanlang 👇',
        "playlists_empty": "📂 Hozircha pleylist yo'q. Istalgan trek ostida «📂 Pleylistga» ni bosing.",
        "playlist_header": '📂 <b>{q}</b>\n<i>Raqamni tanlang 👇</i> · {page}/{pages}-sahifa\n' + LINE + '',
        "playlist_empty": "📂 Pleylist hozircha bo'sh.",
        "btn_pl_share": '📤 Ulashish',
        "btn_pl_delete": "🗑 O'chirish",
        "btn_pl_save": "💾 O'zimga saqlash",
        "pl_deleted": "🗑 Pleylist o'chirildi",
        "pl_saved": '✅ Pleylist saqlandi: «{name}»',
        "pl_share_text": '🎧 Mening pleylistim «{name}»',
        "menu_playlists": '📂 Pleylistlar',
        "story_caption": '🎬 <b>Storis uchun klip</b>\n' + LINE + '\nSaqlang va storisga joylang 🔥',
        "btn_app": '🎧 Pleyerni ochish',
        "app_text": '🎧 <b>Pleyer</b>: qidiruv, sevimlilar va pleylistlar Telegram ichida 👇',
        "app_off": "🎧 Pleyer hozir ishlamayapti, birozdan keyin urinib ko'ring.",
        "app_menu": '🎧 Pleyer',
        "wrapped_empty": "📊 Hozircha ma'lumot kam. Bir nechta qo'shiq yuklab oling, men yilingiz yakunini tayyorlayman!",
        "wrapped_caption": "📊 <b>Sizning {year}</b> @{bot} bilan\n" + LINE + "\nDo'stlaringizga ulashing 👇",
        "wr_title": "Sizning {year}", "wr_tracks": "ta trek yuklandi", "wr_artists": "Sevimli ijrochilar",
        "wr_songs": "Top qo'shiqlar", "wr_days": "kun musiqa bilan",
        "btn_add_group": "➕ Guruhga qo'shish",
        "btn_share": "🔗 Ulashish",
        "btn_like": "❤️ Sevimlilarga",
        "btn_liked": "💖 Sevimlilarda",
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
        "yt_video_blocked": "🎬 YouTube hozir bu videoni serverimizga bermayapti. Undagi qo'shiqni yuboraman 🎵",
        "dl_failed": "😔 Yuklab bo'lmadi. Video yopiq, o'chirilgan yoki faqat kirish orqali ochiladi.",
        "too_big": "📦 Video Telegram uchun juda og'ir, hatto past sifatda ham.",
        "file_too_big": "📦 Fayl juda katta. Qisqaroq qism yuboring (20 MB gacha).",
        "busy": "⏳ Bir soniya, oldingi so'rovingizni bajaryapman.",
        "error": "⚠️ Nimadir xato ketdi. Qayta urinib ko'ring.",
        "stats": "📊 <b>Statistika</b>\n" + LINE + "\n👥 Foydalanuvchilar: <b>{users}</b>\n📥 Yuklashlar: <b>{downloads}</b>\n🔍 Aniqlashlar: <b>{recognitions}</b>",
    },
    "en": {
        "start": (
            "⚡️ <b>Yo, {name}!</b> You're in the fastest music bot 🔥\n"
            f"{LINE}\n"
            "🎧 <b>Music</b> — type a song or an artist\n"
            "📥 <b>Video</b> — drop a YouTube · Instagram · TikTok link\n"
            "🔍 <b>Shazam</b> — send a video, audio, voice or video note, I'll name the track\n"
            "🔥 <b>Top of the week</b> · 🇺🇿 <b>UZ</b> · 🇷🇺 <b>RU</b> — fresh charts in the menu\n"
            "⚡ <b>Speed up</b> · 🌙 <b>Slowed + reverb</b> — any song in one tap\n"
            "❤️ <b>My music</b> — like tracks and build your playlist\n"
            f"{LINE}\n"
            "👇 Try it now: <code>Pop Smoke Dior</code>"
        ),
        "help": (
            "📖 <b>How it works</b>\n"
            f"{LINE}\n"
            "🎧 Type <code>Dior</code> → pick a number → the MP3 is yours\n"
            "📥 Drop a link → HD video, no watermark\n"
            "🎵 Tap «Get the song» under a video → the bot finds the track from it\n"
            "🔍 Send a video / audio / voice → Shazam names the song\n"
            "❤️ Tap «Add to favorites» → the track goes to /mymusic\n"
            "⚡ / 🌙 / 🎧 / 🔊 Under any MP3 → speed up, slowed, 8D or bass boost\n"
            "🎤 Minus → the song without vocals · 🔔 Ringtone for iPhone and Android\n"
            "⭕ Video → video note or voice message · 📝 Lyrics\n"
            "🎧 Mood → a playlist for your vibe · 📊 My year → your stats (/wrapped)\n"
            "🎵 Similar · 📂 Playlists (/playlists) · 🔔 Follow an artist (/follows)\n"
            "🎬 Stories clip · 🎧 Player inside Telegram (/app)\n"
            "🔥 Menu → top of the week, Uzbekistan and Russia charts (/top)\n"
            f"{LINE}\n"
            "👥 Add the bot to a group and it will download links right in the chat"
        ),
        "choose_lang": "🌐 Choose a language:",
        "lang_set": "✅ Language: English",
        "searching": "🔎",
        "nothing_found": "🙈 Nothing found for «<b>{q}</b>». Try spelling it differently.",
        "results_header": "🎧 <b>{q}</b>\n<i>Pick a number 👇</i> · page {page}/{pages}\n" + LINE,
        "search_expired": "⌛️ This search expired, send your request again.",
        "downloading": "⏳",
        "audio_footer": "⚡️ @{bot} — music in a second",
        "video_caption": "{icon} <b>Done!</b> Video from {platform}\n" + LINE + "\n⚡️ Downloaded with @{bot}",
        "btn_get_song": "🎵 Get the song from this video",
        "link_choice": "{icon} <b>{platform}</b>\n" + LINE + "\nWhat should I download? Pick one 👇",
        "btn_dl_video": "🎬 Video in HD",
        "btn_dl_audio": "🎵 Audio MP3",
        "btn_dl_shazam": "🔍 Find the music (Shazam)",
        "link_expired": "⌛ This link has expired, send it again.",
        "lib_added": "✅ <b>{name}</b> was added to the bot's library. Now people can find it with search 🔎",
        "btn_lyrics": "📝 Lyrics",
        "lyrics_title": "📝 <b>{name}</b>",
        "lyrics_none": "😔 Couldn't find the lyrics of «{name}».",
        "inline_loading": "⏳ Loading…",
        "inline_open": "🎧 Open the bot",
        "inline_hint": "Type a song or artist name",
        "btn_8d": "🎧 8D",
        "btn_bass": "🔊 Bass boost",
        "btn_minus": "🎤 Instrumental",
        "btn_ringtone": "🔔 Ringtone",
        "fx_header_8d": "🎧 <b>8D</b> version (use headphones)",
        "fx_header_bass": "🔊 <b>Bass boost</b> version",
        "fx_header_minus": "🎤 <b>Instrumental</b> (karaoke version)",
        "minus_mono": "😔 This track is mono, the vocals can't be separated.",
        "ringtone_caption": "🔔 <b>Ringtone</b>: {name}\n" + LINE + "\n📱 iPhone: .m4r file → Share → GarageBand → Ringtone\n🤖 Android: .mp3 file → Settings → Sound → Ringtone",
        "btn_note": "⭕ Video note",
        "btn_voice": "🎙 Voice message",
        "video_more": "🎬 More things to do with this video 👇",
        "menu_mood": "🎧 Mood",
        "mood_pick": "🎧 <b>Music for your mood</b>\n" + LINE + "\nPick what you need now 👇",
        "mood_sad": "😢 Sad", "mood_car": "🚗 Car", "mood_gym": "🏋️ Gym",
        "mood_toy": "💃 Party / wedding", "mood_chill": "😌 Chill", "mood_love": "❤️ Love",
        "menu_wrapped": "📊 My {year}",
        "btn_similar": '🎵 Similar',
        "btn_playlist": '📂 To playlist',
        "btn_follow": '🔔 Follow artist',
        "btn_story": '🎬 For Stories',
        "btn_more": '🎛 Effects & ringtone',
        "btn_back": '⬅️ Back',
        "similar_header": '🎵 <b>Like «{q}»</b>\n<i>Pick a number 👇</i> · page {page}/{pages}\n' + LINE + '',
        "similar_none": '😔 No similar tracks found.',
        "follow_on": "🔔 Following {name}! I'll message you when a new song drops.",
        "follow_off": '🔕 No longer following {name}.',
        "follow_none": "😔 Couldn't find this artist.",
        "follows_header": '🔔 <b>You follow:</b>\n' + LINE + '\nTap a name to unfollow 👇',
        "follows_empty": "🔔 You don't follow anyone yet. Tap «🔔 Follow artist» under any track.",
        "new_release": '🔥 <b>New release!</b>\n👤 {artist}\n🎧 {title}\n' + LINE + '\nTap and be the first to listen 👇',
        "btn_listen": '🎧 Listen',
        "pl_choose": '📂 Which playlist?',
        "btn_pl_new": '➕ New playlist',
        "pl_ask_name": '✍️ Type a name for the new playlist:',
        "pl_added": '✅ Added to «{name}»',
        "pl_exists": 'Already in «{name}»',
        "playlists_header": '📂 <b>My playlists</b>\n' + LINE + '\nPick a playlist 👇',
        "playlists_empty": '📂 No playlists yet. Tap «📂 To playlist» under any track.',
        "playlist_header": '📂 <b>{q}</b>\n<i>Pick a number 👇</i> · page {page}/{pages}\n' + LINE + '',
        "playlist_empty": '📂 This playlist is empty.',
        "btn_pl_share": '📤 Share',
        "btn_pl_delete": '🗑 Delete',
        "btn_pl_save": '💾 Save to mine',
        "pl_deleted": '🗑 Playlist deleted',
        "pl_saved": '✅ Playlist saved: «{name}»',
        "pl_share_text": '🎧 My playlist «{name}»',
        "menu_playlists": '📂 Playlists',
        "story_caption": '🎬 <b>Stories clip</b>\n' + LINE + '\nSave it and post to your Stories 🔥',
        "btn_app": '🎧 Open player',
        "app_text": '🎧 <b>Player</b>: search, favorites and playlists right in Telegram 👇',
        "app_off": '🎧 The player is unavailable right now, try again a bit later.',
        "app_menu": '🎧 Player',
        "wrapped_empty": "📊 Not enough data yet. Download a few songs and I'll make your year in music!",
        "wrapped_caption": "📊 <b>Your {year}</b> with @{bot}\n" + LINE + "\nShare it with friends 👇",
        "wr_title": "Your {year}", "wr_tracks": "tracks downloaded", "wr_artists": "Top artists",
        "wr_songs": "Top songs", "wr_days": "days with music",
        "btn_add_group": "➕ Add to group",
        "btn_share": "🔗 Share",
        "btn_like": "❤️ Add to favorites",
        "btn_liked": "💖 In favorites",
        "share_text": "🔥 Download music and videos from YouTube, Instagram and TikTok + Shazam right in Telegram",
        "liked": "💖 Added to «My music»",
        "unliked": "💔 Removed from «My music»",
        "my_music_header": "❤️ <b>My music</b> · {n} tracks\n<i>Pick a number 👇</i> · page {page}/{pages}\n" + LINE,
        "my_music_empty": "❤️ <b>My music</b> is empty for now.\nTap «❤️ Add to favorites» under any track and it will show up here.",
        "menu_top_world": "🔥 Top of the week",
        "menu_top_uz": "🇺🇿 Top UZ",
        "menu_top_ru": "🇷🇺 Top RU",
        "chart_world_header": "🔥 <b>Top of the week</b> · what everyone shazams and plays on TikTok\n<i>Pick a number 👇</i> · page {page}/{pages}\n" + LINE,
        "chart_uz_header": "🇺🇿 <b>Top Uzbekistan</b>\n<i>Pick a number 👇</i> · page {page}/{pages}\n" + LINE,
        "chart_ru_header": "🇷🇺 <b>Top Russia</b>\n<i>Pick a number 👇</i> · page {page}/{pages}\n" + LINE,
        "chart_failed": "😔 The chart didn't load right now. Try again in a minute.",
        "btn_up": "⚡ Speed up",
        "btn_slow": "🌙 Slowed + reverb",
        "fx_header_up": "⚡ <b>Speed up</b> version",
        "fx_header_slow": "🌙 <b>Slowed + reverb</b> version",
        "menu_my_music": "❤️ My music",
        "menu_help": "❓ Help",
        "menu_lang": "🌐 Language",
        "recognizing": "🎧",
        "not_recognized": "🙉 Couldn't recognise the track. Send a clip where the music is clearer (10–20 sec).",
        "recognized_card": "🔍 <b>Shazam found it!</b>\n" + LINE + "\n🎵 <b>{title}</b>\n👤 {artist}\n" + LINE + "\n⏬ Getting the MP3…",
        "recognized_header": "🔍 Found by sound",
        "song_not_found_dl": "🎵 It's <b>{title}</b> — {artist}, but no MP3 was found. Try searching by name.",
        "unsupported_link": "🤔 I don't know this link. Send YouTube, Instagram or TikTok.",
        "track_failed": "😔 This track won't download right now. Try another number from the list.",
        "yt_video_blocked": "🎬 YouTube won't give this video to our server right now. Sending the song from it 🎵",
        "dl_failed": "😔 Couldn't download. The video may be private, deleted or available only after login.",
        "too_big": "📦 This video is too heavy for Telegram even in low quality.",
        "file_too_big": "📦 The file is too big. Send a shorter clip (up to 20 MB).",
        "busy": "⏳ One sec, still working on your previous request.",
        "error": "⚠️ Something went wrong. Please try again.",
        "stats": "📊 <b>Stats</b>\n" + LINE + "\n👥 Users: <b>{users}</b>\n📥 Downloads: <b>{downloads}</b>\n🔍 Recognitions: <b>{recognitions}</b>",
    },
}

LANGS = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}

PLATFORM_ICONS = {"youtube": ("▶️", "YouTube"), "instagram": ("📸", "Instagram"), "tiktok": ("🎵", "TikTok")}

DEFAULT_LANG = "ru"


def t(lang: str | None, key: str, **kw) -> str:
    table = TEXTS.get(lang or DEFAULT_LANG, TEXTS[DEFAULT_LANG])
    text = table.get(key) or TEXTS[DEFAULT_LANG][key]
    return text.format(**kw) if kw else text


def guess_lang(language_code: str | None) -> str:
    """Telegram app language -> bot language (uz, ru, en). Unknown languages get Russian."""
    code = (language_code or "").lower()[:2]
    if code == "uz":
        return "uz"
    if code == "en":
        return "en"
    return DEFAULT_LANG


def menu_labels(key: str) -> set[str]:
    """All language variants of a reply-keyboard button (so any language works)."""
    return {table[key] for table in TEXTS.values()}
