import asyncio
import json
import logging
import os
import random
import sqlite3
import time
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardButton, WebAppInfo,
    LabeledPrice, PreCheckoutQuery
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ================= 1. НАСТРОЙКИ И СЕТЬ =================
BOT_TOKEN = "8838508680:AAHguMr07zwQ7hbSUKjyaNDB7bXd1DTh8b0"
WEBAPP_URL = "https://prokudin95.github.io/pokemon-app/"  # Ваша ссылка на GitHub Pages
PORT = int(os.environ.get("PORT", 8080))

ADMIN_USERNAMES = ["prokudin95"]
ADMIN_IDS = set()

def check_admin(user_id: int, username: str = "") -> bool:
    if user_id in ADMIN_IDS:
        return True
    if username and username.lower().lstrip("@") in [u.lower().lstrip("@") for u in ADMIN_USERNAMES]:
        ADMIN_IDS.add(user_id)
        return True
    return False

MAX_ENERGY = 100
ENERGY_RECOVERY_SECONDS = 120  # +1 ⚡️ каждые 2 минуты

CP_RANGES = {
    "Common": (100, 500),
    "Uncommon": (500, 1100),
    "Rare": (1100, 2100),
    "Epic": (2100, 3400),
    "Legendary": (3500, 5500)
}

# ================= 2. БАЗА 5 ПОКОЛЕНИЙ ПОКЕМОНОВ =================
POKEMON_DB = {
    "Legendary": [
        (144, "Артикуно", 1), (145, "Запдос", 1), (146, "Молтрес", 1), (150, "Мьюту", 1), (151, "Мью", 1),
        (243, "Райко", 2), (244, "Энтей", 2), (245, "Суикун", 2), (249, "Лугия", 2), (250, "Хо-Ох", 2),
        (382, "Кайогр", 3), (383, "Граудон", 3), (384, "Райкваза", 3), (386, "Деоксис", 3),
        (483, "Диалга", 4), (484, "Палкия", 4), (487, "Гиратина", 4), (493, "Аркеус", 4),
        (643, "Реширам", 5), (644, "Зекром", 5), (646, "Кюрем", 5)
    ],
    "Epic": [
        (3, "Венузавр", 1), (6, "Чаризард", 1), (9, "Бластойз", 1), (94, "Генгар", 1), (149, "Драгонайт", 1),
        (160, "Фералигатр", 2), (212, "Скизор", 2), (248, "Тиранитар", 2),
        (254, "Септиль", 3), (257, "Блейзикен", 3), (260, "Свамперт", 3), (373, "Саламенс", 3), (376, "Метагросс", 3),
        (448, "Лукарио", 4), (445, "Гарчомп", 4), (475, "Галлейд", 4),
        (571, "Зороарк", 5), (635, "Хайдрейгон", 5), (637, "Волкарона", 5)
    ],
    "Rare": [
        (25, "Пикачу", 1), (26, "Райчу", 1), (59, "Арканайн", 1), (131, "Лапрас", 1), (133, "Иви", 1),
        (169, "Кробат", 2), (181, "Амфарос", 2), (196, "Эспеон", 2), (197, "Умбреон", 2),
        (282, "Гардевуар", 3), (330, "Флайгон", 3), (350, "Милотик", 3), (359, "Абсол", 3),
        (405, "Люксрэй", 4), (468, "Тогекисс", 4), (470, "Лифеон", 4), (471, "Гласеон", 4),
        (530, "Экскадрил", 5), (553, "Крукодайл", 5), (609, "Шанделюр", 5)
    ],
    "Uncommon": [
        (2, "Ивизавр", 1), (5, "Чармелеон", 1), (8, "Вартортл", 1), (18, "Пиджеот", 1),
        (153, "Бейлиф", 2), (156, "Квилава", 2), (159, "Кроконав", 2),
        (253, "Гровайл", 3), (256, "Комбаскен", 3), (259, "Марштомп", 3),
        (388, "Гротл", 4), (391, "Монферно", 4), (394, "Принплап", 4),
        (496, "Сервайн", 5), (499, "Пигнайт", 5), (502, "Дьювотт", 5)
    ],
    "Common": [
        (1, "Бульбазавр", 1), (4, "Чармандер", 1), (7, "Сквиртл", 1), (10, "Катерпи", 1), (16, "Пиджи", 1), (19, "Раттата", 1),
        (152, "Чикорита", 2), (155, "Синдаквил", 2), (158, "Тотодайл", 2), (161, "Сентрет", 2),
        (252, "Трико", 3), (255, "Торчик", 3), (258, "Мадкип", 3), (261, "Пучиена", 3),
        (387, "Туртвиг", 4), (390, "Чимчар", 4), (393, "Пиплап", 4), (396, "Старли", 4), (403, "Шинкс", 4),
        (495, "Снайви", 5), (498, "Тепиг", 5), (501, "Ошавотт", 5), (504, "Патрат", 5), (509, "Пуррлойн", 5)
    ]
}

