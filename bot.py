import os
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Настройка логирования, чтобы в панели BotHost появились те самые логи
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8838508680:AAHguMr07zwQ7hbSUKjyaNDB7bXd1DTh8b0"
PORT = int(os.environ.get("PORT", 8080))

# Веб-сервер отдает ваш index.html прямо с сервера BotHost
async def handle_index(request):
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html")
    except FileNotFoundError:
        return web.Response(text="Ошибка: файл index.html не загружен в корневую папку BotHost!", status=404)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def cmd_start(message: types.Message):
        # Получаем адрес нашего сервера на BotHost автоматически
        # (или вставьте сюда вашу прямую ссылку от BotHost, например: https://your-bot.othost.ru/)
        bot_info = await bot.get_me()
        
        # Создаем кнопку, ведущую на сервер BotHost
        builder = InlineKeyboardBuilder()
        # Вместо ДАНОГО примера подставьте домен, который вам выдал BotHost
        builder.row(InlineKeyboardButton(text="🎮 Играть в PokéHunter", web_app=WebAppInfo(url="ЗДЕСЬ_ССЫЛКА_ОТ_BOTHOST")))
        
        await message.answer("👋 <b>Добро пожаловать в PokéHunter MMO!</b>", reply_markup=builder.as_markup(), parse_mode="HTML")

    app = web.Application()
    app.router.add_get("/", handle_index)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"🚀 Веб-сервер и бот успешно запущены на порту {PORT}!")

    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
