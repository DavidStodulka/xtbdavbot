import logging
import os
import asyncio
import time
import httpx
import hashlib

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from openai import AsyncOpenAI
from gnews import GNews
import tweepy

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Načtení proměnných z prostředí (Render Variables)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWITTER_API_KEY = os.getenv("X_API_KEY")
TWITTER_API_SECRET = os.getenv("X_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
USER_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# OpenAI klient
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# GNews klient
gnews_client = GNews(language='cs', country='CZ', max_results=5)

# Twitter klient
auth = tweepy.OAuth1UserHandler(
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_SECRET
)
twitter_api = tweepy.API(auth)

# Klíčová slova
KEYWORDS = [
    "Trump", "Putin", "Biden", "Elon Musk", "AI", "katastrofa", "terorismus",
    "počasí", "tornado", "bouře", "zemětřesení", "nasdaq", "US500", "US100",
    "US30", "inflace", "FED", "ECB", "měna", "krypto", "dogecoin", "bitcoinu"
]

# Duplikáty
seen_hashes = set()
bot_running = True

# Funkce pro hodnocení zprávy
async def analyze_article(text):
    prompt = f"""
Zpráva:
{text}

Analyzuj její význam pro trhy. Skóre 0–10 (jak moc ovlivní trh). Pokud >5, přidej investiční doporučení (long/short, aktivum, důvod).
Vrať JSON ve formátu: {{"score": X, "comment": "...", "recommendation": "..."}}
    """
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    reply = response.choices[0].message.content.strip()
    return reply

# Odeslání zprávy
async def send_to_telegram(context: ContextTypes.DEFAULT_TYPE, msg: str):
    await context.bot.send_message(chat_id=USER_CHAT_ID, text=msg)

# Filtrování a hashování
def is_duplicate(text):
    hash_ = hashlib.sha256(text.encode()).hexdigest()
    if hash_ in seen_hashes:
        return True
    seen_hashes.add(hash_)
    return False

# Získání zpráv z GNews a X
def get_news():
    headlines = []
    articles = gnews_client.get_news_by_keywords(KEYWORDS)
    for a in articles:
        headlines.append(a['title'] + "\n" + a['description'])

    tweets = []
    for keyword in KEYWORDS:
        try:
            results = twitter_api.search_tweets(q=keyword, count=3, lang='en', result_type='recent')
            for tweet in results:
                tweets.append(tweet.text)
        except Exception as e:
            logger.warning(f"Chyba Twitter API: {e}")
    return headlines + tweets

# Hlavní kontrola zpráv
async def check_news(context: ContextTypes.DEFAULT_TYPE):
    if not bot_running:
        return
    logger.info("Spouštím kontrolu zpráv...")
    messages = get_news()
    for msg in messages:
        if is_duplicate(msg):
            continue
        try:
            analysis = await analyze_article(msg)
            if '"score":' in analysis:
                score = int(analysis.split('"score":')[1].split(',')[0].strip())
                if score >= 6:
                    full_message = f"ZPRÁVA:\n{msg}\n\nANALÝZA:\n{analysis}"
                    await send_to_telegram(context, full_message)
        except Exception as e:
            logger.error(f"Chyba v analýze: {e}")
    logger.info("Kontrola dokončena.")

# Příkazy
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot spuštěn.")
    context.job_queue.run_repeating(check_news, interval=600, first=10)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_running
    bot_running = False
    await update.message.reply_text("Bot pozastaven.")

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Test OK, bot běží.")

# Main
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("test", test))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
