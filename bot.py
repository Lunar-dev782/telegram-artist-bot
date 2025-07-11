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
dp.include_router(router)

# 🔌 Дані для Supabase
SUPABASE_URL = "https://clbcovdeoahrmxaoijyt.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNsYmNvdmRlb2Focm14YW9panl0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIxNTc4NTAsImV4cCI6MjA2NzczMzg1MH0.dxwJhTZ9ei4dOnxmCvGztb8pfUqTlprfd0-woF6Y-lY"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# 📋 Стан машини
class Form(StatesGroup):
    category = State()
    description = State()
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
    logging.info(f"Команда /start від користувача {message.from_user.id}")
    await message.answer(
        "🎨 Привіт! Це бот для публікацій у спільноті [Назва].\n"
        "Обери розділ, у якому хочеш зробити пост, та дотримуйся простих умов, щоб бути опублікованим 💫",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=cat)] for cat in CATEGORIES.keys()],
            resize_keyboard=True
        )
    )
    await state.set_state(Form.category)

# 🟢 /help
@router.message(Command("help"))
async def cmd_help(message: Message):
    logging.info(f"Команда /help від користувача {message.from_user.id}")
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
    logging.info(f"Команда /rules від користувача {message.from_user.id}")
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

# 🟢 Тестування основного чату
@router.message(Command("test_main_chat"))
async def test_main_chat(message: Message):
    try:
        logging.info(f"Тестування доступу до основного чату {MAIN_CHAT_ID}")
        await bot.send_message(chat_id=MAIN_CHAT_ID, text="Тестове повідомлення від бота")
        await message.answer("Тестове повідомлення успішно надіслано в основний чат!")
    except Exception as e:
        logging.error(f"Помилка тестування основного чату: {e}")
        await message.answer(f"Помилка: {e}")

