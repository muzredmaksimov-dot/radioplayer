import os
import time
import csv
import threading
from flask import Flask, request
import telebot
from telebot import types

# === НАСТРОЙКИ ===
TOKEN = os.environ.get("BOT_TOKEN", " 8560880695:AAGpb-pKAt28ydK5XFhnJ9wS32hGRzTWrTo")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "866964827"))
CHANNEL_ID = os.environ.get("CHANNEL_ID", 1002905716039")

CSV_FILE = "tracks_stats.csv"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# === ХРАНИЛИЩЕ ===
tracks = {}  # track_id: {"title": str, "msg_id": int, "likes": int, "meh": int, "dislikes": int}
buffer_lock = threading.Lock()

# === УТИЛИТЫ ===
def load_stats():
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                track_id = row["track_id"]
                tracks[track_id] = {
                    "title": row["title"],
                    "msg_id": int(row["msg_id"]),
                    "likes": int(row["likes"]),
                    "meh": int(row["meh"]),
                    "dislikes": int(row["dislikes"]),
                }

def save_stats():
    with buffer_lock:
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["track_id", "title", "msg_id", "likes", "meh", "dislikes"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for track_id, data in tracks.items():
                writer.writerow({
                    "track_id": track_id,
                    "title": data["title"],
                    "msg_id": data["msg_id"],
                    "likes": data["likes"],
                    "meh": data["meh"],
                    "dislikes": data["dislikes"],
                })

def build_keyboard(track_id):
    kb = types.InlineKeyboardMarkup(row_width=3)
    data = tracks[track_id]
    kb.add(
        types.InlineKeyboardButton(f"👍 {data['likes']}", callback_data=f"like_{track_id}"),
        types.InlineKeyboardButton(f"😐 {data['meh']}", callback_data=f"meh_{track_id}"),
        types.InlineKeyboardButton(f"👎 {data['dislikes']}", callback_data=f"dislike_{track_id}")
    )
    return kb

# === ОБРАБОТКА РЕАКЦИЙ ===
@bot.callback_query_handler(func=lambda c: any(c.data.startswith(p) for p in ["like_", "meh_", "dislike_"]))
def handle_reaction(c):
    action, track_id = c.data.split("_")
    with buffer_lock:
        if track_id in tracks:
            if action == "like":
                tracks[track_id]["likes"] += 1
            elif action == "meh":
                tracks[track_id]["meh"] += 1
            else:
                tracks[track_id]["dislikes"] += 1
            # обновляем клавиатуру
            kb = build_keyboard(track_id)
            try:
                bot.edit_message_reply_markup(CHAT_ID:=CHANNEL_ID, message_id=tracks[track_id]["msg_id"], reply_markup=kb)
            except Exception as e:
                print("Ошибка обновления клавиатуры:", e)
    c.answer()  # закрывает "часики" у пользователя

# === КОМАНДЫ АДМИНА ===
@bot.message_handler(commands=["publish"])
def publish_track(message):
    if message.chat.id != ADMIN_CHAT_ID:
        return
    if not message.audio:
        bot.send_message(ADMIN_CHAT_ID, "Отправьте mp3 с названием трека!")
        return
    track_id = str(int(time.time()))
    title = message.audio.title or "Новый трек"
    msg = bot.send_audio(CHANNEL_ID, message.audio.file_id, title=title, reply_markup=build_keyboard(track_id))
    tracks[track_id] = {"title": title, "msg_id": msg.message_id, "likes": 0, "meh": 0, "dislikes": 0}
    save_stats()
    bot.send_message(ADMIN_CHAT_ID, f"Трек опубликован: {title}")

@bot.message_handler(commands=["stats"])
def send_stats(message):
    if message.chat.id != ADMIN_CHAT_ID:
        return
    msg = "📊 Статистика треков:\n\n"
    for t in tracks.values():
        msg += f"{t['title']}: 👍 {t['likes']} | 😐 {t['meh']} | 👎 {t['dislikes']}\n"
    bot.send_message(ADMIN_CHAT_ID, msg)

@bot.message_handler(commands=["top"])
def publish_top(message):
    if message.chat.id != ADMIN_CHAT_ID:
        return
    top_tracks = sorted(tracks.items(), key=lambda x: x[1]["likes"], reverse=True)[:5]
    msg = "🏆 Топ треков по лайкам:\n\n"
    for _, t in top_tracks:
        msg += f"{t['title']}: 👍 {t['likes']}\n"
    bot.send_message(CHANNEL_ID, msg)

# === WEBHOOK / FLASK ===
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "", 200

@app.route("/")
def index(): return "Music Channel Bot running!"
@app.route("/health")
def health(): return "OK"

# === ЗАПУСК ===
if __name__ == "__main__":
    load_stats()
    print("🚀 Бот запускается...")
    if "RENDER" in os.environ:
        try:
            bot.remove_webhook()
        except Exception as e:
            print("Ошибка удаления вебхука:", e)
        time.sleep(1)
        webhook_url = f"https://radioplayer-tq0i.onrender.com/webhook/{TOKEN}"
        try:
            bot.set_webhook(url=webhook_url)
            print("Вебхук установлен:", webhook_url)
        except Exception as e:
            print("Ошибка установки вебхука:", e)
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port)
    else:
        bot.remove_webhook()
        bot.polling(none_stop=True)
