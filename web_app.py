import setuptools
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import sys
import io
from database import MusicDatabase
from config import Config

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
# Настраиваем CORS для работы с Vercel
CORS(app, origins=[
    "https://music-frontend.vercel.app",
    "http://localhost:3000",
    "http://localhost:5000"
])

# Инициализация базы данных
db = MusicDatabase()

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'status': 'ok',
        'message': 'Music Bot API is running',
        'endpoints': [
            '/tracks - получить все треки',
            '/track/<id> - получить конкретный трек',
            '/track/<id>/play - воспроизвести трек',
            '/search?q=<query> - поиск треков',
            '/track/<id>/download - скачать трек'
        ]
    })

@app.route('/tracks', methods=['GET'])
def get_tracks():
    """Получить все треки"""
    try:
        tracks = db.get_all_tracks()
        # Конвертируем в список для JSON
        tracks_list = []
        for track in tracks:
            tracks_list.append({
                'id': track[0],
                'title': track[1],
                'artist': track[2],
                'file_path': track[3],
                'duration': track[4],
                'cover_url': track[5] if track[5] else '/static/default-cover.jpg'
            })
        return jsonify(tracks_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/track/<int:track_id>', methods=['GET'])
def get_track(track_id):
    """Получить информацию о треке"""
    try:
        track = db.get_track(track_id)
        if track:
            return jsonify({
                'id': track[0],
                'title': track[1],
                'artist': track[2],
                'file_path': track[3],
                'duration': track[4],
                'cover_url': track[5] if track[5] else '/static/default-cover.jpg'
            })
        return jsonify({'error': 'Track not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/track/<int:track_id>/play', methods=['GET'])
def play_track(track_id):
    """Воспроизвести трек (стриминг)"""
    try:
        track = db.get_track(track_id)
        if not track:
            return jsonify({'error': 'Track not found'}), 404
        
        file_path = track[3]
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            # Ищем файл в директории downloads
            possible_path = os.path.join('downloads', os.path.basename(file_path))
            if os.path.exists(possible_path):
                file_path = possible_path
            else:
                return jsonify({'error': 'File not found'}), 404
        
        # Отправляем файл для воспроизведения
        return send_file(
            file_path,
            mimetype='audio/mpeg',
            as_attachment=False,
            download_name=f"{track[1]} - {track[2]}.mp3"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/track/<int:track_id>/download', methods=['GET'])
def download_track(track_id):
    """Скачать трек"""
    try:
        track = db.get_track(track_id)
        if not track:
            return jsonify({'error': 'Track not found'}), 404
        
        file_path = track[3]
        
        if not os.path.exists(file_path):
            possible_path = os.path.join('downloads', os.path.basename(file_path))
            if os.path.exists(possible_path):
                file_path = possible_path
            else:
                return jsonify({'error': 'File not found'}), 404
        
        return send_file(
            file_path,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=f"{track[1]} - {track[2]}.mp3"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/search', methods=['GET'])
def search_tracks():
    """Поиск треков"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify([])
        
        tracks = db.search_tracks(query)
        tracks_list = []
        for track in tracks:
            tracks_list.append({
                'id': track[0],
                'title': track[1],
                'artist': track[2],
                'file_path': track[3],
                'duration': track[4],
                'cover_url': track[5] if track[5] else '/static/default-cover.jpg'
            })
        return jsonify(tracks_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/static/default-cover.jpg')
def default_cover():
    """Заглушка для обложки"""
    # Здесь можно вернуть стандартную картинку
    # Пока возвращаем 404
    return '', 404

import telegram
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

# Токен бота
TOKEN = "8496222715:AAF5Yrq4VqWS9KNixjjT_wKInY1OBF9p0lk"
bot = telegram.Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

# Обработчик команды /start
def start(update, context):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Привет! Я бот-плеер. Нажми кнопку ниже, чтобы открыть плеер:",
        reply_markup={
            "inline_keyboard": [[
                {"text": "🎵 Открыть плеер", "web_app": {"url": "https://music-frontend.vercel.app"}}
            ]]
        }
    )

# Регистрируем обработчики
dispatcher.add_handler(CommandHandler("start", start))

# Эндпоинт для вебхука (ОБЯЗАТЕЛЬНО ДОБАВИТЬ!)
@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))