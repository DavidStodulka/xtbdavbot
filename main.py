import os
import aiohttp
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.ext import Application, defaults
from telegram.ext import idle

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

TRACKING_TOPICS = {
    "ai_tech": {
        "keywords": ["AI", "artificial intelligence", "machine learning", "deep learning", "Microsoft", "NVIDIA", "Meta", "Cathie Wood"],
        "weight": 3
    },
    "politics_geopolitics": {
        "keywords": ["Biden", "Xi Jinping", "Jerome Powell", "FED", "war", "sanctions", "trade war", "election", "inflation"],
        "weight": 4
    },
    "weather_natural_events": {
        "keywords": ["hurricane", "earthquake", "flood", "climate change", "storm", "drought"],
        "weight": 2
    },
    "cryptocurrency": {
        "keywords": ["dogecoin", "Elon Musk"],
        "weight": 1
    }
}

async def fetch_tweets(keyword):
    url = f"https://api.twitter.com/2/tweets/search/recent?query={keyword}&max_results=10"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])
            else:
                return []

def analyze_tweets(tweets, weight=1):
    positive_words = ["profit", "gain", "bull", "rise", "up", "surge", "win"]
    negative_words = ["loss", "bear", "drop", "decline", "down", "fall", "risk"]

    score = 0
    for tweet in tweets:
        text = tweet.get("text", "").lower()
        for word in positive_words:
            if word in text:
                score += 1 * weight
        for word in negative_words:
            if word in text:
                score -= 1 * weight
    return score

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot je online, připraven sledovat Twitter signály ve vybraných oborech.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_score = 0
    details = []

    for topic, config in TRACKING_TOPICS.items():
        keyword_query = " OR ".join(config["keywords"])
        tweets = await fetch_tweets(keyword_query)
        if not tweets:
            details.append(f"{topic}: Žádné tweety")
            continue
        score = analyze_tweets(tweets, weight=config["weight"])
        details.append(f"{topic}: skóre {score}")
        total_score += score

    if total_score > 5:
        prediction = "Trh vypadá býčím směrem 🚀 (silný signál)"
    elif total_score > 0:
        prediction = "Trh je mírně býčí."
    elif total_score == 0:
        prediction = "Trh je neutrální."
    elif total_score > -5:
        prediction = "Trh může být mírně medvědí."
    else:
        prediction = "Varování: trh může klesat 🐻 (silný signál)"

    detail_text = "\n".join(details)
    await update.message.reply_text(f"{prediction}\n\nPodrobnosti:\n{detail_text}")

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))

    await app.initialize()
    await app.start()
    print("XTBDavBot běží ✅")
    await idle()
    await app.stop()
    await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())  # Toto už funguje, protože neukončujeme loop ručně uvnitř app.run_polling()
