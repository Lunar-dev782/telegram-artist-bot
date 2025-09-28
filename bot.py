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
import html
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
from aiogram.types import Update


# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s - %(message)s')

# 🔐 Токен бота
TOKEN = "8190742713:AAFu6-6hM3C9ZIAho2eNmlYz8drJni61OdM"
ADMIN_CHAT_ID = -1003034016408
MAIN_CHAT_ID = -1002440054241
ADMIN_CONTACTS = ["@Admin1", "@Admin2"]

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
    main_menu = State()
    category = State()
    repost_platform = State()
    repost_link = State()
    description = State()
    images = State()
    question = State()
    awaiting_answer = State()

# 📋 Категорії та їх хештеги
CATEGORIES = {
    "💰 Платні послуги⚓": {
        "description": (
            "🏴‍☠️ <b>Тут матроси виставляють творчі послуги за оплату.</b>\n"
            "🦜 Сквааак! Основні вимоги — Зроби репост "
            "<a href='https://t.me/mytci_ua/14'>нашої спільноти</a> 🦜\n"
            "— Додай опис та посилання.\n"
            "— 18+ — під цензуру.\n"
            "— Додай прайс-лист (мінімум 50 грн).\n"
            "— Приклади робіт і дедлайни.\n"
            "— Вкажи способи оплати.\n"
            "— Російські та проросійські фандоми — <u>за борт</u>!\n\n"
        ),
        "hashtag": "#ТворчіПропозиції",
        "repost": True,
        "anonymous": False
    },
    "📣 Промо соцмереж🏴‍☠": {
        "description": (
            "🦜 <b>Тут рекламують свої арт-сторінки та профілі.</b>\n"
            "🦜 Сквааак! Основні вимоги — Зроби репост "
            "<a href='https://t.me/mytci_ua/14'>нашої спільноти</a> 🦜\n"
            "— Додай опис та посилання.\n"
            "— 18+ — ховаємо під цензуру.\n"
            "— Додай посилання на свій порт.\n"
            "— Жодної аморальщини!\n"
            "— Російська мова та проросійські фандоми — за борт!\n\n"
        ),
        "hashtag": "#ПромоСоцмереж",
        "repost": True,
        "anonymous": False
    },
    "🎉Активності🦜": {
        "description": (
            "⚓ <b>Тут організовують конкурси, челенджі та івенти.</b>\n"
            "🦜 Сквааак! Основні вимоги — Зроби репост "
            "<a href='https://t.me/mytci_ua/14'>нашої спільноти</a> 🦜\n"
            "— Додай опис та посилання.\n"
            "— 18+ — під цензуру.\n"
            "— Додай опис, банер і посилання.\n"
            "— Жодної проросійщини та російських фандомів!\n"
        ),
        "hashtag": "#ТворчіАктивності",
        "repost": True,
        "anonymous": False
    },
    "🖋Критики/Фідбеку🔎": {
        "description": (
            "📜 <b>Якщо шукаєш критики чи поради — тобі сюди.</b>\n"
            "🦜 Сквааак! Основні вимоги:\n"
            "— Напишіть ваше звернення чи питання.\n"
            "— 18+ — під цензуру.\n"
            "— Без сторонніх посилань.\n"
            "— Жодної аморальності чи цькувань.\n"
            "— Російські та проросійські фандоми — за борт!\n"
        ),
        "hashtag": "#ПошукФідбеку",
        "repost": False,
        "anonymous": True
    },
    "📢Пошук/Корисності🏴‍☠": {
        "description": (
            "🔔 <b>Тут матроси діляться корисною або цікавою інформацією, шукають помічників, пишуть відгуки або задають питання екіпажу.</b>\n"
            "🦜 Сквааак! Основні вимоги:\n"
            "— Додай опис або посилання.\n"
            "— Дотримуйся правил безпечної гавані.\n"
            "— Лише перевірена інформація.\n"
            "— Без образ та аморальщини.\n\n"
        ),
        "hashtag": "#Корисне",
        "repost": False,
        "anonymous": True
    },
    "🌟Інше🧭": {
        "description": (
            "🗺️ <b>Тут усе інше творчого характеру.</b>\n"
            "🦜 Сквааак! Основні вимоги:\n"
            "— Додай опис та посилання.\n"
            "— Дотримуйся загальних правил корабля.\n"
            "— 18+ — під цензуру.\n"
            "— Жодної проросійщини та аморальності.\n"
            "— Якщо сумніваєшся — звернись до нашої команди.\n"
        ),
        "hashtag": "#ТворчийМікс",
        "repost": False,
        "anonymous": False
    }
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
        await asyncio.sleep(3600)

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
        subscription_status = await check_subscription(user_id)
        logging.info(f"Результат перевірки підписки для user_id={user_id}: {subscription_status}")
        if not subscription_status:
            await message.answer(
                "🦜 Сквааак!Ви не підписані на наш канал! Будь ласка, підпишіться за посиланням: "
                "<a href='https://t.me/mytci_ua'>Перейти до каналу</a> і натисніть 'Я підписався(лась). Скваак!'.",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="Я підписався(лась)")]],
                    resize_keyboard=True
                )
            )
            await state.clear()
            return

        await message.answer(
            "🎨 <b>🦜 Сквааак! Привіт, матросе!</b>\n\n"
"<i>Ти на борту Митецького Порту ім. Капітанки М’юз!</i>\n\n"
"Я — вірний папуга Капітанки, <b>глашатай і писар</b> цього корабля. <b>Сквааак!</b>\n\n"
"📌 Якщо маєш <b>пост чи новину</b> для екіпажу — кидай мені в дзьоб, а я віднесу на <u>дошку оголошень</u>!\n\n"
"⚠️ <b>Пам’ятай:</b> тримай контент у межах нашого уставу, бо інакше отримаєш <i>скваак-догану</i>! 🏴‍☠️",
            parse_mode="HTML",
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
        logging.error(f"Помилка в show_main_menu для user_id={user_id}: {str(e)}\n{traceback.format_exc()}")
        await message.answer(
            "🦜Виникла помилка. Сквааак! Спробуйте ще раз або зверніться до <code>@tina263678</code>.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.main_menu)




# 🟢 Запуск фонової задачі очищення
async def on_startup():
    asyncio.create_task(cleanup_old_submissions())

from datetime import datetime

# 🟢 /start
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user

    # Реєстрація користувача в таблиці users
    try:
        supabase.table("users").upsert({
            "user_id": user.id,
            "telegram_username": user.username or None,
            "full_name": user.full_name,
            "updated_at": datetime.utcnow()
        }, on_conflict=["user_id"]).execute()
    except Exception as e:
        logging.error(f"Не вдалося зареєструвати користувача {user.id} у таблиці users: {e}")

    await show_main_menu(message, state)


# дубль для тексту "start"
@router.message(F.text.lower() == "start")
async def cmd_pochnimo(message: Message, state: FSMContext):
    await cmd_start(message, state)


@router.message(F.text == "Я підписався(лась)")
async def check_subscription_again(message: Message, state: FSMContext):
    await cmd_start(message, state)


 # 🟢 Обробка /rules або кнопки "📜 Правила"
@router.message(Form.main_menu, F.text == "📜 Правила")
@router.message(Command("rules"))
async def cmd_rules(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Команда або кнопка /правила від користувача {user_id}")

    rules_text = (
        "<b>🦜 Сквааак! Читай уважно!</b>\n\n"

        "📌 <b>Правила для матросів:</b>\n"
        "1. Категорії: вибирай уважно, читай умови.\n"
        "2. Авторство: пости тільки свої скарби! Заборонено чужі та генеративні.\n"
        "3. Оформлення: до 5 картинок, короткий опис, соцмережі за бажанням.\n"
        "4. Частота: максимум 2 «пограбування» на тиждень.\n"
        "5. Підтримка: репост "
        "<a href='https://t.me/mytci_ua/14'>[Натисни тут🦜]</a> або поділись ботом з трьома друзями.\n\n"

        "🚫 <b>Заборонено:</b>\n"
        "— NSFW без блюру/згоди\n"
        "— 18+ тільки з позначкою\n"
        "— Токсичність, реклама без дозволу\n"
        "— Порушення законів і авторських прав\n"
        "— Російська мова у постах\n\n"

        "🤖 <b>Бот:</b>\n"
        "— Дотримуйся анкети, крок за кроком\n"
        "— Якщо завис — напиши /start або пиши @tina263678\n"
        "— Спам = скваак-догана 🦜\n\n"

        "🛠 <b>Модератори:</b>\n"
        "— Мають право: відхиляти пости, видавати бан або обмеження\n\n"

        "❓ Питання? Пиши в наш чат\n"
        "🔗 Повна версія правил: <a href='https://t.me/mytci_ua/14'>[тут]</a>"
    )

    await message.answer(rules_text, parse_mode="HTML")
    await state.set_state(Form.main_menu)

# 🟢 Глобальний обробник кнопки "Назад"
@router.message(F.text == "⬅️ Назад")
async def handle_back(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Глобальний обробник: користувач {user_id} натиснув 'Назад'")
    
    # завжди очищаємо стан, щоб не залипали попередні анкети
    await state.clear()
    
    # показуємо головне меню
    await show_main_menu(message, state)


# 🟢 Обробка "Запропонувати пост"
@router.message(Form.main_menu, F.text == "📝 Запропонувати пост")
async def handle_propose_post(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} обрав 'Запропонувати пост'")

    try:
        seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        recent_submissions = supabase.table("submissions").select("submitted_at").eq("user_id", user_id).gte("submitted_at", seven_days_ago).execute()
        if len(recent_submissions.data) >= 2:
            await message.answer(
                "Скваак! Ви можете подавати не більше 2 заявок на тиждень. Спробуйте пізніше!",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True
                )
            )
            await state.set_state(Form.main_menu)
            return

        await message.answer(
            "🎨 <b>Обери категорію для публікації:</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=cat)] for cat in CATEGORIES.keys()] + [[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.category)
    except Exception as e:
        logging.error(f"Помилка в handle_propose_post для user_id={user_id}: {e}")
        await message.answer(
            "⚠️ Виникла помилка. Спробуйте ще раз або зверніться до <code>@tina263678</code>.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.main_menu)

# 🟢 Обробка "Інші питання"
@router.message(Form.main_menu, F.text == "❓ Інші питання")
async def handle_other_questions(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} обрав 'Інші питання'")
    await message.answer(
        f"❓ <b>Сквааак! Якщо у тебе є питання, кидай його в мій дзьоб 🦜 , "
        f"і ми відповімо протягом доби!</b>\n\n",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        )
    )
    await state.set_state(Form.question)


# 🟢 Обробка питань до адмінів
@router.message(Form.question)
async def process_question(message: Message, state: FSMContext):
    user_id = message.from_user.id
    question = message.text.strip()
    logging.info(f"Користувач {user_id} надіслав питання: {question}")

    if message.text and message.text.strip() == "⬅️ Назад":
        logging.info(f"Користувач {user_id} натиснув 'Назад' у стані Form.question")
        await show_main_menu(message, state)
        return

    if not question:
        await message.answer(
            "🦜Скваак! Будь ласка, напишіть ваше питання.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        return

    try:
        question_id = str(uuid.uuid4())
        logging.info(f"Створення питання з question_id={question_id}")

        user_display_name = (message.from_user.full_name or "Користувач").replace("<", "&lt;").replace(">", "&gt;")
        question_data = {
            "question_id": question_id,
            "user_id": user_id,
            "username": user_display_name,
            "question_text": question,
            "status": "pending",
            "submitted_at": datetime.utcnow().isoformat()
        }
        logging.info(f"Підготовлені дані для вставки в таблицю questions: {question_data}")

        result = supabase.table("questions").insert(question_data).execute()
        logging.info(f"Результат вставки в Supabase: {result.data}")
        if not result.data:
            raise ValueError("Не вдалося зберегти питання в Supabase: порожній результат")

        await message.answer(
            "🦜 <b>Сквааак! Твоє питання кинуто в мій дзьоб! "
            "Очікуй відповіді протягом доби.</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.main_menu)
    except Exception as e:
        logging.error(f"Загальна помилка при обробці питання від user_id={user_id}: {str(e)}\n{traceback.format_exc()}")
        await message.answer(
            f"⚠️ Виникла помилка при надсиланні питання: {str(e)}. Спробуйте ще раз або зверніться до <code>@AdminUsername</code>.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.main_menu)

# 🟢 Універсальний обробник команд
@router.message(Command(commands=["start", "rules", "help", "питання", "код"]))
async def handle_commands(message: Message, state: FSMContext):
    user_id = message.from_user.id
    command = message.text.split()[0].lstrip("/").lower()
    logging.info(f"DEBAG: Початок обробки команди /{command} для user_id={user_id}, повний текст: {message.text}")

    # Очищаємо стан для уникнення конфліктів
    await state.clear()
    logging.info(f"DEBAG: Стан очищено для user_id={user_id}")

    try:
        if command == "start":
            logging.info(f"DEBAG: Виконується команда /start для user_id={user_id}")
            await show_main_menu(message, state)
        elif command == "rules":
            logging.info(f"DEBAG: Виконується команда /rules для user_id={user_id}")
            await cmd_rules(message, state)
        elif command == "help":
            logging.info(f"DEBAG: Виконується команда /help для user_id={user_id}")
            await cmd_help(message, state)
        elif command == "питання":
            logging.info(f"DEBAG: Адмін {user_id} використав команду /питання")
            admin_check = supabase.table("admins").select("admin_id").eq("admin_id", user_id).execute()
            if not admin_check.data:
                logging.warning(f"Користувач {user_id} не є адміном")
                await message.answer("⚠️ У вас немає доступу до цієї команди.")
                return

            question = supabase.table("questions").select("*").eq("status", "pending").order("submitted_at", desc=False).limit(1).execute()
            logging.info(f"DEBAG: Результат запиту до questions для admin_id={user_id}: {question.data}")
            if not question.data:
                await message.answer("ℹ️ Наразі немає нових питань.")
                return

            question_data = question.data[0]
            user_id_question = question_data["user_id"]
            question_id = question_data["question_id"]
            username = question_data["username"]
            question_text = question_data["question_text"]

            message_text = (
                f"❓ Питання від <b>{username}</b> (ID: {user_id_question}):\n\n"
                f"{question_text}"
            )
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="✉️ Відповісти", callback_data=f"answer:{user_id_question}:{question_id}")
            keyboard.button(text="⏭️ Пропустити", callback_data=f"skip:{user_id_question}:{question_id}")
            keyboard.button(text="🗑️ Видалити", callback_data=f"delete:{user_id_question}:{question_id}")
            markup = keyboard.as_markup()

            await message.answer(
                message_text,
                parse_mode="HTML",
                reply_markup=markup
            )
        elif command == "код":
            logging.info(f"DEBAG: Адмін {user_id} ввів команду /код: {message.text}")
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await message.answer("⚠️ Введіть код. Використовуйте: /код <код>")
                return

            code = parts[1].strip()
            logging.info(f"DEBAG: Введено код {code} для user_id={user_id}")
            if code != "12345":
                logging.warning(f"Невірний код від admin_id={user_id}: {code}")
                await message.answer("⚠️ Невірний код. Спробуйте ще раз.")
                return

            existing_admin = supabase.table("admins").select("admin_id").eq("admin_id", user_id).execute()
            logging.info(f"DEBAG: Перевірка наявності адміна для user_id={user_id}: {existing_admin.data}")
            if existing_admin.data:
                await message.answer("✅ Ви вже авторизовані.")
                return

            admin_data = {
                "admin_id": user_id,
                "added_at": datetime.utcnow().isoformat()
            }
            result = supabase.table("admins").insert(admin_data).execute()
            logging.info(f"DEBAG: Адмін {user_id} доданий до таблиці admins: {result.data}")
            if not result.data:
                raise ValueError("Не вдалося додати адміна до бази даних")

            await message.answer("✅ Ви успішно авторизовані як адмін! Використовуйте /питання для перегляду питань.")
    except Exception as e:
        logging.error(f"Помилка при обробці команди /{command} для user_id={user_id}: {str(e)}\n{traceback.format_exc()}")
        await message.answer(
            "⚠️ Виникла помилка при обробці команди. Спробуйте ще раз або зверніться до <code>@AdminUsername</code>.",
            parse_mode="HTML"
        )
    finally:
        logging.info(f"DEBAG: Завершення обробки команди /{command} для user_id={user_id}")

# 🟢 Обробник невідомих команд тільки в головному меню
@router.message(StateFilter(Form.main_menu), F.text.startswith("/"))
async def handle_unknown_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    command = message.text.split()[0].lstrip("/").lower()
    logging.info(f"DEBAG: Користувач {user_id} ввів невідому команду /{command}")
    
    await message.answer(
        "⚠️ <b>Невідома команда.</b> Використовуйте /start, /rules, /help або оберіть дію з меню.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📜 Правила"), KeyboardButton(text="📝 Запропонувати пост")],
                [KeyboardButton(text="❓ Інші питання")]
            ],
            resize_keyboard=True
        )
    )
    # лишаємо користувача в головному меню
    await state.set_state(Form.main_menu)


# 🟢 Обробка головного меню (некоректні дії)
@router.message(Form.main_menu)
async def handle_invalid_main_menu(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()
    logging.info(f"Користувач {user_id} надіслав дію у стані Form.main_menu: {text}, тип контенту: {message.content_type}")

    # Обробка кнопки "Назад"
    if text == "⬅️ Назад":
        logging.info(f"Користувач {user_id} натиснув 'Назад' у стані Form.main_menu")
        await show_main_menu(message, state)
        return

    # Відповідь на некоректний ввід
    await message.answer(
        "🦜Сквааак! <b>Виберіть дію з головного меню.</b>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📜 Правила"), KeyboardButton(text="📝 Запропонувати пост")],
                [KeyboardButton(text="❓ Інші питання")]
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(Form.main_menu)

# ===== СТАНИ =====
class AdminAnswer(StatesGroup):
    awaiting_answer = State()

# ===== УНІВЕРСАЛЬНА ПЕРЕВІРКА АДМІНА =====
async def is_admin(admin_id: int) -> bool:
    result = supabase.table("admins").select("admin_id").eq("admin_id", admin_id).execute()
    return bool(result.data)

# ===== ОБРОБКА КНОПОК (ВІДПОВІДЬ / ПРОПУСК / ВИДАЛЕННЯ) =====
@router.callback_query(F.data.startswith(("answer:", "skip:", "delete:")))
async def handle_question_buttons(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("⚠️ Некоректний формат даних.")
        return

    action, user_id_str, question_id = parts
    try:
        user_id = int(user_id_str)
    except ValueError:
        await callback.answer("⚠️ Некоректний user_id.")
        return

    if not await is_admin(admin_id):
        await callback.answer("⚠️ У вас немає доступу.")
        return

    question_res = supabase.table("questions").select("*").eq("question_id", question_id).eq("user_id", user_id).execute()
    if not question_res.data:
        await callback.answer("⚠️ Питання не знайдено або вже оброблено.")
        return

    q_data = question_res.data[0]
    question_text = q_data["question_text"]
    user_name = q_data.get("username", "Користувач")
    clickable_user = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"

    if action == "answer":
        await callback.message.answer(
            f"Введіть відповідь для {clickable_user}:\n\n{html.escape(question_text)}",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Скасувати")]],
                resize_keyboard=True
            )
        )
        await state.set_state(AdminAnswer.awaiting_answer)
        await state.update_data(user_id=user_id, question_id=question_id, question_text=question_text)
        await callback.answer()
        return

    elif action == "skip":
        try:
            supabase.table("questions").update({"status": "skipped"}).eq("question_id", question_id).eq("user_id", user_id).execute()
        except Exception as e:
            await callback.answer(f"⚠️ Помилка при пропуску: {e}")
            return
        await callback.answer("⏭ Питання пропущено.")
        await send_next_question(admin_id)
        return

    elif action == "delete":
        try:
            supabase.table("questions").delete().eq("question_id", question_id).eq("user_id", user_id).execute()
        except Exception as e:
            await callback.answer(f"⚠️ Помилка при видаленні: {e}")
            return
        await callback.answer("🗑 Питання видалено.")
        await send_next_question(admin_id)
        return

# ===== ОБРОБКА ВІДПОВІДІ АДМІНА =====
@router.message(AdminAnswer.awaiting_answer)
async def process_answer(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    answer_text = message.text.strip()

    if answer_text == "⬅️ Скасувати":
        await message.answer("✅ Введення відповіді скасовано.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        await send_next_question(admin_id)
        return

    if not answer_text:
        await message.answer("⚠️ Текст відповіді не може бути порожнім.")
        return

    data = await state.get_data()
    user_id = data["user_id"]
    question_id = data["question_id"]
    question_text = data["question_text"]

    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"🦜Скваак! <b>Відповідь на ваше питання:</b>\n\n{html.escape(question_text)}\n\n<b>Відповідь:</b> {html.escape(answer_text)}",
            parse_mode="HTML"
        )
        # Видаляємо питання з бази даних після надсилання відповіді
        supabase.table("questions").delete().eq("question_id", question_id).eq("user_id", user_id).execute()
    except Exception as e:
        await message.answer(f"⚠️ Неможливо надіслати повідомлення: {e}")
        await state.clear()
        return

    await message.answer("✅ Відповідь надіслано. 🦜Скваак!.", reply_markup=ReplyKeyboardRemove())

    cont_buttons = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➡️ Продовжити", callback_data="continue_answering"),
            InlineKeyboardButton(text="⛔ Зупинитись", callback_data="stop_answering")
        ]
    ])
    await message.answer("Виберіть дію:", reply_markup=cont_buttons)
    await state.clear()

