import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://poke-mini-app.onrender.com")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

class AttackNotify(BaseModel):
    defender_id: int  # Telegram ID защищающегося
    attacker_name: str
    defender_poke: str
    defender_cp: int

@app.get("/", response_class=HTMLResponse)
async def serve_game():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Игра загружается...</h1>"

# API для отправки уведомления о нападении
@app.post("/api/attack")
async def notify_attack(data: AttackNotify):
    try:
        text = (
            f"⚔️ <b>ВНИМАНИЕ! На вас напали на Арене!</b>\n\n"
            f"👤 Нападающий: <b>{data.attacker_name}</b>\n"
            f"🛡 Авто-защита выбрала вашего сильнейшего покемона: <b>{data.defender_poke}</b> ({data.defender_cp} CP)\n\n"
            f"Зайдите в игру, чтобы дать отпор и вернуть рейтинг!"
        )
        await bot.send_message(chat_id=data.defender_id, text=text, parse_mode="HTML")
        return {"status": "success", "message": "Notification sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@dp.message(Command("start"))
async def start_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть в PokéHunter MMO", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer(
        "👋 Добро пожаловать в PokéHunter MMO!\n\nНажми кнопку ниже, чтобы запустить игру:",
        reply_markup=keyboard
    )

async def run_bot():
    print("🤖 Telegram-бот запущен...")
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    uvicorn.run("bot:app", host="0.0.0.0", port=PORT)
