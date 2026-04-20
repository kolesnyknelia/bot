import os
import logging
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

if not TOKEN:
    raise RuntimeError("Не знайдено TELEGRAM_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise RuntimeError("Не знайдено OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

ACCESS_CODES = {"AAA111", "BBB222", "CCC333"}
AUTHORIZED_USERS = set()
USER_STATE = {}
USER_DATA = {}

USD_TO_UAH = 43
CNY_TO_UAH = 5.8
SEA_USD_PER_KG = 5
AIR_USD_PER_KG = 15

FAQ_MODULE_1 = {
    "❓ Таблиця не копіюється": "Зайди через Google Chrome і авторизуйся в Google. Далі: Файл → Зробити копію.",
    "❓ З якої сторінки запуск": "Рекламу запускаємо тільки з бізнес-сторінки (fan page). Особистий профіль не використовується.",
    "❓ З якого пристрою": "Працюємо тільки з комп’ютера або ноутбука. Телефон — тільки для перевірки.",
    "❓ Табличка разово?": "Ні. Це твій постійний робочий інструмент.",
    "❓ Всі товари одразу?": "Ні. Тестуємо по одному товару.",
    "❓ Чи конкуренти Rozetka": "Ні. Наші конкуренти — лендінги + реклама FB/Instagram.",
    "❓ Як порахувати вагу": "Шукай у інших продавців, через Google по фото або на AliExpress.",
    "❓ Спочатку купуємо?": "Ні. Спочатку тест, потім викуп.",
}

FAQ_MODULE_2 = {
    "❓ Скільки товарів в акаунті": "1 акаунт = 1 товар = 1 лендінг. Так безпечніше.",
    "❓ Чи міняти піксель": "Ні. Піксель ставиться один раз і не змінюється.",
    "❓ Коли новий піксель": "Тільки якщо інший рекламний акаунт.",
    "❓ Чи вимикати рекламу при зміні сайту": "Ні. Сайт і реклама незалежні.",
    "❓ Немає показів": "На нових акаунтах реклама може стартувати до 24 годин. Перевір дату і час.",
    "❓ Коли вимикати рекламу": "Якщо 5$ витрат і 0 замовлень — вимикаємо.",
}

def main_keyboard():
    return ReplyKeyboardMarkup([
        ["📦 Розрахувати товар", "💰 Маржа"],
        ["❓ FAQ", "🎬 Креативи"],
        ["📊 Аналіз", "💬 Питання"]
    ], resize_keyboard=True)

def faq_keyboard():
    return ReplyKeyboardMarkup([
        ["📦 Модуль 1 — Пошук товарів"],
        ["🎨 Модуль 2 — Сайт і креативи"],
        ["⬅️ Назад"]
    ], resize_keyboard=True)

def module1_keyboard():
    return ReplyKeyboardMarkup([[q] for q in FAQ_MODULE_1] + [["⬅️ Назад"]], resize_keyboard=True)

def module2_keyboard():
    return ReplyKeyboardMarkup([[q] for q in FAQ_MODULE_2] + [["⬅️ Назад"]], resize_keyboard=True)

def creatives_keyboard():
    return ReplyKeyboardMarkup([
        ["📌 Структура креативу"],
        ["✍️ Приклади текстів"],
        ["❌ Помилки"],
        ["🔢 Скільки креативів"],
        ["🤖 Генератор креативів"],
        ["⬅️ Назад"]
    ], resize_keyboard=True)

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in AUTHORIZED_USERS:
        USER_STATE[user_id] = "auth"
        await update.message.reply_text("Введи код доступу 🔑")
        return

    await update.message.reply_text("Меню 👇", reply_markup=main_keyboard())

async def generate_creatives(user_text: str) -> str:
    prompt = f"""
Ти — асистент для товарного бізнесу.
На основі опису товару створи українською мовою:

1. 3 гачки для реклами
2. 3 короткі тексти для креативу
3. 3 ідеї для відео-креативу

Пиши просто, продаюче, без води.
Товар / опис:
{user_text}
"""
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )
    return response.output_text

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    text = update.message.text.strip()

    if user not in AUTHORIZED_USERS:
        if text in ACCESS_CODES:
            AUTHORIZED_USERS.add(user)
            USER_STATE[user] = None
            await update.message.reply_text("✅ Доступ відкрито", reply_markup=main_keyboard())
        else:
            await update.message.reply_text("❌ Невірний код")
        return

    if text == "❓ FAQ":
        await update.message.reply_text("Обери модуль", reply_markup=faq_keyboard())
        return

    if text == "📦 Модуль 1 — Пошук товарів":
        await update.message.reply_text("Модуль 1 👇", reply_markup=module1_keyboard())
        return

    if text == "🎨 Модуль 2 — Сайт і креативи":
        await update.message.reply_text("Модуль 2 👇", reply_markup=module2_keyboard())
        return

    if text == "🎬 Креативи":
        await update.message.reply_text("Обери 👇", reply_markup=creatives_keyboard())
        return

    if text == "📌 Структура креативу":
        await update.message.reply_text(
            "1. Гачок (перші 2–3 секунди)\n"
            "2. Проблема\n"
            "3. Рішення\n"
            "4. Демонстрація товару\n"
            "5. Заклик до дії"
        )
        return

    if text == "✍️ Приклади текстів":
        await update.message.reply_text(
            "Приклади:\n\n"
            "Втомилась від безладу у волоссі?\n"
            "Ця шпилька тримає весь день\n"
            "Легка, стильна і зручна\n"
            "Замов зараз 👇"
        )
        return

    if text == "❌ Помилки":
        await update.message.reply_text(
            "Помилки:\n"
            "- немає гачка\n"
            "- довге відео\n"
            "- багато тексту\n"
            "- не зрозуміло, що продається"
        )
        return

    if text == "🔢 Скільки креативів":
        await update.message.reply_text("Роби 3–5 креативів на один товар")
        return

    if text == "🤖 Генератор креативів":
        USER_STATE[user] = "creative_generator"
        await update.message.reply_text(
            "Напиши коротко:\n"
            "що за товар, для кого він і яку проблему вирішує.\n\n"
            "Наприклад:\n"
            "Шпилька для густого волосся, для дівчат, які хочуть щоб зачіска трималась весь день"
        )
        return

    if text == "⬅️ Назад":
        USER_STATE[user] = None
        await update.message.reply_text("Меню 👇", reply_markup=main_keyboard())
        return

    if text in FAQ_MODULE_1:
        await update.message.reply_text(FAQ_MODULE_1[text])
        return

    if text in FAQ_MODULE_2:
        await update.message.reply_text(FAQ_MODULE_2[text])
        return

    if text == "📦 Розрахувати товар":
        USER_STATE[user] = "calc"
        await update.message.reply_text("Введи: 5 130")
        return

    if USER_STATE.get(user) == "calc":
        parsed = parse_calc_input(text)
        if not parsed:
            await update.message.reply_text("Формат: 5 130")
            return

        p, w = parsed
        await update.message.reply_text(calculate_product_cost(p, w))
        return

    if text == "💰 Маржа":
        USER_STATE[user] = "m1"
        USER_DATA[user] = {}
        await update.message.reply_text("Введи ціну продажу в грн")
        return

    if USER_STATE.get(user) == "m1":
        value = parse_number(text)
        if value is None:
            await update.message.reply_text("Введи тільки число, наприклад 400")
            return
        USER_DATA[user]["sale"] = value
        USER_STATE[user] = "m2"
        await update.message.reply_text("Введи собівартість в грн")
        return

    if USER_STATE.get(user) == "m2":
        value = parse_number(text)
        if value is None:
            await update.message.reply_text("Введи тільки число, наприклад 100")
            return
        USER_DATA[user]["cost"] = value
        USER_STATE[user] = "m3"
        await update.message.reply_text("Введи рекламу в доларах")
        return

    if USER_STATE.get(user) == "m3":
        value = parse_number(text)
        if value is None:
            await update.message.reply_text("Введи тільки число, наприклад 2")
            return

        ads = value * USD_TO_UAH
        sale = USER_DATA[user]["sale"]
        cost = USER_DATA[user]["cost"]
        profit = sale - cost - ads

        await update.message.reply_text(
            f"💰 Ціна продажу: {sale:.2f} грн\n"
            f"📦 Собівартість: {cost:.2f} грн\n"
            f"📢 Реклама: {value:.2f}$ = {ads:.2f} грн\n\n"
            f"✅ Чистий прибуток: {profit:.2f} грн"
        )
        USER_STATE[user] = None
        return

    if USER_STATE.get(user) == "creative_generator":
        await update.message.reply_text("Генерую креативи... ⏳")
        try:
            result = await generate_creatives(text)
            await update.message.reply_text(result)
        except Exception:
            await update.message.reply_text("Не вдалося згенерувати. Спробуй ще раз.")
        USER_STATE[user] = None
        return

    if text == "📊 Аналіз":
        await update.message.reply_text("Аналіз товару скоро додамо 📦")
        return

    if text == "💬 Питання":
        await update.message.reply_text("Напиши своє питання 👇")
        USER_STATE[user] = "question"
        return

    if USER_STATE.get(user) == "question":
        await update.message.reply_text("Питання отримано ✅")
        USER_STATE[user] = None
        return

    await update.message.reply_text("Обери кнопку 👇", reply_markup=main_keyboard())

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling()

if __name__ == "__main__":
    main()
