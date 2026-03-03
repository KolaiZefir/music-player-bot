import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import time

class Database:
    def __init__(self, db_path='music_player.db'):
        self.db_path = db_path
        self.cache = {}  # Простой кеш в памяти
        self.cache_ttl = 300  # 5 минут
        self.init_db()

    def init_db(self):
        """Инициализация базы данных с индексами для скорости"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    channel_id TEXT,
                    registered_at TIMESTAMP
                )
            ''')
            
            # Таблица треков с индексами
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tracks (
                    track_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    file_id TEXT UNIQUE,
                    file_name TEXT,
                    title TEXT,
                    artist TEXT,
                    duration INTEGER,
                    file_size INTEGER,
                    mime_type TEXT,
                    thumbnail_id TEXT,
                    channel_message_id INTEGER,
                    added_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Индексы для быстрого поиска
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tracks_user_id ON tracks(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tracks_added_at ON tracks(added_at DESC)')
            
            # Таблица плейлистов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS playlists (
                    playlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица связей плейлист-трек
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    playlist_id INTEGER,
                    track_id INTEGER,
                    position INTEGER,
                    added_at TIMESTAMP,
                    FOREIGN KEY (playlist_id) REFERENCES playlists (playlist_id) ON DELETE CASCADE,
                    FOREIGN KEY (track_id) REFERENCES tracks (track_id) ON DELETE CASCADE,
                    PRIMARY KEY (playlist_id, track_id)
                )
            ''')
            
            # Индекс для быстрого получения треков плейлиста
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_playlist_tracks ON playlist_tracks(playlist_id, position)')
            
            conn.commit()
            print("✅ База данных инициализирована с индексами")

    def add_user(self, user_id: int, username: str, first_name: str, last_name: str = None):
        """Добавление пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, registered_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, username, first_name, last_name, datetime.now()))
                conn.commit()
        except Exception as e:
            print(f"Ошибка добавления пользователя: {e}")

    def set_user_channel(self, user_id: int, channel_id: str):
        """Привязка канала к пользователю"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET channel_id = ? WHERE user_id = ?
                ''', (channel_id, user_id))
                conn.commit()
                print(f"✅ Канал {channel_id} привязан к пользователю {user_id}")
        except Exception as e:
            print(f"❌ Ошибка привязки канала: {e}")

    def add_track(self, user_id: int, file_id: str, file_name: str, 
                  title: str = None, artist: str = None, 
                  duration: int = 0, file_size: int = 0,
                  mime_type: str = None, thumbnail_id: str = None,
                  channel_message_id: int = None):
        """Добавление трека в базу"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if not title:
                    title = file_name
                if not artist:
                    artist = "Unknown"
                
                cursor.execute('''
                    INSERT OR IGNORE INTO tracks 
                    (user_id, file_id, file_name, title, artist, duration, file_size, mime_type, thumbnail_id, channel_message_id, added_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, file_id, file_name, title, artist, duration, file_size, mime_type, thumbnail_id, channel_message_id, datetime.now()))
                conn.commit()
                
                # Очищаем кеш для этого пользователя
                self.clear_cache(user_id)
                
                return cursor.lastrowid
        except Exception as e:
            print(f"Ошибка добавления трека: {e}")
            return None

    def get_user_tracks(self, user_id: int) -> List[Dict]:
        """Получение треков с кешированием"""
        cache_key = f"tracks_{user_id}"
        
        # Проверяем кеш
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                print(f"✅ Данные из кеша для user_id={user_id}")
                return cached_data
        
        # Нет в кеше - грузим из БД
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM tracks 
                WHERE user_id = ? 
                ORDER BY added_at DESC
            ''', (user_id,))
            tracks = [dict(row) for row in cursor.fetchall()]
            
            # Сохраняем в кеш
            self.cache[cache_key] = (tracks, time.time())
            print(f"✅ Загружено {len(tracks)} треков из БД для user_id={user_id}")
            
            return tracks

    def get_track_by_id(self, track_id: int) -> Optional[Dict]:
        """Получение трека по ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tracks WHERE track_id = ?', (track_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Ошибка получения трека: {e}")
            return None

    def delete_track(self, user_id: int, track_id: int):
        """Удаление трека"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM tracks WHERE track_id = ? AND user_id = ?
                ''', (track_id, user_id))
                conn.commit()
                self.clear_cache(user_id)
        except Exception as e:
            print(f"Ошибка удаления трека: {e}")

    def get_user_channel(self, user_id: int) -> Optional[str]:
        """Получение channel_id пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT channel_id FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            print(f"Ошибка получения канала: {e}")
            return None

    def create_playlist(self, user_id: int, name: str) -> int:
        """Создание нового плейлиста"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            now = datetime.now()
            cursor.execute('''
                INSERT INTO playlists (user_id, name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, name, now, now))
            conn.commit()
            playlist_id = cursor.lastrowid
            print(f"✅ Плейлист '{name}' создан для user_id={user_id}")
            return playlist_id

    def get_user_playlists(self, user_id: int) -> List[Dict]:
        """Получение всех плейлистов пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.*, COUNT(pt.track_id) as tracks_count
                FROM playlists p
                LEFT JOIN playlist_tracks pt ON p.playlist_id = pt.playlist_id
                WHERE p.user_id = ?
                GROUP BY p.playlist_id
                ORDER BY p.updated_at DESC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]

    def add_track_to_playlist(self, playlist_id: int, track_id: int) -> bool:
        """Добавление трека в плейлист"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Получаем максимальную позицию
                cursor.execute('''
                    SELECT MAX(position) FROM playlist_tracks 
                    WHERE playlist_id = ?
                ''', (playlist_id,))
                max_pos = cursor.fetchone()[0]
                position = (max_pos or 0) + 1
                
                # Добавляем трек
                cursor.execute('''
                    INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position, added_at)
                    VALUES (?, ?, ?, ?)
                ''', (playlist_id, track_id, position, datetime.now()))
                
                # Обновляем время изменения плейлиста
                cursor.execute('''
                    UPDATE playlists SET updated_at = ? WHERE playlist_id = ?
                ''', (datetime.now(), playlist_id))
                
                conn.commit()
                print(f"✅ Трек {track_id} добавлен в плейлист {playlist_id}")
                return True
        except Exception as e:
            print(f"❌ Ошибка добавления трека в плейлист: {e}")
            return False

    def remove_track_from_playlist(self, playlist_id: int, track_id: int) -> bool:
        """Удаление трека из плейлиста"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM playlist_tracks 
                    WHERE playlist_id = ? AND track_id = ?
                ''', (playlist_id, track_id))
                
                # Обновляем время изменения плейлиста
                cursor.execute('''
                    UPDATE playlists SET updated_at = ? WHERE playlist_id = ?
                ''', (datetime.now(), playlist_id))
                
                conn.commit()
                print(f"✅ Трек удален из плейлиста {playlist_id}")
                return True
        except Exception as e:
            print(f"❌ Ошибка удаления трека из плейлиста: {e}")
            return False

    def get_playlist_tracks(self, playlist_id: int) -> List[Dict]:
        """Получение всех треков плейлиста"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, pt.position 
                FROM tracks t
                JOIN playlist_tracks pt ON t.track_id = pt.track_id
                WHERE pt.playlist_id = ?
                ORDER BY pt.position
            ''', (playlist_id,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_playlist(self, playlist_id: int) -> bool:
        """Удаление плейлиста"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM playlists WHERE playlist_id = ?', (playlist_id,))
                conn.commit()
                print(f"✅ Плейлист {playlist_id} удален")
                return True
        except Exception as e:
            print(f"❌ Ошибка удаления плейлиста: {e}")
            return False

    def clear_cache(self, user_id: int = None):
        """Очистка кеша"""
        if user_id:
            self.cache.pop(f"tracks_{user_id}", None)
            print(f"✅ Кеш очищен для user_id={user_id}")
        else:
            self.cache.clear()
            print("✅ Весь кеш очищен")