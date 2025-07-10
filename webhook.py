import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update, Message

# Токен та URL
TOKEN = "7645134499:AAFRfwsn7dr5W2m81gCJPwX944PRqk-sjEc"
WEBHOOK_URL = "https://telegram-artist-bot.onrender.com"
WEBHOOK_PATH = "/webhook/telegram"

# Ініціалізація бота
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ✅ Простий хендлер — відповідає на всі повідомлення
@dp.message()
async def echo_message(message: Message):
    await message.answer(f"Ти написав: {message.text}")

# 📌 Встановлення webhook при запуску
async def on_startup(app):
    try:
        await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
        logging.info(f"✅ Webhook встановлено: {WEBHOOK_URL}{WEBHOOK_PATH}")
    except Exception as e:
        logging.error(f"❌ Помилка при встановленні webhook: {e}")

# 📥 Обробка запиту від Telegram
async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update(**data)
        logging.info(f"📲 Отримано оновлення: {update}")
        await dp.feed_update(bot, update)
        return web.Response(status=200)
    except Exception as e:
        logging.error(f"❌ Помилка обробки запиту: {e}")
        return web.Response(status=500)

# 🔄 Health check
async def health_check(request):
    return web.json_response({"status": "running", "webhook": WEBHOOK_URL + WEBHOOK_PATH})

# 🚀 Основна функція запуску сервера
def main():
    logging.basicConfig(level=logging.INFO)
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", health_check)
    app.on_startup.append(on_startup)

    try:
        logging.info("🚀 Запуск сервера на порту 8000...")
        web.run_app(app, host="0.0.0.0", port=8000)
    except Exception as e:
        logging.error(f"❌ Помилка при запуску сервера: {e}")
    except (KeyboardInterrupt, SystemExit):
        logging.info("🛑 Бот завершив роботу")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"❌ Фатальна помилка: {e}")
    finally:
        bot.session.close()
