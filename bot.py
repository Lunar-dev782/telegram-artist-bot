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
MAIN_CHAT_ID = -1002865535470

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

# ✅ FSM
class FSMSubmission(StatesGroup):
    waiting_for_text = State()

# 🟡 /submit
@router.message(Command("submit"))
async def start_submission(message: Message, state: FSMContext):
    await message.answer("✍️ Напишіть текст, який хочете надіслати:")
    await state.set_state(FSMSubmission.waiting_for_text)

# ✉️ Приймаємо текст
@router.message(FSMSubmission.waiting_for_text)
async def receive_submission_text(message: Message, state: FSMContext, bot: Bot):
    submission_id = str(uuid.uuid4())
    user_id = message.from_user.id
    text = message.text.strip()

    await state.clear()

    await message.answer("✅ Дякую! Вашу заявку передано на модерацію.")

    # Надсилаємо в адмінський чат
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Схвалити", callback_data=f"approve:{user_id}:{submission_id}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject:{user_id}:{submission_id}")
        ]
    ])

    # Зберігаємо в тимчасову пам’ять (в реальному проєкті — у базу)
    message.bot.submissions = getattr(message.bot, "submissions", {})
    message.bot.submissions[submission_id] = {
        "user_id": user_id,
        "text": text,
        "username": message.from_user.username or f"id{user_id}"
    }

    await bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"🆕 Заявка від @{message.from_user.username or user_id}:\n\n{text}",
        reply_markup=keyboard
    )

# ✅ Схвалення
@router.callback_query(F.data.startswith("approve:"))
async def approve_submission(callback: CallbackQuery, bot: Bot):
    try:
        _, user_id_str, submission_id = callback.data.split(":")
        user_id = int(user_id_str)

        data = bot.submissions.get(submission_id)
        if not data:
            await callback.message.edit_text("⚠️ Заявку не знайдено або вона вже оброблена.")
            return

        # Публікуємо в канал
        post_text = (
            f"📢 <b>Публікація від @{data['username']}:</b>\n\n"
            f"{data['text']}\n\n"
            f"#public"
        )

        await bot.send_message(CHANNEL_ID, post_text, parse_mode=ParseMode.HTML)
        await bot.send_message(user_id, "🎉 Вашу заявку схвалено та опубліковано в каналі!")

        await callback.message.edit_text("✅ Заявку схвалено та опубліковано.")
        bot.submissions.pop(submission_id, None)

    except Exception as e:
        logging.error(f"❌ approve_submission error: {e}")
        await callback.message.edit_text("⚠️ Помилка при схваленні заявки.")

    await callback.answer()

# ❌ Відхилення
@router.callback_query(F.data.startswith("reject:"))
async def reject_submission(callback: CallbackQuery, bot: Bot):
    try:
        _, user_id_str, submission_id = callback.data.split(":")
        user_id = int(user_id_str)

        data = bot.submissions.get(submission_id)
        if data:
            await bot.send_message(user_id, "😔 Вашу заявку відхилено.")
            bot.submissions.pop(submission_id, None)

        await callback.message.edit_text("❌ Заявку відхилено.")

    except Exception as e:
        logging.error(f"❌ reject_submission error: {e}")
        await callback.message.edit_text("⚠️ Помилка при відхиленні заявки.")

    await callback.answer()

# Обробка помилок
@dp.errors()
async def error_handler(update, exception):
    logging.exception(f"Виняток: {exception}")
    return True

# Експортуємо dp і bot для webhook.py
__all__ = ["dp", "bot", "TOKEN"]