# ===== ПРОДОВЖЕННЯ / ЗУПИНКА СЕАНСУ =====
@router.callback_query(F.data == "continue_answering")
async def continue_answering(callback: CallbackQuery):
    await callback.answer()
    await send_next_question(callback.from_user.id)

@router.callback_query(F.data == "stop_answering")
async def stop_answering(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("⛔ Ви завершили сеанс відповідей.")
    await callback.message.edit_text("✅ Сеанс завершено.")

# ===== ВІДПРАВКА НАСТУПНОГО ПИТАННЯ =====
async def send_next_question(admin_id: int):
    pending_qs = supabase.table("questions").select("*").in_("status", ["pending", "skipped"]).order("submitted_at").execute()
    if not pending_qs.data:
        cont_buttons = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➡️ Почати спочатку", callback_data="restart_answering"),
                InlineKeyboardButton(text="⛔ Завершити сеанс", callback_data="stop_answering")
            ]
        ])
        await bot.send_message(admin_id, "✅ Нових питань немає.", reply_markup=cont_buttons)
        return

    next_q = pending_qs.data[0]
    total = len(pending_qs.data)
    user_name = next_q.get('username', 'Користувач')
    clickable_user = f"<a href='tg://user?id={next_q['user_id']}'>{html.escape(user_name)}</a>"

    # 🔽 Ось тут формується текст питання:
    text = (
        f"📩 Питання від {clickable_user} (1/{total}):\n\n"
        f"<b>Текст питання:</b>\n{html.escape(next_q['question_text'])}"
    )
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Відповісти", callback_data=f"answer:{next_q['user_id']}:{next_q['question_id']}"),
            InlineKeyboardButton(text="⏭ Пропустити", callback_data=f"skip:{next_q['user_id']}:{next_q['question_id']}")
        ],
        [
            InlineKeyboardButton(text="🗑 Видалити", callback_data=f"delete:{next_q['user_id']}:{next_q['question_id']}"),
            InlineKeyboardButton(text="⛔ Зупинитись", callback_data="stop_answering")
        ]
    ])
    await bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=buttons)

