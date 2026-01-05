import csv
import os
from aiogram import Bot, Dispatcher, executor, types
from config import BOT_TOKEN, CHANNEL_USERNAME, ADMIN_ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)


# ================== ВСПОМОГАТЕЛЬНОЕ ==================

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def is_subscriber(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False


def get_next_track_id() -> int:
    if not os.path.exists("tracks.csv"):
        return 1
    with open("tracks.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        return len(rows) + 1


def save_track(track_id: int, artist: str, title: str):
    file_exists = os.path.exists("tracks.csv")
    with open("tracks.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["track_id", "artist", "title"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "track_id": track_id,
            "artist": artist,
            "title": title
        })


def get_votes(track_id: int):
    likes = neutral = dislikes = 0
    if not os.path.exists("votes.csv"):
        return likes, neutral, dislikes

    with open("votes.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["track_id"] == str(track_id):
                if row["vote"] == "like":
                    likes += 1
                elif row["vote"] == "neutral":
                    neutral += 1
                elif row["vote"] == "dislike":
                    dislikes += 1
    return likes, neutral, dislikes


def vote_keyboard(track_id: int):
    likes, neutral, dislikes = get_votes(track_id)

    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton(f"❤️ {likes}", callback_data=f"vote:{track_id}:like"),
        types.InlineKeyboardButton(f"😐 {neutral}", callback_data=f"vote:{track_id}:neutral"),
        types.InlineKeyboardButton(f"👎 {dislikes}", callback_data=f"vote:{track_id}:dislike"),
    )
    return kb


# ================== ГОЛОСОВАНИЕ ==================

@dp.callback_query_handler(lambda c: c.data.startswith("vote:"))
async def vote_handler(callback: types.CallbackQuery):
    _, track_id, vote = callback.data.split(":")
    user_id = callback.from_user.id

    if not await is_subscriber(user_id):
        await callback.answer(
            "Голосовать могут только подписчики канала 📻",
            show_alert=True
        )
        return

    rows = []
    updated = False

    if os.path.exists("votes.csv"):
        with open("votes.csv", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    for row in rows:
        if row["track_id"] == track_id and row["user_id"] == str(user_id):
            row["vote"] = vote
            updated = True

    if not updated:
        rows.append({
            "track_id": track_id,
            "user_id": str(user_id),
            "vote": vote
        })

    with open("votes.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["track_id", "user_id", "vote"])
        writer.writeheader()
        writer.writerows(rows)

    await callback.message.edit_reply_markup(
        reply_markup=vote_keyboard(int(track_id))
    )

    await callback.answer("Твой голос учтён 👍")


# ================== ПУБЛИКАЦИЯ (АДМИН) ==================

@dp.message_handler(commands=["publish"])
async def publish_track(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer("Пришли MP3 файл")
    audio = await dp.wait_for(types.Message, content_types=types.ContentType.AUDIO)

    await message.answer("Исполнитель?")
    artist_msg = await dp.wait_for(types.Message)
    artist = artist_msg.text.strip()

    await message.answer("Название трека?")
    title_msg = await dp.wait_for(types.Message)
    title = title_msg.text.strip()

    track_id = get_next_track_id()
    save_track(track_id, artist, title)

    caption = (
        "🎧 <b>Новинка на радио</b>\n\n"
        f"🎤 <b>Исполнитель:</b> {artist}\n"
        f"🎵 <b>Трек:</b> {title}\n\n"
        "▶️ Послушай трек и оцени — твой голос влияет на эфир 👇"
    )

    await bot.send_audio(
        chat_id=CHANNEL_USERNAME,
        audio=audio.audio.file_id,
        caption=caption,
        parse_mode="HTML",
        reply_markup=vote_keyboard(track_id)
    )

    await message.answer("✅ Новинка опубликована")


# ================== ЗАПУСК ==================

if if name == "__main__":
    executor.start_polling(dp, skip_updates=True)
