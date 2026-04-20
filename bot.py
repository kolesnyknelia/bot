import logging
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ====== НАЛАШТУВАННЯ ======
ACCESS_CODES = [
    "AAA111",
    "BBB222",
    "CCC333"
]

USED_CODES = set()
AUTHORIZED_USERS = set()

logging.basicConfig(level=logging.INFO)

# ====== /start ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in AUTHORIZED_USERS:
        await show_menu(update)
        return

    await update.message.reply_text("Введи код доступу 🔑")

# ====== МЕНЮ ======
async def show_menu(update: Update):
    keyboard = [
        ["📦 Розрахувати товар"],
        ["📊 Аналіз товару"],
        ["💬 Питання"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привіт 👋 Обери дію:",
        reply_markup=reply_markup
    )

# ====== ОБРОБКА ПОВІДОМЛЕНЬ ======
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # 🔐 Якщо не авторизований
    if user_id not in AUTHORIZED_USERS:
        if text in ACCESS_CODES and text not in USED_CODES:
            AUTHORIZED_USERS.add(user_id)
            USED_CODES.add(text)

            await update.message.reply_text("✅ Доступ відкрито")
            await show_menu(update)
        else:
            await update.message.reply_text("Невірний або вже використаний код ❌")
        return

    # ====== КНОПКИ ======
    if text == "📦 Розрахувати товар":
        await update.message.reply_text("Введи так: 5 130")
        return

    if text == "📊 Аналіз товару":
        await update.message.reply_text("Надішли фото товару або скрін з 1688 📸")
        return

    if text == "💬 Питання":
        await update.message.reply_text("Напиши своє питання 👇")
        return

    # ====== ПРОСТИЙ РОЗРАХУНОК ======
    try:
        parts = text.split()
        if len(parts) == 2:
            price = float(parts[0])
            weight = float(parts[1])

            result = price * 1.5 + weight * 0.2

            await update.message.reply_text(
                f"📦 Результат: {round(result, 2)} грн"
            )
            return
    except:
        pass

    await update.message.reply_text("Не зрозуміла команду 🤷‍♀️")

# ====== ЗАПУСК ======
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
