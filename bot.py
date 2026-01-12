import os
import telebot
import time
import csv
from telebot import types
from flask import Flask, request
import requests
import base64
import threading

# === НАСТРОЙКИ ===
TOKEN = os.environ.get("BOT_TOKEN")       # токен бота в Render ENV
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")  # id админа
CSV_FILE = "backup_results.csv"
SUBSCRIBERS_FILE = "subscribers.txt"
GITHUB_REPO = "muzredmaksimov-dot/radioplayer_results"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# === ХРАНИЛИЩЕ ===
user_last_message = {}
user_states = {}
buffer_lock = threading.Lock()
result_buffer = []

# === СООБЩЕНИЯ ===
def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    try:
        msg = bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
        user_last_message.setdefault(chat_id, []).append(msg.message_id)
        return msg
    except Exception as e:
        print("Ошибка отправки:", e)

def cleanup_chat(chat_id):
    for msg_id in user_last_message.get(chat_id, []):
        try:
            bot.delete_message(chat_id, msg_id)
        except:
            pass
    user_last_message[chat_id] = []

# === GITHUB UTILS ===
def github_read_file(repo, path, token):
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"token {token}"} if token else {}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content_b64 = r.json().get("content", "")
            return base64.b64decode(content_b64).decode("utf-8")
        return ""
    except Exception as e:
        print("GitHub read error:", e)
        return ""

def github_write_file(repo, path, token, content, commit_msg):
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"token {token}"} if token else {}
        r_get = requests.get(url, headers=headers)
        b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        payload = {"message": commit_msg, "content": b64}
        if r_get.status_code == 200:
            payload["sha"] = r_get.json().get("sha")
        r_put = requests.put(url, headers=headers, json=payload)
        return r_put.status_code in (200, 201)
    except Exception as e:
        print("GitHub write error:", e)
        return False

def github_append_line(repo, path, token, line, header_if_missing=None):
    existing = github_read_file(repo, path, token)
    if not existing:
        new_text = (header_if_missing + "\n" if header_if_missing else "") + line + "\n"
    else:
        if not existing.endswith("\n"):
            existing += "\n"
        new_text = existing + line + "\n"
    return github_write_file(repo, path, token, new_text, f"Update {path}")

# === СТАРТ ===
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    cleanup_chat(chat_id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🚀 Начать игру", callback_data="start_game"))
    send_message(chat_id,
                 "Привет! 🎵\nЧтобы участвовать в игре «Алиса по пятницам», нужно собрать три трека в правильном порядке.\n\n"
                 "Нажмите кнопку ниже, чтобы начать.",
                 reply_markup=kb)

# === ЗАПУСК ИГРЫ ===
@bot.callback_query_handler(func=lambda c: c.data == "start_game")
def start_game(c):
    chat_id = c.message.chat.id
    try:
        bot.delete_message(chat_id, c.message.message_id)
    except:
        pass

    # Проверка подписки на тестовый канал
    channel = "@test111"
    try:
        member = bot.get_chat_member(channel, chat_id)
        if member.status not in ["member", "administrator", "creator"]:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{channel[1:]}"))
            send_message(chat_id,
                         "Для участия подпишитесь на канал «test111»",
                         reply_markup=kb)
            return
    except Exception as e:
        print(f"⚠️ Не удалось проверить подписку пользователя {chat_id}: {e}")
        send_message(chat_id, "⚠️ Не удалось проверить подписку, но игра продолжается (тестовый режим)")

    # Начало игры: запрос телефона
    msg = send_message(chat_id, "Оставьте свой номер телефона:")
    user_states[chat_id] = {"step": "phone", "data": {}}

# === ОБРАБОТКА ВВОДА ===
@bot.message_handler(func=lambda m: True)
def handle_input(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    if not state:
        return

    step = state.get("step")
    text = message.text.strip()

    if step == "phone":
        state["data"]["phone"] = text
        state["step"] = "fio"
        send_message(chat_id, "Укажите ФИО:")
    elif step == "fio":
        state["data"]["fio"] = text
        state["step"] = "track1"
        send_message(chat_id, "Введите первый трек:")
    elif step == "track1":
        state["data"]["track1"] = text
        state["step"] = "track2"
        send_message(chat_id, "Введите второй трек:")
    elif step == "track2":
        state["data"]["track2"] = text
        state["step"] = "track3"
        send_message(chat_id, "Введите третий трек:")
    elif step == "track3":
        state["data"]["track3"] = text
        line = f"{state['data']['fio']}|{state['data']['phone']}|{state['data']['track1']}|{state['data']['track2']}|{state['data']['track3']}"
        github_append_line(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN, line, header_if_missing="ФИО|номер телефона|трек1|трек2|трек3")
        send_message(chat_id, "Спасибо за участие! Следите за результатами в @test111")
        user_states.pop(chat_id, None)

# === КОМАНДЫ АДМИНА ===
@bot.message_handler(commands=["reset"])
def reset_game(message):
    if str(message.chat.id) != ADMIN_CHAT_ID:
        send_message(message.chat.id, "⛔ Нет доступа")
        return
    github_write_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN, "ФИО|номер телефона|трек1|трек2|трек3\n", "Reset game")
    send_message(message.chat.id, "✅ Данные сброшены")

@bot.message_handler(commands=["results"])
def get_results(message):
    if str(message.chat.id) != ADMIN_CHAT_ID:
        send_message(message.chat.id, "⛔ Нет доступа")
        return
    content = github_read_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN)
    tmp_path = "/tmp/backup_results.csv"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    with open(tmp_path, "rb") as f:
        bot.send_document(message.chat.id, f, caption="Результаты игры")

# === FLASK WEBHOOK ===
@app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        bot.process_new_updates([update])
        return ""
    return "Bad Request", 400

@app.route('/')
def index(): return "Алиса по пятницам бот работает!"
@app.route('/health')
def health(): return "OK"

if __name__ == "__main__":
    print("🚀 Бот запущен")
    bot.remove_webhook()
    time.sleep(1)
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
    bot.set_webhook(url=f"{RENDER_URL}/webhook/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
