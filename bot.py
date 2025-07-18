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
TOKEN = "7645134499:AAG5kuDHsUG-djs4qRjS7IX22UjzYKSXQHw"
ADMIN_CHAT_ID = -1002802098163
MAIN_CHAT_ID = -1002865535470
ADMIN_CONTACTS = ["@Admin1", "@Admin2"]

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
    main_menu = State()  # Головне меню після /start
    category = State()   # Вибір категорії
    repost_platform = State()  # Вибір платформи репосту
    repost_link = State()      # Отримання посилання на репост
    description = State()      # Введення опису та соцмереж
    images = State()           # Завантаження зображень
    question = State()         # Надсилання питання адмінам
    answer = State()           # Введення відповіді адміном

# 📋 Категорії та їх описи
CATEGORIES = {
    "💸 Платні послуги": "Коміші, прайси, реклама. Репост обов’язковий.",
    "📣 Самопіар": "Промоція вашого контенту, блогу або профілю. Репост обов’язковий.",
    "🎭 Активності": "Івенти, конкурси, лотереї, DTIYS (Draw This In Your Style).",
    "🔍 Пошук критика / притика": "Шукаєш фідбек? Тобі сюди.",
    "📩 Оголошення / звернення": "Обговорення, звернення — без зображень. Репост не обов’язковий.",
    "➕ Інше": "Щось, що не вмістилось в інші категорії.",
    "🐾 Адопти": "Пости про персонажів, яких ви пропонуєте для адопції.",
    "🧵 Реквести": "Запити на створення персонажів або іншого контенту."
}

# 🟢 Фонова задача для видалення старих заявок
async def cleanup_old_submissions():
    while True:
        try:
            logging.info("Запуск задачі очищення старих заявок")
            seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
            result = supabase.table("submissions").delete().lt("submitted_at", seven_days_ago).execute()
            logging.info(f"Видалено {len(result.data)} заявок, старших за 7 днів")
        except Exception as e:
            logging.error(f"Помилка при очищенні старих заявок: {e}")
        await asyncio.sleep(3600)  # Перевірка кожну годину

# 🟢 Перевірка підписки на канал
async def check_subscription(user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(chat_id=MAIN_CHAT_ID, user_id=user_id)
        logging.info(f"Статус підписки для user_id={user_id}: {chat_member.status}")
        return chat_member.status in ["member", "creator", "administrator"]
    except TelegramForbiddenError as e:
        logging.error(f"Помилка TelegramForbiddenError при перевірці підписки для user_id={user_id}: {e}")
        return False
    except TelegramBadRequest as e:
        logging.error(f"Помилка TelegramBadRequest при перевірці підписки для user_id={user_id}: {e}")
        return False
    except TelegramRetryAfter as e:
        logging.warning(f"Обмеження Telegram API, повтор через {e.retry_after} секунд для user_id={user_id}")
        await asyncio.sleep(e.retry_after)
        return False
    except Exception as e:
        logging.error(f"Невідома помилка при перевірці підписки для user_id={user_id}: {e}")
        return False

# 🟢 Головне меню
async def show_main_menu(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Показ головного меню для користувача {user_id}")

    try:
        # Перевірка підписки
        subscription_status = await check_subscription(user_id)
        logging.info(f"Результат перевірки підписки для user_id={user_id}: {subscription_status}")
        if not subscription_status:
            await message.answer(
                "⚠️ Ви не підписані на наш канал! Будь ласка, підпишіться за посиланням: "
                "[Перейти до каналу](https://t.me/+bTmE3LOAMFI5YzBi) і натисніть 'Я підписався(лась)'.",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="Я підписався(лась)")]],
                    resize_keyboard=True
                )
            )
            return

        await message.answer(
            "🎨 Вітаємо в боті спільноти *Митці ЮА*! Оберіть дію:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📜 Правила"), KeyboardButton(text="📝 Запропонувати пост")],
                    [KeyboardButton(text="❓ Інші питання")]
                ],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.main_menu)
    except Exception as e:
        logging.error(f"Помилка в show_main_menu для user_id={user_id}: {e}")
        await message.answer("⚠️ Виникла помилка. Спробуйте ще раз або зверніться до @AdminUsername.")

