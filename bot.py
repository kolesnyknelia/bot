import os
import sqlite3
import logging
import json
import re
import requests
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_PATH = os.getenv("BOT_DB_PATH", "bot_access.db")

ADMIN_ID = 642635219

if not TOKEN:
    raise RuntimeError("Не знайдено TELEGRAM_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise RuntimeError("Не знайдено OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

USER_STATE = {}
USER_DATA = {}

USD_TO_UAH = 43
CNY_TO_UAH = 5.8
SEA_USD_PER_KG = 5
AIR_USD_PER_KG = 15


FAQ_MODULE_1 = {
    "❓ Таблиця не копіюється": (
        "Щоб відкрити Google Таблицю:\n\n"
        "1. Зайдіть у браузер Google Chrome\n"
        "2. Обовʼязково авторизуйтесь у своєму Google-акаунті\n\n"
        "Далі:\n"
        "3. Відкрийте посилання, яке я даю\n"
        "4. Таблиця відкриється саме в браузері\n"
        "5. Натисніть: Файл → Зробити копію\n\n"
        "❗ Якщо ви не авторизовані в Google — таблиця не відкриється повноцінно "
        "і кнопки «Зробити копію» не буде."
    ),
    "❓ З якої сторінки запуск": (
        "Рекламу у Facebook ми не запускаємо з особистої сторінки.\n\n"
        "❌ Особиста сторінка — це ваш профіль (ім’я і прізвище)\n"
        "✅ Рекламу запускаємо тільки з бізнес-сторінки (fan page)\n\n"
        "Особистий акаунт потрібен тільки для:\n"
        "- входу в Facebook\n"
        "- доступу до рекламного кабінету\n"
        "- створення бізнес-сторінки\n"
        "- управління рекламою\n\n"
        "📌 Підсумок:\n"
        "Реклама запускається тільки з бізнес-сторінки."
    ),
    "❓ З якого пристрою": (
        "Ми працюємо з комп’ютера або ноутбука.\n\n"
        "📱 Телефон використовується тільки для перевірки, "
        "але не для налаштувань реклами.\n\n"
        "💻 На комп’ютері або ноутбуці ви:\n"
        "- заходите в Facebook-акаунт\n"
        "- працюєте з рекламним кабінетом\n"
        "- проходите всі налаштування по уроках\n\n"
        "🔐 Важливий момент:\n"
        "Ніхто не бачить ваш особистий профіль.\n"
        "Люди бачать тільки бізнес-сторінку."
    ),
    "❓ Табличка разово?": (
        "Google-таблиця з товарами — це не разове завдання, "
        "а ваш основний робочий інструмент.\n\n"
        "У товарному бізнесі табличка використовується постійно.\n\n"
        "Ви будете:\n"
        "- додавати нові товари\n"
        "- аналізувати старі\n"
        "- порівнювати між собою\n"
        "- відсіювати слабкі\n"
        "- повертатись до товарів знову\n\n"
        "📌 Табличка — це ваша база, пам’ять і контроль."
    ),
    "❓ Всі товари одразу?": (
        "Ні, всі товари одночасно ми не запускаємо.\n\n"
        "✅ Правильно:\n"
        "1. Обрали товар\n"
        "2. Зробили сайт\n"
        "3. Зробили креативи\n"
        "4. Запустили рекламу\n\n"
        "Якщо товар зайшов — працюємо з ним далі.\n"
        "Якщо не зайшов — переходимо до наступного.\n\n"
        "📌 Тестуємо товари тільки по черзі."
    ),
    "❓ Чи конкуренти Rozetka": (
        "❌ Ні, маркетплейси не є нашими конкурентами.\n\n"
        "Ми не порівнюємо ціни з Prom, Rozetka, OLX "
        "і не орієнтуємось на їхні умови.\n\n"
        "✅ Наші реальні конкуренти — це ті, хто продає "
        "той самий товар через односторінкові сайти "
        "і запускає рекламу у Facebook та Instagram.\n\n"
        "Саме їх ми аналізуємо:\n"
        "- сайти\n"
        "- креативи\n"
        "- подачу товару"
    ),
    "❓ Як порахувати вагу": (
        "Якщо на 1688 не вказана вага — це нормально.\n\n"
        "Що робимо:\n"
        "1. Дивимось цього ж товару в інших продавців\n"
        "2. Відкриваємо схожі оголошення\n"
        "3. Шукаємо товар через Google по фото\n"
        "4. Дивимось Amazon, AliExpress та інші сайти\n"
        "5. Можна також запитати в ChatGPT\n\n"
        "📌 Якщо ваги немає у одного продавця — шукаємо її в інших джерелах."
    ),
    "❓ Спочатку купуємо?": (
        "❌ Ні, ми не закуповуємо товар наперед без тесту.\n\n"
        "✅ Правильна логіка:\n"
        "1. Обрали товар\n"
        "2. Зробили сайт і креативи\n"
        "3. Запустили рекламу\n"
        "4. Якщо товар зайшов — робимо викуп\n\n"
        "Якщо хочеться перевірити якість товару, можна:\n"
        "- подивитися огляди на YouTube\n"
        "- почитати відгуки на AliExpress\n"
        "- замовити товар на себе для креативів\n\n"
        "📌 Спочатку тест → потім викуп."
    ),
}

FAQ_MODULE_2 = {
    "❓ Скільки товарів в акаунті": (
        "Теоретично в одному рекламному акаунті можна запускати різні товари "
        "і різні лендінги. Але ми так не робимо.\n\n"
        "Причина — ризики.\n\n"
        "Якщо в одному акаунті 5 товарів і один порушить правила Facebook, "
        "заблокувати можуть весь рекламний акаунт.\n\n"
        "Тоді постраждають усі товари одразу.\n\n"
        "✅ Ми працюємо так:\n"
        "1 рекламний акаунт = 1 товар = 1 лендінг\n\n"
        "Так безпечніше."
    ),
    "❓ Чи міняти піксель": (
        "❌ Ні, кожного разу новий піксель ставити не потрібно.\n\n"
        "Правильна схема:\n"
        "1 рекламний акаунт = 1 товар = 1 лендінг = 1 піксель\n\n"
        "Піксель ставиться на сайт один раз і далі залишається там постійно.\n"
        "Рекламу можна запускати, зупиняти, перезапускати, міняти тексти "
        "і креативи — піксель не чіпаємо."
    ),
    "❓ Коли новий піксель": (
        "Новий піксель потрібен тільки в одному випадку:\n"
        "якщо цей самий сайт ви підключаєте до іншого рекламного акаунту.\n\n"
        "Кожен акаунт має свій власний піксель.\n\n"
        "📌 Підсумок:\n"
        "Піксель ставиться один раз на один товар.\n"
        "Інший акаунт = інший піксель."
    ),
    "❓ Чи вимикати рекламу при зміні сайту": (
        "❌ Ні, вимикати рекламу не потрібно.\n\n"
        "Сайт і реклама — це окремі процеси.\n\n"
        "Поки реклама працює, ви можете:\n"
        "- змінювати тексти\n"
        "- змінювати фото\n"
        "- додавати блоки\n"
        "- редагувати структуру\n\n"
        "📌 Сайт можна змінювати, рекламу для цього вимикати не потрібно."
    ),
    "❓ Немає показів": (
        "Якщо у вас новий рекламний акаунт — це нормальна ситуація.\n\n"
        "Facebook не завжди запускає рекламу миттєво.\n"
        "Вона може висіти без показів певний час, навіть якщо все налаштовано правильно.\n\n"
        "Що перевірити:\n"
        "- дату старту реклами\n"
        "- час старту реклами\n\n"
        "На нових акаунтах запуск може затягнутись до 24 годин.\n\n"
        "📌 Підсумок:\n"
        "Ставимо правильну дату і час та чекаємо приблизно добу."
    ),
    "❓ Коли вимикати рекламу": (
        "Спочатку дивимось не на бюджет, а на відкрутку — скільки реально списалось.\n\n"
        "Якщо гроші списуються — реклама працює.\n\n"
        "Орієнтир:\n"
        "- до 3$ → просто чекаємо\n"
        "- 3–5$ → уже дивимось на результат\n\n"
        "Якщо на 3$ уже є хоча б 1 замовлення — рекламу залишаємо.\n"
        "Якщо відкрутка дійшла до 5$ і замовлень 0 — вимикаємо.\n\n"
        "📌 Головне правило:\n"
        "Реклама вважається робочою тільки тоді, коли є замовлення."
    ),
}

IMPORTANT_INFO = {
    "📌 Правила роботи": (
        "Ми працюємо поетапно:\n\n"
        "- не біжимо вперед уроків\n"
        "- не запускаємо багато товарів одразу\n"
        "- не ускладнюємо\n"
        "- повторюємо по уроках\n\n"
        "❗ Головне правило:\n"
        "результат дає не перегляд, а дія"
    ),
    "📥 Як здавати домашки": (
        "Домашки здаємо чітко і без води.\n\n"
        "Що потрібно:\n"
        "- скрін або посилання\n"
        "- короткий опис, що зроблено\n"
        "- конкретно, без довгих пояснень\n\n"
        "✅ Приклад:\n"
        "Зробила сайт, ось посилання. Додала 3 креативи, готова до перевірки.\n\n"
        "❌ Неправильно:\n"
        "Я щось пробувала, але не знаю..."
    ),
    "💬 Як писати питання": (
        "Щоб отримати швидку відповідь:\n\n"
        "- пишемо конкретно\n"
        "- одне питання = один запит\n"
        "- без великих історій\n\n"
        "✅ Приклад:\n"
        "Не працює реклама, немає показів, відкрутка 0\n\n"
        "❌ Не так:\n"
        "Щось не так, не розумію що"
    ),
    "🔍 Що перевірити перед зверненням": (
        "Перед тим як писати питання, перевір:\n\n"
        "- чи подивилась урок\n"
        "- чи зробила все по інструкції\n"
        "- чи перевірила FAQ\n"
        "- чи немає вже відповіді в боті\n\n"
        "📌 Часті причини:\n"
        "- не та дата запуску\n"
        "- не той піксель\n"
        "- не збережений сайт\n"
        "- не той акаунт\n\n"
        "❗ 80% питань — це не помилка, а неуважність"
    ),
    "⚡ Важливо зрозуміти": (
        "У цьому навчанні:\n\n"
        "немає чарівної кнопки\n"
        "немає ідеального товару з першого разу\n\n"
        "✔ є тест\n"
        "✔ є помилки\n"
        "✔ є досвід\n\n"
        "📌 Підсумок:\n"
        "Той, хто робить — заробляє.\n"
        "Той, хто відкладає — стоїть на місці."
    ),
}

CREATIVE_CATEGORIES = {
    "💎 Аксесуари / б'юті": "Акцент на вау-ефект, красу, стиль, зовнішній вигляд, емоцію, до/після.",
    "💅 Манікюр / догляд": "Акцент на економію часу, зручність вдома, охайність, все потрібне в одному наборі.",
    "🛏 Подушки / комфорт": "Акцент на комфорт, сон, шию, спину, відпочинок після роботи, зняття напруги.",
    "📱 Чохли / гаджети": "Акцент на захист, функціональність, стиль, зручність, магніт, підставку, ударостійкість.",
    "🏠 Товари для дому": "Акцент на порядок, простоту, економію часу, користь щодня, полегшення побуту.",
    "🍳 Кухонні товари": "Акцент на швидкість, легкість, чистоту, зручність, економію часу на кухні.",
    "🚗 Авто-товари": "Акцент на комфорт у машині, безпеку, організацію простору, користь у дорозі.",
    "🐶 Товари для тварин": "Акцент на комфорт тварини, зручність для господаря, менше бруду, більше турботи.",
    "🧒 Дитячі товари": "Акцент на безпеку, спокій батьків, зручність, користь для дитини.",
    "🩺 Здоров'я / комфорт": "Акцент на полегшення, зручність, менше болю/дискомфорту, комфорт щодня.",
    "📦 Універсальна категорія": "Універсальна подача: проблема → рішення → демонстрація → результат → заклик.",
}


def db_connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            access_until TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def ensure_admin():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (ADMIN_ID,))
    row = cur.fetchone()
    now = datetime.utcnow().isoformat()
    far_future = "2099-12-31T23:59:59"
    if row:
        cur.execute(
            "UPDATE users SET is_admin = 1, access_until = ? WHERE user_id = ?",
            (far_future, ADMIN_ID)
        )
    else:
        cur.execute(
            """
            INSERT INTO users (user_id, username, full_name, access_until, is_admin, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ADMIN_ID, "", "Admin", far_future, 1, now)
        )
    conn.commit()
    conn.close()


def touch_user(user_id: int, username: str, full_name: str):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    now = datetime.utcnow().isoformat()
    if row:
        cur.execute(
            "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
            (username or "", full_name or "", user_id)
        )
    else:
        cur.execute(
            """
            INSERT INTO users (user_id, username, full_name, access_until, is_admin, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, username or "", full_name or "", "", 0, now)
        )
    conn.commit()
    conn.close()


