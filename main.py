import os
import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from openai import OpenAI
from gnewsclient import GNews
import requests
import time

# --- Nastavení proměnných z prostředí ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# --- Inicializace klientů ---
openai = OpenAI(api_key=OPENAI_API_KEY)
gnews = GNews(language="english", max_results=10)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Funkce pro získání Twitter zpráv podle klíčových slov ---
def fetch_twitter_mentions(keywords):
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    query = " OR ".join(keywords) + " -is:retweet lang:en"
    url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=10"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        logger.warning(f"Twitter API error: {resp.status_code}")
        return []
    tweets = resp.json().get("data", [])
    return [t["text"] for t in tweets]

# --- Funkce pro získání Google News ---
def fetch_google_news():
    news_items = gnews.get_news()
    return [item["title"] + " " + item.get("description", "") for item in news_items]

# --- Vyhodnocení relevance a generování signálu pomocí OpenAI ---
async def analyze_news_and_signal(text):
    prompt = (
        "Jsi expert na finanční trhy. Podívej se na následující zprávu a rozhodni:\n"
        "1) Je zpráva relevantní pro finanční trhy? (ano/ne)\n"
        "2) Jaký typ obchodní příležitosti nabízí? (long, short, držet, ignorovat)\n"
        "3) Jaké je riziko (nízké, střední, vysoké)?\n"
        "4) Odhadovaný výnos slovně (např. malý, střední, velký)\n"
        "5) Krátký komentář k doporučení (max 1 odstavec).\n\n"
        f"Zpráva: {text}\n\nOdpověď v JSON s klíči: relevant, action, risk, profit, comment."
    )
    response = await openai.chat.completions.acreate(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
        temperature=0.3,
    )
    content = response.choices[0].message.content
    return content

# --- Filtrace hloupých zpráv ---
def is_useful_news(text):
    nonsense_keywords = [
        "football", "soccer", "match", "score", "biden cancer", "celebrity gossip",
        "weather forecast", "horoscope", "movie", "music", "entertainment"
    ]
    low_relevance = any(k in text.lower() for k in nonsense_keywords)
    return not low_relevance

# --- Posílání zpráv do Telegramu ---
async def send_signal(context: ContextTypes.DEFAULT_TYPE, message: str):
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

# --- Hlavní periodická úloha ---
async def periodic_news_check(application):
    keywords = ["Trump", "AI", "US30", "Nasdaq100", "Dogecoin", "Ukraine", "Russia", "inflation", "FED"]

    while True:
        all_news = []
        all_news.extend(fetch_twitter_mentions(keywords))
        all_news.extend(fetch_google_news())

        for news in all_news:
            if not is_useful_news(news):
                continue
            analysis = await analyze_news_and_signal(news)
            # Jednoduchý filtr na základě relevance v odpovědi AI
            if '"relevant": "ano"' in analysis.lower():
                message = f"📈 Trading tip:\n{news}\n\nAnalýza:\n{analysis}"
                await send_signal(application.bot, message)
                await asyncio.sleep(5)  # mezera mezi zprávami

        await asyncio.sleep(900)  # 15 minut

# --- Telegram příkazy ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot spuštěn. Budu hledat a posílat relevantní tržní signály.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot zastaven. Ručně zastavit skript nebo vypnout server.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Zkontroluji nové zprávy a pošlu tipy... (spuštěno ručně)")

# --- Spuštění bota ---
if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("check", check))

    # Spustit periodickou kontrolu na pozadí
    async def run_periodic():
        await periodic_news_check(application)

    asyncio.create_task(run_periodic())

    application.run_polling()