POKEMON_TYPES = {
    1: "🌿 Трава", 2: "🌿 Трава", 3: "🌿 Трава", 4: "🔥 Огонь", 5: "🔥 Огонь", 6: "🔥 Огонь",
    7: "💧 Вода", 8: "💧 Вода", 9: "💧 Вода", 25: "⚡️ Электро", 26: "⚡️ Электро", 94: "👻 Призрак",
    131: "💧 Вода", 133: "⚪️ Обычный", 144: "❄️ Лед", 145: "⚡️ Электро", 146: "🔥 Огонь",
    149: "🐲 Дракон", 150: "🔮 Психик", 151: "🔮 Психик", 152: "🌿 Трава", 155: "🔥 Огонь",
    158: "💧 Вода", 160: "💧 Вода", 212: "⚙️ Сталь", 248: "🪨 Камень", 249: "🔮 Психик", 250: "🔥 Огонь",
    252: "🌿 Трава", 254: "🌿 Трава", 255: "🔥 Огонь", 257: "🔥 Огонь", 258: "💧 Вода", 260: "💧 Вода",
    373: "🐲 Дракон", 376: "⚙️ Сталь", 382: "💧 Вода", 383: "🏜 Земля", 384: "🐲 Дракон",
    387: "🌿 Трава", 390: "🔥 Огонь", 393: "💧 Вода", 448: "🥋 Боевой", 493: "⚪️ Обычный",
    495: "🌿 Трава", 498: "🔥 Огонь", 501: "💧 Вода", 571: "🌑 Темный", 643: "🐲 Дракон"
}

EVOLUTIONS = {
    1: 2, 2: 3, 4: 5, 5: 6, 7: 8, 8: 9, 25: 26,
    152: 153, 153: 154, 155: 156, 156: 157, 158: 159, 159: 160,
    252: 253, 253: 254, 255: 256, 256: 257, 258: 259, 259: 260,
    387: 388, 388: 389, 390: 391, 391: 392, 393: 394, 394: 395,
    495: 496, 496: 497, 498: 499, 499: 500, 501: 502, 502: 503
}

ALL_POKEMON_MAP = {}
for r, p_list in POKEMON_DB.items():
    for item in p_list:
        pid, name, gen = item[0], item[1], item[2]
        ALL_POKEMON_MAP[pid] = {"name": name, "rarity": r, "gen": gen}

def generate_cp(rarity: str, is_shiny: bool) -> int:
    min_cp, max_cp = CP_RANGES.get(rarity, (100, 500))
    cp = random.randint(min_cp, max_cp)
    if is_shiny: cp = int(cp * 1.15)
    return cp

