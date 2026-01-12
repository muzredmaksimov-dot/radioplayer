import os
import csv
import time
import base64
import requests
import threading
import telebot
from telebot import types
from flask import Flask, request

# ========= НАСТРОЙКИ =========
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # строкой
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")  # @RadioMIR_Efir

CSV_FILE = "alice_friday_results.csv"
SUBSCRIBERS_FILE = "subscribers.txt"

GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

CURRENT_ARTIST = "Алиса"
# ============================

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

user_states = {}
result_buffer = []
buffer_lock = threading.Lock()

# ========= GITHUB =========
def github_read(path):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return base64.b64decode(r.json()["content"]).decode("utf-8")
    return ""

def github_write(path, content, msg):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    r = requests.get(url, headers=headers)
    payload = {
        "message": msg,
        "content": base64.b64encode(content.encode()).decode()
    }
    if r.status_code == 200:
        payload["sha"] = r.json()["sha"]
    requests.put(url, headers=headers, json=payload)

def github_append(path, line, header=None):
    existing = github_read(path)
    if not existing and header:
        new = header + "\n" + line + "\n"
    else:
        new = existing.rstrip() + "\n" + line + "\n"
    github_write(path, new, f"Update {path}")

# ========= СТАРТ =========
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id

    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, chat_id)
        if member.status not in ("member", "administrator", "creator"):
            raise Exception
    except:
        bot.send_message(
            chat_id,
            "Для участия подпишитесь на канал «Радио МИР|Эфир» 👇\n"
            f"https://t.me/{CHANNEL_USERNAME.replace('@','')}"
        )
        return

    subs = github_read(SUBSCRIBERS_FILE).splitlines()
    if str(chat_id) not in subs:
        subs.append(str(chat_id))
        github_write(SUBSCRIBERS_FILE, "\n".join(subs), "Add subscriber")

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🎸 Начать игру", callback_data="start_game"))
    bot.send_message(
        chat_id,
        f"🎶 *Алиса по пятницам*\n\n"
        f"Соберите 3 трека группы «{CURRENT_ARTIST}» в правильном порядке.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# ========= ИГРА =========
@bot.callback_query_handler(func=lambda c: c.data == "start_game")
def start_game(c):
    chat_id = c.message.chat.id
    user_states[chat_id] = {}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("📱 Отправить номер", request_contact=True))
    bot.send_message(chat_id, "Отправьте номер телефона:", reply_markup=kb)

@bot.message_handler(content_types=["contact"])
def phone(message):
    chat_id = message.chat.id
    user_states[chat_id]["phone"] = message.contact.phone_number
    bot.send_message(chat_id, "Введите ФИО:", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: m.chat.id in user_states and "name" not in user_states[m.chat.id])
def name(message):
    chat_id = message.chat.id
    user_states[chat_id]["name"] = message.text
    bot.send_message(chat_id, f"Трек №1 группы «{CURRENT_ARTIST}»:")

@bot.message_handler(func=lambda m: m.chat.id in user_states and "track1" not in user_states[m.chat.id])
def track1(message):
    user_states[message.chat.id]["track1"] = message.text
    bot.send_message(message.chat.id, "Трек №2:")

@bot.message_handler(func=lambda m: m.chat.id in user_states and "track2" not in user_states[m.chat.id])
def track2(message):
    user_states[message.chat.id]["track2"] = message.text
    bot.send_message(message.chat.id, "Трек №3:")

@bot.message_handler(func=lambda m: m.chat.id in user_states and "track3" not in user_states[m.chat.id])
def track3(message):
    chat_id = message.chat.id
    user_states[chat_id]["track3"] = message.text

    row = [
        user_states[chat_id]["name"],
        user_states[chat_id]["phone"],
        user_states[chat_id]["track1"],
        user_states[chat_id]["track2"],
        user_states[chat_id]["track3"],
    ]

    with buffer_lock:
        result_buffer.append(row)

    bot.send_message(chat_id, "✅ Спасибо за участие!\nСледите за результатами в канале Радио МИР|Эфир 🎉")
    del user_states[chat_id]

# ========= ADMIN =========
@bot.message_handler(commands=["results"])
def results(message):
    if str(message.chat.id) != ADMIN_CHAT_ID:
        return
    push_buffer()
    content = github_read(CSV_FILE)
    tmp = "/tmp/results.csv"
    open(tmp, "w", encoding="utf-8").write(content)
    with open(tmp, "rb") as f:
        bot.send_document(message.chat.id, f)

@bot.message_handler(commands=["reset"])
def reset(message):
    if str(message.chat.id) != ADMIN_CHAT_ID:
        return
    header = "ФИО|Телефон|Трек1|Трек2|Трек3"
    github_write(CSV_FILE, header + "\n", "Reset game")
    bot.send_message(message.chat.id, "🔄 Игра сброшена")

# ========= BUFFER =========
def push_buffer():
    with buffer_lock:
        if not result_buffer:
            return
        header = "ФИО|Телефон|Трек1|Трек2|Трек3"
        for r in result_buffer:
            github_append(CSV_FILE, "|".join(r), header)
        result_buffer.clear()

def auto_flush():
    while True:
        time.sleep(120)
        push_buffer()

threading.Thread(target=auto_flush, daemon=True).start()

# ========= WEBHOOK =========
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "ok"

@app.route("/")
def index():
    return "Alice Friday Bot running"

# ========= RUN =========
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"https://YOUR-RENDER-URL.onrender.com/webhook/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
