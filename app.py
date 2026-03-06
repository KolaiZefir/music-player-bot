import logging
import os
import json
import sqlite3
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- НАСТРОЙКИ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8496222715:AAF5Yrq4VqWS9KNixjjT_wKInY1OBF9p0lk')
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', '-1003801427378'))
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://music-frontend.vercel.app')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://music-bot-final-51qb.onrender.com')
PORT = int(os.environ.get('PORT', 10000))

# --- БАЗА ДАННЫХ ---
DB_PATH = 'music.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT UNIQUE,
            file_name TEXT,
            added_at TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ База данных готова")

def save_track(file_id, file_name):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            'INSERT OR IGNORE INTO tracks (file_id, file_name, added_at) VALUES (?, ?, ?)',
            (file_id, file_name, datetime.now())
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        return False

def get_all_tracks():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, file_id, file_name FROM tracks ORDER BY added_at DESC')
    tracks = [{'id': row[0], 'file_id': row[1], 'title': row[2] or 'Без названия'} for row in c.fetchall()]
    conn.close()
    return tracks

# --- FLASK ---
app = Flask(__name__)

# --- БОТ ---
bot = Bot(token=BOT_TOKEN)

# --- ОБРАБОТЧИКИ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🎵 Привет, {user.first_name}!",
        reply_markup={
            "inline_keyboard": [[
                {"text": "🎧 ОТКРЫТЬ ПЛЕЕР", "web_app": {"url": f"{FRONTEND_URL}?user_id={user.id}"}}
            ]]
        }
    )

# --- СОЗДАЁМ APPLICATION ---
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))

# --- ЗАПУСК БОТА (инициализация) ---
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(application.initialize())
loop.run_until_complete(bot.initialize())

# --- УСТАНОВКА ВЕБХУКА ---
webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
loop.run_until_complete(bot.set_webhook(url=webhook_url))
logger.info(f"✅ Вебхук: {webhook_url}")

# --- МАРШРУТЫ ---
@app.route('/')
def index():
    return jsonify({"status": "ok", "tracks": len(get_all_tracks())})

@app.route('/api/tracks')
def api_tracks():
    return jsonify(get_all_tracks())

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update_data = request.get_json()
        update = Update.de_json(update_data, bot)
        loop.run_until_complete(application.process_update(update))
        return 'ok', 200
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return 'error', 500

# --- ЗАПУСК ---
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=PORT)