# 🟢 Запуск фонової задачі очищення
async def on_startup():
    asyncio.create_task(cleanup_old_submissions())

# 🟢 /start
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await show_main_menu(message, state)

@router.message(F.text.lower() == "start")
async def cmd_pochnimo(message: Message, state: FSMContext):
    await show_main_menu(message, state)

@router.message(F.text == "Я підписався(лась)")
async def check_subscription_again(message: Message, state: FSMContext):
    await show_main_menu(message, state)

# 🟢 Обробка головного меню
@router.message(Form.main_menu, F.text == "📜 Правила")
@router.message(Command("rules"))
async def cmd_rules(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Команда або кнопка /правила від користувача {user_id}")
    rules_text = (
        "📖 Ознайомся з основними правилами спільноти *Митці ЮА*:\n\n"
        "📜 Правила публікацій:\n"
        "1. Дотримуйтесь умов для обраної категорії.\n"
        "2. Надсилайте лише оригінальний контент.\n"
        "3. Не більше 5 зображень на пост.\n"
        "4. Публікації дозволені не частіше, ніж 2 пости на 7 днів.\n"
        "5. Зробіть репост нашої спільноти в соцмережі або надішліть друзям.\n"
        "6. Заборонено NSFW, образливий або незаконний контент.\n"
        "7. Адміни мають право відхилити заявку з поясненням.\n\n"
        "📩 З питаннями: @AdminUsername\n"
        "👉 [Докладні правила](https://telegra.ph/Pravyla-Mytci-UA)"
    )
    await message.answer(
        rules_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        )
    )

