import os
import re
import time
import json
import random
import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from typing import List, Dict
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
TOKEN = "7645134499:AAG5kuDHsUG-djs4qRjS7IX22UjzYKSXQHw"
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

# 🔌 Дані для Supabase (лише для користувачів)
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

# 🟢 Функція для перевірки користувача в Supabase
async def check_user(user_id: int, username: str = None) -> Dict:
    try:
        response = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if response.data:
            return response.data[0]
        else:
            supabase.table("users").insert({
                "user_id": user_id,
                "username": username or "",
                "post_count": 0,
                "last_post_date": None
            }).execute()
            return {"user_id": user_id, "username": username or "", "post_count": 0, "last_post_date": None}
    except Exception as e:
        logging.error(f"Помилка при перевірці користувача в Supabase: {e}")
        return {"user_id": user_id, "username": "", "post_count": 0, "last_post_date": None}

# 🟢 Оновлення даних користувача в Supabase
async def update_user(user_id: int, post_count: int, last_post_date: str):
    try:
        supabase.table("users").update({
            "post_count": post_count,
            "last_post_date": last_post_date
        }).eq("user_id", user_id).execute()
    except Exception as e:
        logging.error(f"Помилка при оновленні користувача в Supabase: {e}")

# 🟢 /start
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    logging.info(f"Команда /start від користувача {user_id}")
    user_data = await check_user(user_id, username)
    post_count = user_data["post_count"]
    last_post_date = user_data["last_post_date"]
    if last_post_date:
        last_post = datetime.fromisoformat(last_post_date.replace("Z", "+00:00"))
        days_left = (7 - (datetime.utcnow() - last_post).days)
        if days_left > 0:
            await message.answer(f"⚠️ Ви можете подавати заявку не частіше, ніж раз на 7 днів. Залишилося {days_left} днів.")
            return
    await message.answer(
        f"🎨 Привіт! Це бот для публікацій у спільноті [Назва].\n"
        f"Ваші пости: {post_count}\n"
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
    user_data = await check_user(user_id)
    post_count = user_data["post_count"]
    last_post_date = user_data["last_post_date"]
    if last_post_date:
        last_post = datetime.fromisoformat(last_post_date.replace("Z", "+00:00"))
        days_left = (7 - (datetime.utcnow() - last_post).days)
        if days_left > 0:
            await message.answer(f"⚠️ Ви можете подавати заявку не частіше, ніж раз на 7 днів. Залишилося {days_left} днів.")
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
    submission_id = str(uuid.uuid4())  # Унікальний ідентифікатор заявки
    logging.info(f"Фінальна обробка заявки від користувача {user.id}, submission_id={submission_id}. Дані: {data}, Фото: {photos}")
    await state.clear()

    text = (
        f"📥 <b>Нова заявка від</b> @{user.username or user.first_name}\n"
        f"<b>Категорія:</b> {data['category']}\n"
        f"<b>Нік:</b> {data.get('nickname', 'Невказано')}\n"
        f"<b>Опис:</b> {data.get('description', 'Невказано')}\n"
        f"<b>Соцмережі:</b>\n{data.get('socials', 'Невказано')}\n"
        f"submission_id: {submission_id}"
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
        await state.update_data(media_message_ids=media_message_ids)  # Зберігаємо message_id для видалення
        await bot.send_message(user.id, "✅ Заявка успішно надіслана на перевірку!")
    except TelegramBadRequest as e:
        logging.error(f"Помилка TelegramBadRequest при надсиланні в адмінський чат: {e}")
        await bot.send_message(user.id, "⚠️ Виникла помилка при надсиланні заявки адмінам (BadRequest). Зверніться до @AdminUsername.")
    except TelegramForbiddenError as e:
        logging.error(f"Помилка TelegramForbiddenError: бот не має доступу до адмінського чату {ADMIN_CHAT_ID}: {e}")
        await bot.send_message(user.id, "⚠️ Виникла помилка: бот не може надіслати заявку адмінам (Forbidden). Зверніться до @AdminUsername.")
    except Exception as e:
        logging.error(f"Невідома помилка при надсиланні в адмінський чат: {e}")
        await bot.send_message(user.id, "⚠️ Виникла помилка при надсиланні заявки адмінам. Зверніться до @AdminUsername.")

# 🟢 Схвалення посту
@router.callback_query(lambda c: c.data.startswith("approve:"))
async def approve_post(callback: CallbackQuery, state: FSMContext):
    logging.info(f"Callback approve отриманий від адміна {callback.from_user.id}, дані: {callback.data}")
    parts = callback.data.split(":")
    user_id = int(parts[1])
    submission_id = parts[2]
    logging.info(f"Адмін {callback.from_user.id} схвалив заявку для користувача {user_id}, submission_id={submission_id}")

    # Отримуємо дані з стану (message_ids для видалення)
    data = await state.get_data()
    media_message_ids = data.get("media_message_ids", [])

    try:
        # Отримуємо перше повідомлення за message_id
        first_message = await bot.get_message(chat_id=ADMIN_CHAT_ID, message_id=media_message_ids[0])
        if not first_message or not first_message.photo:
            logging.error(f"Не знайдено повідомлення для submission_id={submission_id}")
            await callback.message.edit_text("⚠️ Не вдалося знайти заявку для публікації.")
            await callback.answer()
            return

        # Витягуємо фото
        photos = [photo.file_id for photo in first_message.photo]
        caption = first_message.caption or ""
        description_match = re.search(r"<b>Опис:</b>\s*(.*?)(?=\n<b>Соцмережі:</b>|$)", caption, re.DOTALL)
        description = description_match.group(1).strip() if description_match else "Невказано"
        socials_match = re.search(r"<b>Соцмережі:</b>\n(.*?)(?=\n|$)", caption, re.DOTALL)
        socials = socials_match.group(1).strip() if socials_match else "Невказано"

        # Публікуємо в основний чат
        post_text = (
            f"📢 <b>{re.search(r'<b>Категорія:</b>\s*(.*?)\n', caption).group(1)}</b>\n\n"
            f"{description}\n\n"
            f"🌐 <b>Соцмережі:</b>\n{socials}\n"
            f"👤 Від: @{re.search(r'<b>Нова заявка від</b>\s*@(\w+)', caption).group(1)}\n"
            f"#public"
        )
        media = [InputMediaPhoto(media=photos[0], caption=post_text, parse_mode="HTML")]
        for photo in photos[1:]:
            media.append(InputMediaPhoto(media=photo))

        logging.info(f"Відправка медіа-групи в основний чат {MAIN_CHAT_ID}")
        await bot.send_media_group(chat_id=MAIN_CHAT_ID, media=media)

        # Оновлюємо дані користувача
        user_data = await check_user(user_id)
        new_post_count = user_data["post_count"] + 1
        await update_user(user_id, new_post_count, datetime.utcnow().isoformat())

        # Видаляємо повідомлення з адмін-групи
        for msg_id in media_message_ids:
            try:
                await bot.delete_message(chat_id=ADMIN_CHAT_ID, message_id=msg_id)
            except Exception as e:
                logging.error(f"Помилка видалення повідомлення {msg_id}: {e}")
        await callback.message.delete()

        await bot.send_message(user_id, f"🎉 Вашу публікацію схвалено та опубліковано в основному чаті! Ви опублікували {new_post_count} постів.")
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
async def reject_post(callback: CallbackQuery, state: FSMContext):
    logging.info(f"Callback reject отриманий від адміна {callback.from_user.id}, дані: {callback.data}")
    parts = callback.data.split(":")
    user_id = int(parts[1])
    submission_id = parts[2]
    logging.info(f"Адмін {callback.from_user.id} відхилив заявку для користувача {user_id}, submission_id={submission_id}")

    # Отримуємо дані з стану (message_ids для видалення)
    data = await state.get_data()
    media_message_ids = data.get("media_message_ids", [])

    try:
        # Видаляємо повідомлення з адмін-групи
        for msg_id in media_message_ids:
            try:
                await bot.delete_message(chat_id=ADMIN_CHAT_ID, message_id=msg_id)
            except Exception as e:
                logging.error(f"Помилка видалення повідомлення {msg_id}: {e}")
        await callback.message.delete()

        await bot.send_message(user_id, "😔 Вашу публікацію відхилено. Причина: Невідповідність вимогам.")
        await callback.answer()
    except Exception as e:
        logging.error(f"Помилка при відхиленні заявки: {e}")
        await callback.message.edit_text("⚠️ Помилка при відхиленні заявки. Зверніться до розробника.")
        await callback.answer()

# 🟢 Діагностичний обробник callback-запитів
@router.callback_query()
async def debug_callback(callback: CallbackQuery):
    logging.info(f"DEBUG: Отримано callback-запит: {callback.data} від адміна {callback.from_user.id}")
    await callback.answer("Отримано callback, але немає обробника")

# 🟢 Обробка помилок
@dp.errors()
async def error_handler(update, exception):
    logging.exception(f"Виникла помилка при обробці оновлення {update.update_id if update else 'невідоме'}: {exception}")
    if update and hasattr(update, 'callback_query'):
        await update.callback_query.answer("⚠️ Виникла помилка. Спробуйте ще раз.")
    return True
