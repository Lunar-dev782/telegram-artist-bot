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
TOKEN = "7645134499:AAFv6nRPsiy-6p2h2HJHhmeUZby2PGu9vFg"
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
    "💰 Платні пропозиції": {
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
                "<a href='https://t.me/+bTmE3LOAMFI5YzBi'>Перейти до каналу</a> і натисніть 'Я підписався(лась)'.",
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
        "<b>🎨 Ласкаво просимо до спільноти <i>Митці ЮА</i>!</b>\n\n"
        
        "<b>📌 Основні правила публікацій:</b>\n"
        "1. <b>Категорії:</b> обирай відповідну, читай умови уважно.\n"
        "2. <b>Авторство:</b> тільки власні роботи. Заборонені:\n"
        "   — плагіат;\n"
        "   — генеративне ШІ (навіть частково);\n"
        "   — чужий контент без дозволу.\n"
        "3. <b>Оформлення:</b> до 5 зображень, короткий опис, соцмережі (за бажанням).\n"
        "4. <b>Частота:</b> максимум 2 публікації на тиждень.\n"
        "5. <b>Підтримка:</b> зроби репост <a href='https://t.me/c/2865535470/16'>цього допису</a> або поділись ботом з 3 друзями.\n\n"

        "<b>🚫 Заборонено:</b>\n"
        "— NSFW без мінімального блюру або без згоди адмінів\n"
        "— Нецензурні частини допускаються <u>тільки в коментарях</u> — з позначкою 18+\n"
        "— Образи, токсична поведінка, реклама без згоди\n"
        "— Порушення законів, авторських прав\n"
        "— Використання російської мови в постах\n\n"

        "<b>🤖 Користування ботом:</b>\n"
        "— Дотримуйся усіх етапів анкети. Не пропускай жоден крок.\n"
        "— Якщо бот завис або не відповідає — введи /start або звернись до адміна: <code>@AdminUsername</code>\n"
        "— Спам, флуд або зловживання функціями — призведе до блокування\n\n"

        "<b>🛠 Модерація:</b>\n"
        "— Модератори можуть:\n"
        "   — відхилити пост, якщо він не відповідає умовам;\n"
        "   — видалити контент, що порушує правила;\n"
        "   — видати бан або обмежити доступ до бота.\n\n"

        "<b>❓ Питання чи скарги?</b> Пиши <code>@AdminUsername</code>\n"
        "<b>🔗 Повна версія правил:</b> <a href='https://t.me/c/2865535470/16'>тут</a>"
    )

    await message.answer(
        rules_text,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        )
    )
    await state.set_state(Form.main_menu)

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

# ===== УНІВЕРСАЛЬНИЙ ХЕНДЛЕР КОМАНД =====
@router.message(Command(commands=["start", "rules", "help", "питання", "код"]))
async def handle_commands(message: Message, state: FSMContext):
    user_id = message.from_user.id
    command = message.text.split()[0].lstrip("/").lower()
    logging.info(f"Обробка команди /{command} від user_id={user_id}")

    try:
        if command == "start":
            await show_main_menu(message, state)

        elif command == "rules":
            await cmd_rules(message, state)

        elif command == "help":
            await cmd_help(message, state)

        elif command == "питання":
            logging.info(f"Користувач {user_id} викликав команду /питання")
            if not await is_admin(user_id):
                logging.warning(f"Користувач {user_id} не має прав адміна")
                await message.answer("⚠️ У вас немає доступу до цієї команди. Спочатку авторизуйтесь за допомогою /код.")
                return
            logging.info(f"Користувач {user_id} є адміном, викликаємо send_next_question")
            await send_next_question(user_id)

        elif command == "код":
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await message.answer("⚠️ Введіть код. Використовуйте: /код <код>")
                return

            code = parts[1].strip()
            if code != "12345":
                await message.answer("⚠️ Невірний код. Спробуйте ще раз.")
                return

            existing_admin = supabase.table("admins").select("admin_id").eq("admin_id", user_id).execute()
            if existing_admin.data:
                await message.answer("✅ Ви вже авторизовані.")
                return

            admin_data = {"admin_id": user_id, "added_at": datetime.utcnow().isoformat()}
            result = supabase.table("admins").insert(admin_data).execute()
            if not result.data:
                raise ValueError("Не вдалося додати адміна до бази даних")

            await message.answer("✅ Ви успішно авторизовані як адмін! Використовуйте /питання для перегляду питань.")

    except Exception as e:
        logging.error(f"Помилка при обробці команди /{command} для user_id={user_id}: {str(e)}\n{traceback.format_exc()}")
        await message.answer(
            "⚠️ Виникла помилка при обробці команди. Спробуйте ще раз або зверніться до <code>@AdminUsername</code>.",
            parse_mode="HTML"
        )

