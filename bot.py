import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8560880695:AAFUHhlq3kW_xP8gCd_Biv6q79S0VCoW8e4"
FILE = "tracks.json"

def load():
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Использование:\n/add Исполнитель | Название | ссылка_на_mp3"
        )
        return

    artist, title, audio = " ".join(args).split("|")
    tracks = load()

    track = {
        "id": len(tracks) + 1,
        "artist": artist.strip(),
        "title": title.strip(),
        "audio": audio.strip()
    }

    tracks.append(track)
    save(tracks)

    await update.message.reply_text(f"Добавлено:\n{artist} — {title}")

async def list_tracks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tracks = load()
    text = "\n".join([f"{t['id']}. {t['artist']} — {t['title']}" for t in tracks])
    await update.message.reply_text(text or "Пока пусто")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("list", list_tracks))

app.run_polling()
