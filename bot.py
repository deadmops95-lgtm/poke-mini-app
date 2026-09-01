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

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://poke-mini-app.onrender.com")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

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

class AdminPokeGive(BaseModel):
    target_username: str
    poke_id: int
    poke_name: str
    poke_cp: int

class AttackNotify(BaseModel):
    defender_username: str
    attacker_name: str
    defender_poke: str
    defender_cp: int

@app.get("/", response_class=HTMLResponse)
async def serve_game():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Игра загружается...</h1>"

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
        "exists": True, "user_id": row[0], "username": row[1],
        "coins": row[2], "candies": row[3], "pokeballs": row[4],
        "energy": row[5], "pokedex": row[6], "stats_caught": row[7], "stats_shiny": row[8]
    }
    conn.close()
    return data

@app.post("/api/user/save")
async def save_user(user: UserSync):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, coins, candies, pokeballs, energy, pokedex, stats_caught, stats_shiny)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username, coins=excluded.coins, candies=excluded.candies,
            pokeballs=excluded.pokeballs, energy=excluded.energy, pokedex=excluded.pokedex,
            stats_caught=excluded.stats_caught, stats_shiny=excluded.stats_shiny
    """, (user.user_id, user.username, user.coins, user.candies, user.pokeballs, user.energy, user.pokedex, user.stats_caught, user.stats_shiny))
    conn.commit()
    conn.close()
    return {"status": "saved"}

# Статистика: только онлайн и сколько всего зарегистрировалось
@app.get("/api/admin/stats")
async def get_server_stats():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0] or 1
    conn.close()
    return {
        "online_users": total_users,
        "total_registered": total_users
    }

@app.post("/api/admin/give-poke")
async def admin_give_poke(data: AdminPokeGive):
    clean_target = data.target_username.replace("@", "").strip().lower()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, pokedex FROM users WHERE LOWER(username) = ?", (clean_target,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Игрок не найден в базе данных!")
    
    user_id, pokedex_json = row[0], row[1]
    try:
        pokedex = json.loads(pokedex_json or "[]")
    except:
        pokedex = []
    
    new_poke = {"id": data.poke_id, "name": data.poke_name, "cp": data.poke_cp, "is_shiny": False}
    pokedex.insert(0, new_poke)
    
    cursor.execute("UPDATE users SET pokedex = ? WHERE user_id = ?", (json.dumps(pokedex), user_id))
    conn.commit()
    conn.close()
    
    try:
        await bot.send_message(chat_id=user_id, text=f"🎁 Админ выдал вам покемона: <b>{data.poke_name}</b> ({data.poke_cp} CP)!", parse_mode="HTML")
    except:
        pass
        
    return {"status": "success"}

@app.post("/api/attack")
async def notify_attack(data: AttackNotify):
    clean_target = data.defender_username.replace("@", "").strip().lower()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (clean_target,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Защитник не найден!")
        
    defender_id = row[0]
    try:
        text = f"⚔️ <b>На вас напали на Арене!</b>\n\n👤 Нападающий: <b>{data.attacker_name}</b>\n🛡 Авто-защита выбрала: <b>{data.defender_poke}</b> ({data.defender_cp} CP)\n\nЗайдите в игру дать отпор!"
        await bot.send_message(chat_id=defender_id, text=text, parse_mode="HTML")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@dp.message(Command("start"))
async def start_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть в PokéHunter MMO", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer("👋 Добро пожаловать в PokéHunter MMO!", reply_markup=keyboard)

async def run_bot():
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    uvicorn.run("bot:app", host="0.0.0.0", port=PORT)
