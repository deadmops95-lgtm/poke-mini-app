import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# Токен берется из переменных окружения Render (или можно вписать напрямую для теста)
TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН_БОТА_ОТ_BOTFATHER")
# Ссылка на твой сайт (когда опубликуешь на Render, укажи её здесь)
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://poke-hunter-mmo.onrender.com")

dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть в PokéHunter MMO", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer(
        "👋 Добро пожаловать в PokéHunter MMO!\n\nНажми кнопку ниже, чтобы запустить игру:",
        reply_markup=keyboard
    )

async def main():
    bot = Bot(token=TOKEN)
    print("Бот запущен и ожидает подключения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
