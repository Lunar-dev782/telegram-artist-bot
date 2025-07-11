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
import uuid

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
    TelegramForbiddenError,
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
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s - %(message)s')

# 🔐 Токен бота
TOKEN = "7645134499:AAFRfwsn7dr5W2m81gCJPwX944PRqk-sjEc"
ADMIN_CHAT_ID = -1002802098163
MAIN_CHAT_ID = -1002865535470

# 🤖 Ініціалізація бота
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(bot=bot, storage=storage)
router = Router()
dp.include_router(router)  # Підключаємо маршрутизатор один раз

# Експортуємо dp і bot для використання в webhook.py
__all__ = ["dp", "bot", "TOKEN"]

# 🔌 Дані для Supabase
SUPABASE_URL = "https://clbcovdeoahrmxaoijyt.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNsYmNvdmRlb2Focm14YW9panl0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIxNTc4NTAsImV4cCI6MjA2NzczMzg1MH0.dxwJhTZ9ei4dOnxmCvGztb8pfUqTlprfd0-woF6Y-lY"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


# 🟢 /start
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    logging.info(f"Команда /start від користувача {message.from_user.id}")
    await message.answer("Напишіть щось")
    await state.set_state("waiting_for_message")

# 🟢 Обробка текстового повідомлення
@router.message(StateFilter("waiting_for_message"), F.text)
async def handle_message(message: Message, state: FSMContext):
    user_message = message.text
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} надіслав повідомлення: {user_message}")
    
    # Зберігаємо повідомлення в Supabase
    try:
        submission_id = str(uuid.uuid4())
        supabase.table("submissions").insert({
            "user_id": user_id,
            "username": message.from_user.username or message.from_user.first_name,
            "description": user_message,  # Змінено на "description"
            "status": "pending",
            "submitted_at": datetime.utcnow().isoformat(),
            "submission_id": submission_id
        }).execute()
    except Exception as e:
        logging.error(f"Помилка при збереженні в Supabase: {e}")
        await message.answer("⚠️ Виникла помилка. Зверніться до адмінів.")
        return

    # Надсилаємо повідомлення в адмін-групу з кнопкою підтвердження
    try:
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"Нове повідомлення від @{message.from_user.username or message.from_user.first_name}:\n{user_message}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Опублікувати", callback_data=f"approve_{user_id}_{submission_id}")
            ]])
        )
        await message.answer("✅ Повідомлення надіслано на перевірку!")
        await state.clear()
    except Exception as e:
        logging.error(f"Помилка при надсиланні в адмін-групу: {e}")
        await message.answer("⚠️ Виникла помилка при надсиланні. Зверніться до адмінів.")

# 🟢 Обробка callback-запитів
@router.callback_query(F.data.startswith("approve_"))
async def handle_callback(query: CallbackQuery):
    logging.info(f"Callback від адміна {query.from_user.id}: {query.data}")
    parts = query.data.split("_", 2)
    user_id = int(parts[1])
    submission_id = parts[2]
    
    # Отримуємо повідомлення з Supabase
    try:
        submission = supabase.table("submissions").select("description").eq("submission_id", submission_id).eq("user_id", user_id).execute()
        if not submission.data:
            await query.message.edit_text("⚠️ Заявка не знайдена.")
            await query.answer()
            return
        user_message = submission.data[0]["description"]
    except Exception as e:
        logging.error(f"Помилка при отриманні з Supabase: {e}")
        await query.message.edit_text("⚠️ Помилка при обробці. Зверніться до розробника.")
        await query.answer()
        return

    # Публікуємо повідомлення на канал
    try:
        await bot.send_message(
            chat_id=MAIN_CHAT_ID,
            text=user_message
        )
        supabase.table("submissions").update({
            "status": "approved",
            "moderated_at": datetime.utcnow().isoformat(),
            "moderator_id": query.from_user.id
        }).eq("submission_id", submission_id).execute()
        await query.message.reply_text("✅ Повідомлення опубліковано!")
        await bot.send_message(user_id, "🎉 Ваш пост опубліковано!")
    except Exception as e:
        logging.error(f"Помилка при публікації: {e}")
        await query.message.reply_text(f"⚠️ Помилка: {e}")
    await query.answer()

# 🟢 Обробка помилок
@dp.error()
async def error_handler(update, exception):
    logging.exception(f"Виняток: {exception}")
    return True
