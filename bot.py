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
            stats_shiny INTEGER DEFAULT 0,
            last_daily INTEGER DEFAULT 0,
            last_energy_time INTEGER DEFAULT 0,
            active_incubator TEXT DEFAULT NULL,
            egg_inventory TEXT DEFAULT '{"common":3,"rare":2,"legend":1}',
            vip_until INTEGER DEFAULT 0,
            shiny_charm INTEGER DEFAULT 0,
            dungeon_level INTEGER DEFAULT 1,
            dungeon_reset_time INTEGER DEFAULT 0,
            last_wheel_spin INTEGER DEFAULT 0
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
    last_daily: int
    last_energy_time: int
    active_incubator: str = None
    egg_inventory: str = '{"common":3,"rare":2,"legend":1}'
    dungeon_level: int = 1
    dungeon_reset_time: int = 0
    last_wheel_spin: int = 0

class AttackNotify(BaseModel):
    defender_username: str
    attacker_name: str
    defender_poke: str
    defender_cp: int

class AdminGive(BaseModel):
    target_username: str
    item_type: str
    poke_id: int = 0
    amount: int = 0

@app.get("/", response_class=HTMLResponse)
async def serve_game():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Файл index.html не найден на сервере!</h1>"

@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, coins, candies, pokeballs, energy, pokedex, stats_caught, stats_shiny, last_daily, last_energy_time, active_incubator, egg_inventory, vip_until, dungeon_level, dungeon_reset_time, last_wheel_spin FROM users WHERE user_id = ?", (user_id,))
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
        "vip_until": row[13],
        "dungeon_level": row[14],
        "dungeon_reset_time": row[15],
        "last_wheel_spin": row[16]
    }
    conn.close()
    return data

@app.post("/api/user/save")
async def save_user(user: UserSync):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, coins, candies, pokeballs, energy, pokedex, stats_caught, stats_shiny, last_daily, last_energy_time, active_incubator, egg_inventory, dungeon_level, dungeon_reset_time, last_wheel_spin)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            egg_inventory=excluded.egg_inventory,
            dungeon_level=excluded.dungeon_level,
            dungeon_reset_time=excluded.dungeon_reset_time,
            last_wheel_spin=excluded.last_wheel_spin
    """, (
        user.user_id, user.username, user.coins, user.candies, user.pokeballs, 
        user.energy, user.pokedex, user.stats_caught, user.stats_shiny, 
        user.last_daily, user.last_energy_time, user.active_incubator, user.egg_inventory,
        user.dungeon_level, user.dungeon_reset_time, user.last_wheel_spin
    ))
    conn.commit()
    conn.close()
    return {"status": "saved"}

@app.get("/api/pvp/find/{username}")
async def find_pvp_opponent(username: str):
    clean_target = username.replace("@", "").strip().lower()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, pokedex FROM users WHERE LOWER(username) = ?", (clean_target,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Игрок не найден!")

    pokedex = json.loads(row[1] or "[]")
    if not pokedex:
        raise HTTPException(status_code=400, detail="У игрока нет покемонов!")

    strongest = max(pokedex, key=lambda x: x.get('cp', 0))
    return {
        "username": row[0],
        "defender_poke": strongest.get('name', 'Покемон'),
        "defender_poke_id": strongest.get('id', 25),
        "defender_cp": strongest.get('cp', 300)
    }

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
        text = f"⚔️ <b>На вас напали на Арене!</b>\n\n👤 Нападающий: <b>{data.attacker_name}</b>\n🛡 Защитник: <b>{data.defender_poke}</b> ({data.defender_cp} CP)"
        await bot.send_message(chat_id=defender_id, text=text, parse_mode="HTML")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/stats")
async def get_server_stats():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0] or 1
    conn.close()
    return {"online_users": total_users, "total_registered": total_users}

@app.post("/api/admin/give")
async def admin_give(data: AdminGive):
    clean_target = data.target_username.replace("@", "").strip().lower()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, coins, candies, pokeballs, pokedex FROM users WHERE LOWER(username) = ?", (clean_target,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Игрок не найден в базе данных!")
    
    user_id, coins, candies, pokeballs, pokedex_json = row[0], row[1], row[2], row[3], row[4]
    try:
        pokedex = json.loads(pokedex_json or "[]")
    except:
        pokedex = []
    
    msg_text = ""
    if data.item_type == "poke":
        new_poke = {"id": data.poke_id, "cp": 300 + (data.poke_id * 8), "is_shiny": False}
        pokedex.insert(0, new_poke)
        cursor.execute("UPDATE users SET pokedex = ? WHERE user_id = ?", (json.dumps(pokedex), user_id))
        msg_text = f"🎁 Администратор подарил вам покемона <b>#{data.poke_id}</b>!"
    elif data.item_type == "coins":
        coins += data.amount
        cursor.execute("UPDATE users SET coins = ? WHERE user_id = ?", (coins, user_id))
        msg_text = f"🎁 Начислено монеты: <b>+{data.amount} 🪙</b>!"
    elif data.item_type == "candies":
        candies += data.amount
        cursor.execute("UPDATE users SET candies = ? WHERE user_id = ?", (candies, user_id))
        msg_text = f"🎁 Начислено конфеты: <b>+{data.amount} 🍬</b>!"
    elif data.item_type == "pokeballs":
        pokeballs += data.amount
        cursor.execute("UPDATE users SET pokeballs = ? WHERE user_id = ?", (pokeballs, user_id))
        msg_text = f"🎁 Начислено покеболы: <b>+{data.amount} 🔴</b>!"

    conn.commit()
    conn.close()
    
    try:
        await bot.send_message(chat_id=user_id, text=msg_text, parse_mode="HTML")
    except:
        pass
        
    return {"status": "success"}

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
