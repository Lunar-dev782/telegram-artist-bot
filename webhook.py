import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from bot import router, TOKEN 

# Токен та URL 

TOKEN = "7645134499:AAFRfwsn7dr5W2m81gCJPwX944PRqk-sjEc" 
WEBHOOK_URL = "https://telegram-artist-bot-f1nz.onrender.com" 
WEBHOOK_PATH = "/webhook/telegram" 

# Ініціалізація Bot
bot = Bot(token=TOKEN)

# Створюємо storage для Dispatcher
storage = MemoryStorage()

# Створюємо Dispatcher
dp = Dispatcher(storage=MemoryStorage())

# Підключаємо router до Dispatcher
dp.include_router(router)

# Функція для встановлення вебхука
async def on_startup(app):
    try:
        # Встановлюємо вебхук
        await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
        logging.info(f"✅ Webhook встановлено: {WEBHOOK_URL}{WEBHOOK_PATH}")
    except Exception as e:
        logging.error(f"❌ Помилка при встановленні вебхука: {e}")

 #Обробка запиту вебхука
async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update(**data)
        logging.info(f"📲 Отримано оновлення: {update}")

        # Використовуємо коректний метод
        await dp.feed_update(bot, update)  # ✅ Виправлено

        return web.Response(status=200)
    except Exception as e:
        logging.error(f"❌ Помилка обробки запиту: {e}")
        return web.Response(status=500)


# ✅ Перевірка стану сервера (Uptime Robot)
async def health_check(request):
    return web.json_response({"status": "running", "webhook": WEBHOOK_URL + WEBHOOK_PATH})

# 🔥 Основна функція запуску сервера
def main():
    logging.basicConfig(level=logging.INFO)

    # Створення та налаштування додатка aiohttp
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", health_check)  # Додаємо маршрут для Uptime Robot
    app.on_startup.append(on_startup)

    try:
        logging.info("🚀 Запуск сервера на порту 8000...")
        web.run_app(app, host="0.0.0.0", port=8000)
    except Exception as e:
        logging.error(f"❌ Помилка при запуску серверу: {e}")
    except (KeyboardInterrupt, SystemExit):
        logging.info("🛑 Бот завершив роботу")

# 🔧 Запуск бота
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"❌ Фатальна помилка: {e}")
    finally:
        # Закриваємо сесію бота після завершення всіх операцій
        bot.session.close()  
