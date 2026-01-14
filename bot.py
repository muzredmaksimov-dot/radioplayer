import os
import telebot
import time
import csv
import datetime
import threading
import requests
import base64
from telebot import types
from flask import Flask, request

# === НАСТРОЙКИ ===
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = str(os.environ.get("ADMIN_CHAT_ID"))
CSV_FILE = "results.csv"

GITHUB_REPO = "muzredmaksimov-dot/radioplayer"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

CHANNEL_ID = -1002905716039
CHANNEL_URL = "https://t.me/test111"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# === ХРАНИЛИЩА ===
user_states = {}
user_main_message = {}
user_finished = set()
friday_reminders = set()
current_artist = "АРТИСТ"

lock = threading.Lock()

# === GITHUB ===
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
    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json()["sha"]

    payload = {
        "message": msg,
        "content": base64.b64encode(content.encode()).decode()
    }
    if sha:
        payload["sha"] = sha

    requests.put(url, headers=headers, json=payload)

# === CSV ===
def ensure_csv():
    if not github_read(CSV_FILE):
        header = "ФИО;Телефон;Трек1;Трек2;Трек3\n"
        github_write(CSV_FILE, header, "Init CSV")

def append_csv(row):
    data = github_read(CSV_FILE)
    github_write(CSV_FILE, data + row + "\n", "Add result")

# === ВСПОМОГАТЕЛЬНОЕ ===
def is_friday():
    return datetime.datetime.now().weekday() == 4

def set_screen(chat_id, text, kb=None):
    if chat_id in user_main_message:
        try:
            bot.edit_message_text(text, chat_id, user_main_message[chat_id], reply_markup=kb)
            return
        except:
            pass
    msg = bot.send_message(chat_id, text, reply_markup=kb)
    user_main_message[chat_id] = msg.message_id

# === START ===
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id

    if not is_friday():
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔔 Напомнить в пятницу", callback_data="remind"))
        set_screen(
            chat_id,
            "🎵 *Алиса по пятницам*\n\n"
            "Каждую пятницу с 7:00 до 20:00 в эфире звучат песни одного артиста.\n"
            "Твоя задача — прислать 3 трека в правильном порядке.\n\n"
            "🎁 В понедельник подведём итоги и разыграем умную колонку!",
            kb
        )
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🚀 Играть", callback_data="play"))
    set_screen(chat_id, f"🎵 Сегодня собираем треклист *{current_artist}*", kb)

# === НАПОМИНАНИЕ ===
@bot.callback_query_handler(func=lambda c: c.data == "remind")
def remind(c):
    friday_reminders.add(c.message.chat.id)
    bot.answer_callback_query(c.id, "🔔 Напомним в пятницу в 9:00")

# === ИГРА ===
@bot.callback_query_handler(func=lambda c: c.data == "play")
def play(c):
    chat_id = c.message.chat.id

    try:
        status = bot.get_chat_member(CHANNEL_ID, chat_id).status
        if status not in ("member", "administrator", "creator"):
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Подписаться", url=CHANNEL_URL))
            kb.add(types.InlineKeyboardButton("Проверить подписку", callback_data="play"))
            set_screen(chat_id, "Подпишитесь на канал, чтобы играть 👇", kb)
            return
    except:
        return

    user_states[chat_id] = {"step": "phone", "data": {}}
    set_screen(chat_id, "Введите номер телефона:")

@bot.message_handler(func=lambda m: m.chat.id in user_states)
def game_flow(m):
    chat_id = m.chat.id
    state = user_states[chat_id]
    step = state["step"]
    text = m.text.strip()

    if step == "phone":
        state["data"]["phone"] = text
        state["step"] = "fio"
        set_screen(chat_id, "Введите ФИО:")
    elif step == "fio":
        state["data"]["fio"] = text
        state["step"] = "t1"
        set_screen(chat_id, "Введите первый трек:")
    elif step == "t1":
        state["data"]["t1"] = text
        state["step"] = "t2"
        set_screen(chat_id, "Введите второй трек:")
    elif step == "t2":
        state["data"]["t2"] = text
        state["step"] = "t3"
        set_screen(chat_id, "Введите третий трек:")
    elif step == "t3":
        state["data"]["t3"] = text
        ensure_csv()
        row = f"{state['data']['fio']};{state['data']['phone']};{state['data']['t1']};{state['data']['t2']};{state['data']['t3']}"
        append_csv(row)
        user_states.pop(chat_id)
        user_finished.add(chat_id)
        set_screen(chat_id, "✅ Спасибо за участие!\n\nСледите за эфиром 💙")

# === АДМИН ===
@bot.message_handler(commands=["new"])
def new_artist(m):
    global current_artist
    if str(m.chat.id) != ADMIN_CHAT_ID:
        return
    current_artist = m.text.replace("/new", "").strip()
    bot.send_message(m.chat.id, f"🎤 Артист установлен: {current_artist}")

@bot.message_handler(commands=["reset"])
def reset(m):
    if str(m.chat.id) != ADMIN_CHAT_ID:
        return

    ensure_csv()
    github_write(CSV_FILE, "ФИО;Телефон;Трек1;Трек2;Трек3\n", "Reset CSV")

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🚀 Играть", callback_data="play"))

    for chat_id in list(user_finished):
        try:
            bot.delete_message(chat_id, user_main_message.get(chat_id))
        except:
            pass
        msg = bot.send_message(chat_id, f"🎵 В эту пятницу собираем треклист *{current_artist}*", reply_markup=kb, parse_mode="Markdown")
        user_main_message[chat_id] = msg.message_id

    user_finished.clear()
    bot.send_message(m.chat.id, "✅ Игра перезапущена и рассылка отправлена")

@bot.message_handler(commands=["results"])
def results(m):
    if str(m.chat.id) != ADMIN_CHAT_ID:
        return

    content = github_read(CSV_FILE)
    if not content:
        bot.send_message(m.chat.id, "❌ Файл пуст")
        return

    path = "/tmp/results.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    with open(path, "rb") as f:
        bot.send_document(m.chat.id, f)

# === НАПОМИНАНИЕ В 9:00 ===
def friday_notifier():
    while True:
        now = datetime.datetime.now()
        if now.weekday() == 4 and now.hour == 9 and now.minute == 0:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🚀 Играть", callback_data="play"))
            for chat_id in friday_reminders:
                try:
                    msg = bot.send_message(chat_id, "🎵 Игра началась!", reply_markup=kb)
                    user_main_message[chat_id] = msg.message_id
                except:
                    pass
            friday_reminders.clear()
            time.sleep(60)
        time.sleep(10)

threading.Thread(target=friday_notifier, daemon=True).start()

# === WEBHOOK ===
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.data.decode())
    bot.process_new_updates([update])
    return ""

@app.route("/")
def index():
    return "Bot OK"

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{os.environ.get('RENDER_EXTERNAL_URL')}/webhook/{TOKEN}")
    app.run(host="0.0.0.0", port=10000)
