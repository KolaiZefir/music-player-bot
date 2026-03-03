import os
from flask import Flask, render_template, jsonify, send_file, request
from flask_cors import CORS
from database import Database
from config import BOT_TOKEN
import requests
import io
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["https://music-frontend.vercel.app"])
db = Database()

def get_file_from_telegram(file_id: str):
    """Получение файла из Telegram"""
    try:
        response = requests.get(
            f'https://api.telegram.org/bot{BOT_TOKEN}/getFile',
            params={'file_id': file_id},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                file_path = data['result']['file_path']
                file_url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}'
                file_response = requests.get(file_url, timeout=60)
                if file_response.status_code == 200:
                    return file_response.content
    except Exception as e:
        logger.error(f"Ошибка получения файла: {e}")
    return None

@app.route('/')
def index():
    return render_template('player.html')

@app.route('/player')
def player():
    return render_template('player.html')

@app.route('/api/tracks/<int:user_id>')
def get_tracks(user_id):
    """Получение списка треков"""
    try:
        tracks = db.get_user_tracks(user_id)
        return jsonify(tracks)
    except Exception as e:
        logger.error(f"Ошибка получения треков: {e}")
        return jsonify([])

@app.route('/api/track/<int:track_id>/stream')
def stream_track(track_id):
    """Стриминг трека"""
    try:
        track = db.get_track_by_id(track_id)
        if not track:
            return "Track not found", 404
        
        file_content = get_file_from_telegram(track['file_id'])
        if not file_content:
            return "Error loading file", 500
        
        filename = track['file_name'].lower()
        if filename.endswith('.mp4'):
            mime_type = 'video/mp4'
        elif filename.endswith('.mp3'):
            mime_type = 'audio/mpeg'
        else:
            mime_type = track.get('mime_type', 'audio/mpeg')
        
        file_io = io.BytesIO(file_content)
        file_io.seek(0)
        
        return send_file(
            file_io,
            mimetype=mime_type,
            as_attachment=False,
            download_name=track['file_name']
        )
    except Exception as e:
        logger.error(f"Ошибка стриминга: {e}")
        return "Error", 500

@app.route('/api/playlists/<int:user_id>', methods=['GET'])
def get_playlists(user_id):
    """Получение плейлистов пользователя"""
    try:
        playlists = db.get_user_playlists(user_id)
        return jsonify(playlists)
    except Exception as e:
        logger.error(f"Ошибка получения плейлистов: {e}")
        return jsonify([])

@app.route('/api/playlist/create', methods=['POST'])
def create_playlist():
    """Создание нового плейлиста"""
    try:
        data = request.json
        user_id = data.get('user_id')
        name = data.get('name')
        
        if not user_id or not name:
            return jsonify({'error': 'Missing data'}), 400
        
        playlist_id = db.create_playlist(user_id, name)
        return jsonify({'playlist_id': playlist_id, 'success': True})
    except Exception as e:
        logger.error(f"Ошибка создания плейлиста: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlist/<int:playlist_id>/tracks', methods=['GET'])
def get_playlist_tracks(playlist_id):
    """Получение треков плейлиста"""
    try:
        tracks = db.get_playlist_tracks(playlist_id)
        return jsonify(tracks)
    except Exception as e:
        logger.error(f"Ошибка получения треков плейлиста: {e}")
        return jsonify([])

@app.route('/api/playlist/<int:playlist_id>/add', methods=['POST'])
def add_to_playlist(playlist_id):
    """Добавление трека в плейлист"""
    try:
        data = request.json
        track_id = data.get('track_id')
        
        if not track_id:
            return jsonify({'error': 'Missing track_id'}), 400
        
        success = db.add_track_to_playlist(playlist_id, track_id)
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Ошибка добавления в плейлист: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlist/<int:playlist_id>/remove', methods=['POST'])
def remove_from_playlist(playlist_id):
    """Удаление трека из плейлиста"""
    try:
        data = request.json
        track_id = data.get('track_id')
        
        if not track_id:
            return jsonify({'error': 'Missing track_id'}), 400
        
        success = db.remove_track_from_playlist(playlist_id, track_id)
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Ошибка удаления из плейлиста: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlist/<int:playlist_id>/delete', methods=['DELETE'])
def delete_playlist(playlist_id):
    """Удаление плейлиста"""
    try:
        success = db.delete_playlist(playlist_id)
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Ошибка удаления плейлиста: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)