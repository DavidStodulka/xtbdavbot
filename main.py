import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
import re
from dotenv import load_dotenv

load_dotenv()

# Nastavení logování
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Tvoje proměnné prostředí
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Funkce pro zpracování příkazů
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Bot je aktivní. Napiš /check pro analýzu.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sentiment = analyze_sentiment()
    await update.message.reply_text(f"Aktuální sentiment: {sentiment}")

# Analýza sentimentu z Twitteru
def analyze_sentiment() -> str:
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    url = "https://api.twitter.com/2/tweets/search/recent?query=bitcoin&max_results=10"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        tweets = response.json().get("data", [])
        text_combined = " ".join(tweet["text"] for tweet in tweets)

        # Zjednodušená analýza: kladná/negativní slova
        positive_words = ["bull", "moon", "pump", "green", "profit"]
        negative_words = ["bear", "crash", "dump", "red", "loss"]

        pos_count = sum(len(re.findall(rf"\b{word}\b", text_combined, re.IGNORECASE)) for word in positive_words)
        neg_count = sum(len(re.findall(rf"\b{word}\b", text_combined, re.IGNORECASE)) for word in negative_words)

        if pos_count > neg_count:
            return "Pozitivní 📈"
        elif neg_count > pos_count:
            return "Negativní 📉"
        else:
            return "Neutrální 😐"

    except Exception as e:
        logger.error(f"Chyba při analýze: {e}")
        return "Nepodařilo se načíst data ❌"

# Spuštění bota
def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))

    # Pouze await bez asyncio.run()
    app.run_polling()  # Render sám řeší event loop

if __name__ == "__main__":
    main()
