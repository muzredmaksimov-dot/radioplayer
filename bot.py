import os
import telebot
from telebot import types
from flask import Flask, request
import threading
import csv
import time

# === НАСТРОЙКИ ===
TOKEN = "8560880695:AAFUHhlq3kW_xP8gCd_Biv6q79S0VCoW8e4"
ADMIN_CHAT_ID = 866964827  # ID админа
CHANNEL_ID = "@testposring"  # Официальный канал
CSV_FILE = "tracks_stats.csv"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# === ХРАНИЛИЩЕ ТРЕКОВ ===
track_states = {}  # {track_id: {"title": str, "likes": int, "super": int, "dislikes": int, "message_id": int}}

buffer_lock = threading.Lock()
result_buffer = []  # временный буфер строк CSV

# === УТИЛИТЫ ===
def save_buffer_to_csv():
    with buffer_lock:
        if not track_states:
            return
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["title", "likes", "super", "dislikes"])
            for t in track_states.values():
                w.writerow([t["title"], t["likes"], t["super"], t["dislikes"]])

# === ОТПРАВКА ТРЕКА ===
def send_track_to_channel(title, audio_file_path):
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton(f"👍 0", callback_data=f"like_0"),
        types.InlineKeyboardButton(f"🔥 0", callback_data=f"super_0"),
        types.InlineKeyboardButton(f"👎 0", callback_data=f"dislike_0")
    )
    with open(audio_file_path, "rb") as f:
        msg = bot.send_audio(CHANNEL_ID, f, title=title, reply_markup=kb)
        # Сохраняем трек в память
        track_states[msg.message_id] = {"title": title, "likes": 0, "super": 0, "dislikes": 0, "message_id": msg.message_id}

# === РЕАКЦИИ ===
@bot.callback_query_handler(func=lambda c: c.data.startswith(("like_", "super_", "dislike_")))
def handle_reaction(c):
    chat_id = c.message.chat.id
    msg_id = c.message.message_id
    track = track_states.get(msg_id)
    if not track:
        return

    reaction = c.data.split("_")[0]
    if reaction == "like":
        track["likes"] += 1
    elif reaction == "super":
        track["super"] += 1
    elif reaction == "dislike":
        track["dislikes"] += 1

    # Обновляем кнопки с новым счетом
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton(f"👍 {track['likes']}", callback_data=f"like_0"),
        types.InlineKeyboardButton(f"🔥 {track['super']}", callback_data=f"super_0"),
        types.InlineKeyboardButton(f"👎 {track['dislikes']}", callback_data=f"dislike_0")
    )
    try:
        bot.edit_message_reply_markup(CHANNEL_ID, msg_id, reply_markup=kb)
    except:
        pass

    c.answer()  # убираем "часики"

# === АДМИН: ТОП-3 ===
@bot.message_handler(commands=["top"])
def top_command(m):
    if m.chat.id != ADMIN_CHAT_ID:
        bot.send_message(m.chat.id, "⛔ У вас нет доступа к этой команде.")
        return

    if not track_states:
        bot.send_message(ADMIN_CHAT_ID, "📊 Пока нет опубликованных треков.")
        return

    def top_n(key, n=3):
        return sorted(track_states.values(), key=lambda x: x[key], reverse=True)[:n]

    top_likes = top_n("likes")
    top_super = top_n("super")
    top_dislikes = top_n("dislikes")

    msg_lines = ["🔥 Топ-3 трека по реакциям:"]
    msg_lines.append("\n👍 Лайки:")
    for t in top_likes:
        msg_lines.append(f"{t['title']} — {t['likes']}")
    msg_lines.append("\n🔥 Супер:")
    for t in top_super:
        msg_lines.append(f"{t['title']} — {t['super']}")
    msg_lines.append("\n👎 Дизлайки:")
    for t in top_dislikes:
        msg_lines.append(f"{t['title']} — {t['dislikes']}")

    bot.send_message(ADMIN_CHAT_ID, "\n".join(msg_lines))

# === АДМИН: ПУБЛИКАЦИЯ ТОПА В КАНАЛ ===
@bot.message_handler(commands=["publish_top"])
def publish_top_command(m):
    if m.chat.id != ADMIN_CHAT_ID:
        bot.send_message(m.chat.id, "⛔ У вас нет доступа к этой команде.")
        return

    if not track_states:
        bot.send_message(ADMIN_CHAT_ID, "📊 Нет треков для публикации.")
        return

    # Формируем текст топа
    def top_n_text(key, n=3):
        t = sorted(track_states.values(), key=lambda x: x[key], reverse=True)[:n]
        return "\n".join([f"{x['title']} — {x[key]}" for x in t])

    text = (
        "🔥 Топ-3 треков по реакциям:\n\n"
        f"👍 Лайки:\n{top_n_text('likes')}\n\n"
        f"🔥 Супер:\n{top_n_text('super')}\n\n"
        f"👎 Дизлайки:\n{top_n_text('dislikes')}"
    )

    bot.send_message(CHANNEL_ID, text)
    bot.send_message(ADMIN_CHAT_ID, "✅ Топ успешно опубликован в канал.")

# === АДМИН: ЗАГРУЗКА ТРЕКОВ ИЗ ЛИЧКИ ===
@bot.message_handler(content_types=["audio"])
def handle_admin_audio(m):
    if m.chat.id != ADMIN_CHAT_ID:
        return

    title = m.audio.title or "Без названия"
    file_info = bot.get_file(m.audio.file_id)
    file_path = f"tracks/{title}.mp3"
    os.makedirs("tracks", exist_ok=True)
    downloaded_file = bot.download_file(file_info.file_path)
    with open(file_path, "wb") as f:
        f.write(downloaded_file)

    send_track_to_channel(title, file_path)
    bot.send_message(ADMIN_CHAT_ID, f"✅ Трек '{title}' опубликован в канал.")

# === FLUSH CSV ПЕРИОДИЧЕСКИ ===
def auto_flush():
    while True:
        time.sleep(120)
        save_buffer_to_csv()

threading.Thread(target=auto_flush, daemon=True).start()

# === WEBHOOK / FLASK ===
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        bot.process_new_updates([update])
        return ""
    return "Bad Request", 400

@app.route("/")
def index(): return "Music Channel Bot running!"
@app.route("/health")
def health(): return "OK"

# === ЗАПУСК ===
if name == "__main__":
    print("🚀 Бот запущен")
    if "RENDER" in os.environ:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"https://your-app-name.onrender.com/webhook/{TOKEN}")
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    else:
        bot.remove_webhook()
        bot.polling(none_stop=True)