# ===== ОБРОБНИК НЕВІДОМИХ КОМАНД =====
@router.message(F.text.startswith("/"))
async def handle_unknown_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    command = message.text.split()[0].lstrip("/").lower()
    known_commands = ["start", "rules", "help", "питання", "код"]
    
    if command in known_commands:
        logging.info(f"Команда /{command} від user_id={user_id} вже обробляється в handle_commands, пропускаємо")
        return  # Пропускаємо, якщо команда відома

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
    await state.set_state(Form.main_menu)
        

# ===== НАСТУПНЕ ПИТАННЯ =====
async def send_next_question(admin_id: int):
    try:
        logging.info(f"Запит питань зі статусами 'pending' або 'skipped' для admin_id={admin_id}")
        pending_qs = supabase.table("questions").select("*").in_("status", ["pending", "skipped"]).order("submitted_at").execute()
        logging.info(f"Отримано {len(pending_qs.data)} питань: {pending_qs.data}")

        if not pending_qs.data:
            cont_buttons = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="➡️ Почати спочатку", callback_data="restart_answering"),
                    InlineKeyboardButton(text="⛔ Завершити сеанс", callback_data="stop_answering")
                ]
            ])
            await bot.send_message(admin_id, "✅ Нових питань немає.", parse_mode="HTML", reply_markup=cont_buttons)
            return

        next_q = pending_qs.data[0]
        total = len(pending_qs.data)
        user_name = next_q.get('username', 'Користувач')
        clickable_user = f"<a href='tg://user?id={next_q['user_id']}'>{html.escape(user_name)}</a>"

        text = (
            f"📩 Питання від {clickable_user} (1/{total}):\n"
            f"<b>ID:</b> <code>{next_q['user_id']}</code>\n\n"
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
    except Exception as e:
        logging.error(f"Помилка в send_next_question для admin_id={admin_id}: {str(e)}\n{traceback.format_exc()}")
        await bot.send_message(admin_id, f"⚠️ Помилка при отриманні питань: {str(e)}. Зверніться до <code>@AdminUsername</code>.", parse_mode="HTML")

# ===== ОБРОБКА КНОПОК (ВІДПОВІДЬ / ПРОПУСК / ВИДАЛЕННЯ) =====
@router.callback_query(F.data.startswith(("answer:", "skip:", "delete:")))
async def handle_question_buttons(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    parts = callback.data.split(":")
    if len(parts) != 3:
        logging.error(f"Некоректний формат callback_data: {callback.data}")
        await callback.answer("⚠️ Некоректний формат даних.")
        return

    action, user_id_str, question_id = parts
    try:
        user_id = int(user_id_str)
    except ValueError:
        logging.error(f"Некоректний user_id у callback_data: {user_id_str}")
        await callback.answer("⚠️ Некоректний user_id.")
        return

    if not await is_admin(admin_id):
        logging.warning(f"Користувач {admin_id} не є адміном")
        await callback.answer("⚠️ У вас немає доступу.")
        return

    try:
        question_res = supabase.table("questions").select("*").eq("question_id", question_id).eq("user_id", user_id).execute()
        logging.info(f"Результат запиту питання: {question_res.data}")
    except Exception as e:
        logging.error(f"Помилка при запиті питання з Supabase: {str(e)}\n{traceback.format_exc()}")
        await callback.answer("⚠️ Помилка при отриманні питання.")
        return

    if not question_res.data:
        logging.warning(f"Питання не знайдено: question_id={question_id}, user_id={user_id}")
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
            logging.info(f"Питання пропущено: question_id={question_id}, user_id={user_id}")
        except Exception as e:
            logging.error(f"Помилка при пропуску питання: {str(e)}\n{traceback.format_exc()}")
            await callback.answer(f"⚠️ Помилка при пропуску: {str(e)}")
            return
        await callback.answer("⏭ Питання пропущено.")
        await send_next_question(admin_id)
        return

    elif action == "delete":
        try:
            supabase.table("questions").delete().eq("question_id", question_id).eq("user_id", user_id).execute()
            logging.info(f"Питання видалено: question_id={question_id}, user_id={user_id}")
        except Exception as e:
            logging.error(f"Помилка при видаленні питання: {str(e)}\n{traceback.format_exc()}")
            await callback.answer(f"⚠️ Помилка при видаленні: {str(e)}")
            return
        await callback.answer("🗑 Питання видалено.")
        await send_next_question(admin_id)
        return

# ===== ОБРОБКА ВІДПОВІДІ =====
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

    await bot.send_message(
        chat_id=user_id,
        text=f"✉️ <b>Відповідь на ваше питання:</b>\n\n{html.escape(question_text)}\n\n<b>Відповідь:</b> {html.escape(answer_text)}",
        parse_mode="HTML"
    )

    supabase.table("questions").update({
        "status": "answered",
        "answered_at": datetime.utcnow().isoformat(),
        "admin_id": admin_id,
        "answer_text": answer_text
    }).eq("question_id", question_id).eq("user_id", user_id).execute()

    await message.answer("✅ Відповідь надіслано.", reply_markup=ReplyKeyboardRemove())
    await message.answer("Виберіть дію:", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Продовжити", callback_data="continue_answering"),
             InlineKeyboardButton(text="⛔ Зупинитись", callback_data="stop_answering")]
        ]
    ))
    await state.clear()

