import os
import re
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Не знайдено TELEGRAM_BOT_TOKEN у змінних Railway")

# =========================
# НАЛАШТУВАННЯ
# =========================
CNY_TO_UAH = 5.8
USD_TO_UAH = 43
SEA_USD_PER_KG = 5
AIR_USD_PER_KG = 15

SEA_UAH_PER_KG = SEA_USD_PER_KG * USD_TO_UAH
AIR_UAH_PER_KG = AIR_USD_PER_KG * USD_TO_UAH

# =========================
# КОДИ ДОСТУПУ
# False = ще не використаний
# True = вже використаний
# =========================
ACCESS_CODES = {
    "OLYA123": False,
    "IRA456": False,
    "TANYA789": False,
    "STUDENT001": False,
    "STUDENT002": False,
}

# Хто вже авторизований
AUTHORIZED_USERS = set()

# Стан користувача
# calc = чекаємо ручний розрахунок
# analysis = режим аналізу
# question = режим питання
USER_STATE = {}

# =========================
# КЛАВІАТУРА
# =========================
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["📦 Розрахувати товар"],
        ["📊 Аналіз товару"],
        ["💬 Питання"],
    ],
    resize_keyboard=True
)

# =========================
# ДОПОМІЖНІ ФУНКЦІЇ
# =========================
def calc_result(price_yuan: float, weight_g: float) -> str:
    price_uah = price_yuan * CNY_TO_UAH
    weight_kg = weight_g / 1000

    sea_delivery = weight_kg * SEA_UAH_PER_KG
    air_delivery = weight_kg * AIR_UAH_PER_KG

    total_sea = price_uah + sea_delivery
    total_air = price_uah + air_delivery

    return (
        f"💰 Викуп: {price_yuan:.2f} ¥ = {price_uah:.2f} грн\n"
        f"⚖️ Вага: {weight_g:.0f} г\n\n"
        f"🚢 Ціна товару з доставкою (море): {total_sea:.2f} грн\n"
        f"✈️ Ціна товару з доставкою (авіа): {total_air:.2f} грн"
    )

def parse_manual_input(text: str):
    numbers = re.findall(r"\d+(?:[.,]\d+)?", text.replace(",", "."))
    if len(numbers) < 2:
        return None
    try:
        price_yuan = float(numbers[0])
        weight_g = float(numbers[1])
        return price_yuan, weight_g
    except ValueError:
        return None

async def show_menu(update: Update):
    await update.message.reply_text(
        "Привіт 👋 Обери дію:",
        reply_markup=MAIN_KEYBOARD
    )

# =========================
# КОМАНДИ
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Введи код доступу 🔑")
        return

    await show_menu(update)

# =========================
# ОБРОБКА ТЕКСТУ
# =========================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    text = update.message.text.strip()

    # 1. Якщо користувач ще не авторизований
    if user_id not in AUTHORIZED_USERS:
        if text in ACCESS_CODES and ACCESS_CODES[text] is False:
            AUTHORIZED_USERS.add(user_id)
            ACCESS_CODES[text] = True
            USER_STATE[user_id] = None

            logger.info(
                "Авторизація: id=%s username=%s name=%s code=%s",
                user.id,
                user.username,
                user.full_name,
                text
            )

            await update.message.reply_text("Доступ відкрито ✅")
            await show_menu(update)
        else:
            await update.message.reply_text("Невірний або вже використаний код ❌")
        return

    # 2. Кнопки
    if text == "📦 Розрахувати товар":
        USER_STATE[user_id] = "calc"
        await update.message.reply_text(
            "Введи дані у форматі:\n"
            "5 130\n\n"
            "де:\n"
            "5 = ціна в юанях\n"
            "130 = вага в грамах"
        )
        return

    if text == "📊 Аналіз товару":
        USER_STATE[user_id] = "analysis"
        await update.message.reply_text(
            "Надішли фото товару або скрін з 1688 📸\n\n"
            "Зараз ця функція в режимі підготовки."
        )
        return

    if text == "💬 Питання":
        USER_STATE[user_id] = "question"
        await update.message.reply_text(
            "Напиши своє питання 👇\n\n"
            "Зараз ця функція в режимі підготовки."
        )
        return

    # 3. Режим розрахунку
    if USER_STATE.get(user_id) == "calc":
        parsed = parse_manual_input(text)
        if not parsed:
            await update.message.reply_text(
                "Не вдалося розпізнати дані.\n"
                "Спробуй так: 5 130"
            )
            return

        price_yuan, weight_g = parsed
        await update.message.reply_text(calc_result(price_yuan, weight_g))
        return

    # 4. Режим аналізу
    if USER_STATE.get(user_id) == "analysis":
        await update.message.reply_text(
            "Для аналізу товару скоро додамо окрему логіку 📦"
        )
        return

    # 5. Режим питання
    if USER_STATE.get(user_id) == "question":
        await update.message.reply_text(
            "Питання отримала ✅\n"
            "Цей блок ще допрацьовується."
        )
        return

    # 6. Якщо нічого не вибрано
    await show_menu(update)

# =========================
# ЗАПУСК
# =========================
def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("БОТ ПРАЦЮЄ 🚀")
    application.run_polling()

if __name__ == "__main__":
    main()