# ===== ПЕРЕЗАПУСК СЕАНСУ =====
@router.callback_query(F.data == "restart_answering")
async def restart_answering(callback: CallbackQuery):
    await callback.answer("🔄 Сеанс розпочато заново.")
    await send_next_question(callback.from_user.id)


# 🟢 Команда /повідомлення для адміна (підтримує /повідомлення та /msg)
@router.message(lambda m: m.text and (m.text.startswith("/повідомлення") or m.text.startswith("/msg")))
async def send_message_to_user(message: Message):
    admin_id = message.from_user.id

    # 🔐 Перевірка чи є адміном
    admin_check = supabase.table("admins").select("admin_id").eq("admin_id", admin_id).execute()
    if not admin_check.data:
        await message.answer("⚠️ У вас немає доступу до цієї команди.")
        return

    # Розбір аргументів: /повідомлення <ціль> <текст>
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        # Уникаємо кутових дужок, бо бот має HTML-парсер за замовчуванням
        await message.answer("⚠️ Використовуйте формат:\n/повідомлення user_id або @юзернейм текст")
        return

    target = parts[1].strip()
    text = parts[2].strip()
    if not text:
        await message.answer("⚠️ Текст повідомлення не може бути порожнім.")
        return

    # 🎯 Знаходимо target_id у таблиці users
    target_id = None
    try:
        if target.startswith("@"):
            username = target.lstrip("@")
            user_lookup = supabase.table("users").select("user_id").eq("telegram_username", username).execute()
            if not user_lookup.data:
                await message.answer("⚠️ Не знайдено користувача з таким @username у базі.")
                return
            target_id = user_lookup.data[0]["user_id"]
        else:
            # спроба перетворити в int — якщо не число, повертаємо помилку
            try:
                target_id = int(target)
            except ValueError:
                await message.answer("⚠️ ID користувача має бути числом або @username.")
                return

            # перевірка наявності в users
            user_lookup = supabase.table("users").select("user_id").eq("user_id", target_id).execute()
            if not user_lookup.data:
                await message.answer("⚠️ У базі немає користувача з таким ID.")
                return
    except Exception as e:
        logging.exception("Помилка при пошуку користувача в таблиці users")
        await message.answer(f"⚠️ Помилка при пошуку користувача: {e}")
        return

    # ✉️ Надсилаємо повідомлення — ЕКРАНУЄМО HTML-символи
    safe_text = html.escape(text)
    message_to_send = f"📩 <b>Повідомлення від адміністрації:</b>\n\n{safe_text}"
    try:
        # явно вказуємо parse_mode="HTML" бо ми вже екранірували текст
        await bot.send_message(chat_id=target_id, text=message_to_send, parse_mode="HTML")
        await message.answer("✅ Повідомлення успішно надіслано.")
    except TelegramForbiddenError:
        await message.answer("⚠️ Неможливо надіслати повідомлення — користувач заблокував бота або закрив приватні повідомлення.")
    except TelegramBadRequest as e:
        logging.exception("TelegramBadRequest при відправці повідомлення")
        await message.answer(f"⚠️ Помилка при відправці повідомлення: {e}")
    except Exception as e:
        logging.exception("Невідома помилка при відправці повідомлення")
        await message.answer(f"⚠️ Не вдалося надіслати повідомлення: {e}")

  
