import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@dataclass
class Settings:
    cny_to_uah: float = float(os.getenv("CNY_TO_UAH", "5.8"))
    buyout_percent: float = float(os.getenv("BUYOUT_PERCENT", "0.10"))
    buyout_min_uah: float = float(os.getenv("BUYOUT_MIN_UAH", "20"))
    sea_rate_usd_per_kg: float = float(os.getenv("SEA_RATE_USD_PER_KG", "5.0"))
    air_rate_usd_per_kg: float = float(os.getenv("AIR_RATE_USD_PER_KG", "15.0"))
    usd_to_uah: float = float(os.getenv("USD_TO_UAH", "41.0"))


class VisionExtraction(BaseModel):
    title: Optional[str] = Field(default=None)
    purchase_price: Optional[float] = Field(default=None)
    currency: Optional[str] = Field(default=None, description="CNY або UAH або USD")
    weight_grams: Optional[float] = Field(default=None)
    notes: Optional[str] = Field(default=None)


class CostResult(BaseModel):
    title: Optional[str]
    purchase_price_input: float
    purchase_currency: str
    purchase_uah: float
    buyout_uah: float
    sea_delivery_uah: float
    air_delivery_uah: float
    total_sea_uah: float
    total_air_uah: float
    weight_grams: float


settings = Settings()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")

USER_DRAFTS: dict[int, dict] = {}


def format_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


def convert_to_uah(price: float, currency: str) -> float:
    currency = currency.upper()
    if currency == "CNY":
        return price * settings.cny_to_uah
    if currency == "USD":
        return price * settings.usd_to_uah
    if currency == "UAH":
        return price
    raise ValueError(f"Невідома валюта: {currency}")


def calculate_costs(title: Optional[str], purchase_price: float, currency: str, weight_grams: float) -> CostResult:
    purchase_uah = convert_to_uah(purchase_price, currency)
    buyout_uah = max(purchase_uah * settings.buyout_percent, settings.buyout_min_uah)

    weight_kg = weight_grams / 1000.0
    sea_delivery_uah = weight_kg * settings.sea_rate_usd_per_kg * settings.usd_to_uah
    air_delivery_uah = weight_kg * settings.air_rate_usd_per_kg * settings.usd_to_uah

    return CostResult(
        title=title,
        purchase_price_input=purchase_price,
        purchase_currency=currency.upper(),
        purchase_uah=purchase_uah,
        buyout_uah=buyout_uah,
        sea_delivery_uah=sea_delivery_uah,
        air_delivery_uah=air_delivery_uah,
        total_sea_uah=purchase_uah + buyout_uah + sea_delivery_uah,
        total_air_uah=purchase_uah + buyout_uah + air_delivery_uah,
        weight_grams=weight_grams,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Надішли фото або скрін товару.\n"
        "Якщо я не знайду ціну або вагу, використай /setmanual\n\n"
        "Приклад ручного вводу:\n"
        "ціна 12.8 юаня, вага 165 грам"
    )
    await update.message.reply_text(text)


async def rates_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Поточні ставки:\n"
        f"Курс юаня: {settings.cny_to_uah}\n"
        f"Курс долара: {settings.usd_to_uah}\n"
        f"Викуп: {settings.buyout_percent * 100:.0f}% (мінімум {settings.buyout_min_uah} грн)\n"
        f"Море: {settings.sea_rate_usd_per_kg} $/кг\n"
        f"Авіа: {settings.air_rate_usd_per_kg} $/кг"
    )
    await update.message.reply_text(text)


async def example_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Приклад:\nНадішли скрін товару, де видно ціну та вагу.\n"
        "Або напиши після фото: ціна 12.8 юаня, вага 165 грам"
    )


async def setmanual_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    USER_DRAFTS.setdefault(user_id, {})
    USER_DRAFTS[user_id]["awaiting_manual"] = True
    await update.message.reply_text(
        "Введи дані одним повідомленням у форматі:\n"
        "ціна 12.8 юаня, вага 165 грам"
    )

async def handle_manual_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text == "📦 Розрахувати товар":
        USER_DRAFTS.setdefault(user_id, {})
        USER_DRAFTS[user_id]["awaiting_manual"] = True
        await update.message.reply_text("Введи дані у форматі: ціна 12.8 юаня, вага 165 грам")
        return

    if text == "📊 Аналіз товару":
        await update.message.reply_text("Надішли фото товару або скрін з 1688 📸")
        return

    if text == "💬 Питання":
        await update.message.reply_text("Напиши своє питання 👇")
        return

    draft = USER_DRAFTS.get(user_id, {})
    if not draft.get("awaiting_manual"):
        return

    parsed = parse_manual_input(text)
    if not parsed:
        await update.message.reply_text(
            "Не вдалося розпізнати дані.\n"
            "Спробуй так: ціна 12.8 юаня, вага 165 грам"
        )
        return

    result = calculate_costs(
        title=draft.get("title"),
        purchase_price=parsed["price"],
        currency=parsed["currency"],
        weight_grams=parsed["weight_grams"],
    )
    USER_DRAFTS[user_id]["awaiting_manual"] = False
    await update.message.reply_text(render_result(result))