# ================= 3. БАЗА ДАННЫХ SQLITE =================
def get_db():
    conn = sqlite3.connect("pokemon_bot.db")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
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
            vip_until REAL DEFAULT 0,
            eggs_common INTEGER DEFAULT 1,
            eggs_rare INTEGER DEFAULT 1,
            eggs_legend INTEGER DEFAULT 0,
            egg_type TEXT DEFAULT NULL,
            egg_hatch_time REAL DEFAULT 0
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
            is_shadow INTEGER DEFAULT 0,
            cp INTEGER DEFAULT 100
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS towers (
            tower_id INTEGER PRIMARY KEY,
            name TEXT,
            req_cp INTEGER,
            champ_name TEXT DEFAULT 'Страж Лиги',
            p_name TEXT,
            p_id INTEGER,
            rate_hr INTEGER DEFAULT 15
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_uid ON inventory(user_id);")
    conn.commit()

    towers_init = [
        (1, "🥉 Башня Канто", 500, "Геодуд", 74, 15),
        (2, "🥈 Башня Джото", 1200, "Скизор", 212, 25),
        (3, "🥇 Башня Хоэнна", 2200, "Саламенс", 373, 45),
        (4, "💠 Башня Синно", 3100, "Лукарио", 448, 70),
        (5, "👑 Башня Юновы", 4000, "Зороарк", 571, 100),
        (6, "☠️ Башня Теней", 4600, "Теневой Мьюту", 150, 130),
        (7, "🌌 Башня Создателя", 5200, "Аркеус", 493, 200)
    ]
    for tid, tname, req_cp, pname, pid, rate in towers_init:
        cur.execute("""
            INSERT OR IGNORE INTO towers (tower_id, name, req_cp, champ_name, p_name, p_id, rate_hr)
            VALUES (?, ?, ?, 'Страж Лиги', ?, ?, ?)
        """, (tid, tname, req_cp, pname, pid, rate))
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
        cur.execute("""
            INSERT INTO users (user_id, username, coins, candies, energy, last_energy_calc)
            VALUES (?, ?, 500, 10, 100, ?)
        """, (user_id, username, now))
        cur.execute("""
            INSERT INTO inventory (user_id, pokemon_id, pokemon_name, gen, rarity, is_shiny, cp)
            VALUES (?, 25, 'Пикачу', 1, 'Rare', 0, 780)
        """, (user_id,))
        conn.commit()
        cur.close()
        conn.close()
        return get_user_data(user_id, username)

    col_names = [desc[0] for desc in cur.description]
    user_dict = dict(zip(col_names, u))

    # Серверный расчет регенерации энергии
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

def update_user(user_id: int, **kwargs):
    conn = get_db()
    cur = conn.cursor()
    for k, v in kwargs.items():
        cur.execute(f"UPDATE users SET {k} = ? WHERE user_id = ?", (v, user_id))
    conn.commit()
    cur.close()
    conn.close()

def change_coins(user_id: int, delta: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET coins = MAX(0, COALESCE(coins, 0) + ?) WHERE user_id = ?", (delta, user_id))
    conn.commit()
    cur.close()
    conn.close()

def change_candies(user_id: int, delta: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET candies = MAX(0, COALESCE(candies, 0) + ?) WHERE user_id = ?", (delta, user_id))
    conn.commit()
    cur.close()
    conn.close()

def get_inventory(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, pokemon_id, pokemon_name, gen, rarity, is_shiny, is_shadow, cp FROM inventory WHERE user_id = ? ORDER BY cp DESC", (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ================= 4. AIOHTTP REST API СЕРВЕР =================
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

async def api_get_full_profile(request):
    try:
        data = await request.json()
        uid = int(data.get("user_id", 0))
        username = data.get("username", "")

        u = get_user_data(uid, username)
        inv_rows = get_inventory(uid)

        inventory = []
        for r in inv_rows:
            inventory.append({
                "inv_id": r[0], "id": r[1], "name": r[2], "gen": r[3],
                "rarity": r[4], "is_shiny": bool(r[5]), "is_shadow": bool(r[6]),
                "type": POKEMON_TYPES.get(r[1], "⚪️ Обычный"), "cp": r[7],
                "evoTo": EVOLUTIONS.get(r[1])
            })

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT tower_id, name, req_cp, champ_name, p_name, p_id, rate_hr FROM towers")
        towers = [{"id": r[0], "name": r[1], "req": r[2], "champ": r[3], "pName": r[4], "pid": r[5], "rate": r[6]} for r in cur.fetchall()]
        cur.close()
        conn.close()

        now = time.time()
        incubator = None
        if u.get("egg_type"):
            incubator = {"type": u["egg_type"], "hatchTime": int(u["egg_hatch_time"] * 1000)}

        return web.json_response({
            "status": "ok",
            "user": {"coins": u["coins"], "candies": u["candies"], "energy": u["energy"], "is_vip": now < u.get("vip_until", 0)},
            "inventory": inventory,
            "eggs": {"common": u.get("eggs_common", 0), "rare": u.get("eggs_rare", 0), "legend": u.get("eggs_legend", 0)},
            "incubator": incubator,
            "towers": towers
        })
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def api_hunt_handler(request):
    try:
        data = await request.json()
        uid = int(data.get("user_id", 0))
        u = get_user_data(uid)
        
        if u["energy"] < 20:
            return web.json_response({"status": "error", "message": "Недостаточно энергии!"})

        update_user(uid, energy=u["energy"] - 20, last_energy_calc=time.time())
        change_coins(uid, 25)

        roll = random.random()
        rarity = "Rare" if roll > 0.85 else ("Uncommon" if roll > 0.55 else "Common")
        pool = POKEMON_DB.get(rarity, POKEMON_DB["Common"])
        pid, name, gen = random.choice(pool)
        shiny = 1 if random.random() < 0.05 else 0
        cp = generate_cp(rarity, bool(shiny))

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO inventory (user_id, pokemon_id, pokemon_name, gen, rarity, is_shiny, cp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (uid, pid, name, gen, rarity, shiny, cp))
        inv_id = cur.lastrowid
        conn.commit()
        cur.close()
        conn.close()

        return web.json_response({
            "status": "ok",
            "energy": u["energy"] - 20,
            "coins": u["coins"] + 25,
            "pokemon": {
                "inv_id": inv_id, "id": pid, "name": name, "gen": gen,
                "type": POKEMON_TYPES.get(pid, "⚪️ Обычный"), "cp": cp,
                "is_shiny": bool(shiny), "evoTo": EVOLUTIONS.get(pid)
            }
        })
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

# ================= 5. TELEGRAM БОТ ХЕНДЛЕРЫ =================
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    get_user_data(message.from_user.id, message.from_user.username or "")
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎮 Открыть PokéHunter MMO 3.0", web_app=WebAppInfo(url=WEBAPP_URL)))
    await message.answer(
        "👋 <b>Добро пожаловать в PokéHunter MMO 3.0!</b>\n\nНажмите кнопку ниже для запуска игры:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    pay = message.successful_payment
    uid = message.from_user.id
    stars = pay.total_amount
    if stars == 50:
        change_coins(uid, 1000)
        await message.answer("🎉 Начислено <b>+1 000 🪙 монет</b>!", parse_mode="HTML")
    elif stars == 150:
        conn = get_db()
        conn.execute("UPDATE users SET eggs_legend = eggs_legend + 1 WHERE user_id = ?", (uid,))
        conn.commit()
        conn.close()
        await message.answer("🎉 🟡 <b>Легендарное Яйцо</b> добавлено в ваш инвентарь!", parse_mode="HTML")

# ================= 6. СТАРТ БОТА И ВЕБ-СЕРВЕРА =================
async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()

    bot = Bot(token=BOT_TOKEN)

    app = web.Application(middlewares=[cors_middleware])
    app.router.add_options("/{tail:.*}", api_options_handler)
    app.router.add_post("/api/get_full_profile", api_get_full_profile)
    app.router.add_post("/api/hunt", api_hunt_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"🚀 Веб-сервер API запущен на порту {PORT}!")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