# 🟢 Обробка вибору категорії
@router.message(Form.category)
async def handle_category_selection(message: Message, state: FSMContext):
    user_id = message.from_user.id
    category = message.text.strip()
    logging.info(f"Користувач {user_id} обрав категорію: {category}")

    if category == "⬅️ Назад":
        logging.info(f"Користувач {user_id} натиснув 'Назад' у стані Form.category")
        await show_main_menu(message, state)
        return

    if category not in CATEGORIES:
        await message.answer(
            "⚠️ <b>Будь ласка, виберіть категорію з запропонованих.</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=cat)] for cat in CATEGORIES.keys()] + [[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        return

    # Перевірка підписки
    subscription_status = await check_subscription(user_id)
    logging.info(f"Результат перевірки підписки для user_id={user_id}: {subscription_status}")
    if not subscription_status:
        await message.answer(
            "🦜Скваак! Порушення! За борт!⚠️ Ви не підписані на наш канал! Будь ласка, підпишіться за посиланням: "
            "<a href='https://t.me/+bTmE3LOAMFI5YzBi'>Перейдіть до каналу</a> і натисніть 'Я підписався(лась)'.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Я підписався(лась)")]],
                resize_keyboard=True
            )
        )
        await state.clear()
        return

    # Зберігаємо категорію у стан
    await state.update_data(category=category)
    category_config = CATEGORIES[category]

    # 🔹 Якщо потрібен репост
    if category_config.get("repost", False):
        await message.answer(
            f"🦜Скваак! Категорія <b>{category}</b>: {category_config['description']}\n"
            f"<b>Де ти поділився(лась) інформацією?</b>\n\n",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Соцмережа"), KeyboardButton(text="Надіслано друзям")],
                    [KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.repost_platform)

    # 🔹 Якщо репост НЕ потрібен
    else:
        await message.answer(
            f"🦜Скваак! Категорія <b>{category}</b>: {category_config['description']}\n\n",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.update_data(repost_platform="", repost_link="")
        await state.set_state(Form.description)


# 🟢 Обробка вибору платформи для репосту
@router.message(Form.repost_platform)
async def process_repost_platform(message: Message, state: FSMContext):
    platform = message.text.strip()
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} обрав спосіб поширення: {platform}")

    if platform == "⬅️ Назад":
        logging.info(f"Користувач {user_id} натиснув 'Назад' у стані Form.repost_platform")
        await show_main_menu(message, state)
        return

    if platform not in ["Соцмережа", "Надіслано друзям"]:
        await message.answer(
            "⚠️ <b>Будь ласка, вибери один із запропонованих варіантів:</b> 'Соцмережа' або 'Надіслано друзям'.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Соцмережа"), KeyboardButton(text="Надіслано друзям")],
                    [KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True
            )
        )
        return

    await state.update_data(repost_platform=platform)
    if platform == "Соцмережа":
        await message.answer(
            f"🦜Скваак!<b>Будь ласка, надішли посилання на соцмережу у якій ви опублікували допис.</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.repost_link)
    else:
        await message.answer(
            "✅ <b>Дякуємо! Сквааак!🦜 Наша команда скоро зв’яжеться з вами для перевірки поширення. Очікуйте!</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await message.answer(
            f"✅ <b>🦜Скваак! Поки ми перевіряємо, надішліть одним повідомленням:</b>\n\n"
            f"1. <b>Короткий опис</b>\n"
            f"2. <b>Лінки на соцмережі</b>\n",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.update_data(repost_link="")
        await state.set_state(Form.description)


# 🟢 Обробка посилання на репост
@router.message(Form.repost_link)
async def process_repost_link(message: Message, state: FSMContext):
    repost_link = message.text.strip()
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} надіслав посилання на допис: {repost_link}")

    if repost_link == "⬅️ Назад":
        logging.info(f"Користувач {user_id} натиснув 'Назад' у стані Form.repost_link")
        await show_main_menu(message, state)
        return

    pattern = re.compile(
        r'^(https?://)?'
        r'([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
        r'(/.*)?$|'
        r'^@[a-zA-Z0-9_]{5,}$',
        re.UNICODE
    )
    if not pattern.match(repost_link):
        await message.answer(
            "⚠️ <b>🦜Скваак! Помилка! Посилання виглядає некоректним.</b> Надішліть посилання у форматі @нікнейм або повне URL.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        return

    await state.update_data(repost_link=repost_link)
    # Після цього обробник більше нічого не надсилає
    await state.set_state(Form.description)


# 🟢 Опис та соцмережі одним повідомленням
@router.message(Form.description)
async def get_description_and_socials(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} надіслав анкету: {message.text}")

    # Кнопка Назад
    if message.text and message.text.strip() == "⬅️ Назад":
        logging.info(f"Користувач {user_id} натиснув 'Назад' у стані Form.description")
        await state.clear()   # ❗️очищаємо попередні дані
        await show_main_menu(message, state)
        return

    if not message.text:
        await message.answer(
            "🦜Скваак! <b>Будь ласка, надішліть опис та соцмережі одним повідомленням.</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True,
            ),
        )
        return

    try:
        description_text = message.text.strip()
        # зберігаємо опис і створюємо новий пустий список фото
        await state.update_data(raw_description=description_text, photos=[])

        await message.answer(
            "📸 <b>Надішліть до 5 зображень до вашого поста (прикріпіть їх до одного повідомлення) або оберіть 'Надіслати без фото'.</b>🦜Скваак!",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Надіслати без фото")],
                    [KeyboardButton(text="⬅️ Назад")],
                ],
                resize_keyboard=True,
            ),
        )
        await state.set_state(Form.images)
    except Exception as e:
        logging.error(
            f"Помилка обробки повідомлення для user_id={user_id}: {str(e)}\n{traceback.format_exc()}"
        )
        await message.answer(
            "⚠️ <b>Помилка обробки повідомлення. Спробуй ще раз.</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True,
            ),
        )
        await state.set_state(Form.images)


