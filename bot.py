import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ACCESS_CODES = {"AAA111"}
AUTHORIZED_USERS = set()
USER_STATE = {}
USER_DATA = {}

USD_TO_UAH = 43
CNY_TO_UAH = 5.8

# ================= КЛАВІАТУРИ =================

def main_keyboard():
    return ReplyKeyboardMarkup([
        ["📦 Розрахувати товар", "💰 Маржа"],
        ["❓ FAQ", "🎬 Креативи"],
        ["📊 Аналіз", "💬 Питання"]
    ], resize_keyboard=True)

def creatives_keyboard():
    return ReplyKeyboardMarkup([
        ["📌 Структура креативу"],
        ["✍️ Приклади текстів"],
        ["❌ Помилки"],
        ["🔢 Скільки креативів"],
        ["✅ Чек-лист"],
        ["⬅️ Назад"]
    ], resize_keyboard=True)

# ================= ЛОГІКА =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id

    if user not in AUTHORIZED_USERS:
        USER_STATE[user] = "auth"
        await update.message.reply_text("Введи код доступу 🔑")
        return

    await update.message.reply_text("Меню 👇", reply_markup=main_keyboard())

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    text = update.message.text

    # 🔐 Авторизація
    if user not in AUTHORIZED_USERS:
        if text in ACCESS_CODES:
            AUTHORIZED_USERS.add(user)
            await update.message.reply_text("✅ Доступ відкрито", reply_markup=main_keyboard())
        else:
            await update.message.reply_text("❌ Невірний код")
        return

    # 🎬 КРЕАТИВИ
    if text == "🎬 Креативи":
        await update.message.reply_text("Обери 👇", reply_markup=creatives_keyboard())
        return

    if text == "📌 Структура креативу":
        await update.message.reply_text(
            "🔥 Структура:\n\n"
            "1. Гачок (перші 2-3 сек)\n"
            "2. Проблема\n"
            "3. Рішення (товар)\n"
            "4. Демонстрація\n"
            "5. Заклик до дії"
        )
        return

    if text == "✍️ Приклади текстів":
        await update.message.reply_text(
            "📢 Приклади:\n\n"
            "Втомилась від безладу у волоссі?\n"
            "Ця шпилька тримає весь день\n"
            "Легка, стильна і зручна\n"
            "Замов зараз 👇"
        )
        return

    if text == "❌ Помилки":
        await update.message.reply_text(
            "❌ Помилки:\n\n"
            "- немає гачка\n"
            "- довге відео\n"
            "- багато тексту\n"
            "- не зрозуміло що продається"
        )
        return

    if text == "🔢 Скільки креативів":
        await update.message.reply_text(
            "👉 Робимо 3–5 креативів на товар"
        )
        return

    if text == "✅ Чек-лист":
        await update.message.reply_text(
            "✔ Є гачок\n"
            "✔ Є проблема\n"
            "✔ Є рішення\n"
            "✔ Є демонстрація\n"
            "✔ Є заклик"
        )
        return

    if text == "⬅️ Назад":
        await update.message.reply_text("Меню 👇", reply_markup=main_keyboard())
        return

    # 📦 РОЗРАХУНОК
    if text == "📦 Розрахувати товар":
        USER_STATE[user] = "calc"
        await update.message.reply_text("Введи: 5 130")
        return

    if USER_STATE.get(user) == "calc":
        try:
            p, w = map(float, text.split())
            cost = p * CNY_TO_UAH
            await update.message.reply_text(f"Собівартість: {round(cost,2)} грн")
        except:
            await update.message.reply_text("Формат: 5 130")
        return

    # 💰 МАРЖА
    if text == "💰 Маржа":
        USER_STATE[user] = "m1"
        USER_DATA[user] = {}
        await update.message.reply_text("Ціна продажу?")
        return

    if USER_STATE.get(user) == "m1":
        USER_DATA[user]["sale"] = float(text)
        USER_STATE[user] = "m2"
        await update.message.reply_text("Собівартість?")
        return

    if USER_STATE.get(user) == "m2":
        USER_DATA[user]["cost"] = float(text)
        USER_STATE[user] = "m3"
        await update.message.reply_text("Реклама $ ?")
        return

    if USER_STATE.get(user) == "m3":
        ads = float(text) * USD_TO_UAH
        sale = USER_DATA[user]["sale"]
        cost = USER_DATA[user]["cost"]
        profit = sale - cost - ads

        await update.message.reply_text(f"💰 Прибуток: {round(profit,2)} грн")
        USER_STATE[user] = None
        return

    await update.message.reply_text("Обери кнопку 👇", reply_markup=main_keyboard())

# ================= ЗАПУСК =================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling()

if __name__ == "__main__":
    main()
