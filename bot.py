import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI
import uvicorn

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получаем переменные окружения
TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН_БОТА")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://poke-mini-app.onrender.com")
PORT = int(os.getenv("PORT", 10000))

# Инициализация бота и FastAPI
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Эндпоинт для проверки здоровья сервера (Render требует этот порт)
@app.get("/")
async def root():
    return {"status": "online", "game": "PokeHunter MMO Server"}

# Команда /start в Telegram
@dp.message(Command("start"))
async def start_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть в PokéHunter MMO", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer(
        "👋 Добро пожаловать в PokéHunter MMO (Online Server Mode)!\n\nНажми кнопку ниже, чтобы зайти в игру:",
        reply_markup=keyboard
    )

async def run_bot():
    print("🤖 Telegram-бот запущен...")
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    # Запускаем бота в фоне вместе с FastAPI
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    # Запуск сервера на порту, который требует Render
    uvicorn.run("bot:app", host="0.0.0.0", port=PORT)