# 🟢 Завершення надсилання зображень (/done)
@router.message(StateFilter(Form.images), Command("done"))
async def done_images(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    category = data.get("category", "")

    if not photos:
        await message.answer("🦜Скваак!Ви ще не надіслали жодного фото⚠")
        return

    logging.info(
        f"Користувач {message.from_user.id} завершив надсилання {len(photos)} фото. Категорія: {category}"
    )
    await finish_submission(message.from_user, state, photos)


# 🟢 Надсилання без фото
@router.message(StateFilter(Form.images), F.text == "Надіслати без фото")
async def submit_without_photos(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} обрав 'Надіслати без фото'")
    await finish_submission(message.from_user, state, photos=[])


# 🟢 Обробка зображень та команд у цьому стані
@router.message(StateFilter(Form.images))
async def get_images(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(
        f"Користувач {user_id} надіслав повідомлення в стані Form.images: {message.text or 'Фото'}"
    )

    # Кнопка "Назад"
    if message.text and message.text.strip() == "⬅️ Назад":
        logging.info(f"Користувач {user_id} натиснув 'Назад' у стані Form.images")
        await state.clear()   # ❗️очищаємо попередні фото
        await show_main_menu(message, state)
        return

    # Кнопка "Надіслати без фото"
    if message.text and message.text.strip() == "Надіслати без фото":
        logging.info(f"Користувач {user_id} обрав 'Надіслати без фото'")
        await finish_submission(message.from_user, state, photos=[])
        return

    # Команда /done
    if message.text and message.text.strip().lower() == "/done":
        data = await state.get_data()
        photos = data.get("photos", [])
        category = data.get("category", "")

        if not photos:
            await message.answer("⚠️ Ви ще не надіслали жодного фото.")
            return

        logging.info(
            f"Користувач {user_id} завершив надсилання {len(photos)} фото. Категорія: {category}"
        )
        await finish_submission(message.from_user, state, photos)
        return

    # Фото
    if message.photo:
        data = await state.get_data()
        photos = data.get("photos", [])
        photos.append(message.photo[-1].file_id)
        logging.info(
            f"Користувач {user_id} надіслав зображення: {message.photo[-1].file_id}"
        )

        if len(photos) >= 5:
            await finish_submission(message.from_user, state, photos)
        else:
            await state.update_data(photos=photos)
            await message.answer(
                f"🦜Скваак! <b>Зображення прийнято📸 ({len(photos)}/5). Надішліть ще або натисніть /done.</b>",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="/done"), KeyboardButton(text="⬅️ Назад")]
                    ],
                    resize_keyboard=True,
                ),
            )
        return

    # Якщо щось інше
    await message.answer(
        "🦜Скваак!<b>Будь ласка, надішліть зображення, натисніть 'Надіслати без фото' або /done.</b>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Надіслати без фото")],
                [KeyboardButton(text="/done"), KeyboardButton(text="⬅️ Назад")],
            ],
            resize_keyboard=True,
        ),
    )


