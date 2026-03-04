import logging
import os
import sqlite3
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import config

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Инициализация Flask ---
app = Flask(__name__)

# --- Инициализация Bot и Application для обработки обновлений ---
# Важно: мы НЕ запускаем polling, а только создаем объекты для обработки запросов
bot = Bot(token=config.BOT_TOKEN)

# Создаем Application без запуска polling
# Это контейнер для наших обработчиков команд
telegram_app = Application.builder().token(config.BOT_TOKEN).build()

# --- Обработчики команд бота ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение с ссылкой на Mini App"""
    user = update.effective_user
    mini_app_url = f"{config.FRONTEND_URL}?user_id={user.id}" # Передаем user_id во фронтенд
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n"
        f"Нажми кнопку ниже, чтобы открыть музыкальный плеер:",
        reply_markup={
            "inline_keyboard": [[
                {"text": "🎵 Открыть плеер", "web_app": {"url": mini_app_url}}
            ]]
        }
    )

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает посты из канала (сохраняет ссылки на музыку)"""
    # Проверяем, что сообщение из нашего канала
    if update.channel_post and update.channel_post.chat.id == config.CHANNEL_ID:
        # Логика сохранения ссылок в базу данных
        # (Здесь нужно вызвать вашу функцию из database.py)
        logger.info(f"Новый пост в канале: {update.channel_post.text}")
        # Пример: save_music_link(update.channel_post.text)
        await update.channel_post.reply_text("Ссылка сохранена!") # Опционально

# --- Регистрируем обработчики ---
telegram_app.add_handler(CommandHandler("start", start))
# Добавляем обработчик для сообщений из канала (бот должен быть админом)
telegram_app.add_handler(MessageHandler(filters.Chat(chat_id=config.CHANNEL_ID) & filters.TEXT & ~filters.COMMAND, handle_channel_post))
# Добавьте сюда другие ваши обработчики (например, для загрузки музыки)

# --- Flask маршруты ---

@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "message": "Music Bot Backend is running",
        "bot_token_configured": bool(config.BOT_TOKEN),
        "channel_id": config.CHANNEL_ID,
        "frontend_url": config.FRONTEND_URL
    })

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Этот маршрут Telegram будет вызывать при новых сообщениях"""
    try:
        # Получаем обновление от Telegram в формате JSON
        update_data = request.get_json(force=True)
        logger.info(f"Received update: {update_data}")

        # Преобразуем JSON в объект Update библиотеки python-telegram-bot
        update = Update.de_json(update_data, bot)

        # Передаем обновление в нашу Application для обработки
        await telegram_app.process_update(update)

        return 'ok', 200
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return 'error', 500

@app.route('/api/music-list', methods=['GET'])
def get_music_list():
    """API для фронтенда: возвращает список музыки"""
    # Здесь должна быть логика получения списка из БД
    # Пример:
    # music_list = get_all_music_links()
    music_list = [
        {"id": 1, "title": "Песня 1", "url": "https://example.com/song1.mp3"},
        {"id": 2, "title": "Песня 2", "url": "https://example.com/song2.mp3"},
    ]
    return jsonify(music_list)

@app.route('/api/download/<int:music_id>', methods=['GET'])
def download_music(music_id):
    """API для скачивания музыки (если нужно)"""
    # Логика скачивания
    return jsonify({"message": f"Downloading music {music_id}"})

# --- Функция для установки вебхука (вызывается один раз) ---
def setup_webhook():
    webhook_url = f"https://{request.host}/webhook" if request else f"{config.RENDER_EXTERNAL_URL}/webhook"
    # Или просто задайте явно:
    # webhook_url = "https://music-bot-backend-ng9f.onrender.com/webhook"
    
    logger.info(f"Setting webhook to: {webhook_url}")
    try:
        bot.set_webhook(url=webhook_url)
        logger.info("Webhook set successfully")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# --- Запуск Flask ---
if __name__ == '__main__':
    # Устанавливаем вебхук при старте (но только один раз, можно вынести в отдельную команду)
    # Для простоты, установим здесь, но нужно быть осторожным, чтобы не сбрасывать вебхук часто.
    # Лучше сделать отдельный скрипт setup.py или эндпоинт /setup_webhook
    try:
        # Получаем внешний URL от Render или используем локальный для теста
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if render_url:
            webhook_url = f"{render_url}/webhook"
            bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook set to {webhook_url}")
        else:
            logger.warning("RENDER_EXTERNAL_URL not set, skipping webhook setup. Run setup manually.")
    except Exception as e:
        logger.error(f"Failed to set webhook on startup: {e}")

    # Запускаем Flask сервер
    app.run(host='0.0.0.0', port=config.PORT, debug=config.DEBUG)