import asyncio
import logging
import os
from aiohttp import web
from aiogram.types import Update
from bot import dp, bot, TOKEN  # Імпортуємо dp, bot, TOKEN із bot.py

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s - %(message)s')

# Токен та URL
WEBHOOK_URL = "https://telegram-artist-bot-f1nz.onrender.com"
WEBHOOK_PATH = "/webhook/telegram"

# Функція для встановлення вебхука
async def on_startup(app):
    try:
        await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
        logging.info(f"✅ Webhook встановлено: {WEBHOOK_URL}{WEBHOOK_PATH}")
    except Exception as e:
        logging.error(f"❌ Помилка при встановленні вебхука: {e}")

# Обробка запиту вебхука
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

# Перевірка стану сервера (Uptime Robot)
async def health_check(request):
    return web.json_response({"status": "running", "webhook": WEBHOOK_URL + WEBHOOK_PATH})

# Основна функція запуску сервера
def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", health_check)
    app.on_startup.append(on_startup)

    try:
        logging.info("🚀 Запуск сервера...")
        web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
    except Exception as e:
        logging.error(f"❌ Помилка при запуску серверу: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"❌ Фатальна помилка: {e}")
    finally:
        asyncio.run(bot.session.close())
