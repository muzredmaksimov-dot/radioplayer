import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import telebot
from telebot.types import (
    Message, 
    ReplyKeyboardMarkup,
    KeyboardButton
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения Render
BOT_TOKEN = os.getenv("BOT_TOKEN", "8560880695:AAFUHhlq3kW_xP8gCd_Biv6q79S0VCoW8e4")

# Если запускаем локально и хотим указать администратора
ADMIN_ID = 582134246  # Замени на свой ID в Telegram
ADMIN_IDS = [ADMIN_ID] if ADMIN_ID else []

# Файлы
TRACKS_FILE = "tracks.json"
AUDIO_DIR = "audio"
COVERS_DIR = "covers"

# Создаем директории если их нет
Path(AUDIO_DIR).mkdir(exist_ok=True)
Path(COVERS_DIR).mkdir(exist_ok=True)

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Хранилище состояния пользователей
user_states = {}

class UserState:
    """Класс для хранения состояния пользователя"""
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.step = None  # Текущий шаг
        self.temp_data = {}  # Временные данные трека

class TrackManager:
    """Простой менеджер треков"""
    
    @staticmethod
    def load_tracks() -> List[Dict]:
        """Загрузка треков из файла"""
        try:
            if os.path.exists(TRACKS_FILE):
                with open(TRACKS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Ошибка загрузки треков: {e}")
            return []
    
    @staticmethod
    def save_tracks(tracks: List[Dict]):
        """Сохранение треков в файл"""
        try:
            with open(TRACKS_FILE, 'w', encoding='utf-8') as f:
                json.dump(tracks, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранено {len(tracks)} треков")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения треков: {e}")
            return False
    
    @staticmethod
    def add_track(track: Dict) -> bool:
        """Добавление нового трека"""
        tracks = TrackManager.load_tracks()
        
        # Генерируем ID
        track_id = int(datetime.now().timestamp())
        track['id'] = track_id
        
        # Добавляем дату
        track['added_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Инициализируем голоса
        if 'votes' not in track:
            track['votes'] = {'likes': 0, 'dislikes': 0}
        
        # Добавляем эмодзи по умолчанию для обложки
        if 'artwork' not in track:
            track['artwork'] = '🎵'
        
        tracks.append(track)
        return TrackManager.save_tracks(tracks)
    
    @staticmethod
    def delete_track(track_id: int) -> bool:
        """Удаление трека"""
        tracks = TrackManager.load_tracks()
        tracks = [t for t in tracks if t.get('id') != track_id]
        return TrackManager.save_tracks(tracks)
    
    @staticmethod
    def get_stats() -> Dict:
        """Получение статистики"""
        tracks = TrackManager.load_tracks()
        
        total_likes = sum(t.get('votes', {}).get('likes', 0) for t in tracks)
        total_dislikes = sum(t.get('votes', {}).get('dislikes', 0) for t in tracks)
        
        return {
            'total_tracks': len(tracks),
            'total_likes': total_likes,
            'total_dislikes': total_dislikes,
        }

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Основная клавиатура с 4 кнопками"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    markup.add(
        KeyboardButton("📋 Список треков"),
        KeyboardButton("➕ Добавить трек")
    )
    markup.add(
        KeyboardButton("🗑️ Удалить трек"),
        KeyboardButton("📊 Статистика")
    )
    
    return markup

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("❌ Отмена"))
    return markup

def get_tracks_list_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура со списком треков для удаления"""
    tracks = TrackManager.load_tracks()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    
    if not tracks:
        markup.add(KeyboardButton("📭 Нет треков"))
    
    for track in tracks[:10]:  # Ограничиваем 10 треками
        artist = track.get('artist', 'Артист')
        title = track.get('title', 'Трек')
        track_id = track.get('id', 0)
        
        # Сокращаем текст если слишком длинный
        button_text = f"{artist[:15]} - {title[:15]}"
        if len(artist) > 15 or len(title) > 15:
            button_text += "..."
        
        markup.add(KeyboardButton(f"🗑️ {button_text} | ID:{track_id}"))
    
    markup.add(KeyboardButton("❌ Отмена"))
    return markup

@bot.message_handler(commands=['start', 'help'])
def handle_start(message: Message):
    """Обработчик команды /start"""
    user = message.from_user
    
    # Проверяем, админ ли
    admin_status = "👑 Администратор" if is_admin(user.id) else "👤 Пользователь"
    
    welcome_text = (
        f"🎧 Привет, {user.first_name}!\n"
        f"Я бот для управления радиостанцией <b>РАДИО МИР</b>\n"
        f"Статус: {admin_status}\n\n"
        "Выбери действие:"
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "📋 Список треков")
def handle_list_tracks(message: Message):
    """Показать список треков"""
    tracks = TrackManager.load_tracks()
    
    if not tracks:
        bot.send_message(
            message.chat.id,
            "📭 Список треков пуст.\nДобавь первый трек!",
            reply_markup=get_main_keyboard()
        )
        return
    
    response = "📋 <b>Список треков:</b>\n\n"
    
    for i, track in enumerate(tracks, 1):
        artist = track.get('artist', 'Неизвестный')
        title = track.get('title', 'Без названия')
        likes = track.get('votes', {}).get('likes', 0)
        dislikes = track.get('votes', {}).get('dislikes', 0)
        
        response += (
            f"{i}. <b>{artist}</b> - {title}\n"
            f"   👍 {likes} | 👎 {dislikes}\n\n"
        )
    
    bot.send_message(
        message.chat.id,
        response,
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "➕ Добавить трек")
def handle_add_track_start(message: Message):
    """Начало добавления трека"""
    if not is_admin(message.from_user.id):
        bot.send_message(
            message.chat.id,
            "❌ Только администратор может добавлять треки",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Инициализируем состояние
    user_state = UserState(message.from_user.id)
    user_state.step = 'waiting_artist'
    user_states[message.from_user.id] = user_state
    
    bot.send_message(
        message.chat.id,
        "🎤 <b>Шаг 1 из 4</b>\n"
        "Напиши имя исполнителя:",
        reply_markup=get_cancel_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "❌ Отмена")
def handle_cancel(message: Message):
    """Обработка отмены"""
    user_id = message.from_user.id
    
    if user_id in user_states:
        del user_states[user_id]
    
    bot.send_message(
        message.chat.id,
        "❌ Действие отменено",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda message: 
    message.from_user.id in user_states and 
    user_states[message.from_user.id].step == 'waiting_artist')
def handle_artist_input(message: Message):
    """Обработка ввода исполнителя"""
    user_id = message.from_user.id
    user_state = user_states[user_id]
    
    user_state.temp_data['artist'] = message.text.strip()
    user_state.step = 'waiting_title'
    
    bot.send_message(
        message.chat.id,
        "🎵 <b>Шаг 2 из 4</b>\n"
        "Напиши название трека:",
        reply_markup=get_cancel_keyboard()
    )

@bot.message_handler(func=lambda message: 
    message.from_user.id in user_states and 
    user_states[message.from_user.id].step == 'waiting_title')
def handle_title_input(message: Message):
    """Обработка ввода названия трека"""
    user_id = message.from_user.id
    user_state = user_states[user_id]
    
    user_state.temp_data['title'] = message.text.strip()
    user_state.step = 'waiting_cover'
    
    bot.send_message(
        message.chat.id,
        "🖼️ <b>Шаг 3 из 4</b>\n"
        "Загрузи обложку (PNG файл):\n\n"
        "<i>Нажми на скрепку 📎 и выбери файл</i>",
        reply_markup=get_cancel_keyboard()
    )

@bot.message_handler(
    func=lambda message: 
    message.from_user.id in user_states and 
    user_states[message.from_user.id].step == 'waiting_cover',
    content_types=['document']
)
def handle_cover_input(message: Message):
    """Обработка загрузки обложки"""
    user_id = message.from_user.id
    user_state = user_states[user_id]
    
    if not message.document:
        bot.send_message(
            message.chat.id,
            "❌ Пожалуйста, отправь файл как документ",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    file_name = message.document.file_name or ""
    
    # Проверяем расширение
    if not file_name.lower().endswith('.png'):
        bot.send_message(
            message.chat.id,
            "❌ Файл должен быть в формате PNG!\n"
            "Пожалуйста, загрузи PNG файл:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    try:
        # Скачиваем файл
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Сохраняем файл
        filename = f"cover_{user_id}_{int(datetime.now().timestamp())}.png"
        filepath = os.path.join(COVERS_DIR, filename)
        
        with open(filepath, 'wb') as f:
            f.write(downloaded_file)
        
        user_state.temp_data['cover'] = filename
        user_state.step = 'waiting_audio'
        
        bot.send_message(
            message.chat.id,
            "✅ Обложка сохранена!\n\n"
            "🎵 <b>Шаг 4 из 4</b>\n"
            "Загрузи аудиофайл (MP3):\n\n"
            "<i>Нажми на скрепку 📎 и выбери MP3 файл</i>",
            reply_markup=get_cancel_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка сохранения обложки: {e}")
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_keyboard()
        )
        if user_id in user_states:
            del user_states[user_id]

@bot.message_handler(
    func=lambda message: 
    message.from_user.id in user_states and 
    user_states[message.from_user.id].step == 'waiting_audio',
    content_types=['audio', 'document']
)
def handle_audio_input(message: Message):
    """Обработка загрузки аудио"""
    user_id = message.from_user.id
    user_state = user_states[user_id]
    
    file_id = None
    file_name = ""
    
    if message.audio:
        # Если отправлено как аудио
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "audio.mp3"
        
        # Проверяем формат
        if not message.audio.mime_type == 'audio/mpeg':
            bot.send_message(
                message.chat.id,
                "❌ Файл должен быть в формате MP3!",
                reply_markup=get_cancel_keyboard()
            )
            return
            
    elif message.document:
        # Если отправлено как документ
        file_name = message.document.file_name or ""
        
        if not file_name.lower().endswith('.mp3'):
            bot.send_message(
                message.chat.id,
                "❌ Файл должен быть в формате MP3!",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        file_id = message.document.file_id
    
    if not file_id:
        bot.send_message(
            message.chat.id,
            "❌ Не удалось получить файл",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    try:
        # Скачиваем файл
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Сохраняем файл
        filename = f"audio_{user_id}_{int(datetime.now().timestamp())}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)
        
        with open(filepath, 'wb') as f:
            f.write(downloaded_file)
        
        # Формируем трек
        track = {
            'artist': user_state.temp_data.get('artist', 'Исполнитель'),
            'title': user_state.temp_data.get('title', 'Трек'),
            'audio': f"audio/{filename}",
            'artwork': f"covers/{user_state.temp_data.get('cover', 'default')}"
        }
        
        # Добавляем трек
        if TrackManager.add_track(track):
            # Очищаем состояние
            if user_id in user_states:
                del user_states[user_id]
            
            bot.send_message(
                message.chat.id,
                f"✅ <b>Трек успешно добавлен!</b>\n\n"
                f"🎤 <b>Исполнитель:</b> {track['artist']}\n"
                f"🎵 <b>Название:</b> {track['title']}\n\n"
                f"Теперь он появится в приложении радиостанции!",
                reply_markup=get_main_keyboard()
            )
        else:
            raise Exception("Ошибка сохранения трека")
            
    except Exception as e:
        logger.error(f"Ошибка сохранения аудио: {e}")
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_keyboard()
        )
        if user_id in user_states:
            del user_states[user_id]

@bot.message_handler(func=lambda message: message.text == "🗑️ Удалить трек")
def handle_delete_track_start(message: Message):
    """Начало удаления трека"""
    if not is_admin(message.from_user.id):
        bot.send_message(
            message.chat.id,
            "❌ Только администратор может удалять треки",
            reply_markup=get_main_keyboard()
        )
        return
    
    tracks = TrackManager.load_tracks()
    
    if not tracks:
        bot.send_message(
            message.chat.id,
            "📭 Нет треков для удаления",
            reply_markup=get_main_keyboard()
        )
        return
    
    bot.send_message(
        message.chat.id,
        "🗑️ <b>Выбери трек для удаления:</b>\n"
        "Нажми на кнопку с названием трека",
        reply_markup=get_tracks_list_keyboard()
    )

@bot.message_handler(func=lambda message: message.text.startswith("🗑️ "))
def handle_delete_track_selection(message: Message):
    """Обработка выбора трека для удаления"""
    try:
        # Извлекаем ID из текста кнопки
        text = message.text
        if "| ID:" in text:
            track_id_str = text.split("| ID:")[1].strip()
            track_id = int(track_id_str)
            
            if TrackManager.delete_track(track_id):
                bot.send_message(
                    message.chat.id,
                    "✅ Трек удален!",
                    reply_markup=get_main_keyboard()
                )
            else:
                bot.send_message(
                    message.chat.id,
                    "❌ Не удалось удалить трек",
                    reply_markup=get_main_keyboard()
                )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Ошибка формата",
                reply_markup=get_main_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка удаления трека: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при удалении",
            reply_markup=get_main_keyboard()
        )

@bot.message_handler(func=lambda message: message.text == "📊 Статистика")
def handle_stats(message: Message):
    """Показать статистику"""
    stats = TrackManager.get_stats()
    tracks = TrackManager.load_tracks()
    
    response = (
        "📊 <b>Статистика радиостанции:</b>\n\n"
        f"🎵 Всего треков: <b>{stats['total_tracks']}</b>\n"
        f"👍 Всего лайков: <b>{stats['total_likes']}</b>\n"
        f"👎 Всего дизлайков: <b>{stats['total_dislikes']}</b>\n"
    )
    
    # Показываем топ-3 трека
    if tracks:
        # Сортируем по лайкам
        sorted_tracks = sorted(
            tracks, 
            key=lambda x: x.get('votes', {}).get('likes', 0), 
            reverse=True
        )[:3]
        
        if sorted_tracks:
            response += "\n🏆 <b>Топ-3 трека:</b>\n"
            for i, track in enumerate(sorted_tracks, 1):
                artist = track.get('artist', 'Артист')
                title = track.get('title', 'Трек')
                likes = track.get('votes', {}).get('likes', 0)
                dislikes = track.get('votes', {}).get('dislikes', 0)
                
                response += f"{i}. <b>{artist}</b> - {title}\n"
                response += f"   👍 {likes} | 👎 {dislikes}\n"
    
    bot.send_message(
        message.chat.id,
        response,
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message: Message):
    """Обработка всех остальных сообщений"""
    # Если пользователь в процессе добавления трека
    if message.from_user.id in user_states:
        bot.send_message(
            message.chat.id,
            "⚠️ Заверши добавление трека или нажми '❌ Отмена'",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Иначе показываем основное меню
    bot.send_message(
        message.chat.id,
        "Используй кнопки для управления:",
        reply_markup=get_main_keyboard()
    )

def main():
    """Запуск бота"""
    logger.info("🚀 Запуск бота радиостанции...")
    
    # Создаем начальные файлы
    if not os.path.exists(TRACKS_FILE):
        with open(TRACKS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        logger.info("Создан файл tracks.json")
    
    logger.info(f"Бот запущен с токеном: {BOT_TOKEN[:10]}...")
    
    # Бесконечный опрос
    bot.infinity_polling()

if __name__ == "__main__":
    main()
