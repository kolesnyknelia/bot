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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ACCESS_CODES = {"AAA111", "BBB222", "CCC333"}
AUTHORIZED_USERS = set()
USER_STATE = {}
USER_DATA = {}

USD_TO_UAH = 43
CNY_TO_UAH = 5.8

# ================= FAQ =================

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

# ================= UI =================

def main_keyboard():
    return ReplyKeyboardMarkup([
        ["📦 Розрахувати товар", "💰 Розрахувати маржу"],
        ["❓ Часті питання", "📊 Аналіз товару"],
        ["💬 Питання"]
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

# ================= LOGIC =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid not in AUTHORIZED_USERS:
        USER_STATE[uid] = "auth"
        await update.message.reply_text("Введи код доступу 🔑")
        return

    await update.message.reply_text("Меню 👇", reply_markup=main_keyboard())

# ===== TEXT =====

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    # авторизація
    if uid not in AUTHORIZED_USERS:
        if text in ACCESS_CODES:
            AUTHORIZED_USERS.add(uid)
            await update.message.reply_text("✅ Доступ відкрито", reply_markup=main_keyboard())
        else:
            await update.message.reply_text("❌ Невірний код")
        return

    # меню
    if text == "❓ Часті питання":
        await update.message.reply_text("Обери модуль", reply_markup=faq_keyboard())
        return

    if text == "📦 Модуль 1 — Пошук товарів":
        await update.message.reply_text("Модуль 1 👇", reply_markup=module1_keyboard())
        return

    if text == "🎨 Модуль 2 — Сайт і креативи":
        await update.message.reply_text("Модуль 2 👇", reply_markup=module2_keyboard())
        return

    if text == "⬅️ Назад":
        await update.message.reply_text("Меню 👇", reply_markup=main_keyboard())
        return

    # FAQ відповіді
    if text in FAQ_MODULE_1:
        await update.message.reply_text(FAQ_MODULE_1[text])
        return

    if text in FAQ_MODULE_2:
        await update.message.reply_text(FAQ_MODULE_2[text])
        return

    # ===== РОЗРАХУНОК ТОВАРУ =====
    if text == "📦 Розрахувати товар":
        USER_STATE[uid] = "calc"
        await update.message.reply_text("Введи: 5 130")
        return

    if USER_STATE.get(uid) == "calc":
        try:
            p, w = map(float, text.split())
            cost = p * CNY_TO_UAH
            await update.message.reply_text(f"Собівартість: {round(cost,2)} грн")
        except:
            await update.message.reply_text("Формат: 5 130")
        return

    # ===== МАРЖА =====
    if text == "💰 Розрахувати маржу":
        USER_STATE[uid] = "m1"
        USER_DATA[uid] = {}
        await update.message.reply_text("Ціна продажу?")
        return

    if USER_STATE.get(uid) == "m1":
        USER_DATA[uid]["sale"] = float(text)
        USER_STATE[uid] = "m2"
        await update.message.reply_text("Собівартість?")
        return

    if USER_STATE.get(uid) == "m2":
        USER_DATA[uid]["cost"] = float(text)
        USER_STATE[uid] = "m3"
        await update.message.reply_text("Реклама $ ?")
        return

    if USER_STATE.get(uid) == "m3":
        ads = float(text) * USD_TO_UAH
        sale = USER_DATA[uid]["sale"]
        cost = USER_DATA[uid]["cost"]
        profit = sale - cost - ads

        await update.message.reply_text(
            f"💰 Прибуток: {round(profit,2)} грн"
        )

        USER_STATE[uid] = None
        return

    # ===== інше =====
    await update.message.reply_text("Обери кнопку 👇", reply_markup=main_keyboard())

# ================= RUN =================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling()

if __name__ == "__main__":
    main()