# ===== ПРОДОВЖЕННЯ / ЗУПИНКА =====
@router.callback_query(F.data == "continue_answering")
async def continue_answering(callback: CallbackQuery):
    await callback.answer()
    await send_next_question(callback.from_user.id)

@router.callback_query(F.data == "stop_answering")
async def stop_answering(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("⛔ Ви завершили сеанс відповідей.")
    await callback.message.edit_text("✅ Сеанс завершено.")

# ===== НАСТУПНЕ ПИТАННЯ =====
async def send_next_question(admin_id: int):
    pending_qs = supabase.table("questions").select("*").eq("status", "pending").order("submitted_at").execute()
    if not pending_qs.data:
        await bot.send_message(admin_id, "✅ Нових питань немає.", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Почати спочатку", callback_data="restart_answering"),
                 InlineKeyboardButton(text="⛔ Завершити сеанс", callback_data="stop_answering")]
            ]
        ))
        return

    next_q = pending_qs.data[0]
    total = len(pending_qs.data)
    clickable_user = f"<a href='tg://user?id={next_q['user_id']}'>{html.escape(next_q.get('username', 'Користувач'))}</a>"

    text = (
        f"📩 Питання від {clickable_user} (1/{total}):\n"
        f"<b>Текст питання:</b>\n{html.escape(next_q['question_text'])}"
    )
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Відповісти", callback_data=f"answer:{next_q['user_id']}:{next_q['question_id']}"),
         InlineKeyboardButton(text="⏭ Пропустити", callback_data=f"skip:{next_q['user_id']}:{next_q['question_id']}")],
        [InlineKeyboardButton(text="🗑 Видалити", callback_data=f"delete:{next_q['user_id']}:{next_q['question_id']}"),
         InlineKeyboardButton(text="⛔ Зупинитись", callback_data="stop_answering")]
    ])
    await bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=buttons)

