import asyncio
import json
import logging
import os
import random
import sqlite3
import time
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, WebAppInfo, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = "8838508680:AAHguMr07zwQ7hbSUKjyaNDB7bXd1DTh8b0"
WEBAPP_URL = "https://prokudin95.github.io/pokemon-app/"
PORT = int(os.environ.get("PORT", 8080))

MAX_ENERGY = 100
ENERGY_RECOVERY_SECONDS = 120

POKEMON_DB = {
    "Legendary": [(144, "Артикуно", 1), (150, "Мьюту", 1), (384, "Райкваза", 3), (493, "Аркеус", 4), (643, "Реширам", 5)],
    "Epic": [(3, "Венузавр", 1), (6, "Чаризард", 1), (9, "Бластойз", 1), (94, "Генгар", 1), (149, "Драгонайт", 1)],
    "Rare": [(25, "Пикачу", 1), (26, "Райчу", 1), (133, "Иви", 1), (134, "Вапореон", 1)],
    "Common": [(1, "Бульбазавр", 1), (4, "Чармандер", 1), (7, "Сквиртл", 1), (152, "Чикорита", 2), (155, "Синдаквил", 2)]
}

def get_db():
    conn = sqlite3.connect("pokemon_bot.db")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 500,
            candies INTEGER DEFAULT 10,
            energy INTEGER DEFAULT 100,
            last_energy_calc REAL DEFAULT 0,
            dungeon_floor INTEGER DEFAULT 1,
            tourney_stage INTEGER DEFAULT 1
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            pokemon_id INTEGER,
            pokemon_name TEXT,
            gen INTEGER DEFAULT 1,
            rarity TEXT,
            is_shiny INTEGER DEFAULT 0,
            cp INTEGER DEFAULT 100
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def get_user_data(user_id: int, username: str = ""):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    u = cur.fetchone()
    now = time.time()
    
    if not u:
        cur.execute("INSERT INTO users (user_id, username, coins, candies, energy, last_energy_calc) VALUES (?, ?, 500, 10, 100, ?)", (user_id, username, now))
        cur.execute("INSERT INTO inventory (user_id, pokemon_id, pokemon_name, gen, rarity, is_shiny, cp) VALUES (?, 25, 'Пикачу', 1, 'Rare', 0, 780)", (user_id,))
        conn.commit()
        cur.close()
        conn.close()
        return get_user_data(user_id, username)

    col_names = [desc[0] for desc in cur.description]
    user_dict = dict(zip(col_names, u))

    last_calc = user_dict.get("last_energy_calc", now)
    current_energy = user_dict.get("energy", 100)
    if current_energy < MAX_ENERGY:
        recovered = int((now - last_calc) / ENERGY_RECOVERY_SECONDS)
        if recovered > 0:
            new_energy = min(MAX_ENERGY, current_energy + recovered)
            cur.execute("UPDATE users SET energy = ?, last_energy_calc = ? WHERE user_id = ?", (new_energy, now, user_id))
            conn.commit()
            user_dict["energy"] = new_energy
            user_dict["last_energy_calc"] = now

    cur.close()
    conn.close()
    return user_dict

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=200)
    else:
        response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

async def api_options_handler(request):
    return web.Response(status=200)

async def api_admin_stats_handler(request):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM inventory")
        total_pokemon = cur.fetchone()[0]
        cur.execute("SELECT SUM(coins) FROM users")
        total_coins = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM inventory WHERE is_shiny = 1")
        total_shiny = cur.fetchone()[0]
        cur.close()
        conn.close()
        return web.json_response({"status": "ok", "stats": {"users": total_users, "caught": total_pokemon, "coins": total_coins, "shiny": total_shiny}})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def api_hunt_handler(request):
    try:
        data = await request.json()
        uid = int(data.get("user_id", 0))
        u = get_user_data(uid)
        
        if u["energy"] < 20:
            return web.json_response({"status": "error", "message": "Недостаточно энергии!"})

        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET energy = energy - 20, coins = coins + 25, last_energy_calc = ? WHERE user_id = ?", (time.time(), uid))

        roll = random.random()
        rarity = "Rare" if roll > 0.85 else "Common"
        pool = POKEMON_DB.get(rarity, POKEMON_DB["Common"])
        pid, name, gen = random.choice(pool)
        shiny = 1 if random.random() < 0.05 else 0
        cp = random.randint(300, 800) if rarity == "Common" else random.randint(1200, 2000)

        cur.execute("INSERT INTO inventory (user_id, pokemon_id, pokemon_name, gen, rarity, is_shiny, cp) VALUES (?, ?, ?, ?, ?, ?, ?)", (uid, pid, name, gen, rarity, shiny, cp))
        inv_id = cur.lastrowid
        conn.commit()
        cur.close()
        conn.close()

        return web.json_response({
            "status": "ok",
            "energy": u["energy"] - 20,
            "coins": u["coins"] + 25,
            "pokemon": {"inv_id": inv_id, "id": pid, "name": name, "gen": gen, "type": "⚪️ Обычный", "cp": cp, "is_shiny": bool(shiny)}
        })
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

