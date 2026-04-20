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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Не знайдено TELEGRAM_BOT_TOKEN у Railway Variables")

# =========================
# НАЛАШТУВАННЯ
# =========================
ACCESS_CODES = {
    "AAA111",
    "BBB222",
    "CCC333",
}

AUTHORIZED_USERS = set()
USER_STATE = {}
USER_DATA = {}

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
            ["📦 Розрахувати товар", "💰 Розрахувати маржу"],
            ["📊 Аналіз товару", "💬 Питання"],
        ],
        resize_keyboard=True
    )


# =========================
# ДОПОМІЖНІ ФУНКЦІЇ
# =========================
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
        price_yuan = float(parts[0])
        weight_g = float(parts[1])
        return price_yuan, weight_g
    except ValueError:
        return None


def parse_number(text: str):
    text = text.replace(",", ".").strip()
    try:
        return float(text)
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
# ЛОГІКА ПІСЛЯ АВТОРИЗАЦІЇ
# =========================
async def handle_authorized_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # КНОПКИ
    if text == "📦 Розрахувати товар":
        USER_STATE[user_id] = "calc_product"
        await update.message.reply_text(
            "Введи так: 5 130\n\n"
            "де:\n"
            "5 — ціна в юанях\n"
            "130 — вага в грамах"
        )
        return

    if text == "💰 Розрахувати маржу":
        USER_STATE[user_id] = "margin_sale_price"
        USER_DATA[user_id] = {}
        await update.message.reply_text("Введи ціну продажу в грн")
        return

    if text == "📊 Аналіз товару":
        USER_STATE[user_id] = "analysis"
        await update.message.reply_text("Надішли фото товару або скрін з 1688 📸")
        return

    if text == "💬 Питання":
        USER_STATE[user_id] = "question"
        await update.message.reply_text("Напиши своє питання 👇")
        return

    # РОЗРАХУВАТИ ТОВАР
    if USER_STATE.get(user_id) == "calc_product":
        parsed = parse_calc_input(text)
        if not parsed:
            await update.message.reply_text("Введи так: 5 130")
            return

        price_yuan, weight_g = parsed
        await update.message.reply_text(calculate_product_cost(price_yuan, weight_g))
        return

    # ПОКРОКОВА МАРЖА
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
            await update.message.reply_text("Введи тільки число, наприклад: 100")
            return

        USER_DATA[user_id]["cost_price"] = cost_price
        USER_STATE[user_id] = "margin_ads_dollars"
        await update.message.reply_text("Введи витрати на рекламу в доларах")
        return

    if USER_STATE.get(user_id) == "margin_ads_dollars":
        ads_dollars = parse_number(text)
        if ads_dollars is None:
            await update.message.reply_text("Введи тільки число, наприклад: 2")
            return

        USER_DATA[user_id]["ads_dollars"] = ads_dollars

        sale_price = USER_DATA[user_id]["sale_price"]
        cost_price = USER_DATA[user_id]["cost_price"]
        ads_uah = ads_dollars * USD_TO_UAH
        profit = sale_price - cost_price - ads_uah

        await update.message.reply_text(
            f"💰 Ціна продажу: {sale_price:.2f} грн\n"
            f"📦 Собівартість: {cost_price:.2f} грн\n"
            f"📢 Реклама: {ads_dollars:.2f}$ = {ads_uah:.2f} грн\n\n"
            f"✅ Чистий прибуток: {profit:.2f} грн"
        )

        USER_STATE[user_id] = None
        USER_DATA[user_id] = {}
        await show_menu(update)
        return

    # АНАЛІЗ ТОВАРУ
    if USER_STATE.get(user_id) == "analysis":
        await update.message.reply_text("Функція аналізу товару ще допрацьовується 📦")
        return

    # ПИТАННЯ
    if USER_STATE.get(user_id) == "question":
        await update.message.reply_text("Дякую, питання отримано ✅")
        USER_STATE[user_id] = None
        await show_menu(update)
        return

    await show_menu(update)


# =========================
# ОБРОБКА ТЕКСТУ
# =========================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Якщо ще не авторизований
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

    # Якщо вже авторизований
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
