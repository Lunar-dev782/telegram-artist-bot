import asyncio
import logging
import os
import traceback
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
        webhook_info = await bot.get_webhook_info()
        logging.info(f"Поточний вебхук: {webhook_info.url}, pending_updates: {webhook_info.pending_update_count}")
        if not webhook_info.url or webhook_info.url != WEBHOOK_URL + WEBHOOK_PATH:
            await bot.delete_webhook(drop_pending_updates=True)  # Видаляємо старий вебхук
            await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
            logging.info(f"✅ Webhook встановлено: {WEBHOOK_URL}{WEBHOOK_PATH}")
        else:
            logging.info(f"✅ Webhook вже встановлено: {webhook_info.url}")
    except Exception as e:
        logging.error(f"❌ Помилка при встановленні вебхука: {e}, traceback={traceback.format_exc()}")

# Обробка запиту вебхука
async def handle_webhook(request):
    if request.method == "POST":
        try:
            data = await request.json()
            update = Update(**data)
            logging.info(f"📲 Отримано оновлення: update_id={update.update_id}, type={update.__class__.__name__}, data={data}")
            await dp.feed_update(bot, update)
            return web.Response(status=200)
        except Exception as e:
            logging.error(f"❌ Помилка обробки запиту: {e}, traceback={traceback.format_exc()}")
            return web.Response(status=500)
    return web.Response(status=405)  # Повертаємо 405 для не-ПОСТ запитів

# Перевірка стану сервера (Uptime Robot)
async def health_check(request):
    return web.json_response({"status": "running", "webhook": WEBHOOK_URL + WEBHOOK_PATH})

# Основна функція запуску сервера
def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", health_check)  # Додано GET для / (здоров’я)
    app.on_startup.append(on_startup)

    try:
        port = int(os.getenv("PORT", 8000))  # Використовуємо порт із змінної середовища, за замовчуванням 8000
        logging.info(f"🚀 Запуск сервера на порті {port}...")
        web.run_app(app, host="0.0.0.0", port=port)
    except Exception as e:
        logging.error(f"❌ Помилка при запуску серверу: {e}, traceback={traceback.format_exc()}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"❌ Фатальна помилка: {e}, traceback={traceback.format_exc()}")
    finally:
        asyncio.run(bot.session.close())
