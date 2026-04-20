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
# FAQ: МОДУЛЬ 1
# =========================
FAQ_MODULE_1 = {
    "❓ Не можу зробити копію таблиці": (
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
    "❓ З якої сторінки запускати рекламу": (
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
    "❓ З якого пристрою ми працюємо": (
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
    "❓ Табличка — разово чи постійно": (
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
    "❓ Запускаємо всі товари одразу?": (
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
    "❓ Чи конкуренти нам Rozetka, OLX": (
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
    "❓ Як порахувати вагу на 1688": (
        "Якщо на 1688 не вказана вага — це нормально.\n\n"
        "Що робимо:\n"
        "1. Дивимось цього ж товару в інших продавців\n"
        "2. Відкриваємо схожі оголошення\n"
        "3. Шукаємо товар через Google по фото\n"
        "4. Дивимось Amazon, AliExpress та інші сайти\n"
        "5. Можна також запитати в ChatGPT\n\n"
        "📌 Якщо ваги немає у одного продавця — шукаємо її в інших джерелах."
    ),
    "❓ Спочатку купуємо, потім продаємо?": (
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

# =========================
# КЛАВІАТУРИ
# =========================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📦 Розрахувати товар", "💰 Розрахувати маржу"],
            ["❓ Часті питання", "📊 Аналіз товару"],
            ["💬 Питання"],
        ],
        resize_keyboard=True
    )

def get_faq_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📦 Модуль 1 — Пошук товарів"],
            ["⬅️ Назад в меню"],
        ],
        resize_keyboard=True
    )

def get_module_1_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["❓ Не можу зробити копію таблиці"],
            ["❓ З якої сторінки запускати рекламу"],
            ["❓ З якого пристрою ми працюємо"],
            ["❓ Табличка — разово чи постійно"],
            ["❓ Запускаємо всі товари одразу?"],
            ["❓ Чи конкуренти нам Rozetka, OLX"],
            ["❓ Як порахувати вагу на 1688"],
            ["❓ Спочатку купуємо, потім продаємо?"],
            ["⬅️ До списку модулів"],
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
        return float(parts[0]), float(parts[1])
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

    # Головні кнопки
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

    if text == "❓ Часті питання":
        USER_STATE[user_id] = "faq_main"
        await update.message.reply_text(
            "Обери модуль 👇",
            reply_markup=get_faq_main_keyboard()
        )
        return

    if text == "📦 Модуль 1 — Пошук товарів":
        USER_STATE[user_id] = "faq_module_1"
        await update.message.reply_text(
            "Обери питання по модулю 1 👇",
            reply_markup=get_module_1_keyboard()
        )
        return

    if text == "⬅️ До списку модулів":
        USER_STATE[user_id] = "faq_main"
        await update.message.reply_text(
            "Обери модуль 👇",
            reply_markup=get_faq_main_keyboard()
        )
        return

    if text == "⬅️ Назад в меню":
        USER_STATE[user_id] = None
        await show_menu(update)
        return

    if text == "📊 Аналіз товару":
        USER_STATE[user_id] = "analysis"
        await update.message.reply_text("Надішли фото товару або скрін з 1688 📸")
        return

    if text == "💬 Питання":
        USER_STATE[user_id] = "question"
        await update.message.reply_text("Напиши своє питання 👇")
        return

    # FAQ відповіді
    if text in FAQ_MODULE_1:
        await update.message.reply_text(FAQ_MODULE_1[text])
        return

    # Розрахунок товару
    if USER_STATE.get(user_id) == "calc_product":
        parsed = parse_calc_input(text)
        if not parsed:
            await update.message.reply_text("Введи так: 5 130")
            return

        price_yuan, weight_g = parsed
        await update.message.reply_text(calculate_product_cost(price_yuan, weight_g))
        return

    # Покрокова маржа
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

    # Аналіз товару
    if USER_STATE.get(user_id) == "analysis":
        await update.message.reply_text("Функція аналізу товару ще допрацьовується 📦")
        return

    # Питання
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
