import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = "8838508680:AAHguMr07zwQ7hbSUKjyaNDB7bXd1DTh8b0"
PORT = int(os.environ.get("PORT", 8080))

# Создаем веб-сервер, который будет отдавать ваш index.html
async def handle_index(request):
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html")
    except FileNotFoundError:
        return web.Response(text="Файл index.html не найден на сервере!", status=404)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def cmd_start(message: types.Message):
        # Ссылка на ваш же BotHost сервер (вместо GitHub)
        webapp_url = f"https://{request_host_placeholder}/" # или ваш домен от BotHost
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🎮 Открыть PokéHunter MMO", web_app=WebAppInfo(url="ВАШ_ДОМЕН_ОТ_BOTHOST")))
        await message.answer("👋 <b>Добро пожаловать в PokéHunter MMO!</b>", reply_markup=builder.as_markup(), parse_mode="HTML")

    app = web.Application()
    app.router.add_get("/", handle_index)
    # Если у index.html есть стихи/картинки, можно добавить раздачу статики, если они внутри файла

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🚀 Сервер запущен на порту {PORT}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
