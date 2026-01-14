import os
import telebot
import time
import csv
from telebot import types
from flask import Flask, request
import requests
import base64
import threading
from datetime import datetime

# === НАСТРОЙКИ ===
TOKEN = os.environ.get("BOT_TOKEN")  # токен бота
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")  # id админа
CSV_FILE = "backup_results.csv"
SUBSCRIBERS_FILE = "subscribers.txt"
ARTIST_FILE = "current_artist.txt"
GITHUB_REPO = "muzredmaksimov-dot/radioplayer"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
CHANNEL_ID = -1002905716039        # test111
CHANNEL_URL = "https://t.me/testposring"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# === ХРАНИЛИЩЕ ===
user_last_message = {}
user_states = {}
buffer_lock = threading.Lock()
result_buffer = []
current_artist = "АРТИСТ"

# === ЗАГРУЗКА текущего артиста с GitHub ===
artist_text = ""
try:
    artist_text = github_read_file(GITHUB_REPO, ARTIST_FILE, GITHUB_TOKEN)
except:
    pass
if artist_text:
    current_artist = artist_text.strip()

# === УТИЛИТЫ GITHUB ===
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

# === CSV CHECK ===
def ensure_csv():
    if not os.path.exists(CSV_FILE):
        headers = ["ФИО", "номер телефона", "трек1", "трек2", "трек3"]
        with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        github_write_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN, ",".join(headers) + "\n", "Создание нового CSV")

# === СООБЩЕНИЯ ===
def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    try:
        msg = bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
        user_last_message.setdefault(chat_id, []).append(msg.message_id)
        return msg
    except Exception as e:
        print("Ошибка отправки:", e)

def cleanup_chat(chat_id, keep_first_rule=False):
    msgs = user_last_message.get(chat_id, [])
    keep = msgs[0:1] if keep_first_rule and msgs else []
    for msg_id in msgs:
        if msg_id not in keep:
            try:
                bot.delete_message(chat_id, msg_id)
            except: 
                pass
    user_last_message[chat_id] = keep

# === КОМАНДА /new ===
@bot.message_handler(commands=["new"])
def set_new_artist(message):
    global current_artist
    if str(message.chat.id) != ADMIN_CHAT_ID:
        send_message(message.chat.id, "⛔ Нет доступа")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        send_message(message.chat.id, "❌ Использование: /new <имя артиста>")
        return
    current_artist = args[1].strip()
    github_write_file(GITHUB_REPO, ARTIST_FILE, GITHUB_TOKEN, current_artist, f"Update current artist: {current_artist}")
    send_message(message.chat.id, f"✅ Текущий артист для пятницы обновлен: «{current_artist}»")

# === КОМАНДА /reset ===
@bot.message_handler(commands=["reset"])
def reset_game(message):
    if str(message.chat.id) != ADMIN_CHAT_ID:
        send_message(message.chat.id, "⛔ Нет доступа")
        return
    # Сброс CSV
    headers = ["ФИО", "номер телефона", "трек1", "трек2", "трек3"]
    open(CSV_FILE, "w", encoding="utf-8", newline="").write(",".join(headers) + "\n")
    github_write_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN, ",".join(headers) + "\n", "Reset game")
    # Рассылка
    subscribers_text = github_read_file(GITHUB_REPO, SUBSCRIBERS_FILE, GITHUB_TOKEN)
    subscribers = [s.strip() for s in subscribers_text.split("\n") if s.strip()]
    sent = 0
    for s in subscribers:
        try:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🚀 Играть", callback_data="start_game"))
            bot.send_message(int(s), f"🎵 В эту пятницу собираем треклист «{current_artist}»!\n\nЛови песни с 7 до 20 и присылай их в правильном порядке.", reply_markup=kb)
            sent += 1
            time.sleep(0.05)
        except:
            pass
    bot.send_message(ADMIN_CHAT_ID, f"✅ Рассылка выполнена ({sent} пользователей).")

# === СТАРТ ===
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    cleanup_chat(chat_id)
    today = datetime.today().weekday()  # 0 = Пн ... 4 = Пт
    kb = types.InlineKeyboardMarkup()
    if today != 4:  # не пятница
        kb.add(types.InlineKeyboardButton("Напомнить в пятницу", callback_data="remind_friday"))
        send_message(chat_id,
                     "Это игра «АЛИСА ПО пятницам».\nКаждую пятницу лови в эфире песни одного исполнителя с 7 до 20 и присылай их в правильном порядке.\nВ понедельник подведем итоги, среди всех кто ответил правильно случайным образом разыграем умную колонку.",
                     reply_markup=kb)
    else:
        kb.add(types.InlineKeyboardButton("🚀 Играть", callback_data="start_game"))
        send_message(chat_id,
                     f"Привет! 🎵 Сегодня пятница! Играем треклист «{current_artist}».",
                     reply_markup=kb)

# === CALLBACKS ===
@bot.callback_query_handler(func=lambda c: c.data == "remind_friday")
def remind_friday(c):
    send_message(c.message.chat.id, "✅ Напоминание установлено! В пятницу получите сообщение о начале игры.")

# === ПРОВЕРКА ПОДПИСКИ И ИГРА ===
@bot.callback_query_handler(func=lambda c: c.data == "start_game")
def start_game(c):
    chat_id = c.message.chat.id
    try:
        bot.delete_message(chat_id, c.message.message_id)
    except: pass
    # Проверка подписки
    CHANNEL_ID = -1002905716039  # test111
    try:
        member_status = bot.get_chat_member(CHANNEL_ID, chat_id).status
        if member_status not in ["member", "administrator", "creator"]:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Подписаться на канал TEST111", url="https://t.me/test111"))
            send_message(chat_id, "Для участия подпишитесь на канал «test111»", reply_markup=kb)
            return
    except:
        send_message(chat_id, "Для участия подпишитесь на канал «test111»")
        return
    # Начало игры
    msg = send_message(chat_id, "Оставьте свой номер телефона:")
    user_states[chat_id] = {"step": "phone", "data": {}}

# === ОБРАБОТКА ВВОДА ===
@bot.message_handler(func=lambda m: True)
def handle_input(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    if not state: return
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
        ensure_csv()
        line = f"{state['data']['fio']}|{state['data']['phone']}|{state['data']['track1']}|{state['data']['track2']}|{state['data']['track3']}"
        github_append_line(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN, line, header_if_missing="ФИО|номер телефона|трек1|трек2|трек3")
        send_message(chat_id, f"Спасибо за участие! Следите за результатами в @test111")
        user_states.pop(chat_id, None)
        cleanup_chat(chat_id, keep_first_rule=True)

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

# === ЗАПУСК ===
if __name__ == "__main__":
    print("🚀 Бот запущен")
    bot.remove_webhook()
    time.sleep(1)
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
    bot.set_webhook(url=f"{RENDER_URL}/webhook/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
