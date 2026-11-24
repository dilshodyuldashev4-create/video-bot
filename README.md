# 🎵 Video & Music Bot для Telegram

Бот, который:

- 🔎 **Находит музыку по названию или имени исполнителя.** Пишешь `Dior` или `Pop Smoke Dior`, бот показывает список из 10 треков с длительностью, кнопками **1–10** и **⬅️ ❌ ➡️** (до 30 результатов). Нажал номер, и сразу приходит MP3 320 kbps с обложкой, исполнителем и названием.
- 📥 **Скачивает видео из YouTube, Instagram и TikTok** в лучшем доступном качестве (до 1080p, H.264 + AAC, чтобы видео играло прямо в Telegram на любом телефоне, TikTok без водяного знака, карусели Instagram альбомом).
- 🎧 **Распознаёт музыку как Shazam.** Присылаешь видео, аудио, голосовое или кружочек, бот слушает несколько отрывков (середина, начало, конец), находит песню и сразу присылает её MP3.
- 🎵 Под каждым скачанным видео есть кнопка **«Скачать песню»**: бот распознаёт музыку из этого видео и присылает MP3.
- 🔥 **Чарты в меню:** «Топ недели» (то, что все шазамят и крутят в TikTok/Reels), топ Узбекистана и топ России. Источник: чарты Shazam, а если для страны чарта нет, свежие хиты с YouTube. Команда `/top`.
- ⚡ **Speed up** и 🌙 **Slowed + reverb** под каждым MP3: бот делает версию песни в один клик.
- ❤️ **Моя музыка:** кнопка «В избранное» под треком и личный плейлист (`/mymusic`).
- 💅 Хайповое оформление: реакции 👀 → 🔥 на сообщения, цветные кнопки, карточка Shazam с обложкой, кнопки «Поделиться» и «В группу», меню на клавиатуре.
- ⚡ Повторные запросы отдаются мгновенно: бот запоминает уже отправленные файлы.
- 🌐 Русский и узбекский интерфейс (выбирается автоматически, смена через `/lang`).
- 👥 Работает в группах: добавь бота в группу, и он будет скачивать присланные ссылки.

## Быстрый старт (Docker)

1. Создайте бота у [@BotFather](https://t.me/BotFather) и скопируйте токен.
2. Скопируйте настройки и впишите токен:
   ```bash
   cp .env.example .env
   nano .env        # BOT_TOKEN=...
   ```
3. Запустите:
   ```bash
   docker compose up -d --build
   docker compose logs -f bot
   ```

### Хорошее качество для длинных видео (рекомендуется)

Обычный Bot API разрешает боту отправлять файлы только до **50 МБ** и скачивать присланные пользователем файлы только до **20 МБ**. Короткие ролики из TikTok/Instagram помещаются всегда, а длинные видео с YouTube бот автоматически скачает в 720p / 480p, чтобы уложиться в лимит.

Чтобы снять ограничение (до **2 ГБ**), запустите свой Bot API сервер, он уже есть в `docker-compose.yml`:

1. Получите `api_id` и `api_hash` на https://my.telegram.org.
2. Добавьте в `.env`:
   ```
   TELEGRAM_API_ID=...
   TELEGRAM_API_HASH=...
   TELEGRAM_API_URL=http://telegram-bot-api:8081
   ```
3. Один раз выполните `logOut` для бота на облачном API: откройте в браузере
   `https://api.telegram.org/bot<ТОКЕН>/logOut`.
4. `docker compose --profile local-api up -d --build`

### Если сервер заблокирован (Hetzner, AWS и т.п.)

YouTube, Instagram и TikTok часто блокируют IP дата-центров («Sign in to confirm you're not a bot»). В `docker-compose.yml` для этого уже всё включено, ничего настраивать не нужно:

- **Cloudflare WARP** (`warp`): если прямой запрос заблокирован, бот повторяет его через WARP и следующий час ходит на этот сайт сразу через него.
- **PO-токены для YouTube** (`pot-provider`): yt-dlp сам получает токены, которые YouTube требует от серверов.
- **SoundCloud как запасной источник MP3**: если YouTube не отдаёт трек ни напрямую, ни через WARP, бот находит ту же песню на SoundCloud.

Команда **`/diag`** в Telegram показывает, что работает с сервера: YouTube, SoundCloud, TikTok напрямую и через прокси (если задан `ADMIN_IDS`, команда доступна только админам).

### Instagram и YouTube cookies

Instagram часто отдаёт видео только авторизованным пользователям, а YouTube иногда просит «подтвердить, что вы не бот» на серверах. В этом случае:

1. Войдите в Instagram / YouTube в браузере (лучше с отдельного аккаунта).
2. Экспортируйте cookies расширением «Get cookies.txt LOCALLY».
3. Положите файл рядом с ботом как `cookies.txt`, раскомментируйте строку с ним в `docker-compose.yml` и укажите `COOKIES_FILE=/app/cookies.txt` в `.env`.

### Группы

Чтобы бот видел ссылки в группе, отключите ему Privacy Mode в @BotFather (`/setprivacy` → Disable) или сделайте его администратором группы.

## Запуск без Docker

Нужны Python 3.11+, `ffmpeg` и [deno](https://deno.com) (yt-dlp использует его для YouTube).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # впишите BOT_TOKEN
python -m bot
```

## Команды

| Команда  | Что делает |
|----------|------------|
| `/start` | Приветствие |
| `/help`  | Как пользоваться |
| `/top`   | Топ недели |
| `/mymusic` | Моя музыка (лайкнутые треки) |
| `/lang`  | Язык: русский / o'zbekcha |
| `/stats` | Статистика (только для `ADMIN_IDS`) |
| `/diag`  | Проверка: какие сайты доступны с сервера |

## Обслуживание

Обновление бота (одной командой):

```bash
cd ~/video-bot && git pull && docker compose up -d --build
```

- **Регулярно обновляйте yt-dlp.** YouTube, Instagram и TikTok часто меняют сайты, и новые версии yt-dlp это чинят: `docker compose build --pull --no-cache && docker compose up -d` (или `pip install -U "yt-dlp[default]"`).
- Временные файлы удаляются автоматически.

## Как устроено

```
bot/
  __main__.py           запуск, роутеры, фоновая очистка
  handlers/start.py     /start /help /lang /stats
  handlers/links.py     ссылка → видео + кнопка «Скачать песню»
  handlers/recognize.py видео/аудио/голос → Shazam → MP3
  handlers/search.py    текст → список 1–10 → MP3
  services/downloader.py yt-dlp: поиск, MP3, видео
  services/recognizer.py распознавание (shazamio)
  services/media.py     ffmpeg/ffprobe
  db.py                 SQLite: пользователи, кэш file_id, поиски, статистика
  texts.py              тексты RU / UZ
```

Тесты (без интернета, с настоящими ffmpeg и yt-dlp на локальном сервере):

```bash
pip install -r requirements-dev.txt
pytest
```