# 🟢 Обробка "Запропонувати пост"
@router.message(Form.main_menu, F.text == "📝 Запропонувати пост")
async def handle_propose_post(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} обрав 'Запропонувати пост'")

    try:
        # Перевірка частоти подачі заявок (до 2 постів за 7 днів)
        seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        recent_submissions = supabase.table("submissions").select("submitted_at").eq("user_id", user_id).gte("submitted_at", seven_days_ago).execute()
        if len(recent_submissions.data) >= 2:
            await message.answer(
                "⚠️ Ви можете подавати не більше 2 заявок на 7 днів. Спробуйте пізніше!",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True
                )
            )
            return

        await message.answer(
            "🎨 Обери категорію для публікації:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=cat)] for cat in CATEGORIES.keys()] + [[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.category)
    except Exception as e:
        logging.error(f"Помилка в handle_propose_post для user_id={user_id}: {e}")
        await message.answer(
            "⚠️ Виникла помилка. Спробуйте ще раз або зверніться до @AdminUsername.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )

# 🟢 Обробка "Інші питання"
@router.message(Form.main_menu, F.text == "❓ Інші питання")
async def handle_other_questions(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} обрав 'Інші питання'")
    await message.answer(
        f"❓ Якщо у вас є питання — напишіть його тут, і наші адміни дадуть відповідь протягом доби.\n\n"
        f"📩 Також можете звернутись напряму:\n{' • '.join(ADMIN_CONTACTS)}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        ),
        parse_mode="Markdown"
    )
    await state.set_state(Form.question)

# 🟢 Обробка питань до адмінів
@router.message(Form.question)
async def process_question(message: Message, state: FSMContext):
    user_id = message.from_user.id
    question = message.text.strip()
    logging.info(f"Користувач {user_id} надіслав питання: {question}")

    if question == "⬅️ Назад":
        await show_main_menu(message, state)
        return

    if not question:
        await message.answer(
            "⚠️ Будь ласка, напишіть ваше питання.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        return

    try:
        # Генерація унікального ID для питання
        question_id = str(uuid.uuid4())
        # Збереження питання в Supabase
        question_data = {
            "question_id": question_id,
            "user_id": user_id,
            "username": message.from_user.username or message.from_user.first_name,
            "question_text": question,
            "status": "pending",
            "submitted_at": datetime.utcnow().isoformat()
        }
        try:
            result = supabase.table("questions").insert(question_data).execute()
            logging.info(f"Питання збережено в Supabase: {result.data}")
            if not result.data:
                raise ValueError("Не вдалося зберегти питання в Supabase")
        except Exception as supabase_error:
            logging.error(f"Помилка Supabase для user_id={user_id}, question_id={question_id}: {str(supabase_error)}\n{traceback.format_exc()}")
            await message.answer(
                "⚠️ Помилка при збереженні питання в базі даних. Спробуйте ще раз або зверніться до @AdminUsername.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True
                )
            )
            return

        # Формування повідомлення з клікабельним ім’ям
        username = message.from_user.username or message.from_user.first_name
        user_link = f'<a href="tg://user?id={user_id}">{username}</a>'
        question_message = (
            f"❓ Нове питання від {user_link} (ID: {user_id}):\n\n"
            f"{question}"
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="✉️ Відповісти", callback_data=f"answer:{user_id}:{question_id}")
        markup = keyboard.as_markup()

        # Перевірка доступу до адмінського чату
        try:
            chat = await bot.get_chat(ADMIN_CHAT_ID)
            logging.info(f"Адмінський чат доступний: {chat.id}")
        except TelegramForbiddenError as e:
            logging.error(f"Бот не має доступу до адмінського чату {ADMIN_CHAT_ID}: {str(e)}\n{traceback.format_exc()}")
            await message.answer(
                "⚠️ Бот не може надіслати питання до адмінів (немає доступу до чату). Зверніться до @AdminUsername.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True
                )
            )
            return
        except TelegramBadRequest as e:
            logging.error(f"Помилка при перевірці адмінського чату {ADMIN_CHAT_ID}: {str(e)}\n{traceback.format_exc()}")
            await message.answer(
                "⚠️ Помилка при перевірці адмінського чату. Зверніться до @AdminUsername.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True
                )
            )
            return

        # Спроба надсилання повідомлення до адмінів
        try:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=question_message,
                parse_mode="HTML",
                reply_markup=markup
            )
        except TelegramRetryAfter as e:
            logging.warning(f"Обмеження Telegram API, повтор через {e.retry_after} секунд для user_id={user_id}")
            await asyncio.sleep(e.retry_after)
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=question_message,
                parse_mode="HTML",
                reply_markup=markup
            )
        except TelegramForbiddenError as e:
            logging.error(f"Помилка TelegramForbiddenError при надсиланні до адмінського чату: {str(e)}\n{traceback.format_exc()}")
            await message.answer(
                "⚠️ Бот не може надіслати питання до адмінів (немає доступу). Зверніться до @AdminUsername.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True
                )
            )
            return
        except TelegramBadRequest as e:
            logging.error(f"Помилка TelegramBadRequest при надсиланні до адмінського чату: {str(e)}\n{traceback.format_exc()}")
            await message.answer(
                "⚠️ Помилка при надсиланні питання до адмінів. Зверніться до @AdminUsername.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True
                )
            )
            return

        await message.answer(
            "✅ Ваше питання надіслано адмінам! Очікуйте відповідь протягом доби.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.main_menu)
    except Exception as e:
        logging.error(f"Загальна помилка при обробці питання від user_id={user_id}: {str(e)}\n 
        {traceback.format_exc()}")
        await message.answer(
            f"⚠️ Виникла помилка при надсиланні питання: {str(e)}. Спробуйте ще раз або зверніться до @AdminUsername.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )

# 🟢 Обробка натискання кнопки "Відповісти"
@router.callback_query(lambda c: c.data.startswith("answer:"))
async def handle_answer_button(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    user_id = int(parts[1])
    question_id = parts[2]
    logging.info(f"Адмін {callback.from_user.id} натиснув 'Відповісти' для user_id={user_id}, question_id={question_id}")

    try:
        # Перевірка існування питання
        question = supabase.table("questions").select("*").eq("question_id", question_id).eq("user_id", user_id).execute()
        if not question.data or question.data[0]["status"] != "pending":
            await callback.message.edit_text("⚠️ Питання не знайдено або вже оброблено.")
            await callback.answer()
            return

        await callback.message.answer(
            f"✉️ Напишіть відповідь для користувача (ID: {user_id}):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Скасувати")]],
                resize_keyboard=True
            )
        )
        await state.update_data(user_id=user_id, question_id=question_id)
        await state.set_state(Form.answer)
        await callback.answer()
    except Exception as e:
        logging.error(f"Помилка при обробці кнопки 'Відповісти' для user_id={user_id}, question_id={question_id}: {e}")
        await callback.message.edit_text("⚠️ Помилка при обробці питання. Зверніться до розробника.")
        await callback.answer()

