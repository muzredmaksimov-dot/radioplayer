import os
import telebot
import time
import csv
from telebot import types
from flask import Flask, request
import requests
import base64

# ================== НАСТРОЙКИ ==================
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

CSV_FILE = "backup_results.csv"

GITHUB_REPO = "muzredmaksimov-dot/radioplayer"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

CHANNEL_ID = -1002905716039        # test111
CHANNEL_URL = "@newredacktor_bot"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ================== ХРАНИЛИЩЕ ==================
user_states = {}

# ================== GITHUB ==================
def github_read_file(repo, path, token):
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"token {token}"} if token else {}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = r.json().get("content", "")
            return base64.b64decode(content).decode("utf-8")
        return ""
    except Exception as e:
        print("GitHub read error:", e)
        return ""

def github_write_file(repo, path, token, content, message):
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"token {token}"} if token else {}
        r_get = requests.get(url, headers=headers)

        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8")
        }

        if r_get.status_code == 200:
            payload["sha"] = r_get.json()["sha"]

        r_put = requests.put(url, headers=headers, json=payload)
        return r_put.status_code in (200, 201)
    except Exception as e:
        print("GitHub write error:", e)
        return False

def github_append_line(repo, path, token, line, header):
    existing = github_read_file(repo, path, token)
    if not existing:
        text = header + "\n" + line + "\n"
    else:
        if not existing.endswith("\n"):
            existing += "\n"
        text = existing + line + "\n"
    github_write_file(repo, path, token, text, "Update results")

# ================== CSV ==================
def ensure_csv():
    if not os.path.exists(CSV_FILE):
        header = "ФИО|номер телефона|трек1|трек2|трек3\n"
        with open(CSV_FILE, "w", encoding="utf-8") as f:
            f.write(header)
        github_write_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN, header, "Create CSV")

# ================== СТАРТ ==================
@bot.message_handler(commands=["start"])
def start(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🚀 Начать игру", callback_data="start_game"))
    bot.send_message(
        message.chat.id,
        "🎵 Игра «Алиса по пятницам»\n\n"
        "Нужно собрать три трека определённого исполнителя в правильном порядке.\n\n"
        "Нажмите кнопку ниже, чтобы начать.",
        reply_markup=kb
    )

# ================== ПРОВЕРКА ПОДПИСКИ ==================
def check_subscription(chat_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, chat_id).status
        return status in ("member", "administrator", "creator")
    except:
        return False

@bot.callback_query_handler(func=lambda c: c.data == "start_game")
def start_game(c):
    chat_id = c.message.chat.id

    if not check_subscription(chat_id):
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("📢 Подписаться", url=CHANNEL_URL),
            types.InlineKeyboardButton("🔄 Проверить подписку", callback_data="check_subscribe")
        )
        bot.send_message(
            chat_id,
            "Для участия подпишитесь на канал «test111»",
            reply_markup=kb
        )
        return

    user_states[chat_id] = {"step": "phone", "data": {}}
    bot.send_message(chat_id, "📞 Оставьте номер телефона:")

@bot.callback_query_handler(func=lambda c: c.data == "check_subscribe")
def recheck(c):
    chat_id = c.message.chat.id
    if check_subscription(chat_id):
        bot.answer_callback_query(c.id, "Подписка подтверждена ✅")
        user_states[chat_id] = {"step": "phone", "data": {}}
        bot.send_message(chat_id, "📞 Оставьте номер телефона:")
    else:
        bot.answer_callback_query(c.id, "Вы ещё не подписаны ❌", show_alert=True)

# ================== ИГРА ==================
@bot.message_handler(
    func=lambda m: (
        m.chat.id in user_states
        and m.text
        and not m.text.startswith("/")
    )
)
def handle_input(message):
    chat_id = message.chat.id
    state = user_states[chat_id]
    text = message.text.strip()

    if state["step"] == "phone":
        state["data"]["phone"] = text
        state["step"] = "fio"
        bot.send_message(chat_id, "✍️ Укажите ФИО:")

    elif state["step"] == "fio":
        state["data"]["fio"] = text
        state["step"] = "track1"
        bot.send_message(chat_id, "🎵 Введите первый трек:")

    elif state["step"] == "track1":
        state["data"]["track1"] = text
        state["step"] = "track2"
        bot.send_message(chat_id, "🎵 Введите второй трек:")

    elif state["step"] == "track2":
        state["data"]["track2"] = text
        state["step"] = "track3"
        bot.send_message(chat_id, "🎵 Введите третий трек:")

    elif state["step"] == "track3":
        state["data"]["track3"] = text

        ensure_csv()
        line = (
            f"{state['data']['fio']}|"
            f"{state['data']['phone']}|"
            f"{state['data']['track1']}|"
            f"{state['data']['track2']}|"
            f"{state['data']['track3']}"
        )

        github_append_line(
            GITHUB_REPO,
            CSV_FILE,
            GITHUB_TOKEN,
            line,
            "ФИО|номер телефона|трек1|трек2|трек3"
        )

        bot.send_message(
            chat_id,
            "✅ Спасибо за участие!\n"
            "За результатами следите в Telegram-канале «Radio MIR | Эфир»"
        )

        user_states.pop(chat_id)

# ================== АДМИН ==================
@bot.message_handler(commands=["reset"])
def reset_game(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        bot.send_message(message.chat.id, "⛔ Нет доступа")
        return

    header = "ФИО|номер телефона|трек1|трек2|трек3\n"
    with open(CSV_FILE, "w", encoding="utf-8") as f:
        f.write(header)

    github_write_file(GITHUB_REPO, CSV_FILE, GITHUB_TOKEN, header, "Reset results")
    bot.send_message(message.chat.id, "✅ Игра сброшена")

@bot.message_handler(commands=["results"])
def send_results(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        bot.send_message(message.chat.id, "⛔ Нет доступа")
        return

    if GITHUB_TOKEN:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CSV_FILE}"
            headers = {"Authorization": f"token {GITHUB_TOKEN}"}
            r = requests.get(url, headers=headers)

            if r.status_code == 200:
                content = base64.b64decode(r.json()["content"])
                path = "/tmp/results.csv"
                with open(path, "wb") as f:
                    f.write(content)
                with open(path, "rb") as f:
                    bot.send_document(message.chat.id, f)
                return
        except Exception as e:
            print("Results error:", e)

    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "rb") as f:
            bot.send_document(message.chat.id, f)
    else:
        bot.send_message(message.chat.id, "Файл ещё не создан")

# ================== WEBHOOK ==================
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        bot.process_new_updates([update])
        return ""
    return "Bad Request", 400

@app.route("/")
def index():
    return "Алиса по пятницам — бот работает"

@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    print("🚀 Bot started")
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{os.environ.get('RENDER_EXTERNAL_URL')}/webhook/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
