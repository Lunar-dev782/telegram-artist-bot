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
    "💰 Платні послуги": {
        "description": "Продаєш коміші, адопти, принти чи щось інше? Розкажи — і тебе знайдуть!",
        "hashtag": "#ТворчіПропозиції"
    },
    "📣 Промо соцмереж": {
        "description": "Показуй свої профілі, блоги, канали. Хай світ побачить тебе!",
        "hashtag": "#ПромоСоцмереж"
    },
    "🎉 Активності": {
        "description": "Конкурси, DTIYS, реквести, івенти — усе, що об'єднує творчих!",
        "hashtag": "#ТворчіАктивності"
    },
    "🔎 У пошуках критики/фідбеку": {
        "description": "Потрібна думка збоку? Запроси фідбек тут!",
        "hashtag": "#ПошукФідбеку"
    },
    "📢 Оголошення": {
        "description": "Новини, запитання, звернення до спільноти — слово за тобою.",
        "hashtag": "#Оголошення"
    },
    "🌟 Інше": {
        "description": "Не знайшлося місця в інших категоріях? Не біда — ця саме для такого!",
        "hashtag": "#ТворчийМікс"
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
                "⚠️ Ви не підписані на наш канал! Будь ласка, підпишіться за посиланням: "
                "<a href='https://t.me/mytci_ua'>Перейти до каналу</a> і натисніть 'Я підписався(лась)'.",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="Я підписався(лась)")]],
                    resize_keyboard=True
                )
            )
            await state.clear()
            return

        await message.answer(
            "🎨 <b>Вітаємо в боті спільноти</b> <i>Митці ЮА</i>! <b>Оберіть дію:</b>",
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
            "⚠️ Виникла помилка. Спробуйте ще раз або зверніться до <code>@AdminUsername</code>.",
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
# 🟢 Обробка /rules або кнопки "📜 Правила"
@router.message(Form.main_menu, F.text == "📜 Правила")
@router.message(Command("rules"))
async def cmd_rules(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Команда або кнопка /правила від користувача {user_id}")
    rules_text = (
    "<b>🏴‍☠️ Правила публікації у спільноті <i>Митці ЮА</i></b>\n\n"

    "<b>📌 Публікація рекламних постів:</b>\n"
    "1. <b>18+</b> — під цензуру! Капітанка М’юз не хоче, аби наш корабель потонув через скарги Телеграму.\n"
    "2. Перед швартуванням поста надай скриншот як підтвердження репосту основного оголошення.\n"
    "3. Додай <b>посилання на порт</b>, де пришвартована реклама.\n"
    "4. Твори без аморальності та її прославляння. Тут ми будуємо <i>безпечну гавань</i>.\n"
    "5. Російська мова та проросійські фандоми — <u>за борт</u>! Наш корабель пливе під іншим прапором.\n\n"

    "<b>⚓ Публікація платних послуг:</b>\n"
    "1. <b>18+</b> — під цензуру, як і в рекламі.\n"
    "2. Підтверди репост головного допису.\n"
    "3. Обов’язково вкажи <b>прайс-лист</b> (ніяких «потім домовимось»).\n"
    "4. Мінімальна ціна — <b>50 грн</b>. Шануй свою працю, щоб інші її теж цінували.\n"
    "5. Додай приклади робіт та чіткі дедлайни. Довіряємо, але перевіряємо.\n"
    "6. Вкажи способи оплати — щоб не доводилося ловити тебе в штормі.\n"
    "7. Російські та проросійські фандоми не пройдуть.\n\n"

    "<b>🦜 Публікація івентів та активностей:</b>\n"
    "1. <b>18+</b> — під цензуру! Ніхто не хоче, щоб корабель потонув через зайву відвертість.\n"
    "2. Скрін репосту — твій <b>квиток на борт</b>.\n"
    "3. Чіткий опис івенту, банер та посилання на оригінал. Без карти скарбів ніхто не знайде твій івент.\n"
    "4. Жодної проросійщини та російських фандомів. Ми пливемо до інших берегів.\n\n"

    "<b>🖋️ Інформаційні та звичайні пости:</b>\n"
    "1. <b>18+</b> — під цензуру, ховаємо за парусами.\n"
    "2. Жодних посилань на сторонні ресурси (навіть у коментарях).\n"
    "3. Жодної підтримки аморальних ідей, образ чи цькувань. Це <i>творча гавань</i>, а не бійцівський клуб.\n"
    "4. Жодних російських та проросійських фандомів.\n"
    "5. Інформацію перевіряємо — не годуй чайок байками.\n\n"

    "<b>🛠 Модерація:</b>\n"
    "— Модератори можуть відхилити пост, якщо він не відповідає умовам.\n"
    "— Видалити контент, що порушує правила.\n"
    "— Видати бан або обмежити доступ до бота.\n\n"

    "<b>❓ Питання чи скарги?</b> Пиши <code>@AdminUsername</code>\n"
    "<b>🔗 Повна версія правил:</b> <a href='https://t.me/mytci_ua/14'>тут</a>"
)

    await message.answer(rules_text, parse_mode="HTML")  # ← ось цього рядка бракує
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
                "⚠️ Ви можете подавати не більше 2 заявок на тиждень. Спробуйте пізніше!",
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
            "⚠️ Виникла помилка. Спробуйте ще раз або зверніться до <code>@AdminUsername</code>.",
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
        f"❓ <b>Якщо у вас є питання — напишіть його тут, і наші адміни дадуть відповідь протягом доби.</b>\n\n"
        f"📩 Також можете звернутись напряму:\n<code>{' • '.join(ADMIN_CONTACTS)}</code>",
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
            "⚠️ Будь ласка, напишіть ваше питання.",
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
            "✅ <b>Ваше питання невдовзі буде переглянуто! Очікуйте відповідь протягом доби.</b>",
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
        "⚠️ <b>Виберіть дію з головного меню.</b>",
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
            text=f"✉️ <b>Відповідь на ваше питання:</b>\n\n{html.escape(question_text)}\n\n<b>Відповідь:</b> {html.escape(answer_text)}",
            parse_mode="HTML"
        )
        # Видаляємо питання з бази даних після надсилання відповіді
        supabase.table("questions").delete().eq("question_id", question_id).eq("user_id", user_id).execute()
    except Exception as e:
        await message.answer(f"⚠️ Неможливо надіслати повідомлення: {e}")
        await state.clear()
        return

    await message.answer("✅ Відповідь надіслано.", reply_markup=ReplyKeyboardRemove())

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

    subscription_status = await check_subscription(user_id)
    logging.info(f"Результат перевірки підписки для user_id={user_id}: {subscription_status}")
    if not subscription_status:
        await message.answer(
            "⚠️ Ви не підписані на наш канал! Будь ласка, підпишіться за посиланням: "
            "<a href='https://t.me/+bTmE3LOAMFI5YzBi'>Перейдіть до каналу</a> і натисніть 'Я підписався(лась)'.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Я підписався(лась)")]],
                resize_keyboard=True
            )
        )
        await state.clear()
        return

    await state.update_data(category=category)
    if category == "📩 Оголошення":
        await message.answer(
            f"✅ Ви обрали категорію <b>{category}</b>: {CATEGORIES[category]['description']}\n\n"
            f"📝 <b>Надішли, будь ласка, цю інформацію одним повідомленням:</b>\n\n"
            f"1. <b>Короткий опис</b>\n"
            f"2. <b>Лінки на соцмережі</b>\n\n",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.update_data(repost_platform="", repost_link="")
        await state.set_state(Form.description)
        return

    await message.answer(
        f"✅ Ви обрали категорію <b>{category}</b>: {CATEGORIES[category]['description']}\n\n"
        f"🔄 <b>Зроби репост поста нашої</b> <a href='https://t.me/c/2865535470/16'>нашої спільноти</a> у соцмережі або надішли 3 друзям\n"
        f"📝 <b>Потім заповни анкету</b>\n\n"
        f"Де ти поділився(лась) інформацією?",
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
            f"🔗 <b>Будь ласка, надішли посилання на соцмережу у якій ви опублікували допис.</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.repost_link)
    else:
        await message.answer(
            "✅ <b>Дякуємо! Адмін скоро зв’яжеться з вами для перевірки поширення. Очікуйте!</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await message.answer(
            f"✅ <b>Дякуємо за розповсюдження! Тепер надішліть одним повідомленням:</b>\n\n"
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
            "⚠️ <b>Посилання виглядає некоректним.</b> Надішліть посилання у форматі @нікнейм (наприклад, @username) або повне URL (наприклад, https://t.me/username, https://www.instagram.com/username).",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        return

    await state.update_data(repost_link=repost_link)
    await message.answer(
        f"✅ <b>Дякуємо за репост! Тепер надішліть одним повідомленням:</b>\n\n"
        f"1. <b>Короткий опис</b>: що це за допис, про що він (2-3 речення).\n"
        f"2. <b>Лінки на соцмережі</b>: у форматі Instagram: @нікнейм, Telegram: @нікнейм, Сайт: https://example.com.\n"
        f"3. <b>До 5 зображень</b>: прикріпіть зображення до повідомлення (якщо є).\n\n",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
    )
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
            "⚠️ <b>Будь ласка, надішліть опис та соцмережі одним повідомленням.</b>",
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
            "📸 <b>Надішліть до 5 зображень до вашої заявки (прикріпіть їх до одного повідомлення) або оберіть 'Надіслати без фото'.</b>",
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
        await message.answer("⚠️ Ви ще не надіслали жодного фото.")
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
                f"📸 <b>Зображення прийнято ({len(photos)}/5). Надішліть ще або натисніть /done.</b>",
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
        "⚠️ <b>Будь ласка, надішліть зображення, натисніть 'Надіслати без фото' або /done.</b>",
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
        "ℹ️ <b>Це бот для подачі заявок на публікацію у спільноті</b> <i>Митці ЮА</i>.\n\n"
        "<b>Як це працює:</b>\n"
        "1️⃣ <u>Обери дію</u> в головному меню після /start.\n"
        "2️⃣ Для публікації: вибери <b>категорію</b>, виконай умови (репост 📩 або надсилання друзям, підписка ✅).\n"
        "3️⃣ Надішли дані <i>одним повідомленням</i> (нік, опис, соцмережі, зображення 🖼️ — якщо потрібно).\n"
        "4️⃣ Чекай на перевірку адміном. ⏳\n\n"
        "📜 <b>Правила:</b> /rules\n"
        f"📩 <b>З питаннями:</b> <code>{' • '.join(ADMIN_CONTACTS)}</code>"
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
        await bot.send_message(user.id, "✅ <b>Заявка успішно надіслана на перевірку!</b>", parse_mode="HTML")
        await state.clear()
    except Exception as e:
        logging.error(f"Помилка при збереженні в Supabase: {str(e)}\n{traceback.format_exc()}")
        await bot.send_message(user.id, f"⚠️ Помилка при збереженні заявки: {str(e)}. Зверніться до <code>@AdminUsername</code>.", parse_mode="HTML")
        await state.clear()
        return

# 🟢 Схвалення посту
@router.callback_query(lambda c: c.data.startswith("approve:"))
async def approve_post(callback: CallbackQuery):
    logging.info(f"Callback approve отриманий від адміна {callback.from_user.id}, дані: {callback.data}")
    parts = callback.data.split(":")
    user_id = int(parts[1])
    submission_id = parts[2]
    logging.info(f"Адмін {callback.from_user.id} схвалив заявку для користувача {user_id}, submission_id={submission_id}")

    try:
        logging.info(f"Перевірка існування заявки в Supabase для user_id={user_id}, submission_id={submission_id}")
        check_submission = supabase.table("submissions").select("*").eq("user_id", user_id).eq("submission_id", submission_id).execute()
        if not check_submission.data:
            logging.error(f"Заявка для user_id={user_id}, submission_id={submission_id} не знайдена в таблиці submissions")
            await callback.message.edit_text("⚠️ Заявку не знайдено в базі даних. Можливо, вона була видалена.")
            await callback.answer()
            return

        logging.info(f"Оновлення статусу заявки в Supabase для user_id={user_id}, submission_id={submission_id}")
        result = supabase.table("submissions").update({
            "status": "approved",
            "moderated_at": datetime.utcnow().isoformat(),
            "moderator_id": callback.from_user.id
        }).eq("user_id", user_id).eq("submission_id", submission_id).execute()
        logging.info(f"Результат оновлення Supabase: {result.data}")

        if not result.data:
            logging.warning(f"Оновлення не змінило жодного рядка для user_id={user_id}, submission_id={submission_id}")
            await callback.message.edit_text("⚠️ Не вдалося оновити статус заявки. Перевірте, чи існує заявка.")
            await callback.answer()
            return

        await asyncio.sleep(0.5)
        logging.info(f"Отримання схваленої заявки для user_id={user_id}, submission_id={submission_id}")
        submission = supabase.table("submissions").select("*").eq("user_id", user_id).eq("submission_id", submission_id).eq("status", "approved").execute()
        logging.info(f"Отримані дані заявки: {submission.data}")

        if not submission.data:
            logging.error(f"Схвалена заявка для user_id={user_id}, submission_id={submission_id} не знайдена після оновлення")
            await callback.message.edit_text("⚠️ Не вдалося знайти схвалену заявку. Можливо, оновлення статусу не відбулося.")
            await callback.answer()
            return

        data = submission.data[0]
        category_hashtag = CATEGORIES[data['category']]['hashtag']
        user_display_name = data['username']
        user_link = f'<a href="tg://user?id={user_id}">{user_display_name}</a>'
        post_text = (
            f"{category_hashtag}\n\n"
            f"{data['description']}\n\n"
            f"Автор публікації: {user_link}"
        )

        if data["images"]:
            media = [InputMediaPhoto(media=data["images"][0], caption=post_text, parse_mode="HTML")]
            for photo in data["images"][1:]:
                media.append(InputMediaPhoto(media=photo))
            await bot.send_media_group(chat_id=MAIN_CHAT_ID, media=media)
        else:
            await bot.send_message(chat_id=MAIN_CHAT_ID, text=post_text, parse_mode="HTML")

        await callback.message.edit_text("✅ <b>Публікацію схвалено та опубліковано в основному чаті!</b>", parse_mode="HTML")
        await bot.send_message(user_id, "🎉 <b>Вашу публікацію схвалено та опубліковано в основному чаті!</b>", parse_mode="HTML")
        await callback.answer()
    except TelegramBadRequest as e:
        logging.error(f"Помилка TelegramBadRequest при публікації в основний чат: {str(e)}\n{traceback.format_exc()}")
        await callback.message.edit_text("⚠️ Помилка при публікації в основний чат (BadRequest).")
        await callback.answer()
    except TelegramForbiddenError as e:
        logging.error(f"Помилка TelegramForbiddenError: бот не має доступу до основного чату {MAIN_CHAT_ID}: {str(e)}\n{traceback.format_exc()}")
        await callback.message.edit_text("⚠️ Помилка: бот не має доступу до основного чату.")
        await callback.answer()
    except Exception as e:
        logging.error(f"Невідома помилка при обробці схвалення: {str(e)}\n{traceback.format_exc()}")
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
        await callback.message.edit_text("❌ <b>Публікацію відхилено та видалено з бази.</b>", parse_mode="HTML")
        await bot.send_message(user_id, "😔 <b>Вашу публікацію відхилено.</b> Причина: невідповідність вимогам.", parse_mode="HTML")
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
                "⚠️ <b>Виникла помилка при обробці вашого запиту.</b> Спробуйте ще раз або зверніться до <code>@AdminUsername</code>.",
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