# 🟢 Обробка відповіді адміна
@router.message(Form.answer)
async def process_answer(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    answer_text = message.text.strip()
    data = await state.get_data()
    user_id = data.get("user_id")
    question_id = data.get("question_id")
    logging.info(f"Адмін {admin_id} надіслав відповідь для user_id={user_id}, question_id={question_id}: {answer_text}")

    if answer_text == "⬅️ Скасувати":
        await message.answer(
            "✅ Обробку відповіді скасовано.",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
        return

    if not answer_text:
        await message.answer(
            "⚠️ Будь ласка, напишіть текст відповіді.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Скасувати")]],
                resize_keyboard=True
            )
        )
        return

    try:
        # Надсилання відповіді користувачу
        await bot.send_message(
            chat_id=user_id,
            text=f"✉️ Відповідь від адміна: {answer_text}"
        )
        # Оновлення статусу питання в Supabase
        result = supabase.table("questions").update({
            "status": "answered",
            "answered_at": datetime.utcnow().isoformat(),
            "admin_id": admin_id,
            "answer_text": answer_text
        }).eq("question_id", question_id).eq("user_id", user_id).execute()
        logging.info(f"Оновлення статусу питання в Supabase: {result.data}")

        if not result.data:
            logging.error(f"Не вдалося оновити питання в Supabase для user_id={user_id}, question_id={question_id}")
            await message.answer("⚠️ Помилка при збереженні відповіді. Спробуйте ще раз.")
            return

        # Оновлення повідомлення в адмінському чаті
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"✅ Відповідь надіслано користувачу (ID: {user_id}) адміном {admin_id}:\n\n{answer_text}"
        )
        await message.answer(
            "✅ Відповідь успішно надіслано користувачу!",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
    except TelegramForbiddenError as e:
        logging.error(f"Помилка TelegramForbiddenError при надсиланні відповіді user_id={user_id}: {e}")
        await message.answer(
            "⚠️ Не вдалося надіслати відповідь користувачу (можливо, він заблокував бота).",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
    except Exception as e:
        logging.error(f"Помилка при надсиланні відповіді для user_id={user_id}: {e}")
        await message.answer(
            "⚠️ Виникла помилка при надсиланні відповіді. Спробуйте ще раз або зверніться до розробника.",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()

# 🟢 Обробка повернення до головного меню
@router.message(F.text == "⬅️ Назад")
async def handle_back(message: Message, state: FSMContext):
    await show_main_menu(message, state)

# 🟢 /help
@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    logging.info(f"Команда /допомога від користувача {message.from_user.id}")
    help_text = (
        "ℹ️ Це бот для подачі заявок на публікацію у спільноті *Митці ЮА*.\n\n"
        "Як це працює:\n"
        "1️⃣ Обери дію в головному меню після /start.\n"
        "2️⃣ Для публікації: вибери категорію, виконай умови (репост або надсилання друзям, підписка, заповнення анкети).\n"
        "3️⃣ Надішли дані одним повідомленням (нік, опис, соцмережі, зображення — якщо потрібно).\n"
        "4️⃣ Чекай на перевірку адміном.\n\n"
        "📜 Правила: /rules\n"
        f"📩 З питаннями: {' • '.join(ADMIN_CONTACTS)}"
    )
    await message.answer(
        help_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        )
    )

# 🟢 Обробка вибору категорії
@router.message(Form.category, lambda message: message.text in CATEGORIES)
async def handle_category_selection(message: Message, state: FSMContext):
    user_id = message.from_user.id
    category = message.text
    logging.info(f"Користувач {user_id} обрав категорію: {category}")

    # Перевірка підписки на канал
    subscription_status = await check_subscription(user_id)
    logging.info(f"Результат перевірки підписки для user_id={user_id}: {subscription_status}")
    if not subscription_status:
        await message.answer(
            "⚠️ Ви не підписані на наш канал! Будь ласка, підпишіться за посиланням: "
            "[Перейти до каналу](https://t.me/+bTmE3LOAMFI5YzBi) і спробуйте ще раз.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Я підписався(лась)")]],
                resize_keyboard=True
            )
        )
        return

    await state.update_data(category=category)
    # Якщо категорія "Оголошення / звернення", репост не обов’язковий
    if category == "📩 Оголошення / звернення":
        await message.answer(
            f"✅ Ви обрали категорію {category}: {CATEGORIES[category]}\n\n"
            f"📝 Надішли, будь ласка, цю інформацію одним повідомленням:\n\n"
            f"1. Короткий опис\n"
            f"2. Лінки на соцмережі (Instagram: @нік, Telegram: @нікнейм, Site: https://blablabla)\n\n"
            f"📌 Приклад:\n"
            f"Нік: @Artist\n"
            f"Опис: Шукаю партнерів для колаборації!\n"
            f"Соцмережі: Instagram: @artist, Telegram: @artist\n\n",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        await state.update_data(repost_platform="", repost_link="")  # Репост не потрібен
        await state.set_state(Form.description)
        return

    await message.answer(
        f"✅ Ви обрали категорію {category}: {CATEGORIES[category]}\n\n"
        f"🔄 Зроби репост [нашої спільноти](https://t.me/community_link) у соцмережі або надішли друзям\n"
        f"📝 Потім заповни анкету\n\n"
        f"Де ти поділився(лась) інформацією?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Соцмережа"), KeyboardButton(text="Надіслано друзям")],
                [KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True
        ),
        parse_mode="Markdown"
    )
    await state.set_state(Form.repost_platform)

