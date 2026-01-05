import os
import time
import telebot
from flask import Flask, request
import csv
import threading

# === НАСТРОЙКИ ===
TOKEN = "8560880695:AAFUHhlq3kW_xP8gCd_Biv6q79S0VCoW8e4"
ADMIN_CHAT_ID = 866964827  # ID админа
CHANNEL_ID = "1002905716039"  # Официальный канал
CSV_FILE = "tracks_stats.csv"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# === СТАТИСТИКА ===
tracks_data = {}  # {название: {"like": int, "neutral": int, "dislike": int}}
buffer_lock = threading.Lock()

# === ФУНКЦИИ ===
def save_csv():
    with buffer_lock:
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["track", "like", "neutral", "dislike"])
            for name, stats in tracks_data.items():
                w.writerow([name, stats["like"], stats["neutral"], stats["dislike"]])

def load_csv():
    if not os.path.exists(CSV_FILE):
        return
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tracks_data[row["track"]] = {
                "like": int(row["like"]),
                "neutral": int(row["neutral"]),
                "dislike": int(row["dislike"])
            }

load_csv()

# === ОБРАБОТКА АУДИО ОТ АДМИНА ===
@bot.message_handler(content_types=["audio"])
def handle_audio(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return
    audio = message.audio
    track_name = audio.title or f"Track_{audio.file_id}"
    tracks_data[track_name] = {"like": 0, "neutral": 0, "dislike": 0}
    save_csv()

    # Отправляем трек в канал с кнопками реакций
    kb = telebot.types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        telebot.types.InlineKeyboardButton(f"👍 0", callback_data=f"like_{track_name}"),
        telebot.types.InlineKeyboardButton(f"😐 0", callback_data=f"neutral_{track_name}"),
        telebot.types.InlineKeyboardButton(f"👎 0", callback_data=f"dislike_{track_name}")
    )
    bot.send_audio(CHANNEL_ID, audio.file_id, title=track_name, reply_markup=kb)
    bot.send_message(ADMIN_CHAT_ID, f"✅ Трек '{track_name}' опубликован в канал.")

# === ОБРАБОТКА РЕАКЦИЙ ===
@bot.callback_query_handler(func=lambda c: c.data.split("_")[0] in ["like", "neutral", "dislike"])
def handle_reaction(c):
    action, track_name = c.data.split("_", 1)
    if track_name not in tracks_data:
        tracks_data[track_name] = {"like": 0, "neutral": 0, "dislike": 0}

    tracks_data[track_name][action] += 1
    save_csv()

    # Обновляем счетчики на кнопках
    kb = telebot.types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        telebot.types.InlineKeyboardButton(f"👍 {tracks_data[track_name]['like']}", callback_data=f"like_{track_name}"),
        telebot.types.InlineKeyboardButton(f"😐 {tracks_data[track_name]['neutral']}", callback_data=f"neutral_{track_name}"),
        telebot.types.InlineKeyboardButton(f"👎 {tracks_data[track_name]['dislike']}", callback_data=f"dislike_{track_name}")
    )
    try:
        bot.edit_message_reply_markup(chat_id=c.message.chat.id,
                                     message_id=c.message.message_id,
                                     reply_markup=kb)
    except:
        pass
    bot.answer_callback_query(c.id, "Голос учтен!")

# === КОМАНДЫ АДМИНА ===
@bot.message_handler(commands=["stats"])
def show_stats(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return
    text = "📊 Статистика по трекам:\n\n"
    for name, stats in tracks_data.items():
        text += f"{name} — 👍{stats['like']} 😐{stats['neutral']} 👎{stats['dislike']}\n"
    bot.send_message(ADMIN_CHAT_ID, text)

@bot.message_handler(commands=["top"])
def post_top(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return
    top_tracks = sorted(tracks_data.items(), key=lambda x: x[1]["like"], reverse=True)[:5]
    text = "🏆 ТОП треков:\n\n"
    for idx, (name, stats) in enumerate(top_tracks, 1):
        text += f"{idx}. {name} — 👍{stats['like']} 😐{stats['neutral']} 👎{stats['dislike']}\n"
    bot.send_message(CHANNEL_ID, text)
    bot.send_message(ADMIN_CHAT_ID, "✅ ТОП опубликован в канал.")

# === WEBHOOK / FLASK ===
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        bot.process_new_updates([update])
        return "", 200
    return "Bad Request", 400

@app.route("/")
def index():
    return "Music Channel Bot running!"

@app.route("/health")
def health():
    return "OK"

# === ЗАПУСК ===
if __name__ == "__main__":
    print("🚀 Бот запускается...")
    if "RENDER" in os.environ:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"https://radioplayer-tq0i.onrender.com/webhook/{TOKEN}")
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port)
    else:
        bot.remove_webhook()
        bot.polling(none_stop=True)
