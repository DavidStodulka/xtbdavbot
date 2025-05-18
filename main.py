import os
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Načtení proměnných ze systému
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

async def fetch_tweets(keyword):
    url = f"https://api.twitter.com/2/tweets/search/recent?query={keyword}&max_results=5"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])
            else:
                return []

def analyze_tweets(tweets):
    positive_words = ["profit", "gain", "bull", "rise"]
    negative_words = ["loss", "bear", "drop", "decline"]

    score = 0
    for tweet in tweets:
        text = tweet.get("text", "").lower()
        for word in positive_words:
            if word in text:
                score += 1
        for word in negative_words:
            if word in text:
                score -= 1
    return score

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot je online, připraven sledovat Twitter signály.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = "bitcoin"
    tweets = await fetch_tweets(keyword)
    if not tweets:
        await update.message.reply_text("Nenalezl jsem žádné nové tweety.")
        return

    score = analyze_tweets(tweets)
    if score > 0:
        prediction = "Trh vypadá býčím směrem 🚀"
    elif score < 0:
        prediction = "Varování: trh může klesat 🐻"
    else:
        prediction = "Trh je neutrální."

    await update.message.reply_text(prediction)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.run_polling()

if __name__ == "__main__":
    main()

