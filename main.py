import logging
import os
import re
import openai
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Konfigurace
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NEWS_KEYWORDS = ["Trump", "Putin", "China", "Biden", "Russia", "Ukraine", "Federal Reserve", "interest rates", "inflation", "war", "terror", "disaster", "crisis", "nasdaq", "us500", "us30", "dogecoin", "elon", "AI", "dollar", "yen", "euro", "oil", "gas", "NATO", "attack", "bomb", "Ceasefire", "peace talks", "Iran", "Israel", "Bitcoin", "SEC"]

EXCLUDED_TOPICS = ["football", "soccer", "tennis", "Premier League", "NBA", "F1", "cancer", "injury", "celebrity", "Taylor Swift", "Liverpool", "Brighton"]

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kontextová proměnná pro vypnutí
active = True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot je aktivní. Sleduji novinky...")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active
    active = False
    await update.message.reply_text("Bot byl vypnut.")

def is_relevant(text: str) -> bool:
    text_lower = text.lower()
    if any(ex.lower() in text_lower for ex in EXCLUDED_TOPICS):
        return False
    return any(k.lower() in text_lower for k in NEWS_KEYWORDS)

def analyze_sentiment(text: str) -> str:
    prompt = (
        f"Zpráva: {text}\n\n"
        "Odpověz přehledně: \n"
        "- Má zpráva významný dopad na finanční trh? (ano/ne)\n"
        "- Jaká strategie by se mohla vyplatit? (long/short/žádná)\n"
        "- Co konkrétně koupit/prodat? (např. US500, USDJPY...)\n"
        "- Jak dlouho držet? (krátkodobě/střednědobě/dlouhodobě)\n"
        "- Riziko: nízké/střední/vysoké\n"
        "- Potenciální výdělek: malý/střední/vysoký\n"
        "- Komentář (max 3 věty lidským tónem):"
    )

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.7
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "Nepodařilo se analyzovat zprávu."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active
    if not active:
        return

    text = update.message.text
    if is_relevant(text):
        logger.info("Relevantní zpráva: " + text)
        result = analyze_sentiment(text)
        await update.message.reply_text(result)
    else:
        logger.info("Zpráva ignorována (nerelevantní): " + text)

# Spuštění
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot spuštěn.")
    app.run_polling()

if __name__ == "__main__":
    main()