# ЧЕСТНЫЙ БОЕВОЙ ДВИЖОК И ПОИСК СИЛЬНЕЙШЕГО ПОКЕМОНА ИГРОКА
async def api_battle_handler(request):
    try:
        data = await request.json()
        uid = int(data.get("user_id", 0))
        my_cp = int(data.get("my_cp", 500))
        target_query = data.get("target", "")
        battle_type = data.get("battle_type", "pvp")
        
        enemy_cp = int(data.get("enemy_cp", 1000))
        enemy_name = data.get("enemy_name", "Соперник")

        # Если это PvP вызов по нику — ищем реального игрока и его сильнейшего покемона в БД
        bot_instance = request.app['bot']
        if battle_type == "pvp" and target_query:
            clean_target = target_query.lstrip("@").lower()
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (clean_target,))
            row = cur.fetchone()
            if row:
                target_uid = row[0]
                cur.execute("SELECT pokemon_name, cp FROM inventory WHERE user_id = ? ORDER BY cp DESC LIMIT 1", (target_uid,))
                p_row = cur.fetchone()
                if p_row:
                    enemy_name = f"@{clean_target} ({p_row[0]})"
                    enemy_cp = p_row[1]
                
                # Отправляем оповещение игроку, которого вызвали на бой
                try:
                    await bot_instance.send_message(
                        target_uid, 
                        f"⚔️ <b>Вас вызвали на дуэль на PvP Арену!</b>\nСоперник проверил вашу защиту. Готовьтесь к отпору!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            cur.close()
            conn.close()

        # ЧЕСТНЫЙ РАСЧЕТ БОЯ: Сравнение CP
        is_win = my_cp >= enemy_cp

        reward_coins = 50
        reward_candies = 0
        dungeon_floor = 1

        conn = get_db()
        cur = conn.cursor()
        if is_win:
            if battle_type == "tourney":
                reward_coins = 200
            elif battle_type == "elemental_cup":
                reward_coins = 500
                reward_candies = 20
            elif battle_type == "dungeon":
                reward_coins = 150
                reward_candies = 5
                cur.execute("SELECT dungeon_floor FROM users WHERE user_id = ?", (uid,))
                r = cur.fetchone()
                current_f = r[0] if r else 1
                dungeon_floor = 1 if current_f >= 3 else current_f + 1
                cur.execute("UPDATE users SET dungeon_floor = ? WHERE user_id = ?", (dungeon_floor, uid))
            elif battle_type in ["tower", "gym"]:
                reward_coins = 150
                reward_candies = 3

            cur.execute("UPDATE users SET coins = coins + ?, candies = candies + ? WHERE user_id = ?", (reward_coins, reward_candies, uid))
            conn.commit()
        cur.close()
        conn.close()

        return web.json_response({
            "status": "ok",
            "win": is_win,
            "enemy_name": enemy_name,
            "enemy_cp": enemy_cp,
            "reward_coins": reward_coins if is_win else 0,
            "reward_candies": reward_candies if is_win else 0,
            "dungeon_floor": dungeon_floor
        })
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    get_user_data(message.from_user.id, message.from_user.username or "")
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎮 Открыть PokéHunter MMO 3.0", web_app=WebAppInfo(url=WEBAPP_URL)))
    await message.answer("👋 <b>Добро пожаловать в PokéHunter MMO 3.0!</b> Все бои и подземелья настроены честно.", reply_markup=builder.as_markup(), parse_mode="HTML")

async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    bot = Bot(token=BOT_TOKEN)

    app = web.Application(middlewares=[cors_middleware])
    app['bot'] = bot # Передаем экземпляр бота для отправки уведомлений
    app.router.add_options("/{tail:.*}", api_options_handler)
    app.router.add_post("/api/admin_stats", api_admin_stats_handler)
    app.router.add_post("/api/hunt", api_hunt_handler)
    app.router.add_post("/api/battle", api_battle_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"🚀 API сервер запущен на порту {PORT}!")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
