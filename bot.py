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

# 📋 Стан машини
class Form(StatesGroup):
    message = State()

# 🟢 /start
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    logging.info(f"Команда /start від користувача {message.from_user.id}")
    await message.answer("Напишіть повідомлення для публікації")
    await state.set_state(Form.message)

# 🟢 Обробка текстового повідомлення
@router.message(Form.message, F.text)
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
            "category": "Загальне",
            "description": user_message,
            "status": "pending",
            "submitted_at": datetime.utcnow().isoformat(),
            "submission_id": submission_id
        }).execute()
        logging.info(f"Заявка збережена в Supabase, submission_id={submission_id}")
    except Exception as e:
        logging.error(f"Помилка при збереженні в Supabase: {e}")
        await message.answer("⚠️ Виникла помилка. Зверніться до адмінів.")
        return

    # Надсилаємо повідомлення в адмін-групу
    try:
        sent_message = await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"Нове повідомлення від @{message.from_user.username or message.from_user.first_name}:\n{user_message}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Опублікувати", callback_data=f"approve_{user_id}_{submission_id}"),
                InlineKeyboardButton(text="❌ Відмовити", callback_data=f"reject_{user_id}_{submission_id}")
            ]])
        )
        # Зберігаємо media_message_ids
        supabase.table("submissions").update({
            "media_message_ids": [sent_message.message_id]
        }).eq("submission_id", submission_id).execute()
        logging.info(f"Повідомлення надіслано в адмін-групу, message_id={sent_message.message_id}")
        await message.answer("✅ Повідомлення надіслано на перевірку!")
        await state.clear()
    except Exception as e:
        logging.error(f"Помилка при надсиланні в адмін-групу: {e}")
        await message.answer("⚠️ Виникла помилка при надсиланні. Зверніться до адмінів.")

# 🟢 Обробка callback-запитів (схвалення)
@router.callback_query(F.data.startswith("approve_"))
async def handle_approve(query: CallbackQuery):
    logging.info(f"Callback отримано: data={query.data}, from_user={query.from_user.id}")
    parts = query.data.split("_", 2)
    user_id = int(parts[1])
    submission_id = parts[2]
    
    # Отримуємо повідомлення з Supabase
    try:
        submission = supabase.table("submissions").select("description").eq("submission_id", submission_id).eq("user_id", user_id).execute()
        logging.info(f"Supabase запит: submission_id={submission_id}, user_id={user_id}, результат={submission.data}")
        if not submission.data:
            logging.error(f"Заявка не знайдена: submission_id={submission_id}, user_id={user_id}")
            await query.message.edit_text("⚠️ Заявка не знайдена.")
            await query.answer()
            return
        user_message = submission.data[0]["description"]
        logging.info(f"Отримано повідомлення з Supabase: {user_message}")
    except Exception as e:
        logging.error(f"Помилка при отриманні з Supabase: {e}")
        await query.message.edit_text("⚠️ Помилка при обробці. Зверніться до розробника.")
        await query.answer()
        return

    # Перевіряємо права бота в каналі
    try:
        chat_member = await bot.get_chat_member(chat_id=MAIN_CHAT_ID, user_id=bot.id)
        if not chat_member.can_post_messages:
            logging.error(f"Бот не має прав для надсилання повідомлень у канал {MAIN_CHAT_ID}")
            await query.message.reply_text("⚠️ Бот не має прав для публікації в канал. Перевірте права адміністратора.")
            await query.answer()
            return
        logging.info(f"Бот має права для надсилання повідомлень у канал {MAIN_CHAT_ID}")
    except Exception as e:
        logging.error(f"Помилка при перевірці прав у каналі {MAIN_CHAT_ID}: {e}")
        await query.message.reply_text(f"⚠️ Помилка при перевірці прав: {e}")
        await query.answer()
        return

    # Публікуємо повідомлення на канал з явним очікуванням відповіді
    try:
        sent_message = await bot.send_message(
            chat_id=MAIN_CHAT_ID,
            text=user_message,
            disable_notification=False
        )
        logging.info(f"Повідомлення успішно надіслано в канал {MAIN_CHAT_ID}, message_id={sent_message.message_id}")
        supabase.table("submissions").update({
            "status": "approved",
            "moderated_at": datetime.utcnow().isoformat(),
            "moderator_id": query.from_user.id
        }).eq("submission_id", submission_id).execute()
        logging.info(f"Статус оновлено в Supabase, submission_id={submission_id}")
        await query.message.reply_text("✅ Повідомлення опубліковано!")
        await bot.send_message(user_id, "🎉 Ваш пост опубліковано!")
    except TelegramForbiddenError as e:
        logging.error(f"Помилка доступу до каналу {MAIN_CHAT_ID}: {e}")
        await query.message.reply_text("⚠️ Бот не має доступу до каналу. Перевірте права адміністратора.")
    except Exception as e:
        logging.error(f"Помилка при публікації в канал {MAIN_CHAT_ID}: {e}, traceback={traceback.format_exc()}")
        await query.message.reply_text(f"⚠️ Помилка при публікації: {e}")
    await query.answer()

# 🟢 Обробка callback-запитів (відхилення)
@router.callback_query(F.data.startswith("reject_"))
async def handle_reject(query: CallbackQuery):
    logging.info(f"Callback отримано: data={query.data}, from_user={query.from_user.id}")
    parts = query.data.split("_", 2)
    user_id = int(parts[1])
    submission_id = parts[2]
    
    try:
        supabase.table("submissions").update({
            "status": "rejected",
            "moderated_at": datetime.utcnow().isoformat(),
            "moderator_id": query.from_user.id,
            "rejection_reason": "Невідповідність вимогам"
        }).eq("submission_id", submission_id).execute()
        logging.info(f"Заявка відхилена, submission_id={submission_id}")
        await query.message.reply_text("❌ Повідомлення відхилено.")
        await bot.send_message(user_id, "😔 Ваш пост відхилено: Невідповідність вимогам.")
    except Exception as e:
        logging.error(f"Помилка при відхиленні: {e}")
        await query.message.reply_text(f"⚠️ Помилка: {e}")
    await query.answer()

# 🟢 Обробка помилок
@dp.error()
async def error_handler(update, exception):
    logging.exception(f"Виняток: {exception}")
    return True