# 🟢 /help
@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    logging.info(f"Команда /допомога від користувача {message.from_user.id}")
    help_text = (
    "🦜 <b>Сквааак! Це бот для подачі заявок на публікацію на нашій дошці</b> <i>Митці ЮА</i>.\n\n"
    "<b>Як працює наша гавань:</b>\n"
    "1️⃣ <u>Обери дію</u> в головному меню після /start.\n"
    "2️⃣ Для публікації: вибери <b>категорію</b>, виконай умови (репост 📩 або поділись з друзями, підписка ✅).\n"
    "3️⃣ Надішли дані <i>одним повідомленням</i> — нік, опис, соцмережі, потім зображення 🖼(якщо є).\n"
    "4️⃣ Чекай на перевірку адміном. ⏳ Не годуй чайок байками!\n\n"
    "📜 <b>Правила для матросів:</b> /rules\n"
    f"📩 <b>Питання до капітанів:</b> <code>{' • '.join(ADMIN_CONTACTS)}</code>"
)

    await message.answer(
        help_text,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        )
    )
    await state.set_state(Form.main_menu)

# 🟢 Фінальна обробка заявки
async def finish_submission(user: types.User, state: FSMContext, photos: list):
    data = await state.get_data()
    submission_id = str(uuid.uuid4())
    logging.info(f"Фінальна обробка заявки від user_id={user.id}, submission_id={submission_id}. Дані стану: {data}, Фото: {photos}")

    if not data.get("category"):
        logging.error(f"Відсутня категорія для user_id={user.id}: {data}")
        await bot.send_message(user.id, "⚠️ Помилка: категорія не вказана. Заповніть анкету ще раз.")
        await state.clear()
        return

    description_text = data.get("raw_description", "Невказано")
    user_display_name = user.full_name or "Користувач"
    user_link = f'<a href="tg://user?id={user.id}">{user_display_name}</a>'
    text = (
        f"📥 <b>Нова заявка від</b> {user_link}\n"
        f"<b>Категорія:</b> {data['category']}\n"
        f"<b>Спосіб поширення:</b> {data.get('repost_platform', 'Невказано')}\n"
        f"<b>Посилання на допис:</b> {data.get('repost_link', 'Невказано')}\n"
        f"<b>Опис:</b>\n{description_text}\n"
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
        keyboard.button(text="📝 Публікацію вручну", callback_data=f"manual:{user.id}:{submission_id}")
        markup = keyboard.as_markup()


        await bot.send_message(chat_id=ADMIN_CHAT_ID, text="🔎 <b>Оберіть дію:</b>", parse_mode="HTML", reply_markup=markup)
    except TelegramBadRequest as e:
        logging.error(f"Помилка TelegramBadRequest при надсиланні в адмінський чат: {str(e)}\n{traceback.format_exc()}")
        await bot.send_message(user.id, "⚠️ Помилка при надсиланні заявки адмінам (BadRequest). Зверніться до <code>@AdminUsername</code>.", parse_mode="HTML")
        await state.clear()
        return
    except TelegramForbiddenError as e:
        logging.error(f"Помилка TelegramForbiddenError: бот не має доступу до адмінського чату {ADMIN_CHAT_ID}: {str(e)}\n{traceback.format_exc()}")
        await bot.send_message(user.id, "⚠️ Помилка: бот не може надіслати заявку адмінам (Forbidden). Зверніться до <code>@AdminUsername</code>.", parse_mode="HTML")
        await state.clear()
        return
    except Exception as e:
        logging.error(f"Невідома помилка при надсиланні в адмінський чат: {str(e)}\n{traceback.format_exc()}")
        await bot.send_message(user.id, "⚠️ Помилка при надсиланні заявки адмінам. Зверніться до <code>@AdminUsername</code>.", parse_mode="HTML")
        await state.clear()
        return

    try:
        submission_data = {
            "user_id": user.id,
            "username": user_display_name,
            "category": data["category"],
            "repost_platform": data.get("repost_platform", ""),
            "repost_link": data.get("repost_link", ""),
            "description": description_text,
            "images": photos if photos else [],
            "status": "pending",
            "submitted_at": datetime.utcnow().isoformat(),
            "submission_id": submission_id,
            "media_message_ids": media_message_ids if media_message_ids else []
        }
        logging.info(f"Підготовлені дані для вставки в Supabase: {submission_data}")
        result = supabase.table("submissions").insert(submission_data).execute()
        logging.info(f"Результат вставки в Supabase: {result.data}")

        if not result.data:
            logging.error(f"Не вдалося вставити заявку в Supabase для user_id={user.id}, submission_id={submission_id}. Дані: {submission_data}")
            await bot.send_message(user.id, "⚠️ Помилка при збереженні заявки в базі даних. Зверніться до <code>@AdminUsername</code>.", parse_mode="HTML")
            await state.clear()
            return

        logging.info(f"Заявка успішно збережена в Supabase: {result.data}")
        await bot.send_message(user.id, "🦜Сквааак! <b>Заявка успішно надіслана на перевірку!</b>", parse_mode="HTML")
        await state.clear()
    except Exception as e:
        logging.error(f"Помилка при збереженні в Supabase: {str(e)}\n{traceback.format_exc()}")
        await bot.send_message(user.id, f"⚠️ Помилка при збереженні заявки: {str(e)}. Зверніться до <code>@AdminUsername</code>.", parse_mode="HTML")
        await state.clear()
        return

# 🟢 Публікація адміністратором вручну
@router.callback_query(lambda c: c.data.startswith("manual:"))
async def manual_post(callback: CallbackQuery):
    logging.info(f"Callback manual отриманий від адміна {callback.from_user.id}, дані: {callback.data}")
    parts = callback.data.split(":")
    user_id = int(parts[1])
    submission_id = parts[2]

    try:
        # ✅ Оновлюємо статус заявки
        result = (
            supabase.table("submissions")
            .update({
                "status": "manual",
                "moderated_at": datetime.utcnow().isoformat(),
                "moderator_id": callback.from_user.id
            })
            .eq("user_id", user_id)
            .eq("submission_id", submission_id)
            .execute()
        )

        if not result.data:
            await callback.message.edit_text("⚠️ Не вдалося оновити статус заявки. Можливо, її вже видалили.")
            await callback.answer()
            return

        # ✅ Повідомлення адмінам та юзеру
        await callback.message.edit_text("📝 <b>Публікація переходить в особистий розгляд.</b>", parse_mode="HTML")
        await bot.send_message(user_id, "🦜Сквааак! <b>Вашу заявку розглянуто — найближчим часом ми опублікуєм її!</b>", parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logging.error(f"Помилка при виборі 'manual': {str(e)}\n{traceback.format_exc()}")
        await callback.message.edit_text("⚠️ Помилка при обробці заявки для ручної публікації.")
        await callback.answer()



# 🟢 Схвалення посту
@router.callback_query(lambda c: c.data.startswith("approve:"))
async def approve_post(callback: CallbackQuery):
    logging.info(f"Callback approve отриманий від адміна {callback.from_user.id}, дані: {callback.data}")
    parts = callback.data.split(":")
    user_id = int(parts[1])
    submission_id = parts[2]
    logging.info(f"Адмін {callback.from_user.id} схвалив заявку для користувача {user_id}, submission_id={submission_id}")

    try:
        # Перевірка чи існує заявка
        check_submission = (
            supabase.table("submissions")
            .select("*")
            .eq("user_id", user_id)
            .eq("submission_id", submission_id)
            .execute()
        )
        if not check_submission.data:
            await callback.message.edit_text("⚠️ Заявку не знайдено в базі даних. Можливо, вона була видалена.")
            await callback.answer()
            return

        # Оновлення статусу заявки
        result = (
            supabase.table("submissions")
            .update({
                "status": "approved",
                "moderated_at": datetime.utcnow().isoformat(),
                "moderator_id": callback.from_user.id
            })
            .eq("user_id", user_id)
            .eq("submission_id", submission_id)
            .execute()
        )

        if not result.data:
            await callback.message.edit_text("⚠️ Не вдалося оновити статус заявки. Перевірте, чи існує заявка.")
            await callback.answer()
            return

        await asyncio.sleep(0.5)

        # Отримання схваленої заявки
        submission = (
            supabase.table("submissions")
            .select("*")
            .eq("user_id", user_id)
            .eq("submission_id", submission_id)
            .eq("status", "approved")
            .execute()
        )

        if not submission.data:
            await callback.message.edit_text("⚠️ Не вдалося знайти схвалену заявку. Можливо, оновлення статусу не відбулося.")
            await callback.answer()
            return

        data = submission.data[0]
        category_config = CATEGORIES.get(data.get('category'), {})
        category_hashtag = category_config.get('hashtag', "")

        # Перевірка на анонімність
        if category_config.get("anonymous", False):
            author_text = "Дірявий Череп"
        else:
            user_display_name = data.get('username') or "Користувач"
            author_text = f'<a href="tg://user?id={user_id}">{html.escape(user_display_name)}</a>'

        # Підстраховка на випадок None
        description = data.get("description") or "— без опису —"

        # Формування поста (хештег в кінці, якщо є)
        post_text = f"{description}\n\n<b>Власник цього скарбу</b>: {author_text}"
        if category_hashtag:
            post_text += f"\n\n{category_hashtag}"

        # Обмеження Telegram: caption для фото/медіа групи — до ~1024 символів,
        # а звичайне повідомлення до 4096 символів. Підстрахуємося.
        if len(post_text) > 4096:
            logging.warning(f"post_text занадто довгий ({len(post_text)}). Тримаємо максимум 4096 символів.")
            post_text = post_text[:4093] + "..."

        images = data.get("images") or []

        # Відправка в канал
        if images:
            # Якщо caption помірний — додаємо як caption до першого фото
            if len(post_text) <= 1024:
                media = [InputMediaPhoto(media=images[0], caption=post_text, parse_mode="HTML")]
                for photo in images[1:]:
                    media.append(InputMediaPhoto(media=photo))
                await bot.send_media_group(chat_id=MAIN_CHAT_ID, media=media)
            else:
                # Якщо caption занадто довгий для caption — спочатку відправляємо галерею без підпису,
                # потім окремим повідомленням текст.
                media = [InputMediaPhoto(media=images[0])]
                for photo in images[1:]:
                    media.append(InputMediaPhoto(media=photo))
                await bot.send_media_group(chat_id=MAIN_CHAT_ID, media=media)
                await bot.send_message(chat_id=MAIN_CHAT_ID, text=post_text, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=MAIN_CHAT_ID, text=post_text, parse_mode="HTML")

        # Повідомлення адміну та користувачу
        await callback.message.edit_text("🦜Сквааак! Чудові новини <b>Публікацію схвалено та опубліковано в основному чаті!</b>", parse_mode="HTML")
        try:
            await bot.send_message(user_id, "🦜Сквааак! <b>Вашу публікацію схвалено та опубліковано в основному чаті!</b>", parse_mode="HTML")
        except Exception as send_err:
            logging.warning(f"Не вдалося надіслати повідомлення користувачу {user_id}: {send_err}")

        await callback.answer()

    except TelegramBadRequest as e:
        logging.error(f"Помилка TelegramBadRequest: {str(e)}\n{traceback.format_exc()}")
        await callback.message.edit_text("⚠️ Помилка при публікації в основний чат (BadRequest).")
        await callback.answer()
    except TelegramForbiddenError as e:
        logging.error(f"Помилка TelegramForbiddenError: {str(e)}\n{traceback.format_exc()}")
        await callback.message.edit_text("⚠️ Помилка: бот не має доступу до основного чату.")
        await callback.answer()
    except Exception as e:
        logging.error(f"Невідома помилка при схваленні: {str(e)}\n{traceback.format_exc()}")
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
        # ❌ Видаляємо заявку з бази
        logging.info(f"Видалення заявки з Supabase для user_id={user_id}, submission_id={submission_id}")
        result = supabase.table("submissions").delete().eq("user_id", user_id).eq("submission_id", submission_id).execute()
        logging.info(f"Результат видалення Supabase: {result.data}")

        # Повідомляємо адміна і користувача
        await callback.message.edit_text("❌ <b>Публікацію відхилено 🦜Сквааак!.</b>", parse_mode="HTML")
        await bot.send_message(user_id, "🦜Сквааак! <b>Вашу публікацію відхилено.</b> Прочитайте правила та спробуйте ще раз.", parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logging.error(f"Помилка при відхиленні заявки: {str(e)}\n{traceback.format_exc()}")
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
                "🦜Сквааак!<b>Виникла помилка при обробці вашого запиту.</b> Спробуйте ще раз або зверніться до <code>@tina263678e</code>.",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True
                )
            )
    except Exception as e:
        logging.error(f"Помилка при надсиланні повідомлення про помилку: {str(e)}\n{traceback.format_exc()}")
    return True

# Запуск фонової задачі при старті
dp.startup.register(on_startup)
