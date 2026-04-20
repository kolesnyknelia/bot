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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# НАЛАШТУВАННЯ
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Не знайдено TELEGRAM_BOT_TOKEN у Railway Variables")

# Коди доступу
ACCESS_CODES = {
    "AAA111",
    "BBB222",
    "CCC333",
}

# Хто вже авторизувався
AUTHORIZED_USERS = set()

# Режим користувача:
# None / "calc" / "analysis" / "question"
USER_STATE = {}

# Курси і доставка
CNY_TO_UAH = 5.8
USD_TO_UAH = 43
SEA_USD_PER_KG = 5
AIR_USD_PER_KG = 15


# =========================
# КЛАВІАТУРА
# =========================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
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
def calculate_cost(price_yuan: float, weight_g: float) -> str:
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
        price_yuan = float(parts[0])
        weight_g = float(parts[1])
        return price_yuan, weight_g
    except ValueError:
        return None


async def show_menu(update: Update):
    await update.message.reply_text(
        "Привіт 👋 Обери дію:",
        reply_markup=get_main_keyboard()
    )


# =========================
# /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in AUTHORIZED_USERS:
        USER_STATE[user_id] = "awaiting_code"
        await update.message.reply_text("Введи код доступу 🔑")
        return

    await show_menu(update)


# =========================
# ГОЛОВНА ЛОГІКА ПІСЛЯ АВТОРИЗАЦІЇ
# =========================
async def handle_authorized_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text == "📦 Розрахувати товар":
        USER_STATE[user_id] = "calc"
        await update.message.reply_text(
            "Введи так: 5 130\n\n"
            "де:\n"
            "5 — ціна в юанях\n"
            "130 — вага в грамах"
        )
        return

    if text == "📊 Аналіз товару":
        USER_STATE[user_id] = "analysis"
        await update.message.reply_text(
            "Надішли фото товару або скрін з 1688 📸"
        )
        return

    if text == "💬 Питання":
        USER_STATE[user_id] = "question"
        await update.message.reply_text(
            "Напиши своє питання 👇"
        )
        return

    # Режим розрахунку
    if USER_STATE.get(user_id) == "calc":
        parsed = parse_calc_input(text)

        if not parsed:
            await update.message.reply_text("Введи так: 5 130")
            return

        price_yuan, weight_g = parsed
        await update.message.reply_text(calculate_cost(price_yuan, weight_g))
        return

    # Режим аналізу
    if USER_STATE.get(user_id) == "analysis":
        await update.message.reply_text(
            "Функція аналізу товару ще допрацьовується 📦"
        )
        return

    # Режим питання
    if USER_STATE.get(user_id) == "question":
        await update.message.reply_text(
            "Дякую, питання отримано ✅"
        )
        return

    await show_menu(update)


# =========================
# ОБРОБКА ВСЬОГО ТЕКСТУ
# =========================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Якщо користувач ще не авторизований
    if user_id not in AUTHORIZED_USERS:
        if text in ACCESS_CODES:
            AUTHORIZED_USERS.add(user_id)
            USER_STATE[user_id] = None

            logger.info(
                "Користувач авторизувався: id=%s username=%s",
                user_id,
                update.effective_user.username,
            )

            await update.message.reply_text("✅ Доступ відкрито")
            await show_menu(update)
            return

        await update.message.reply_text("Невірний код доступу ❌")
        return

    # Якщо вже авторизований — працюємо як звичайний бот
    await handle_authorized_user(update, context)


# =========================
# ЗАПУСК
# =========================
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Бот запущено 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
