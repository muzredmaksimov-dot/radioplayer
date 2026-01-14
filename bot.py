import os
import telebot
import time
import csv
from telebot import types
from flask import Flask, request
import requests
import base64
import threading

# ================= НАСТРОЙКИ =================
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

CSV_FILE = "backup_results.csv"
GITHUB_REPO = "muzredmaksimov-dot/radioplayer"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

CHANNEL_ID = -1002905716039  # test111
CHANNEL_URL = "https://t.me/test111"

# =============================================
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

user_states = {}

# ================= GITHUB ====================
def github_read_file(repo, path, token):
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}"} if token else {}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        content_b64 = r.json().get("content", "")
        return base64.b64decode(content_b64).decode("utf-8")
    return ""

def github_write_file(repo, path, token, content, commit_msg):
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}"} if token else {}

    r_get = requests.get(url, headers=headers)
    payload = {
        "message": commit_msg,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8")
    }

    if r_get.status_code == 200:
        payload["sha"] = r_get.json().get("sha")

    r_put = requests.put(url, headers=headers, json=payload)
    return r_put.status_code in (200, 201)

def ensure_csv():
    content = github_read_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN)
    if not content:
        header = "ФИО|номер телефона|трек1|трек2|трек3\n"
        github_write_file(
            GITHUB_REPO,
            CSV_FILE,
            GITHUB_TOKEN,
            header,
            "Создание CSV"
        )

def github_append_line(line):
    content = github_read_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN)
    if not content:
        content = "ФИО|номер телефона|трек1|трек2|трек3\n"
    if not content.endswith("\n"):
        content += "\n"
    content += line + "\n"

    github_write_file(
        GITHUB_REPO,
        CSV_FILE,
        GITHUB_TOKEN,
        content,
        "Добавлен участник"
    )

# ================= СТАРТ =====================
@bot.message_handler(commands=["start"])
def start(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🚀 Начать игру", callback_data="start_game"))

    bot.send_message(
        message.chat.id,
        "Привет! 🎵\n\n"
        "Чтобы участвовать в игре «Алиса по пятницам», "
        "нужно собрать три трека в правильном порядке.\n\n"
        "Нажмите кнопку ниже 👇",
        reply_markup=kb
    )

# ============ ПРОВЕРКА ПОДПИСКИ ===============
def check_subscription(chat_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, chat_id).status
        return status in ["member", "administrator", "creator"]
    except:
        return False

@bot.callback_query_handler(func=lambda c: c.data in ["start_game", "check_sub"])
def start_game(c):
    chat_id = c.message.chat.id

    if not check_subscription(chat_id):
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("📢 Подписаться", url=CHANNEL_URL),
            types.InlineKeyboardButton("🔄 Проверить подписку", callback_data="check_sub")
        )
        bot.send_message(
            chat_id,
            "Для участия подпишитесь на канал и нажмите «Проверить подписку»",
            reply_markup=kb
        )
        return

    bot.send_message(chat_id, "📱 Оставьте номер телефона:")
    user_states[chat_id] = {"step": "phone", "data": {}}

# ============== ВВОД ДАННЫХ ===================
@bot.message_handler(func=lambda m: True)
def handle_input(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    if not state:
        return

    step = state["step"]
    text = message.text.strip()

    if step == "phone":
        state["data"]["phone"] = text
        state["step"] = "fio"
        bot.send_message(chat_id, "👤 Укажите ФИО:")

    elif step == "fio":
        state["data"]["fio"] = text
        state["step"] = "track1"
        bot.send_message(chat_id, "🎵 Первый трек:")

    elif step == "track1":
        state["data"]["track1"] = text
        state["step"] = "track2"
        bot.send_message(chat_id, "🎵 Второй трек:")

    elif step == "track2":
        state["data"]["track2"] = text
        state["step"] = "track3"
        bot.send_message(chat_id, "🎵 Третий трек:")

    elif step == "track3":
        state["data"]["track3"] = text

        ensure_csv()
        line = (
            f"{state['data']['fio']}|"
            f"{state['data']['phone']}|"
            f"{state['data']['track1']}|"
            f"{state['data']['track2']}|"
            f"{state['data']['track3']}"
        )

        github_append_line(line)

        bot.send_message(
            chat_id,
            "✅ Спасибо за участие!\n"
            "Следите за результатами в канале 👇\n"
            "@test111"
        )

        user_states.pop(chat_id)

# ================= АДМИН ======================
@bot.message_handler(commands=["reset"])
def reset_game(message):
    if str(message.chat.id) != ADMIN_CHAT_ID:
        bot.send_message(message.chat.id, "⛔ Нет доступа")
        return

    header = "ФИО|номер телефона|трек1|трек2|трек3\n"
    github_write_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN, header, "Сброс игры")
    bot.send_message(message.chat.id, "♻️ Игра сброшена")

@bot.message_handler(commands=["results"])
def get_results(message):
    if str(message.chat.id) != ADMIN_CHAT_ID:
        bot.send_message(message.chat.id, "⛔ Нет доступа")
        return

    content = github_read_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN)

    if not content:
        bot.send_message(message.chat.id, "⚠️ Файл результатов ещё не создан")
        return

    lines = content.strip().split("\n")
    if len(lines) <= 1:
        bot.send_message(message.chat.id, "⚠️ Участников пока нет")
        return

    tmp = "/tmp/results.csv"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)

    with open(tmp, "rb") as f:
        bot.send_document(
            message.chat.id,
            f,
            caption=f"📊 Результаты игры\nУчастников: {len(lines) - 1}"
        )

# ================= WEBHOOK ====================
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(
            request.get_data().decode("utf-8")
        )
        bot.process_new_updates([update])
        return "OK"
    return "Bad Request", 400

@app.route("/")
def index():
    return "Bot works"

# ================== RUN =======================
if __name__ == "__main__":
    ensure_csv()
    print("🚀 Бот запущен")

    bot.remove_webhook()
    time.sleep(1)

    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
    bot.set_webhook(f"{RENDER_URL}/webhook/{TOKEN}")

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