# 🟢 Обробка вибору категорії
@router.message(lambda message: message.text in CATEGORIES)
async def handle_category_selection(message: Message, state: FSMContext):
    category = message.text
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} обрав категорію: {category}")
    
    try:
        last_submission = supabase.table("submissions").select("submitted_at").eq("user_id", user_id).order("submitted_at", desc=True).limit(1).execute()
        if last_submission.data:
            last_time = datetime.fromisoformat(last_submission.data[0]["submitted_at"].replace("Z", "+00:00"))
            if datetime.utcnow() - last_time < timedelta(days=7):
                await message.answer("⚠️ Ви можете подавати заявку не частіше, ніж раз на 7 днів. Спробуйте пізніше!")
                return
    except Exception as e:
        logging.error(f"Помилка при перевірці останньої заявки в Supabase: {e}")
        await message.answer("⚠️ Виникла помилка при перевірці вашої заявки. Зверніться до @AdminUsername.")
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
    logging.info(f"Користувач {message.from_user.id} підтвердив виконання умов")
    await message.answer(
        "📋 Надішли, будь ласка, цю інформацію *одним повідомленням*:\n\n"
        "1. Ім’я / нікнейм\n"
        "2. Короткий опис\n"
        "3. Лінки на соцмережі (Instagram: @нік, Telegram: @нікнейм)\n\n"
        "📌 Приклад:\n"
        "Нік: @Artist\n"
        "Опис: Продаю персонажа, унікальний дизайн!\n"
        "Соцмережі: Instagram: @artist, Telegram: @artist\n\n"
        "Після цього надішли до 5 зображень.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(Form.description)

# 🟢 Опис та соцмережі одним повідомленням
@router.message(Form.description)
async def get_description_and_socials(message: Message, state: FSMContext):
    logging.info(f"Користувач {message.from_user.id} надіслав анкету: {message.text}")
    if not message.text or len(message.text.split('\n')) < 3:
        await message.answer(
            "⚠️ Будь ласка, надішли всю інформацію одним повідомленням:\n"
            "1. Ім’я / нікнейм\n"
            "2. Короткий опис\n"
            "3. Лінки на соцмережі\n\n"
            "Спробуй ще раз."
        )
        return

    try:
        lines = message.text.split('\n')
        nickname = lines[0].strip()
        description = lines[1].strip()
        socials = '\n'.join(lines[2:]).strip()

        await state.update_data(nickname=nickname, description=description, socials=socials)
        await message.answer("📸 Надішли до 5 зображень для публікації")
        await state.set_state(Form.images)
    except Exception as e:
        logging.error(f"Помилка обробки повідомлення: {e}")
        await message.answer(
            "⚠️ Помилка формату повідомлення. Переконайся, що ти надіслав усі дані коректно:\n"
            "1. Ім’я / нікнейм\n"
            "2. Короткий опис\n"
            "3. Лінки на соцмережі\n\n"
            "Спробуй ще раз."
        )

# 🟢 Фото
@router.message(Form.images, F.photo)
async def get_images(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    logging.info(f"Користувач {message.from_user.id} надіслав зображення: {message.photo[-1].file_id}")

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
    logging.info(f"Користувач {message.from_user.id} завершив надсилання зображень: {photos}")
    if not photos:
        await message.answer("⚠️ Спочатку надішли хоча б 1 зображення.")
        return
    await message.answer("✅ Дякую! Надіслано на перевірку.")
    await finish_submission(message.from_user, state, photos)

# ✅ Фінальна обробка
async def finish_submission(user: types.User, state: FSMContext, photos: list):
    data = await state.get_data()
    submission_id = str(uuid.uuid4())
    logging.info(f"Фінальна обробка заявки від користувача {user.id}, submission_id={submission_id}. Дані: {data}, Фото: {photos}")
    await state.clear()

    text = (
        f"📥 <b>Нова заявка від</b> @{user.username or user.first_name}\n"
        f"<b>Категорія:</b> {data['category']}\n"
        f"<b>Нік:</b> {data.get('nickname', 'Невказано')}\n"
        f"<b>Опис:</b> {data.get('description', 'Невказано')}\n"
        f"<b>Соцмережі:</b>\n{data.get('socials', 'Невказано')}\n"
        f"#public"
    )

    media = [InputMediaPhoto(media=photos[0], caption=text, parse_mode="HTML")]
    for p in photos[1:]:
        media.append(InputMediaPhoto(media=p))

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Опублікувати", callback_data=f"approve:{user.id}:{submission_id}")
    keyboard.button(text="❌ Відмовити", callback_data=f"reject:{user.id}:{submission_id}")
    markup = keyboard.as_markup()

    try:
        logging.info(f"Надсилання медіа-групи в адмінський чат {ADMIN_CHAT_ID}")
        media_message = await bot.send_media_group(chat_id=ADMIN_CHAT_ID, media=media)
        logging.info(f"Надсилання повідомлення з кнопками в адмінський чат {ADMIN_CHAT_ID}")
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text="🔎 Оберіть дію:", reply_markup=markup)
        media_message_ids = [msg.message_id for msg in media_message]
    except TelegramBadRequest as e:
        logging.error(f"Помилка TelegramBadRequest при надсиланні в адмінський чат: {e}")
        await bot.send_message(user.id, "⚠️ Виникла помилка при надсиланні заявки адмінам (BadRequest). Зверніться до @AdminUsername.")
        return
    except TelegramForbiddenError as e:
        logging.error(f"Помилка TelegramForbiddenError: бот не має доступу до адмінського чату {ADMIN_CHAT_ID}: {e}")
        await bot.send_message(user.id, "⚠️ Виникла помилка: бот не може надіслати заявку адмінам (Forbidden). Зверніться до @AdminUsername.")
        return
    except Exception as e:
        logging.error(f"Невідома помилка при надсиланні в адмінський чат: {e}")
        await bot.send_message(user.id, "⚠️ Виникла помилка при надсиланні заявки адмінам. Зверніться до @AdminUsername.")
        return

    try:
        logging.info(f"Збереження заявки в Supabase для користувача {user.id}, submission_id={submission_id}")
        supabase.table("submissions").insert({
            "user_id": user.id,
            "username": user.username or user.first_name,
            "category": data["category"],
            "nickname": data.get("nickname", ""),
            "description": data.get("description", ""),
            "socials": data.get("socials", ""),
            "images": photos,
            "status": "pending",
            "submitted_at": datetime.utcnow().isoformat(),
            "submission_id": submission_id,
            "media_message_ids": media_message_ids
        }).execute()
        logging.info(f"Заявка успішно збережена в Supabase")
        await bot.send_message(user.id, "✅ Заявка успішно надіслана на перевірку!")
    except Exception as e:
        logging.error(f"Помилка при збереженні в Supabase: {e}")
        await bot.send_message(user.id, "⚠️ Виникла помилка при збереженні заявки. Зверніться до @AdminUsername.")
        return

# 🟢 Схвалення посту та пересилання в основний чат
@router.callback_query(lambda c: c.data.startswith("approve:"))
async def approve_post(callback: types.CallbackQuery):
    logging.info(f"Callback approve отриманий від адміна {callback.from_user.id}, дані: {callback.data}")
    parts = callback.data.split(":")
    user_id = int(parts[1])
    submission_id = parts[2]
    logging.info(f"Адмін {callback.from_user.id} схвалив заявку для користувача {user_id}, submission_id={submission_id}")

    try:
        logging.info(f"Оновлення статусу заявки в Supabase для user_id={user_id}, submission_id={submission_id}")
        result = supabase.table("submissions").update({
            "status": "approved",
            "moderated_at": datetime.utcnow().isoformat(),
            "moderator_id": callback.from_user.id
        }).eq("user_id", user_id).eq("submission_id", submission_id).execute()
        logging.info(f"Результат оновлення Supabase: {result}")
    except Exception as e:
        logging.error(f"Помилка при оновленні статусу в Supabase: {e}")
        await callback.message.edit_text("⚠️ Помилка при схваленні заявки. Зверніться до розробника.")
        await callback.answer()
        return

    try:
        logging.info(f"Отримання схваленої заявки для user_id={user_id}, submission_id={submission_id}")
        submission = supabase.table("submissions").select("*").eq("user_id", user_id).eq("submission_id", submission_id).eq("status", "approved").execute()
        logging.info(f"Отримані дані заявки: {submission.data}")

        if not submission.data:
            logging.error(f"Не знайдено схваленої заявки для користувача {user_id}, submission_id={submission_id}")
            await callback.message.edit_text("⚠️ Не вдалося знайти заявку для публікації.")
            await callback.answer()
            return

        data = submission.data[0]
        media_message_ids = data.get("media_message_ids", [])

        try:
            if media_message_ids:
                logging.info(f"Пересилання медіа-групи з адмінського чату {ADMIN_CHAT_ID} в основний чат {MAIN_CHAT_ID}")
                for message_id in media_message_ids:
                    await asyncio.sleep(1)
                    await bot.forward_message(
                        chat_id=MAIN_CHAT_ID,
                        from_chat_id=ADMIN_CHAT_ID,
                        message_id=message_id
                    )
            else:
                raise ValueError("media_message_ids порожній")
        except Exception as e:
            logging.warning(f"Помилка пересилання: {e}. Спроба відправки медіа-групи напряму.")
            post_text = (
                f"📢 <b>{data['category']}</b>\n\n"
                f"{data['description']}\n\n"
                f"🌐 <b>Соцмережі:</b>\n{data['socials']}\n"
                f"👤 Від: @{data['username']}\n"
                f"#public"
            )
            media = [InputMediaPhoto(media=data["images"][0], caption=post_text, parse_mode="HTML")]
            for photo in data["images"][1:]:
                media.append(InputMediaPhoto(media=photo))
            logging.info(f"Відправка медіа-групи в основний чат {MAIN_CHAT_ID}")
            await bot.send_media_group(chat_id=MAIN_CHAT_ID, media=media)

        await callback.message.edit_text("✅ Публікацію схвалено та опубліковано в основному чаті!")
        await bot.send_message(user_id, "🎉 Вашу публікацію схвалено та опубліковано в основному чаті!")
        await callback.answer()
    except TelegramBadRequest as e:
        logging.error(f"Помилка TelegramBadRequest при публікації в основний чат: {e}")
        await callback.message.edit_text("⚠️ Помилка при публікації в основний чат (BadRequest).")
        await callback.answer()
    except TelegramForbiddenError as e:
        logging.error(f"Помилка TelegramForbiddenError: бот не має доступу до основного чату {MAIN_CHAT_ID}: {e}")
        await callback.message.edit_text("⚠️ Помилка: бот не має доступу до основного чату.")
        await callback.answer()
    except Exception as e:
        logging.error(f"Невідома помилка при публікації в основний чат: {e}")
        await callback.message.edit_text("⚠️ Помилка при публікації в основний чат.")
        await callback.answer()

# 🟢 Відхилення посту
@router.callback_query(lambda c: c.data.startswith("reject:"))
async def reject_post(callback: types.CallbackQuery):
    logging.info(f"Callback reject отриманий від адміна {callback.from_user.id}, дані: {callback.data}")
    parts = callback.data.split(":")
    user_id = int(parts[1])
    submission_id = parts[2]
    logging.info(f"Адмін {callback.from_user.id} відхилив заявку для користувача {user_id}, submission_id={submission_id}")

    try:
        logging.info(f"Оновлення статусу заявки в Supabase для user_id={user_id}, submission_id={submission_id}")
        result = supabase.table("submissions").update({
            "status": "rejected",
            "moderated_at": datetime.utcnow().isoformat(),
            "moderator_id": callback.from_user.id,
            "rejection_reason": "Невідповідність вимогам"
        }).eq("user_id", user_id).eq("submission_id", submission_id).execute()
        logging.info(f"Результат оновлення Supabase: {result}")
        await callback.message.edit_text("❌ Публікацію відхилено.")
        await bot.send_message(user_id, "😔 Вашу публікацію відхилено. Причина: Невідповідність вимогам.")
        await callback.answer()
    except Exception as e:
        logging.error(f"Помилка при відхиленні заявки: {e}")
        await callback.message.edit_text("⚠️ Помилка при відхиленні заявки. Зверніться до розробника.")
        await callback.answer()

# 🟢 Діагностичний обробник callback-запитів
@router.callback_query()
async def debug_callback(callback: types.CallbackQuery):
    logging.info(f"DEBUG: Отримано callback-запит: {callback.data}")
    await callback.answer("Отримано callback, але немає обробника")

# Обробка помилок
@dp.errors()
async def error_handler(update, exception):
    logging.exception(f"Виняток: {exception}")
    return True

# Експортуємо dp і bot для webhook.py
__all__ = ["dp", "bot", "TOKEN"]