def is_admin(user_id: int) -> bool:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0] == 1)


def get_user_record(user_id: int):
    conn = db_connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def has_active_access(user_id: int) -> bool:
    row = get_user_record(user_id)
    if not row:
        return False
    if row["is_admin"] == 1:
        return True
    access_until = row["access_until"]
    if not access_until:
        return False
    try:
        return datetime.utcnow() <= datetime.fromisoformat(access_until)
    except Exception:
        return False


def add_access_30_days(user_id: int):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT access_until FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    now = datetime.utcnow()

    if row:
        access_until = row[0]
        try:
            current_until = datetime.fromisoformat(access_until) if access_until else now
        except Exception:
            current_until = now
        start_from = current_until if current_until > now else now
        new_until = start_from + timedelta(days=30)
        cur.execute(
            "UPDATE users SET access_until = ? WHERE user_id = ?",
            (new_until.isoformat(), user_id)
        )
    else:
        new_until = now + timedelta(days=30)
        cur.execute(
            """
            INSERT INTO users (user_id, username, full_name, access_until, is_admin, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, "", "", new_until.isoformat(), 0, now.isoformat())
        )

    conn.commit()
    conn.close()
    return new_until


def remove_access(user_id: int):
    conn = db_connect()
    cur = conn.cursor()
    past_time = (datetime.utcnow() - timedelta(days=1)).isoformat()
    cur.execute(
        "UPDATE users SET access_until = ? WHERE user_id = ? AND is_admin = 0",
        (past_time, user_id)
    )
    conn.commit()
    conn.close()


def list_active_users():
    conn = db_connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        """
        SELECT * FROM users
        WHERE (is_admin = 1) OR (access_until IS NOT NULL AND access_until != '' AND access_until >= ?)
        ORDER BY is_admin DESC, access_until ASC
        """,
        (now,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def list_expiring_users(days: int = 3):
    conn = db_connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    now = datetime.utcnow()
    future = now + timedelta(days=days)
    cur.execute(
        """
        SELECT * FROM users
        WHERE is_admin = 0
          AND access_until IS NOT NULL
          AND access_until != ''
          AND access_until >= ?
          AND access_until <= ?
        ORDER BY access_until ASC
        """,
        (now.isoformat(), future.isoformat())
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def format_user_line(row) -> str:
    username = row["username"] or "—"
    full_name = row["full_name"] or "—"
    access_until = row["access_until"] or "—"
    admin_label = " (адмін)" if row["is_admin"] == 1 else ""
    username_line = f"@{username}" if username != "—" else "—"
    return (
        f"ID: {row['user_id']}{admin_label}\n"
        f"Username: {username_line}\n"
        f"Ім’я: {full_name}\n"
        f"Доступ до: {access_until}"
    )


def classify_market_level(count: int, market: str) -> str:
    if market == "rozetka":
        if count <= 10:
            return "мало"
        elif count <= 50:
            return "середньо"
        return "багато"

    if market == "prom":
        if count <= 50:
            return "мало"
        elif count <= 200:
            return "середньо"
        return "багато"

    return "невідомо"


def market_risk_label(rozetka_count: int, prom_count: int) -> str:
    score = 0

    if rozetka_count > 50:
        score += 2
    elif rozetka_count > 10:
        score += 1

    if prom_count > 200:
        score += 2
    elif prom_count > 50:
        score += 1

    if score <= 1:
        return "низький"
    elif score <= 3:
        return "середній"
    return "високий"


def safe_request(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.text


def parse_rozetka_count(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    patterns = [
        r"Знайдено\s+(\d+)",
        r"знайдено\s+(\d+)",
        r"(\d+)\s+товар",
        r"(\d+)\s+результат",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                pass

    selectors = [
        '[data-testid="goods-list"] [data-goods-id]',
        '.goods-tile',
        '.catalog-grid li',
        '.tile',
    ]

    for selector in selectors:
        found = soup.select(selector)
        if found:
            return len(found)

    return 0


def parse_prom_count(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    patterns = [
        r"Знайдено\s+(\d+)",
        r"знайдено\s+(\d+)",
        r"(\d+)\s+товар",
        r"(\d+)\s+позиці",
        r"(\d+)\s+результат",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                pass

    selectors = [
        '[data-qaid="product_block"]',
        '.M3v0L',
        '.x-product-card',
        '.catalog-item',
    ]

    for selector in selectors:
        found = soup.select(selector)
        if found:
            return len(found)

    return 0


def main_keyboard(admin: bool = False):
    rows = [
        ["📦 Розрахувати товар", "💰 Розрахувати маржу"],
        ["❓ FAQ", "🎬 Креативи"],
        ["📊 Аналіз", "🔍 Ключові слова"],
        ["🛒 Перевірити Rozetka / Prom", "💬 Питання"],
        ["⚠️ Важлива інформація"],
    ]
    if admin:
        rows.append(["👑 Адмінка"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def admin_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["➕ Додати доступ", "🔄 Продовжити доступ"],
            ["❌ Забрати доступ", "🔍 Знайти користувача"],
            ["📋 Активні користувачі", "⏳ Закінчується скоро"],
            ["⬅️ Назад"],
        ],
        resize_keyboard=True
    )


def faq_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📦 Модуль 1 — Пошук товарів"],
            ["🎨 Модуль 2 — Сайт і креативи"],
            ["⬅️ Назад"],
        ],
        resize_keyboard=True
    )


def module1_keyboard():
    return ReplyKeyboardMarkup(
        [[q] for q in FAQ_MODULE_1.keys()] + [["⬅️ Назад"]],
        resize_keyboard=True
    )


def module2_keyboard():
    return ReplyKeyboardMarkup(
        [[q] for q in FAQ_MODULE_2.keys()] + [["⬅️ Назад"]],
        resize_keyboard=True
    )


def important_info_keyboard():
    return ReplyKeyboardMarkup(
        [[q] for q in IMPORTANT_INFO.keys()] + [["⬅️ Назад"]],
        resize_keyboard=True
    )


def creatives_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📌 Структура креативу"],
            ["✍️ Приклади текстів"],
            ["❌ Помилки"],
            ["🔢 Скільки креативів"],
            ["🗂 Категорії креативів"],
            ["🪝 Ідеї гачків"],
            ["🎥 Сценарії для відео"],
            ["🎯 Генератор оффера"],
            ["🤖 Генератор креативів"],
            ["⬅️ Назад"],
        ],
        resize_keyboard=True
    )


def creative_categories_keyboard():
    return ReplyKeyboardMarkup(
        [[q] for q in CREATIVE_CATEGORIES.keys()] + [["⬅️ До креативів"]],
        resize_keyboard=True
    )


def calculate_product_cost(price_yuan: float, weight_g: float) -> str:
    purchase_uah = price_yuan * CNY_TO_UAH
    weight_kg = weight_g / 1000

    sea_delivery = weight_kg * SEA_USD_PER_KG * USD_TO_UAH
    air_delivery = weight_kg * AIR_USD_PER_KG * USD_TO_UAH

    total_sea = purchase_uah + sea_delivery
    total_air = purchase_uah + air_delivery

    return (
        f"💰 Викуп: {purchase_uah:.2f} грн\n"
        f"⚖️ Вага: {weight_g:.0f} г\n\n"
        f"🚢 Ціна товару з доставкою (море): {total_sea:.2f} грн\n"
        f"✈️ Ціна товару з доставкою (авіа): {total_air:.2f} грн"
    )


def parse_calc_input(text: str):
    parts = text.replace(",", ".").split()
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def parse_number(text: str):
    text = text.replace(",", ".").strip()
    try:
        return float(text)
    except ValueError:
        return None


async def generate_creative_by_mode(mode: str, category: str, user_text: str) -> str:
    category_hint = CREATIVE_CATEGORIES.get(category, "")

    if mode == "creative_hooks":
        task = "Створи 10 сильних рекламних гачків українською мовою."
    elif mode == "creative_video":
        task = (
            "Створи 5 коротких сценаріїв для відео-креативу українською мовою. "
            "Для кожного сценарію дай: гачок, середину, фінал."
        )
    elif mode == "creative_offer":
        task = (
            "Створи 5 варіантів оффера українською мовою. "
            "Для кожного дай: заголовок, підзаголовок, короткий CTA."
        )
    else:
        task = (
            "Створи 3 гачки, 3 тексти для креативу і 3 ідеї для відео-креативу українською мовою."
        )

    prompt = f"""
Ти — маркетинговий асистент для товарного бізнесу.

Категорія товару:
{category}

Підказка по категорії:
{category_hint}

Опис товару:
{user_text}

Завдання:
{task}

Пиши просто, сильно, без води, під Facebook / Instagram / TikTok.
"""
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "Ти сильний маркетинговий асистент для товарного бізнесу. Пиши тільки українською мовою."
            },
            {
                "role": "user",
                "content": prompt
            },
        ],
        temperature=0.9,
    )
    return response.choices[0].message.content


async def generate_market_queries_from_photo(file_url: str) -> dict:
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ти експерт з товарного бізнесу. "
                        "Пиши тільки українською мовою. "
                        "Визнач товар по фото і дай короткі запити для пошуку."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Подивись на фото товару.\n\n"
                                "Поверни відповідь СТРОГО в такому форматі:\n\n"
                                "НАЗВА: ...\n"
                                "ЗАПИТИ: запит1 | запит2 | запит3 | запит4 | запит5\n\n"
                                "Без пояснень. Без списків. Без зайвого тексту."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": file_url}
                        }
                    ]
                }
            ],
            max_tokens=200,
            temperature=0.2
        )

        content = response.choices[0].message.content.strip()
        print("MARKET_RAW_RESPONSE:", content)

        name = "товар"
        queries = []

        for line in content.splitlines():
            line = line.strip()

            if line.startswith("НАЗВА:"):
                name = line.replace("НАЗВА:", "").strip()

            if line.startswith("ЗАПИТИ:"):
                raw_queries = line.replace("ЗАПИТИ:", "").strip()
                queries = [q.strip() for q in raw_queries.split("|") if q.strip()]

        if not queries:
            queries = [name]

        return {
            "main_name": name,
            "queries": queries[:5]
        }

    except Exception as e:
        print("MARKET_PARSE_ERROR:", str(e))
        return {
            "main_name": "товар",
            "queries": ["товар"]
        }
async def generate_search_keywords_from_photo(file_url: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ти експерт з товарного бізнесу. "
                    "Пишеш тільки українською мовою. "
                    "Даєш правильні, живі назви товарів і варіанти для пошуку. "
                    "Не використовуєш суржик."
                )
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Подивись на фото товару і зроби відповідь для пошуку конкурентів.\n\n"
                            "Дуже важливо:\n"
                            "- дай 1 ОСНОВНУ назву товару українською (найбільш природну)\n"
                            "- потім дай різні варіанти назв (як можуть писати продавці)\n"
                            "- використовуй різні варіанти: каблучка / перстень / кільце (якщо підходить)\n"
                            "- для пошуку давай максимум варіантів\n\n"
                            "Структура відповіді:\n\n"
                            "1. Основна назва товару\n"
                            "2. Інші варіанти назв (синоніми)\n"
                            "3. 10 коротких ключових слів\n"
                            "4. 10 словосполучень для пошуку\n"
                            "5. Як шукати в Facebook Ads Library\n"
                            "6. Як шукати в AdHeart\n\n"
                            "Пиши просто, без води, як для учня."
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": file_url}
                    }
                ]
            }
        ],
        max_tokens=900
    )
    return response.choices[0].message.content


async def generate_market_queries_from_photo(file_url: str) -> dict:
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Ти експерт з товарного бізнесу. Пиши українською."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Подивись на фото і напиши:\n"
                                "1. Назву товару\n"
                                "2. 5 коротких запитів для пошуку\n\n"
                                "Формат:\n"
                                "Назва: ...\n"
                                "Запити:\n"
                                "- ...\n"
                                "- ...\n"
                                "- ..."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": file_url}
                        }
                    ]
                }
            ],
            max_tokens=300
        )

        content = response.choices[0].message.content

        # Проста обробка (без JSON)
        lines = content.split("\n")

        name = "товар"
        queries = []

        for line in lines:
            if "Назва" in line:
                name = line.split(":")[-1].strip()
            if "-" in line:
                queries.append(line.replace("-", "").strip())

        if not queries:
            queries = [name]

        return {
            "main_name": name,
            "queries": queries[:5]
        }

    except Exception as e:
        print("ERROR:", e)
        return {
            "main_name": "невідомий товар",
            "queries": ["каблучка", "товар", "купити товар"]
        }


def check_rozetka_query(query: str) -> int:
    url = f"https://rozetka.com.ua/ua/search/?text={quote_plus(query)}"
    html = safe_request(url)
    return parse_rozetka_count(html)


def check_prom_query(query: str) -> int:
    url = f"https://prom.ua/ua/search?search_term={quote_plus(query)}"
    html = safe_request(url)
    return parse_prom_count(html)


async def check_rozetka_prom_from_photo(file_url: str) -> str:
    data = await generate_market_queries_from_photo(file_url)
    main_name = data.get("main_name", "товар")
    queries = data.get("queries", [])

    best_rozetka = 0
    best_prom = 0
    best_rozetka_query = ""
    best_prom_query = ""

    for query in queries[:5]:
        try:
            r_count = check_rozetka_query(query)
            if r_count > best_rozetka:
                best_rozetka = r_count
                best_rozetka_query = query
        except Exception:
            pass

        try:
            p_count = check_prom_query(query)
            if p_count > best_prom:
                best_prom = p_count
                best_prom_query = query
        except Exception:
            pass

    rozetka_level = classify_market_level(best_rozetka, "rozetka")
    prom_level = classify_market_level(best_prom, "prom")
    risk = market_risk_label(best_rozetka, best_prom)

    if best_rozetka == 0 and best_prom == 0:
        recommendation = "товар або слабо представлений, або треба перевірити інші запити вручну"
    elif risk == "високий":
        recommendation = "товар вже може бути перегрітий, тестувати тільки з сильним креативом і новим кутом подачі"
    elif risk == "середній":
        recommendation = "можна тестувати, але обов’язково подивитися ціни, подачу і кількість продавців"
    else:
        recommendation = "товар виглядає перспективніше, конкуренція не критична"

       return (
        f"Товар: {main_name}\n"
        f"Запити: {', '.join(queries)}\n\n"
        f"Rozetka: {best_rozetka}\n"
        f"Prom: {best_prom}"
    )


async def send_main_menu(update: Update, user_id: int):
    await update.message.reply_text(
        "Меню 👇",
        reply_markup=main_keyboard(admin=is_admin(user_id))
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    touch_user(user_id, user.username or "", user.full_name or "")

    if has_active_access(user_id):
        USER_STATE[user_id] = None
        await send_main_menu(update, user_id)
        return

    await update.message.reply_text(
        "Доступ поки не відкритий.\n\n"
        f"Твій Telegram ID: {user_id}\n\n"
        "Щоб отримати доступ, надішли цей ID адміну після оплати."
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    touch_user(user_id, user.username or "", user.full_name or "")

    text = update.message.text.strip() if update.message.text else ""

    if not has_active_access(user_id):
        await update.message.reply_text(
            "Доступ поки не відкритий або закінчився.\n\n"
            f"Твій Telegram ID: {user_id}\n\n"
            "Надішли цей ID адміну для відкриття або продовження доступу."
        )
        return

    if is_admin(user_id):
        if text == "👑 Адмінка":
            USER_STATE[user_id] = None
            await update.message.reply_text("Адмінка 👇", reply_markup=admin_keyboard())
            return

        if text == "➕ Додати доступ":
            USER_STATE[user_id] = "admin_add_access"
            await update.message.reply_text("Введи Telegram ID користувача для відкриття доступу на 30 днів")
            return

        if text == "🔄 Продовжити доступ":
            USER_STATE[user_id] = "admin_extend_access"
            await update.message.reply_text("Введи Telegram ID користувача для продовження доступу на 30 днів")
            return

        if text == "❌ Забрати доступ":
            USER_STATE[user_id] = "admin_remove_access"
            await update.message.reply_text("Введи Telegram ID користувача, якому потрібно закрити доступ")
            return

        if text == "🔍 Знайти користувача":
            USER_STATE[user_id] = "admin_find_user"
            await update.message.reply_text("Введи Telegram ID користувача")
            return

        if text == "📋 Активні користувачі":
            rows = list_active_users()
            if not rows:
                await update.message.reply_text("Активних користувачів поки немає")
                return
            chunks = [format_user_line(row) for row in rows[:30]]
            await update.message.reply_text("\n\n".join(chunks))
            return

        if text == "⏳ Закінчується скоро":
            rows = list_expiring_users(3)
            if not rows:
                await update.message.reply_text("У найближчі 3 дні ні в кого не закінчується доступ")
                return
            chunks = [format_user_line(row) for row in rows[:30]]
            await update.message.reply_text("\n\n".join(chunks))
            return

        if USER_STATE.get(user_id) == "admin_add_access":
            try:
                target_id = int(text)
                new_until = add_access_30_days(target_id)
                USER_STATE[user_id] = None
                await update.message.reply_text(
                    f"✅ Доступ відкрито до:\n{new_until.isoformat()}",
                    reply_markup=admin_keyboard()
                )
            except Exception:
                await update.message.reply_text("Введи правильний Telegram ID цифрами")
            return

        if USER_STATE.get(user_id) == "admin_extend_access":
            try:
                target_id = int(text)
                new_until = add_access_30_days(target_id)
                USER_STATE[user_id] = None
                await update.message.reply_text(
                    f"✅ Доступ продовжено до:\n{new_until.isoformat()}",
                    reply_markup=admin_keyboard()
                )
            except Exception:
                await update.message.reply_text("Введи правильний Telegram ID цифрами")
            return

        if USER_STATE.get(user_id) == "admin_remove_access":
            try:
                target_id = int(text)
                remove_access(target_id)
                USER_STATE[user_id] = None
                await update.message.reply_text(
                    "✅ Доступ закрито",
                    reply_markup=admin_keyboard()
                )
            except Exception:
                await update.message.reply_text("Введи правильний Telegram ID цифрами")
            return

        if USER_STATE.get(user_id) == "admin_find_user":
            try:
                target_id = int(text)
                row = get_user_record(target_id)
                USER_STATE[user_id] = None
                if row:
                    await update.message.reply_text(
                        format_user_line(row),
                        reply_markup=admin_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "Користувача не знайдено",
                        reply_markup=admin_keyboard()
                    )
            except Exception:
                await update.message.reply_text("Введи правильний Telegram ID цифрами")
            return

    if text == "❓ FAQ":
        USER_STATE[user_id] = None
        await update.message.reply_text("Обери модуль", reply_markup=faq_keyboard())
        return

    if text == "📦 Модуль 1 — Пошук товарів":
        USER_STATE[user_id] = None
        await update.message.reply_text("Модуль 1 👇", reply_markup=module1_keyboard())
        return

    if text == "🎨 Модуль 2 — Сайт і креативи":
        USER_STATE[user_id] = None
        await update.message.reply_text("Модуль 2 👇", reply_markup=module2_keyboard())
        return

    if text == "⚠️ Важлива інформація":
        USER_STATE[user_id] = None
        await update.message.reply_text(
            "Обери розділ 👇",
            reply_markup=important_info_keyboard()
        )
        return

    if text in FAQ_MODULE_1:
        USER_STATE[user_id] = None
        await update.message.reply_text(FAQ_MODULE_1[text])
        return

    if text in FAQ_MODULE_2:
        USER_STATE[user_id] = None
        await update.message.reply_text(FAQ_MODULE_2[text])
        return

    if text in IMPORTANT_INFO:
        USER_STATE[user_id] = None
        await update.message.reply_text(IMPORTANT_INFO[text])
        return

    if text == "🎬 Креативи":
        USER_STATE[user_id] = None
        await update.message.reply_text("Обери 👇", reply_markup=creatives_keyboard())
        return

    if text == "📌 Структура креативу":
        USER_STATE[user_id] = None
        await update.message.reply_text(
            "🔥 Структура:\n\n"
            "1. Гачок (перші 2–3 секунди)\n"
            "2. Проблема\n"
            "3. Рішення\n"
            "4. Демонстрація товару\n"
            "5. Заклик до дії"
        )
        return

    if text == "✍️ Приклади текстів":
        USER_STATE[user_id] = None
        await update.message.reply_text(
            "📢 Приклади:\n\n"
            "Втомилась від безладу у волоссі?\n"
            "Ця шпилька тримає весь день\n"
            "Легка, стильна і зручна\n"
            "Замов зараз 👇"
        )
        return

    if text == "❌ Помилки":
        USER_STATE[user_id] = None
        await update.message.reply_text(
            "❌ Помилки:\n\n"
            "- немає гачка\n"
            "- довге відео\n"
            "- багато тексту\n"
            "- не зрозуміло, що продається"
        )
        return

    if text == "🔢 Скільки креативів":
        USER_STATE[user_id] = None
        await update.message.reply_text("👉 Робимо 3–5 креативів на товар")
        return

    if text == "🗂 Категорії креативів":
        USER_STATE[user_id] = None
        lines = ["Категорії, з якими вже можна працювати:\n"]
        for key, value in CREATIVE_CATEGORIES.items():
            lines.append(f"{key}\n— {value}")
        await update.message.reply_text("\n\n".join(lines))
        return

    if text == "🤖 Генератор креативів":
        USER_STATE[user_id] = "choose_category_for_creatives"
        USER_DATA[user_id] = {"creative_mode": "creative_full"}
        await update.message.reply_text(
            "Обери категорію товару 👇",
            reply_markup=creative_categories_keyboard()
        )
        return

    if text == "🪝 Ідеї гачків":
        USER_STATE[user_id] = "choose_category_for_creatives"
        USER_DATA[user_id] = {"creative_mode": "creative_hooks"}
        await update.message.reply_text(
            "Обери категорію товару для гачків 👇",
            reply_markup=creative_categories_keyboard()
        )
        return

    if text == "🎥 Сценарії для відео":
        USER_STATE[user_id] = "choose_category_for_creatives"
        USER_DATA[user_id] = {"creative_mode": "creative_video"}
        await update.message.reply_text(
            "Обери категорію товару для сценаріїв 👇",
            reply_markup=creative_categories_keyboard()
        )
        return

    if text == "🎯 Генератор оффера":
        USER_STATE[user_id] = "choose_category_for_creatives"
        USER_DATA[user_id] = {"creative_mode": "creative_offer"}
        await update.message.reply_text(
            "Обери категорію товару для оффера 👇",
            reply_markup=creative_categories_keyboard()
        )
        return

    if text == "⬅️ До креативів":
        USER_STATE[user_id] = None
        USER_DATA[user_id] = {}
        await update.message.reply_text("Розділ креативів 👇", reply_markup=creatives_keyboard())
        return

    if USER_STATE.get(user_id) == "choose_category_for_creatives":
        if text in CREATIVE_CATEGORIES:
            USER_DATA.setdefault(user_id, {})
            USER_DATA[user_id]["creative_category"] = text
            USER_STATE[user_id] = "creative_generator"

            mode = USER_DATA[user_id].get("creative_mode", "creative_full")
            if mode == "creative_hooks":
                ask = "Напиши назву товару, для кого він і яку проблему вирішує. Я згенерую гачки 👇"
            elif mode == "creative_video":
                ask = "Напиши назву товару, для кого він і яку проблему вирішує. Я згенерую сценарії 👇"
            elif mode == "creative_offer":
                ask = "Напиши назву товару, для кого він і яку проблему вирішує. Я згенерую оффери 👇"
            else:
                ask = "Напиши назву товару, для кого він і яку проблему вирішує. Я згенерую креативи 👇"

            await update.message.reply_text(ask, reply_markup=creatives_keyboard())
            return

        await update.message.reply_text("Обери категорію кнопкою 👇", reply_markup=creative_categories_keyboard())
        return

    if text == "📦 Розрахувати товар":
        USER_STATE[user_id] = "calc"
        await update.message.reply_text(
            "Введи: 5 130\n\n"
            "де:\n"
            "5 — ціна в юанях\n"
            "130 — вага в грамах"
        )
        return

    if USER_STATE.get(user_id) == "calc":
        parsed = parse_calc_input(text)
        if not parsed:
            await update.message.reply_text("Формат: 5 130")
            return

        price_yuan, weight_g = parsed
        await update.message.reply_text(calculate_product_cost(price_yuan, weight_g))
        USER_STATE[user_id] = None
        return

    if text == "💰 Розрахувати маржу":
        USER_STATE[user_id] = "margin_sale_price"
        USER_DATA[user_id] = {}
        await update.message.reply_text("Введи ціну продажу в грн")
        return

    if USER_STATE.get(user_id) == "margin_sale_price":
        sale_price = parse_number(text)
        if sale_price is None:
            await update.message.reply_text("Введи тільки число, наприклад: 400")
            return

        USER_DATA[user_id]["sale_price"] = sale_price
        USER_STATE[user_id] = "margin_cost_price"
        await update.message.reply_text("Введи собівартість товару з доставкою в грн")
        return

    if USER_STATE.get(user_id) == "margin_cost_price":
        cost_price = parse_number(text)
        if cost_price is None:
            await update.message.reply_text("Введи тільки число, наприклад: 300")
            return

        USER_DATA[user_id]["cost_price"] = cost_price
        USER_STATE[user_id] = "margin_ads_dollars"
        await update.message.reply_text("Введи ціну реклами / ліда в доларах")
        return

    if USER_STATE.get(user_id) == "margin_ads_dollars":
        ads_dollars = parse_number(text)
        if ads_dollars is None:
            await update.message.reply_text("Введи тільки число, наприклад: 2")
            return

        sale_price = USER_DATA[user_id]["sale_price"]
        cost_price = USER_DATA[user_id]["cost_price"]
        ads_uah = ads_dollars * USD_TO_UAH
        profit = sale_price - cost_price - ads_uah

        await update.message.reply_text(
            f"💰 Ціна продажу: {sale_price:.2f} грн\n"
            f"📦 Повна собівартість: {cost_price:.2f} грн\n"
            f"📢 Реклама / лід: {ads_dollars:.2f}$ = {ads_uah:.2f} грн\n\n"
            f"✅ Маржа / чистий прибуток: {profit:.2f} грн"
        )

        USER_STATE[user_id] = None
        USER_DATA[user_id] = {}
        return

    if USER_STATE.get(user_id) == "creative_generator":
        await update.message.reply_text("Генерую... ⏳")
        try:
            mode = USER_DATA.get(user_id, {}).get("creative_mode", "creative_full")
            category = USER_DATA.get(user_id, {}).get("creative_category", "📦 Універсальна категорія")
            result = await generate_creative_by_mode(mode, category, text)
            await update.message.reply_text(result)
        except Exception:
            await update.message.reply_text("Зараз генератор тимчасово недоступний. Перевір баланс OpenAI API.")
        USER_STATE[user_id] = None
        USER_DATA[user_id] = {}
        return

    if text == "📊 Аналіз":
        USER_STATE[user_id] = "wait_photo"
        await update.message.reply_text("Скинь фото товару 👇")
        return

    if text == "🔍 Ключові слова":
        USER_STATE[user_id] = "search_photo"
        await update.message.reply_text("Скинь фото товару 👇")
        return

    if text == "🛒 Перевірити Rozetka / Prom":
        USER_STATE[user_id] = "market_photo"
        await update.message.reply_text("Скинь фото товару 👇")
        return

    if update.message.photo and USER_STATE.get(user_id) == "wait_photo":
        photo = update.message.photo[-1].file_id
        file = await context.bot.get_file(photo)
        file_url = file.file_path

        await update.message.reply_text("Аналізую товар... ⏳")

        try:
            result = await analyze_product_from_photo(file_url)
            await update.message.reply_text(result)
        except Exception:
            await update.message.reply_text("Не вдалося зробити аналіз. Спробуй ще раз.")

        USER_STATE[user_id] = None
        return

    if update.message.photo and USER_STATE.get(user_id) == "search_photo":
        photo = update.message.photo[-1].file_id
        file = await context.bot.get_file(photo)
        file_url = file.file_path

        await update.message.reply_text("Підбираю ключові слова... ⏳")

        try:
            result = await generate_search_keywords_from_photo(file_url)
            await update.message.reply_text(result)
        except Exception:
            await update.message.reply_text("Не вдалося підібрати ключові слова. Спробуй ще раз.")

        USER_STATE[user_id] = None
        return

    if update.message.photo and USER_STATE.get(user_id) == "market_photo":
        photo = update.message.photo[-1].file_id
        file = await context.bot.get_file(photo)
        file_url = file.file_path

        await update.message.reply_text("Перевіряю Rozetka / Prom... ⏳")

        try:
            result = await check_rozetka_prom_from_photo(file_url)
            await update.message.reply_text(result)
        except Exception:
            await update.message.reply_text("Не вдалося перевірити Rozetka / Prom. Спробуй ще раз.")

        USER_STATE[user_id] = None
        return

    if text == "💬 Питання":
        USER_STATE[user_id] = "question"
        await update.message.reply_text("Напиши своє питання 👇")
        return

    if USER_STATE.get(user_id) == "question":
        await update.message.reply_text("Питання отримано ✅")
        USER_STATE[user_id] = None
        return

    if text == "⬅️ Назад":
        USER_STATE[user_id] = None
        USER_DATA[user_id] = {}
        await send_main_menu(update, user_id)
        return

    await send_main_menu(update, user_id)


def main():
    init_db()
    ensure_admin()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle))
    app.run_polling()


if __name__ == "__main__":
    main()
