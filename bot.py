import os
import csv
import subprocess
from datetime import datetime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup


# ================== НАСТРОЙКИ ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")  # @radiomir_efir
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS").split(",")}

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")            # andrei/alice-fridays-bot
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

CSV_FILE = "results.csv"
current_artist = "Алиса"
played_users = set()
# ===============================================


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


# ================== GIT ==================
def setup_git():
    repo_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    subprocess.run(["git", "remote", "set-url", "origin", repo_url])
    subprocess.run(["git", "checkout", GITHUB_BRANCH])


def git_commit_and_push():
    subprocess.run(["git", "add", CSV_FILE])
    subprocess.run([
        "git", "commit",
        "-m", f"Game entry {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ])
    subprocess.run(["git", "push"])
# =========================================


# ================== CSV ==================
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
# =========================================


# ================== FSM ==================
class GameForm(StatesGroup):
    phone = State()
    name = State()
    track1 = State()
    track2 = State()
    track3 = State()
# =========================================


# ================== UTILS ==================
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False
# ==========================================


# ================== START ==================
@dp.message_handler(commands=["start"])
async def start_game(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "Для участия подпишитесь на канал «Радио МИР|Эфир» 👇\n"
            f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        )
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Отправить номер телефона", request_contact=True))

    await message.answer(
        "Оставьте свой номер телефона — он понадобится, если вы победите 📞",
        reply_markup=kb
    )
    await GameForm.phone.set()
# ==========================================


# ================== PHONE ==================
@dp.message_handler(content_types=types.ContentType.CONTACT, state=GameForm.phone)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await message.answer("Введите ФИО:", reply_markup=types.ReplyKeyboardRemove())
    await GameForm.name.set()
# ==========================================


# ================== NAME ==================
@dp.message_handler(state=GameForm.name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(f"Трек №1 группы «{current_artist}»")
    await GameForm.track1.set()
# ==========================================


# ================== TRACKS ==================
@dp.message_handler(state=GameForm.track1)
async def get_track1(message: types.Message, state: FSMContext):
    await state.update_data(track1=message.text)
    await message.answer("Трек №2")
    await GameForm.track2.set()


@dp.message_handler(state=GameForm.track2)
async def get_track2(message: types.Message, state: FSMContext):
    await state.update_data(track2=message.text)
    await message.answer("Трек №3")
    await GameForm.track3.set()


@dp.message_handler(state=GameForm.track3)
async def get_track3(message: types.Message, state: FSMContext):
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
        "За результатами следите в телеграм-канале Радио МИР|Эфир!"
    )
    await state.finish()
# ==========================================


# ================== ADMIN ==================
@dp.message_handler(commands=["new"])
async def new_artist(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    global current_artist
    current_artist = message.get_args()
    await message.answer(f"Новый исполнитель: {current_artist}")


@dp.message_handler(commands=["results"])
async def send_results(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer_document(types.InputFile(CSV_FILE))


@dp.message_handler(commands=["reset"])
async def reset_game(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    global played_users
    for user_id in played_users:
        try:
            await bot.send_message(
                user_id,
                "Стартует новая игра «Алиса по пятницам» 🎶\nЖмите /start и участвуйте!"
            )
        except:
            pass

    played_users = set()

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="|")
        writer.writerow(["ФИО", "Телефон", "Трек 1", "Трек 2", "Трек 3"])

    git_commit_and_push()
    await message.answer("Игра сброшена, новая пятница запущена 🔥")
# ==========================================


# ================== RUN ==================
if __name__ == "__main__":
    setup_git()
    init_csv()
    executor.start_polling(dp, skip_updates=True)
# ==========================================
