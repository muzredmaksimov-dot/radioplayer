import os
import telebot
from telebot import types
from flask import Flask, request
import requests
import base64
import threading
import csv
import time

# === НАСТРОЙКИ ===
TOKEN = "ВАШ_BOT_TOKEN"
ADMIN_CHAT_ID = "ВАШ_CHAT_ID"
CSV_FILE = "backup_results.csv"

# GitHub
GITHUB_REPO = "muzredmaksimov-dot/testmuzicbot_results"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Канал для проверки подписки
CHANNEL = "@test111"

# === ХРАНИЛИЩЕ ===
user_states = {}
buffer_lock = threading.Lock()
result_buffer = []

# === ГИТХАБ ===
def github_read_file(repo, path_in_repo, token):
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path_in_repo}"
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content_b64 = r.json().get("content", "")
            return base64.b64decode(content_b64).decode("utf-8")
        return ""
    except Exception as e:
        print("GitHub read error:", e)
        return ""

def github_write_file(repo, path_in_repo, token, content_text, commit_message):
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path_in_repo}"
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        r_get = requests.get(url, headers=headers)
        b64 = base64.b64encode(content_text.encode("utf-8")).decode("utf-8")
        payload = {"message": commit_message, "content": b64}
        if r_get.status_code == 200:
            payload["sha"] = r_get.json().get("sha")
        r_put = requests.put(url, headers=headers, json=payload)
        return r_put.status_code in (200, 201)
    except Exception as e:
        print("GitHub write error:", e)
        return False

def github_append_line(repo, path_in_repo, token, line, header_if_missing=None):
    existing = github_read_file(repo, path_in_repo, token)
    if not existing:
        new_text = (header_if_missing + "\n" if header_if_missing else "") + line + "\n"
    else:
        if not existing.endswith("\n"):
            existing += "\n"
        new_text = existing + line + "\n"
    return github_write_file(repo, path_in_repo, token, new_text, f"Update {path_in_repo}")

# === СООБЩЕНИЯ ===
def send_message(chat_id, text, reply_markup=None):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup)
    except Exception as e:
        print("Send message error:", e)

# === СТАРТ ===
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    user = message.from_user

    # Проверка подписки
    try:
        status = bot.get_chat_member(CHANNEL, chat_id).status
        if status not in ["member", "administrator", "creator"]:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{CHANNEL[1:]}"))
            send_message(chat_id,
                         f"Для участия подпишитесь на канал {CHANNEL}",
                         reply_markup=kb)
            return
    except Exception as e:
        print("Ошибка проверки подписки:", e)
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{CHANNEL[1:]}"))
        send_message(chat_id,
                     f"Для участия подпишитесь на канал {CHANNEL}",
                     reply_markup=kb)
        return

    # Начало игры
    send_message(chat_id, "Привет! Для участия оставьте ваш номер телефона:")
    user_states[chat_id] = {"step": "phone", "data": {}}

# === ОБРАБОТКА ВВОДА ===
@bot.message_handler(func=lambda m: True)
def handle_input(message):
    chat_id = message.chat.id
    text = message.text.strip()
    if chat_id not in user_states:
        send_message(chat_id, "Нажмите /start для начала.")
        return

    state = user_states[chat_id]["step"]

    if state == "phone":
        user_states[chat_id]["data"]["phone"] = text
        user_states[chat_id]["step"] = "fio"
        send_message(chat_id, "Отлично! Теперь введите ФИО:")
    elif state == "fio":
        user_states[chat_id]["data"]["fio"] = text
        user_states[chat_id]["step"] = "track1"
        send_message(chat_id, "Введите название первого трека:")
    elif state.startswith("track"):
        track_num = int(state[-1])
        user_states[chat_id]["data"][f"track{track_num}"] = text
        if track_num < 3:
            user_states[chat_id]["step"] = f"track{track_num + 1}"
            send_message(chat_id, f"Введите название трека {track_num + 1}:")
        else:
            # Финал — записать данные
            row = [
                user_states[chat_id]["data"].get("fio", ""),
                user_states[chat_id]["data"].get("phone", ""),
                user_states[chat_id]["data"].get("track1", ""),
                user_states[chat_id]["data"].get("track2", ""),
                user_states[chat_id]["data"].get("track3", "")
            ]
            with buffer_lock:
                result_buffer.append(row)
            send_message(chat_id, "Спасибо за участие! Следите за результатами в нашем канале.")
            bot.send_message(ADMIN_CHAT_ID, f"Новый участник: {row}")
            user_states.pop(chat_id, None)

# === PUSH BUFFER TO GITHUB ===
def push_buffer_to_github():
    with buffer_lock:
        if not result_buffer:
            return
        file_exists = os.path.exists(CSV_FILE)
        with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not file_exists:
                w.writerow(["FIO", "Phone", "Track1", "Track2", "Track3"])
            for row in result_buffer:
                w.writerow(row)
        # Записать на GitHub
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        github_write_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN, content, "Buffer flush")
        result_buffer.clear()

# Авто-флаш каждые 2 минуты
def auto_flush():
    while True:
        time.sleep(120)
        push_buffer_to_github()

threading.Thread(target=auto_flush, daemon=True).start()

# === АДМИНСКИЕ КОМАНДЫ ===
@bot.message_handler(commands=["reset"])
def reset_csv(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        send_message(message.chat.id, "⛔ Нет доступа.")
        return
    header = ["FIO", "Phone", "Track1", "Track2", "Track3"]
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(header)
    github_write_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN, ",".join(header) + "\n", "Reset CSV")
    send_message(message.chat.id, "✅ CSV сброшен.")

@bot.message_handler(commands=["results"])
def send_results(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        send_message(message.chat.id, "⛔ Нет доступа.")
        return
    try:
        with open(CSV_FILE, "rb") as f:
            bot.send_document(message.chat.id, f, caption="backup_results.csv")
    except:
        send_message(message.chat.id, "❌ CSV пока не создан.")

# === WEBHOOK ===
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        bot.process_new_updates([update])
        return ""
    return "Bad Request", 400

@app.route("/")
def index(): return "Bot running!"

@app.route("/health")
def health(): return "OK"

if __name__ == "__main__":
    print("🚀 Бот запущен")
    if "RENDER" in os.environ:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"https://ВАШ_ДОМЕН.onrender.com/webhook/{TOKEN}")
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    else:
        bot.remove_webhook()
        bot.polling(none_stop=True)
