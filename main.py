import logging
import os
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from gnewsclient import gnewsclient
import tweepy
import openai
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# Načtení proměnných z .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Nastavení API klíčů
openai.api_key = OPENAI_API_KEY

# Logger
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Inicializace GNews klienta
gnews_client = gnewsclient()

# Inicializace Twitter API
twitter_client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

async def analyze_and_send_news(context: ContextTypes.DEFAULT_TYPE, text: str, source: str):
    """Analyzuj zprávu přes OpenAI a případně pošli na Telegram."""
    try:
        prompt = (
            f"Jsi finanční analytik a máš rozhodnout, jestli je tato zpráva "
            f"relevantní pro obchodování CFD a jaký je potenciál zisku.\n"
            f"Zpráva ze zdroje: {source}\n\n"
            f"Text zprávy:\n{text}\n\n"
            f"Napiš krátký, jasný komentář s doporučením (koupit/prodat/držet), "
            f"odhadovaným rizikem a potenciálním ziskem (slovně a číselně). "
            f"Pokud je zpráva nerelevantní, napiš 'NERELEVANTNÍ'."
        )

        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        answer = response.choices[0].message.content.strip()
        logger.info(f"OpenAI odpověď: {answer}")

        if answer == "NERELEVANTNÍ":
            logger.info("Zpráva vyhodnocena jako nerelevantní, neodesílám.")
            return

        msg = f"Zdroj: {source}\nZpráva:\n{text}\n\nKomentář AI:\n{answer}"
        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

    except Exception as e:
        logger.error(f"Chyba při analýze zprávy: {e}")

async def fetch_gnews(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Stahuji zprávy z GNews...")
    client = gnewsclient()
    client.language = 'english'
    client.location = 'global'
    client.topic = 'finance'
    news_list = client.get_news()

    for news in news_list[:5]:  # limit zpráv na 5, aby nebyl spam
        title = news.get('title', '')
        desc = news.get('description', '')
        url = news.get('url', '')
        text = f"{title}\n{desc}\n{url}"
        await analyze_and_send_news(context, text, "GNews")

async def fetch_twitter(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Stahuji tweety z Twitteru...")
    try:
        query = "(finance OR market OR stocks OR economy) lang:en -is:retweet"
        tweets = twitter_client.search_recent_tweets(query=query, max_results=5)
        if tweets.data:
            for tweet in tweets.data:
                text = tweet.text
                await analyze_and_send_news(context, text, "Twitter")
        else:
            logger.info("Žádné relevantní tweety nenalezeny.")
    except Exception as e:
        logger.error(f"Chyba při stahování tweetů: {e}")

# Příkazy pro Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot spuštěn. Budu pravidelně sledovat zprávy a posílat tipy.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot zastaven, ale na Renderu/hostingu bude potřeba ručně ukončit proces.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kontroluji zprávy teď...")
    await fetch_gnews(context)
    await fetch_twitter(context)

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("check", check))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(fetch_gnews, 'interval', minutes=15, args=[app.bot])
    scheduler.add_job(fetch_twitter, 'interval', minutes=15, args=[app.bot])
    scheduler.start()

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
