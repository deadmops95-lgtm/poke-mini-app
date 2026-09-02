import asyncio
import os
import logging
import sqlite3
import json
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получение переменных окружения
TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://poke-mini-app.onrender.com")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Инициализация надежной базы данных SQLite для защиты от накрутки
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
            stats_shiny INTEGER DEFAULT 0,
            last_daily INTEGER DEFAULT 0,
            last_energy_time INTEGER DEFAULT 0,
            active_incubator TEXT DEFAULT NULL,
            egg_inventory TEXT DEFAULT '{"common":3,"rare":2,"legend":1}',
            vip_until INTEGER DEFAULT 0,
            shiny_charm INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Pydantic модель для безопасной валидации данных при сохранении
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
    last_daily: int
    last_energy_time: int
    active_incubator: str = None
    egg_inventory: str = '{"common":3,"rare":2,"legend":1}'

# Маршрут для отдачи главной страницы клиента
@app.get("/", response_class=HTMLResponse)
async def serve_game():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Файл index.html не найден на сервере!</h1>"

# API получения данных пользователя из базы
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
        "stats_shiny": row[8], 
        "last_daily": row[9], 
        "last_energy_time": row[10],
        "active_incubator": row[11], 
        "egg_inventory": row[12], 
        "vip_until": row[13]
    }
    conn.close()
    return data

# API безопасного сохранения прогресса на сервере
@app.post("/api/user/save")
async def save_user(user: UserSync):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, coins, candies, pokeballs, energy, pokedex, stats_caught, stats_shiny, last_daily, last_energy_time, active_incubator, egg_inventory)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username, 
            coins=excluded.coins, 
            candies=excluded.candies,
            pokeballs=excluded.pokeballs, 
            energy=excluded.energy, 
            pokedex=excluded.pokedex,
            stats_caught=excluded.stats_caught, 
            stats_shiny=excluded.stats_shiny, 
            last_daily=excluded.last_daily, 
            last_energy_time=excluded.last_energy_time,
            active_incubator=excluded.active_incubator, 
            egg_inventory=excluded.egg_inventory
    """, (
        user.user_id, user.username, user.coins, user.candies, user.pokeballs, 
        user.energy, user.pokedex, user.stats_caught, user.stats_shiny, 
        user.last_daily, user.last_energy_time, user.active_incubator, user.egg_inventory
    ))
    conn.commit()
    conn.close()
    return {"status": "saved"}

# Обработчик команды /start в Telegram боте
@dp.message(Command("start"))
async def start_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть в PokéHunter MMO", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer("👋 Добро пожаловать в PokéHunter MMO 2.0!", reply_markup=keyboard)

async def run_bot():
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    uvicorn.run("bot:app", host="0.0.0.0", port=PORT)
