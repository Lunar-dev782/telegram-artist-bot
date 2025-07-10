import os
import re
import time
import json
import random
import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from typing import List  # ✅ Додано!

from supabase import create_client, Client

from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command, StateFilter, CommandStart
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramNotFound,
    TelegramRetryAfter,
)
from aiogram.types import (
    Message,
    ContentType,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputMediaPhoto,  # ✅ Додано!
    error_event,
)
from aiogram.types.error_event import ErrorEvent

# 🔐 Токен бота
TOKEN = "7645134499:AAFRfwsn7dr5W2m81gCJPwX944PRqk-sjEc"
ADMIN_CHAT_ID = -1002802098163  # ✅ Не забудь вказати правильний ID

# 🤖 Ініціалізація бота
bobot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
router = Router()  

# 🔌 Дані для Supabase
SUPABASE_URL = "https://clbcovdeoahrmxaoijyt.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNsYmNvdmRlb2Focm14YW9panl0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIxNTc4NTAsImV4cCI6MjA2NzczMzg1MH0.dxwJhTZ9ei4dOnxmCvGztb8pfUqTlprfd0-woF6Y-lY"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# 📋 Стан машини
class Form(StatesGroup):
    category = State()
    description = State()
    socials = State()
    images = State()

# 🟢 /start
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await message.answer(
        "🎨 Вітаємо у спільноті!\nОбери категорію:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🐾 Адопти")],
                [KeyboardButton(text="🎨 Коміші / Прайси")],
                [KeyboardButton(text="🧵 Реквести")],
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(Form.category)

# 🟢 Категорія
@router.message(Form.category)
async def get_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text)
    await message.answer("📝 Опиши пост для публікації (без посилань):")
    await state.set_state(Form.description)

# 🟢 Опис
@router.message(Form.description)
async def get_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("🌐 Вкажи соцмережі (формат):\nInstagram: @нік\nTelegram: @нікнейм")
    await state.set_state(Form.socials)

# 🟢 Соцмережі
@router.message(Form.socials)
async def get_socials(message: Message, state: FSMContext):
    await state.update_data(socials=message.text)
    await message.answer("📸 Надішли до 5 зображень для публікації")
    await state.set_state(Form.images)

# 🟢 Фото
@router.message(Form.images, F.photo)
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

# ✅ /done
@router.message(Form.images, F.text == "/done")
async def done_images(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if not photos:
        await message.answer("⚠️ Спочатку надішли хоча б 1 зображення.")
        return
    await message.answer("✅ Дякую! Надіслано на перевірку.")
    await finish_submission(message.from_user, state, photos)

# ✅ Фінальна обробка
async def finish_submission(user: types.User, state: FSMContext, photos: List[str]):
    data = await state.get_data()
    await state.clear()

    text = (
        f"📥 <b>Нова заявка від</b> @{user.username or user.first_name}\n"
        f"<b>Категорія:</b> {data['category']}\n"
        f"<b>Опис:</b> {data['description']}\n"
        f"<b>Соцмережі:</b>\n{data['socials']}"
    )

    media = [InputMediaPhoto(media=photos[0], caption=text)]
    for p in photos[1:]:
        media.append(InputMediaPhoto(media=p))

    await bot.send_media_group(chat_id=ADMIN_CHAT_ID, media=media)

    supabase.table("submissions").insert({
        "user_id": user.id,
        "username": user.username,
        "category": data["category"],
        "description": data["description"],
        "socials": data["socials"],
        "images": photos,
    }).execute()

# Запуск бота
async def main():
    await router.start_polling(bot)  # Запускаємо polling з router

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
