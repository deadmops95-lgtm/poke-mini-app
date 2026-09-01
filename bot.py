import asyncio
import os
import logging
import sqlite3
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

# Инициализация базы данных SQLite
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 500,
            candies INTEGER DEFAULT 10,
            pokeballs INTEGER DEFAULT 15,
            energy INTEGER DEFAULT 100,
            pokedex TEXT DEFAULT '[]',
            stats_caught INTEGER DEFAULT 1,
            stats_shiny INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Pydantic модели для API
class UserSync(BaseModel):
    user_id: int
    username: str
    coins: int
    candies: int
    pokeballs: int
    energy: int
    pokedex: str
    stats_caught: int
    stats_shiny: int

class AdminAction(BaseModel):
    admin_username: str
    target_user: str
    action_type: str  # coins, candies, balls
    amount: int

class AttackNotify(BaseModel):
    defender_id: int
    attacker_name: str
    defender_poke: str
    defender_cp: int

@app.get("/", response_class=HTMLResponse)
async def serve_game():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Игра загружается...</h1>"

# Получение данных игрока с сервера
@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return {"exists": False}
    
    data = {
        "exists": True,
        "user_id": row[0],
        "username": row[1],
        "coins": row[2],
        "candies": row[3],
        "pokeballs": row[4],
        "energy": row[5],
        "pokedex": row[6],
        "stats_caught": row[7],
        "stats_shiny": row[8]
    }
    conn.close()
    return data

# Синхронизация и сохранение данных игрока
@app.post("/api/user/save")
async def save_user(user: UserSync):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, coins, candies, pokeballs, energy, pokedex, stats_caught, stats_shiny)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            coins=excluded.coins,
            candies=excluded.candies,
            pokeballs=excluded.pokeballs,
            energy=excluded.energy,
            pokedex=excluded.pokedex,
            stats_caught=excluded.stats_caught,
            stats_shiny=excluded.stats_shiny
    """, (user.user_id, user.username, user.coins, user.candies, user.pokeballs, user.energy, user.pokedex, user.stats_caught, user.stats_shiny))
    conn.commit()
    conn.close()
    return {"status": "saved"}

# Статистика сервера для админки
@app.get("/api/admin/stats")
async def get_server_stats():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(coins), SUM(stats_caught) FROM users")
    row = cursor.fetchone()
    conn.close()
    return {
        "online_users": row[0] or 1,
        "total_coins": row[1] or 500,
        "total_caught": row[2] or 1
    }

# Уведомление о нападении на арене
@app.post("/api/attack")
async def notify_attack(data: AttackNotify):
    try:
        text = (
            f"⚔️ <b>ВНИМАНИЕ! На вас напали на Арене!</b>\n\n"
            f"👤 Нападающий: <b>{data.attacker_name}</b>\n"
            f"🛡 Авто-защита выбрала вашего сильнейшего покемона: <b>{data.defender_poke}</b> ({data.defender_cp} CP)\n\n"
            f"Зайдите в игру, чтобы дать отпор!"
        )
        await bot.send_message(chat_id=data.defender_id, text=text, parse_mode="HTML")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@dp.message(Command("start"))
async def start_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть в PokéHunter MMO", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer(
        "👋 Добро пожаловать в PokéHunter MMO (Online Server Mode)!\n\nНажми кнопку ниже, чтобы запустить игру:",
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