# ===== ПЕРЕЗАПУСК =====
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

    if message.text and message.text.strip() == "⬅️ Назад":
        logging.info(f"Користувач {user_id} натиснув 'Назад' у стані Form.description")
        await show_main_menu(message, state)
        return

    if not message.text:
        await message.answer(
            "⚠️ <b>Будь ласка, надішли опис та соцмережі одним повідомленням.</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        return

    try:
        description_text = message.text.strip()
        await state.update_data(raw_description=description_text)
        await message.answer(
            "📸 <b>Надішліть до 5 зображень до вашої заявки (прикріпіть їх до одного повідомлення) або оберіть 'Надіслати без фото'.</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Надіслати без фото")],
                    [KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.images)
    except Exception as e:
        logging.error(f"Помилка обробки повідомлення для user_id={user_id}: {str(e)}\n{traceback.format_exc()}")
        await message.answer(
            "⚠️ <b>Помилка обробки повідомлення. Спробуй ще раз.</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )
        await state.set_state(Form.images)

# 🟢 Обробка зображень
@router.message(Form.images)
async def get_images(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} надіслав повідомлення в стані Form.images: {message.text}")

    if message.text and message.text.strip() == "⬅️ Назад":
        logging.info(f"Користувач {user_id} натиснув 'Назад' у стані Form.images")
        await show_main_menu(message, state)
        return

    if message.text == "Надіслати без фото":
        logging.info(f"Користувач {user_id} обрав 'Надіслати без фото'")
        await submit_without_photos(message, state)
        return

    if message.text == "/done":
        logging.info(f"Користувач {user_id} завершив надсилання зображень")
        await done_images(message, state)
        return

    if message.photo:
        data = await state.get_data()
        photos = data.get("photos", [])
        photos.append(message.photo[-1].file_id)
        logging.info(f"Користувач {user_id} надіслав зображення: {message.photo[-1].file_id}")

        if len(photos) >= 5:
            await finish_submission(message.from_user, state, photos)
        else:
            await state.update_data(photos=photos)
            await message.answer(
                f"📸 <b>Зображення прийнято ({len(photos)}/5). Надішли ще або натисни /done.</b>",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="/done"), KeyboardButton(text="⬅️ Назад")]],
                    resize_keyboard=True
                )
            )
    else:
        await message.answer(
            "⚠️ <b>Будь ласка, надішли зображення, натисни 'Надіслати без фото' або /done.</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Надіслати без фото")],
                    [KeyboardButton(text="/done"), KeyboardButton(text="⬅️ Назад")]
                ],
                resize_keyboard=True
            )
        )

# 🟢 Надсилання без фото
@router.message(Form.images, F.text == "Надіслати без фото")
async def submit_without_photos(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logging.info(f"Користувач {user_id} обрав 'Надіслати без фото'")
    await finish_submission(message.from_user, state, photos=[])

# 🟢 Завершення надсилання зображень
@router.message(Form.images, F.text == "/done")
async def done_images(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    category = data.get("category", "")
    logging.info(f"Користувач {message.from_user.id} завершив надсилання зображень: {photos}, категорія: {category}")
    await finish_submission(message.from_user, state, photos)


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
        logging.info(f"Оновлення статусу заявки в Supabase для user_id={user_id}, submission_id={submission_id}")
        result = supabase.table("submissions").update({
            "status": "rejected",
            "moderated_at": datetime.utcnow().isoformat(),
            "moderator_id": callback.from_user.id,
            "rejection_reason": "Невідповідність вимогам"
        }).eq("user_id", user_id).eq("submission_id", submission_id).execute()
        logging.info(f"Результат оновлення Supabase: {result.data}")
        await callback.message.edit_text("❌ <b>Публікацію відхилено.</b>", parse_mode="HTML")
        await bot.send_message(user_id, "😔 <b>Вашу публікацію відхилено.</b> Причина: Невідповідність вимогам.", parse_mode="HTML")
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
