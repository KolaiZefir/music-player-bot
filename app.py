import logging
import os
import json
import sqlite3
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8496222715:AAF5Yrq4VqWS9KNixjjT_wKInY1OBF9p0lk')
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', '-1003801427378'))
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://music-frontend.vercel.app')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://music-bot-final-51qb.onrender.com')
PORT = int(os.environ.get('PORT', 10000))

# --- БАЗА ДАННЫХ ---
DB_PATH = 'music.db'

def init_db():
    """Создаёт таблицу для хранения треков, если её нет"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT UNIQUE,
            file_name TEXT,
            caption TEXT,
            added_at TIMESTAMP,
            message_id INTEGER UNIQUE
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

def save_track(file_id, file_name, caption, message_id):
    """Сохраняет трек в базу"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            'INSERT OR IGNORE INTO tracks (file_id, file_name, caption, added_at, message_id) VALUES (?, ?, ?, ?, ?)',
            (file_id, file_name, caption, datetime.now(), message_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения трека: {e}")
        return False

def get_all_tracks():
    """Возвращает все треки из базы"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, file_id, file_name, caption FROM tracks ORDER BY added_at DESC')
    rows = c.fetchall()
    conn.close()
    tracks = []
    for row in rows:
        tracks.append({
            'id': row[0],
            'file_id': row[1],
            'title': row[2] or 'Без названия',
            'caption': row[3] or ''
        })
    return tracks

# --- ВЫЗЫВАЕМ ИНИЦИАЛИЗАЦИЮ БД СРАЗУ (чтобы таблица была готова до первого запроса) ---
init_db()

# --- FLASK ПРИЛОЖЕНИЕ ---
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# --- СОЗДАЁМ БОТА И APPLICATION (ОДИН РАЗ) ---
bot = Bot(token=BOT_TOKEN)
application = Application.builder().token(BOT_TOKEN).build()

# --- ОБРАБОТЧИКИ КОМАНД ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    web_app_url = f"{FRONTEND_URL}?user_id={user.id}"
    await update.message.reply_text(
        f"🎵 Привет, {user.first_name}!",
        reply_markup={
            "inline_keyboard": [[
                {"text": "🎧 ОТКРЫТЬ ПЛЕЕР", "web_app": {"url": web_app_url}}
            ]]
        }
    )
    logger.info(f"✅ Ответ на /start отправлен пользователю {user.id}")

async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет аудио из канала в базу"""
    message = update.channel_post
    if message.chat.id != CHANNEL_ID:
        return
    if message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or f"audio_{message.message_id}.mp3"
        caption = message.caption or ""
        if save_track(file_id, file_name, caption, message.message_id):
            logger.info(f"✅ Сохранён трек: {file_name}")

# --- РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ---
application.add_handler(CommandHandler("start", start_command))
application.add_handler(MessageHandler(filters.Chat(chat_id=CHANNEL_ID) & filters.AUDIO, channel_post_handler))

# --- ИНИЦИАЛИЗАЦИЯ БОТА И APPLICATION (АСИНХРОННО) ---
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(application.initialize())
loop.run_until_complete(bot.initialize())
logger.info("✅ Бот инициализирован")

# --- УСТАНОВКА ВЕБХУКА ---
webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
try:
    loop.run_until_complete(bot.set_webhook(url=webhook_url))
    logger.info(f"✅ Вебхук установлен: {webhook_url}")
    webhook_info = loop.run_until_complete(bot.get_webhook_info())
    logger.info(f"📞 Информация о вебхуке: {webhook_info}")
except Exception as e:
    logger.error(f"❌ Ошибка установки вебхука: {e}")

# --- МАРШРУТЫ FLASK ---
@app.route('/')
def index():
    tracks_count = len(get_all_tracks())
    return jsonify({
        "status": "работает! 🎵",
        "bot": "@my_music_player_2024_bot",
        "tracks": tracks_count,
        "webhook": webhook_url
    })

@app.route('/api/tracks')
def api_tracks():
    return jsonify(get_all_tracks())

@app.route('/webhook', methods=['POST'])
def webhook():
    """Принимает обновления от Telegram"""
    try:
        update_data = request.get_json()
        if not update_data:
            return 'ok', 200
        logger.info(f"🔥 Получен webhook: {update_data.get('update_id')}")
        update = Update.de_json(update_data, bot)
        loop.run_until_complete(application.process_update(update))
        return 'ok', 200
    except Exception as e:
        logger.error(f"❌ Ошибка webhook: {e}")
        return 'error', 500

# --- ЗАПУСК (ДЛЯ ЛОКАЛЬНОГО ТЕСТИРОВАНИЯ) ---
if __name__ == '__main__':
    # База уже проинициализирована выше, но для надёжности:
    init_db()
    app.run(host='0.0.0.0', port=PORT)