def parse_manual_input(text: str) -> Optional[dict]:
    price_match = re.search(r"ціна\s*([\d.,]+)", text.lower())
    weight_match = re.search(r"вага\s*([\d.,]+)", text.lower())

    if not price_match or not weight_match:
        return None

    price = float(price_match.group(1).replace(",", "."))
    weight = float(weight_match.group(1).replace(",", "."))

    lower = text.lower()
    if "юан" in lower or "cny" in lower:
        currency = "CNY"
    elif "дол" in lower or "usd" in lower or "$" in lower:
        currency = "USD"
    else:
        currency = "UAH"

    if "кг" in lower:
        weight_grams = weight * 1000
    else:
        weight_grams = weight

    return {"price": price, "currency": currency, "weight_grams": weight_grams}


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    message = update.message
    photo = message.photo[-1]

    await message.reply_text("Аналізую фото і рахую собівартість...")

    photo_file = await context.bot.get_file(photo.file_id)
    image_bytes = await photo_file.download_as_bytearray()

    try:
        extraction = extract_from_image(bytes(image_bytes))
        USER_DRAFTS.setdefault(user_id, {})
        USER_DRAFTS[user_id]["title"] = extraction.title

        if extraction.purchase_price is None or extraction.weight_grams is None or extraction.currency is None:
            USER_DRAFTS[user_id]["awaiting_manual"] = True
            await message.reply_text(
                "Я не зміг точно знайти ціну або вагу на фото.\n"
                f"Що побачив: {extraction.model_dump_json(ensure_ascii=False)}\n\n"
                "Напиши вручну так:\nціна 12.8 юаня, вага 165 грам"
            )
            return

        result = calculate_costs(
            title=extraction.title,
            purchase_price=extraction.purchase_price,
            currency=extraction.currency,
            weight_grams=extraction.weight_grams,
        )
        await message.reply_text(render_result(result))
    except Exception as exc:
        logger.exception("Помилка обробки фото: %s", exc)
        USER_DRAFTS.setdefault(user_id, {})
        USER_DRAFTS[user_id]["awaiting_manual"] = True
        await message.reply_text(
            "Не вдалося обробити фото автоматично.\n"
            "Введи вручну: ціна 12.8 юаня, вага 165 грам"
        )



def extract_from_image(image_bytes: bytes) -> VisionExtraction:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        "Ти аналізуєш скрін товару. Потрібно знайти тільки факти, які реально видно на зображенні. "
        "Поверни JSON з полями: title, purchase_price, currency, weight_grams, notes. "
        "Якщо чогось не видно, став null. Валюта тільки CNY, UAH або USD. "
        "Якщо вага в кг, переведи у грами. Не вигадуй значення."
    )

    response = client.responses.create(
        model=MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image_b64}",
                    },
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "vision_extraction",
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": ["string", "null"]},
                        "purchase_price": {"type": ["number", "null"]},
                        "currency": {"type": ["string", "null"]},
                        "weight_grams": {"type": ["number", "null"]},
                        "notes": {"type": ["string", "null"]},
                    },
                    "required": ["title", "purchase_price", "currency", "weight_grams", "notes"],
                    "additionalProperties": False,
                },
            }
        },
    )

    raw_text = response.output_text
    data = json.loads(raw_text)
    return VisionExtraction(**data)



def render_result(result: CostResult) -> str:
    title = result.title or "Без назви"
    return (
        f"Товар: {title}\n"
        f"Ціна закупки: {result.purchase_price_input} {result.purchase_currency}\n"
        f"Закупка в грн: {format_money(result.purchase_uah)} грн\n"
        f"Вага: {result.weight_grams} г\n"
        f"Викуп: {format_money(result.buyout_uah)} грн\n\n"
        f"Море:\n"
        f"— доставка: {format_money(result.sea_delivery_uah)} грн\n"
        f"— собівартість: {format_money(result.total_sea_uah)} грн\n\n"
        f"Авіа:\n"
        f"— доставка: {format_money(result.air_delivery_uah)} грн\n"
        f"— собівартість: {format_money(result.total_air_uah)} грн"
    )



def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Не задано TELEGRAM_BOT_TOKEN у .env")

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("rates", rates_command))
    application.add_handler(CommandHandler("example", example_command))
    application.add_handler(CommandHandler("setmanual", setmanual_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_text))

    application.run_polling()


if __name__ == "__main__":
    main()