# 🟢 Обробка вибору платформи для репосту
@router.message(Form.repost_platform)
async def process_repost_platform(message: Message, state: FSMContext):
    platform = message.text.strip()
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} обрав спосіб поширення: {platform}")

    if platform not in ["Соцмережа", "Надіслано друзям"]:
        await message.answer(
            "⚠️ Будь ласка, вибери один із запропонованих варіантів: 'Соцмережа' або 'Надіслано друзям'.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Соцмережа"), KeyboardButton(text="Надіслано друзям")],
                    [KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        return

    await state.update_data(repost_platform=platform)
    if platform == "Соцмережа":
        await message.answer(
            f"🔗 Будь ласка, надішли посилання на твій допис у соцмережі.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        await state.set_state(Form.repost_link)
    else:  # Надіслано друзям
        await message.answer(
            "✅ Дякуємо! Адмін скоро зв’яжеться з вами для перевірки доказів. Очікуйте!",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        await message.answer(
            f"📝 Тепер надішли, будь ласка, цю інформацію одним повідомленням:\n\n"
            f"1. Короткий опис\n"
            f"2. Лінки на соцмережі (Instagram: @нік, Telegram: @нікнейм, Site: https://blablabla)\n\n"
            f"📌 Приклад:\n"
            f"Нік: @Artist\n"
            f"Опис: Продаю персонажа, унікальний дизайн!\n"
            f"Соцмережі: Instagram: @artist, Telegram: @artist\n\n",
            parse_mode="Markdown"
        )
        await state.update_data(repost_link="")  # Зберігаємо порожнє посилання
        await state.set_state(Form.description)

# 🟢 Обробка посилання на репост
@router.message(Form.repost_link)
async def process_repost_link(message: Message, state: FSMContext):
    repost_link = message.text.strip()
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} надіслав посилання на допис: {repost_link}")

    if repost_link == "⬅️ Назад":
        await show_main_menu(message, state)
        return

    # Базова перевірка формату URL
    url_pattern = re.compile(
        r'^(https?://)?'  # Протокол (http:// або https://)
        r'([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'  # Домен
        r'(/.*)?$'  # Шлях (опціонально)
    )
    if not url_pattern.match(repost_link):
        await message.answer(
            "⚠️ Посилання виглядає некоректним. Будь ласка, надішли правильне посилання на допис (наприклад, https://www.instagram.com/..., https://t.me/...).",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        return

    await state.update_data(repost_link=repost_link)
    await message.answer(
        f"✅ Дякуємо за репост! Тепер надішли, будь ласка, цю інформацію одним повідомленням:\n\n"
        f"1. Короткий опис\n"
        f"2. Лінки на соцмережі (Instagram: @нік, Telegram: @нікнейм, Site: https://blablabla)\n\n"
        f"📌 Приклад:\n"
        f"Нік: @Artist\n"
        f"Опис: Продаю персонажа, унікальний дизайн!\n"
        f"Соцмережі: Instagram: @artist, Telegram: @artist\n\n",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        ),
        parse_mode="Markdown"
    )
    await state.set_state(Form.description)

# 🟢 Опис та соцмережі одним повідомленням
@router.message(Form.description)
async def get_description_and_socials(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} надіслав анкету: {message.text}")

    if message.text == "⬅️ Назад":
        await show_main_menu(message, state)
        return

    if not message.text:
        await message.answer(
            "⚠️ Будь ласка, надішли опис та соцмережі одним повідомленням.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        return

    try:
        # Приймаємо текст як є
        description_text = message.text.strip()
        # Розділяємо на нікнейм, опис і соцмережі (якщо можливо)
        lines = description_text.split('\n')
        nickname = lines[0].strip() if lines else ""
        description = lines[1].strip() if len(lines) > 1 else description_text
        socials = '\n'.join(lines[2:]).strip() if len(lines) > 2 else ""

        await state.update_data(nickname=nickname, description=description, socials=socials)
        await message.answer(
            "📸 Хочете додати зображення до заявки? Оберіть варіант:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Надіслати без фото"), KeyboardButton(text="Додати фото")],
                    [KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.images)
    except Exception as e:
        logging.error(f"Помилка обробки повідомлення для user_id={user_id}: {str(e)}\n{traceback.format_exc()}")
        await message.answer(
            "⚠️ Помилка обробки повідомлення. Спробуй ще раз.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )

@router.message(Form.images, F.text == "Надіслати без фото")
async def submit_without_photos(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} обрав 'Надіслати без фото'")
    await finish_submission(message.from_user, state, photos=[])

@router.message(Form.images, F.text == "/done")
async def done_images(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    category = data.get("category", "")
    logging.info(f"Користувач {message.from_user.id} завершив надсилання зображень: {photos}, категорія: {category}")

    await finish_submission(message.from_user, state, photos)

@router.message(Form.images, F.photo)
async def get_images(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    logging.info(f"Користувач {message.from_user.id} надіслав зображення: {message.photo[-1].file_id}")

    if len(photos) >= 5:
        await finish_submission(message.from_user, state, photos)
    else:
        await state.update_data(photos=photos)
        await message.answer(
            f"Зображення прийнято ({len(photos)}/5). Надішли ще або натисни /done.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="/done"), KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
    
# ✅ Фінальна обробка заявки
async def finish_submission(user: types.User, state: FSMContext, photos: list):
    data = await state.get_data()
    submission_id = str(uuid.uuid4())  # Унікальний ідентифікатор заявки
    logging.info(f"Фінальна обробка заявки від користувача {user.id}, submission_id={submission_id}. Дані: {data}, Фото: {photos}")

    # Перевірка наявності даних
    if not data.get("category") or not data.get("nickname") or not data.get("description") or not data.get("socials"):
        logging.error(f"Неповні дані в стані для user_id={user.id}: {data}")
        await bot.send_message(user.id, "⚠️ Помилка: неповні дані заявки. Будь ласка, заповніть анкету ще раз.")
        await state.clear()
        return

    text = (
        f"📥 <b>Нова заявка від</b> <a href=\"tg://user?id={user.id}\">{user.username or user.first_name}</a>\n"
        f"<b>Категорія:</b> {data['category']}\n"
        f"<b>Спосіб поширення:</b> {data.get('repost_platform', 'Невказано')}\n"
        f"<b>Посилання на допис:</b> {data.get('repost_link', 'Невказано')}\n"
        f"<b>Нік:</b> {data.get('nickname', 'Невказано')}\n"
        f"<b>Опис:</b> {data.get('description', 'Невказано')}\n"
        f"<b>Соцмережі:</b>\n{data.get('socials', 'Невказано')}\n"
        f"#public"
    )

    try:
        logging.info(f"Надсилання заявки в адмінський чат {ADMIN_CHAT_ID}")
        if photos:
            media = [InputMediaPhoto(media=photos[0], caption=text, parse_mode="HTML")]
            for p in photos[1:]:
                media.append(InputMediaPhoto(media=p))
            media_message = await bot.send_media_group(chat_id=ADMIN_CHAT_ID, media=media)
            media_message_ids = [msg.message_id for msg in media_message]
        else:
            media_message_ids = []
            media_message = await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="HTML")
            media_message_ids.append(media_message.message_id)

        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="✅ Опублікувати", callback_data=f"approve:{user.id}:{submission_id}")
        keyboard.button(text="❌ Відмовити", callback_data=f"reject:{user.id}:{submission_id}")
        markup = keyboard.as_markup()

        await bot.send_message(chat_id=ADMIN_CHAT_ID, text="🔎 Оберіть дію:", reply_markup=markup)
    except TelegramBadRequest as e:
        logging.error(f"Помилка TelegramBadRequest при надсиланні в адмінський чат: {str(e)}\n{traceback.format_exc()}")
        await bot.send_message(user.id, "⚠️ Помилка при надсиланні заявки адмінам (BadRequest). Зверніться до @AdminUsername.")
        await state.clear()
        return
    except TelegramForbiddenError as e:
        logging.error(f"Помилка TelegramForbiddenError: бот не має доступу до адмінського чату {ADMIN_CHAT_ID}: {str(e)}\n{traceback.format_exc()}")
        await bot.send_message(user.id, "⚠️ Помилка: бот не може надіслати заявку адмінам (Forbidden). Зверніться до @AdminUsername.")
        await state.clear()
        return
    except Exception as e:
        logging.error(f"Невідома помилка при надсиланні в адмінський чат: {str(e)}\n{traceback.format_exc()}")
        await bot.send_message(user.id, "⚠️ Помилка при надсиланні заявки адмінам. Зверніться до @AdminUsername.")
        await state.clear()
        return

    try:
        logging.info(f"Збереження заявки в Supabase для користувача {user.id}, submission_id={submission_id}")
        submission_data = {
            "user_id": user.id,
            "username": user.username or user.first_name,
            "category": data["category"],
            "repost_platform": data.get("repost_platform", ""),
            "repost_link": data.get("repost_link", ""),
            "nickname": data.get("nickname", ""),
            "description": data.get("description", ""),
            "socials": data.get("socials", ""),
            "images": photos,
            "status": "pending",
            "submitted_at": datetime.utcnow().isoformat(),
            "submission_id": submission_id,
            "media_message_ids": media_message_ids
        }
        result = supabase.table("submissions").insert(submission_data).execute()
        logging.info(f"Результат вставки в Supabase: {result.data}")

        if not result.data:
            logging.error(f"Не вдалося вставити заявку в Supabase для user_id={user.id}, submission_id={submission_id}. Дані: {submission_data}")
            await bot.send_message(user.id, "⚠️ Помилка при збереженні заявки в базі даних. Зверніться до @AdminUsername.")
            await state.clear()
            return

        logging.info(f"Заявка успішно збережена в Supabase")
        await bot.send_message(user.id, "✅ Заявка успішно надіслана на перевірку!")
        await state.clear()
    except Exception as e:
        logging.error(f"Помилка при збереженні в Supabase: {str(e)}\n{traceback.format_exc()}")
        await bot.send_message(user.id, f"⚠️ Помилка при збереженні заявки: {str(e)}. Зверніться до @AdminUsername.")
        await state.clear()
        return

# 🟢 Схвалення посту
@router.callback_query(lambda c: c.data.startswith("approve:"))
async def approve_post(callback: CallbackQuery):
    logging.info(f"Callback approve отриманий від адміна {callback.from_user.id}, дані: {callback.data}")
    parts = callback.data.split(":")
    user_id = int(parts[1])  # Залишаємо int, оскільки user_id у базі — BIGINT
    submission_id = parts[2]
    logging.info(f"Адмін {callback.from_user.id} схвалив заявку для користувача {user_id}, submission_id={submission_id}")

    try:
        # Перевірка існування заявки
        logging.info(f"Перевірка існування заявки в Supabase для user_id={user_id}, submission_id={submission_id}")
        check_submission = supabase.table("submissions").select("*").eq("user_id", user_id).eq("submission_id", submission_id).execute()
        if not check_submission.data:
            logging.error(f"Заявка для user_id={user_id}, submission_id={submission_id} не знайдена в таблиці submissions")
            await callback.message.edit_text("⚠️ Заявку не знайдено в базі даних. Можливо, вона була видалена.")
            await callback.answer()
            return

        # Оновлення статусу заявки та очищення даних
        logging.info(f"Оновлення статусу заявки в Supabase для user_id={user_id}, submission_id={submission_id}")
        result = supabase.table("submissions").update({
            "status": "approved",
            "moderated_at": datetime.utcnow().isoformat(),
            "moderator_id": callback.from_user.id,
            "description": None,
            "socials": None,
            "images": None,
            "repost_platform": None,
            "repost_link": None,
            "nickname": None
        }).eq("user_id", user_id).eq("submission_id", submission_id).execute()
        logging.info(f"Результат оновлення Supabase: {result.data}")

        if not result.data:
            logging.warning(f"Оновлення не змінило жодного рядка для user_id={user_id}, submission_id={submission_id}")
            await callback.message.edit_text("⚠️ Не вдалося оновити статус заявки. Перевірте, чи існує заявка.")
            await callback.answer()
            return

        # Додаємо невелику затримку для забезпечення синхронізації
        await asyncio.sleep(0.5)

        # Повторна перевірка схваленої заявки
        logging.info(f"Отримання схваленої заявки для user_id={user_id}, submission_id={submission_id}")
        submission = supabase.table("submissions").select("*").eq("user_id", user_id).eq("submission_id", submission_id).eq("status", "approved").execute()
        logging.info(f"Отримані дані заявки: {submission.data}")

        if not submission.data:
            logging.error(f"Схвалена заявка для user_id={user_id}, submission_id={submission_id} не знайдена після оновлення")
            await callback.message.edit_text("⚠️ Не вдалося знайти схвалену заявку. Можливо, оновлення статусу не відбулося.")
            await callback.answer()
            return

        data = submission.data[0]
        post_text = (
            f"📢 <b>{data['category']}</b>\n\n"
            f"{data['description'] or 'Опис відсутній'}\n\n"
            f"🌐 <b>Соцмережі:</b>\n{data['socials'] or 'Невказано'}\n"
            f"👤 Від: <a href=\"tg://user?id={user_id}\">{data['username']}</a>\n"
            f"#public"
        )

        if data["images"]:
            media = [InputMediaPhoto(media=data["images"][0], caption=post_text, parse_mode="HTML")]
            for photo in data["images"][1:]:
                media.append(InputMediaPhoto(media=photo))
            await bot.send_media_group(chat_id=MAIN_CHAT_ID, media=media)
        else:
            await bot.send_message(chat_id=MAIN_CHAT_ID, text=post_text, parse_mode="HTML")

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
        logging.error(f"Невідома помилка при обробці схвалення: {e}")
        await callback.message.edit_text("⚠️ Помилка при схваленні заявки. Зверніться до розробника.")
        await callback.answer()

# 🟢 Відхилення посту
@router.callback_query(lambda c: c.data.startswith("reject:"))
async def reject_post(callback: CallbackQuery):
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
            "rejection_reason": "Невідповідність вимогам",
            "description": None,
            "socials": None,
            "images": None,
            "repost_platform": None,
            "repost_link": None,
            "nickname": None
        }).eq("user_id", user_id).eq("submission_id", submission_id).execute()
        logging.info(f"Результат оновлення Supabase: {result.data}")
        await callback.message.edit_text("❌ Публікацію відхилено.")
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
    logging.exception(f"Виникла помилка при обробці оновлення {getattr(update, 'update_id', 'невідоме')}: {exception}")
    try:
        if update and hasattr(update, 'callback_query'):
            await update.callback_query.answer("⚠️ Виникла помилка. Спробуйте ще раз.")
        elif update and hasattr(update, 'message'):
            await update.message.answer(
                "⚠️ Виникла помилка при обробці вашого запиту. Спробуйте ще раз або зверніться до @AdminUsername.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True
                )
            )
    except Exception as e:
        logging.error(f"Помилка при надсиланні повідомлення про помилку: {e}")
    return True

# Запуск фонової задачі при старті
dp.startup.register(on_startup)
