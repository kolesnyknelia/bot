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


def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📦 Розрахувати товар", "💰 Розрахувати маржу"],
            ["❓ FAQ", "🎬 Креативи"],
            ["📊 Аналіз", "💬 Питання"],
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


def creatives_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📌 Структура креативу"],
            ["✍️ Приклади текстів"],
            ["❌ Помилки"],
            ["🔢 Скільки креативів"],
            ["✅ Чек-лист"],
            ["🤖 Генератор креативів"],
            ["⬅️ Назад"],
        ],
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
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "Ти сильний маркетинговий асистент для товарного бізнесу. Пиши українською мовою."
            },
            {
                "role": "user",
                "content": prompt
            },
        ],
        temperature=0.8,
    )
    return response.choices[0].message.content


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in AUTHORIZED_USERS:
        USER_STATE[user_id] = "auth"
        await update.message.reply_text("Введи код доступу 🔑")
        return

    await update.message.reply_text("Меню 👇", reply_markup=main_keyboard())


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Авторизація
    if user_id not in AUTHORIZED_USERS:
        if text in ACCESS_CODES:
            AUTHORIZED_USERS.add(user_id)
            USER_STATE[user_id] = None
            await update.message.reply_text("✅ Доступ відкрито", reply_markup=main_keyboard())
        else:
            await update.message.reply_text("❌ Невірний код")
        return

    # FAQ
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

    if text in FAQ_MODULE_1:
        USER_STATE[user_id] = None
        await update.message.reply_text(FAQ_MODULE_1[text])
        return

    if text in FAQ_MODULE_2:
        USER_STATE[user_id] = None
        await update.message.reply_text(FAQ_MODULE_2[text])
        return

    # Креативи
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

    if text == "✅ Чек-лист":
        USER_STATE[user_id] = None
        await update.message.reply_text(
            "✔ Є гачок\n"
            "✔ Є проблема\n"
            "✔ Є рішення\n"
            "✔ Є демонстрація\n"
            "✔ Є заклик"
        )
        return

    if text == "🤖 Генератор креативів":
        USER_STATE[user_id] = "creative_generator"
        await update.message.reply_text(
            "Напиши коротко:\n"
            "що за товар, для кого він і яку проблему вирішує.\n\n"
            "Наприклад:\n"
            "Шпилька для густого волосся, для дівчат, які хочуть щоб зачіска трималась весь день"
        )
        return

    # Розрахунок товару
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

    # Маржа
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

    # Генератор креативів
    if USER_STATE.get(user_id) == "creative_generator":
        await update.message.reply_text("Генерую креативи... ⏳")
        try:
            result = await generate_creatives(text)
            await update.message.reply_text(result)
        except Exception as e:
            await update.message.reply_text(f"Помилка генерації: {str(e)}")
        USER_STATE[user_id] = None
        return

    # Аналіз / питання
    if text == "📊 Аналіз":
        USER_STATE[user_id] = None
        await update.message.reply_text("Аналіз товару скоро додамо 📦")
        return

    if text == "💬 Питання":
        USER_STATE[user_id] = "question"
        await update.message.reply_text("Напиши своє питання 👇")
        return

    if USER_STATE.get(user_id) == "question":
        await update.message.reply_text("Питання отримано ✅")
        USER_STATE[user_id] = None
        return

    # Назад
    if text == "⬅️ Назад":
        USER_STATE[user_id] = None
        await update.message.reply_text("Меню 👇", reply_markup=main_keyboard())
        return

    await update.message.reply_text("Обери кнопку 👇", reply_markup=main_keyboard())


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling()


if __name__ == "__main__":
    main()
