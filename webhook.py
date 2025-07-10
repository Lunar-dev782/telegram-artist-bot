import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from bot import router, TOKEN

# Токен та URL
TOKEN = "7645134499:AAFRfwsn7dr5W2m81gCJPwX944PRqk-sjEc"
WEBHOOK_URL = "https://telegram-artist-bot.onrender.com"
WEBHOOK_PATH = "/webhook/telegram"

# 🤖 Ініціалізація бота
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
dp.include_router(router)

# 🪪 Echo-хендлер (для тесту)
@dp.message()
async def echo_message(message: Message):
    await message.answer(f"Ти написав: {message.text}")

# 📌 Встановлюємо webhook на старті
async def on_startup(app: web.Application):
    webhook_full_url = WEBHOOK_URL + WEBHOOK_PATH
    await bot.set_webhook(webhook_full_url)
    logging.info(f"✅ Webhook встановлено: {webhook_full_url}")

# 📥 Обробка оновлень
async def handle_webhook(request: web.Request):
    try:
        data = await request.json()
        update = Update(**data)
        await dp.feed_update(bot, update)
        return web.Response(status=200)
    except Exception as e:
        logging.exception("❌ Помилка при обробці webhook-запиту:")
        return web.Response(status=500)

# 🔄 Health-check
async def health_check(request: web.Request):
    return web.json_response({"status": "running", "webhook": WEBHOOK_URL + WEBHOOK_PATH})

# 🚀 Запуск Aiohttp-серверу
def main():
    logging.basicConfig(level=logging.INFO)

    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/", health_check)
    app.on_startup.append(on_startup)

    web.run_app(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("❌ Фатальна помилка:")
