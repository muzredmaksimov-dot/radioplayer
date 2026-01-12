import os
import csv
import subprocess
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputFile
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage


# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")   # @radiomir_efir
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS").split(",")}

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")             # user/repo
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

CSV_FILE = "results.csv"
current_artist = "Алиса"
played_users = set()
# =============================================


bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================= GIT =================
def setup_git():
    repo_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=False)
    subprocess.run(["git", "checkout", GITHUB_BRANCH], check=False)


def git_commit_and_push():
    subprocess.run(["git", "add", CSV_FILE], check=False)
    subprocess.run(
        ["git", "commit", "-m", f"Game entry {datetime.now()}"],
        check=False
    )
    subprocess.run(["git", "push"], check=False)
# =======================================


# ================= CSV =================
def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter="|")
            writer.writerow(["ФИО", "Телефон", "Трек 1", "Трек 2", "Трек 3"])
        git_commit_and_push()


def save_result(row):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="|")
        writer.writerow(row)
    git_commit_and_push()
# =======================================


# ================= FSM =================
class GameForm(StatesGroup):
    phone = State()
    name = State()
    track1 = State()
    track2 = State()
    track3 = State()
# =======================================


# ================= UTILS =================
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False
# ========================================


# ================= START =================
@dp.message(Command("start"))
async def start_game(message: Message, state: FSMContext):
    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "Для участия подпишитесь на канал «Радио МИР|Эфир» 👇\n"
            f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        )
        return

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отправить номер", request_contact=True)]],
        resize_keyboard=True
    )

    await message.answer(
        "Оставьте номер телефона — он понадобится, если вы победите 📞",
        reply_markup=kb
    )
    await state.set_state(GameForm.phone)
# ========================================


# ================= PHONE =================
@dp.message(GameForm.phone, F.contact)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await message.answer("Введите ФИО:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(GameForm.name)
# ========================================


# ================= NAME =================
@dp.message(GameForm.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(f"Трек №1 группы «{current_artist}»")
    await state.set_state(GameForm.track1)
# ========================================


# ================= TRACKS =================
@dp.message(GameForm.track1)
async def track1(message: Message, state: FSMContext):
    await state.update_data(track1=message.text)
    await message.answer("Трек №2")
    await state.set_state(GameForm.track2)


@dp.message(GameForm.track2)
async def track2(message: Message, state: FSMContext):
    await state.update_data(track2=message.text)
    await message.answer("Трек №3")
    await state.set_state(GameForm.track3)


@dp.message(GameForm.track3)
async def track3(message: Message, state: FSMContext):
    data = await state.get_data()

    save_result([
        data["name"],
        data["phone"],
        data["track1"],
        data["track2"],
        message.text
    ])

    played_users.add(message.from_user.id)

    await message.answer(
        "Спасибо за участие! 🎸\n"
        "Следите за результатами в телеграм-канале Радио МИР|Эфир!"
    )
    await state.clear()
# ========================================


# ================= ADMIN =================
@dp.message(Command("new"))
async def new_artist(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    global current_artist
    current_artist = message.text.replace("/new", "").strip()
    await message.answer(f"Новый исполнитель: {current_artist}")


@dp.message(Command("results"))
async def results(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer_document(InputFile(CSV_FILE))


@dp.message(Command("reset"))
async def reset(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    global played_users
    for user_id in played_users:
        try:
            await bot.send_message(
                user_id,
                "Новая игра «Алиса по пятницам» 🎶\nЖмите /start!"
            )
        except:
            pass

    played_users = set()

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="|")
        writer.writerow(["ФИО", "Телефон", "Трек 1", "Трек 2", "Трек 3"])

    git_commit_and_push()
    await message.answer("Игра сброшена 🔥")
# ========================================


# ================= RUN =================
async def main():
    setup_git()
    init_csv()
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
# ========================================
