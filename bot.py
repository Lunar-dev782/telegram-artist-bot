import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import Message, InputMediaPhoto, FSInputFile
from supabase import create_client
from typing import List

# 🔐 Константи
BOT_TOKEN = "7645134499:AAFRfwsn7dr5W2m81gCJPwX944PRqk-sjEc"
ADMIN_CHAT = -1002802098163
SUPA_URL = "https://clbcovdeoahrmxaoijyt.supabase.co"
SUPA_KEY = "тут твій service_role ключ"

# ✅ Створення бота правильно для aiogram 3.7+
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# 🔗 Підключення до Supabase
supabase = create_client(SUPA_URL, SUPA_KEY)

# 📋 FSM стани
class Form(StatesGroup):
    category = State()
    description = State()
    socials = State()
    images = State()

# 🟢 /start хендлер
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await message.answer(
        "🎨 Вітаємо у спільноті!\nОбери категорію:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="🐾 Адопти")],
                [types.KeyboardButton(text="🎨 Коміші / Прайси")],
                [types.KeyboardButton(text="🧵 Реквести")],
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(Form.category)

# 🟢 Категорія
@dp.message(Form.category)
async def get_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text)
    await message.answer("📝 Опиши пост для публікації (без посилань):")
    await state.set_state(Form.description)

# 🟢 Опис
@dp.message(Form.description)
async def get_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("🌐 Вкажи соцмережі (формат):\nInstagram: @нік\nTelegram: @нікнейм")
    await state.set_state(Form.socials)

# 🟢 Соцмережі
@dp.message(Form.socials)
async def get_socials(message: Message, state: FSMContext):
    await state.update_data(socials=message.text)
    await message.answer("📸 Надішли до 5 зображень для публікації")
    await state.set_state(Form.images)

# 🟢 Зображення
@dp.message(Form.images, F.photo)
async def get_images(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)

    if len(photos) >= 5:
        await message.answer("✅ Дякую! Надіслано на перевірку.")
        await finish_submission(message.from_user, state, photos)
    else:
        await state.update_data(photos=photos)
        await message.answer(f"Зображення прийнято ({len(photos)}/5). Надішли ще або натисни /done.")

# ✅ /done — якщо менше ніж 5 зображень
@dp.message(Form.images, F.text == "/done")
async def done_images(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if not photos:
        await message.answer("⚠️ Спочатку надішли хоча б 1 зображення.")
        return
    await message.answer("✅ Дякую! Надіслано на перевірку.")
    await finish_submission(message.from_user, state, photos)

# ✅ Фінальна обробка
async def finish_submission(user, state: FSMContext, photos: List[str]):
    data = await state.get_data()
    await state.clear()

    # 📥 Формування заявки
    text = (
        f"📥 <b>Нова заявка від</b> @{user.username or user.first_name}\n"
        f"<b>Категорія:</b> {data['category']}\n"
        f"<b>Опис:</b> {data['description']}\n"
        f"<b>Соцмережі:</b>\n{data['socials']}"
    )

    # ⬆️ Відправка в адмін-чат
    media = [InputMediaPhoto(media=photos[0], caption=text)]
    for p in photos[1:]:
        media.append(InputMediaPhoto(media=p))

    await bot.send_media_group(chat_id=ADMIN_CHAT, media=media)

    # 💾 Запис у Supabase
    supabase.table("submissions").insert({
        "user_id": user.id,
        "username": user.username,
        "category": data["category"],
        "description": data["description"],
        "socials": data["socials"],
        "images": photos,
    }).execute()

# 🟢 Старт бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
