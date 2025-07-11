import os
import re
import time
import json
import random
import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from typing import List  

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
    InputMediaPhoto,  
    error_event,
    ReplyKeyboardRemove, 
)

from aiogram.types.error_event import ErrorEvent

# 🔐 Токен бота
TOKEN = "7645134499:AAFRfwsn7dr5W2m81gCJPwX944PRqk-sjEc"
ADMIN_CHAT_ID = -1002802098163  

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

# 📋 Категорії та їх описи
CATEGORIES = {
    "🐾 Адопти": "Пости про персонажів, яких ви пропонуєте для адопції.",
    "🧵 Реквести": "Запити на створення персонажів або іншого контенту.",
    "🎨 Коміші / Прайси": "Оголошення про платні послуги (комішени, прайси).",
    "🎁 Лотереї / Конкурси": "Оголошення про лотереї або конкурси.",
    "📣 Самопіар": "Промоція вашого контенту чи профілю.",
    "🤝 DTIYS": "Челенджі 'Draw This In Your Style'.",
    "📅 Івенти": "Анонси подій, стрімів чи інших заходів."
}

# 🟢 /start
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await message.answer(
        "🎨 Привіт! Це бот для публікацій у спільноті [Назва].\n"
        "Обери розділ, у якому хочеш зробити пост, та дотримуйся простих умов, щоб бути опублікованим 💫",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=cat)] for cat in CATEGORIES.keys()
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(Form.category)

# 🟢 /help
@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "ℹ️ Це бот для подачі заявок на публікацію у спільноті [Назва].\n\n"
        "Як це працює:\n"
        "1️⃣ Обери категорію через команду /start.\n"
        "2️⃣ Виконай умови (репост, підписка, заповнення анкети).\n"
        "3️⃣ Надішли дані одним повідомленням (нік, опис, соцмережі, зображення).\n"
        "4️⃣ Чекай на перевірку адміном.\n\n"
        "📜 Правила: /rules\n"
        "📩 Якщо є питання, пиши адмінам: @AdminUsername"
    )
    await message.answer(help_text)

# 🟢 /rules
@router.message(Command("rules"))
async def cmd_rules(message: Message):
    rules_text = (
        "📜 Правила публікацій:\n"
        "1. Дотримуйтесь умов для обраної категорії.\n"
        "2. Надсилайте лише оригінальний контент.\n"
        "3. Не більше 5 зображень на пост.\n"
        "4. Публікації дозволені не частіше, ніж раз на 7 днів.\n"
        "5. Заборонено NSFW, образливий або незаконний контент.\n"
        "6. Адміни мають право відхилити заявку з поясненням.\n\n"
        "📩 З питаннями: @AdminUsername"
    )
    await message.answer(rules_text)

# 🟢 Обробка вибору категорії
@router.message(lambda message: message.text in CATEGORIES)
async def handle_category_selection(message: Message, state: FSMContext):
    category = message.text
    # Перевірка обмеження частоти публікацій
    user_id = message.from_user.id
    last_submission = supabase.table("submissions").select("submitted_at").eq("user_id", user_id).order("submitted_at", desc=True).limit(1).execute()
    
    if last_submission.data:
        last_time = datetime.fromisoformat(last_submission.data[0]["submitted_at"].replace("Z", "+00:00"))
        if datetime.utcnow() - last_time < timedelta(days=7):
            await message.answer("⚠️ Ви можете подавати заявку не частіше, ніж раз на 7 днів. Спробуйте пізніше!")
            return

    await state.update_data(category=category)
    await message.answer(
        f"✅ Щоб опублікувати в розділі {category}, виконай наступні кроки:\n\n"
        f"🔄 Зроби репост [нашої спільноти](https://t.me/community_link)\n"
        f"✅ Підпишись на [наш канал](https://t.me/channel_link)\n"
        f"📝 Заповни анкету\n\n"
        f"📌 Приклад: {CATEGORIES[category]}\n\n"
        f"Коли все буде готово — натисни 'Я все зробив(ла)'",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Я все зробив(ла)")]],
            resize_keyboard=True
        ),
        parse_mode="Markdown"
    )

# 🟢 Підтвердження виконання умов
@router.message(lambda message: message.text == "Я все зробив(ла)")
async def confirm_ready(message: Message, state: FSMContext):
    await message.answer(
        "📋 Надішли, будь ласка, цю інформацію *одним повідом潇ф повідомленням*:\n\n"
        "1. Ім’я / нікнейм\n"
        "2. Короткий опис\n"
        "3. Лінки на соцмережі (Instagram: @нік, Telegram: @нікнейм)\n"
        "4. Додай до 5 зображень\n\n"
        "📌 Приклад:\n"
        "Нік: @Artist\n"
        "Опис: Продаю персонажа, унікальний дизайн!\n"
        "Соцмережі: Instagram: @artist, Telegram: @artist\n",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(Form.description)

# 🟢 Опис
@router.message(Form.description)
async def get_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer(
        "🌐 Вкажи соцмережі (формат):\n"
        "Instagram: @нік\n"
        "Telegram: @нікнейм"
    )
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
async def finish_submission(user: types.User, state: FSMContext, photos: list):
    data = await state.get_data()
    await state.clear()

    text = (
        f"📥 <b>Нова заявка від</b> @{user.username or user.first_name}\n"
        f"<b>Категорія:</b> {data['category']}\n"
        f"<b>Опис:</b> {data['description']}\n"
        f"<b>Соцмережі:</b>\n{data['socials']}"
    )

    media = [InputMediaPhoto(media=photos[0], caption=text, parse_mode="HTML")]
    for p in photos[1:]:
        media.append(InputMediaPhoto(media=p))

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Опублікувати", callback_data=f"approve:{user.id}")
    keyboard.button(text="❌ Відмовити", callback_data=f"reject:{user.id}")
    markup = keyboard.as_markup()

    await bot.send_media_group(chat_id=ADMIN_CHAT_ID, media=media)
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text="🔎 Оберіть дію:", reply_markup=markup)

    supabase.table("submissions").insert({
        "user_id": user.id,
        "username": user.username or user.first_name,
        "category": data["category"],
        "description": data["description"],
        "socials": data["socials"],
        "images": photos,
        "status": "pending",
        "submitted_at": datetime.utcnow().isoformat()
    }).execute()

# 🟢 Схвалення посту
@router.callback_query(lambda c: c.data.startswith("approve:"))
async def approve_post(callback: types.CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    supabase.table("submissions").update({
        "status": "approved",
        "moderated_at": datetime.utcnow().isoformat(),
        "moderator_id": callback.from_user.id
    }).eq("user_id", user_id).execute()

    await callback.message.edit_text("✅ Публікацію схвалено!")
    await bot.send_message(user_id, "🎉 Вашу публікацію схвалено!")

# 🟢 Відхилення посту
@router.callback_query(lambda c: c.data.startswith("reject:"))
async def reject_post(callback: types.CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    # Можна додати FSM для запиту причини відмови
    supabase.table("submissions"). footnote: update({
        "status": "rejected",
        "moderated_at": datetime.utcnow().isoformat(),
        "moderator_id": callback.from_user.id,
        "rejection_reason": "Невідповідність вимогам"
    }).eq("user_id", user_id).execute()

    await callback.message.edit_text("❌ Публікацію відхилено.")
    await bot.send_message(user_id, "😔 Вашу публікацію відхилено. Причина: Невідповідність вимогам.")# Запуск бота
async def main():
    await router.start_polling(bot)  # Запускаємо polling з router

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
