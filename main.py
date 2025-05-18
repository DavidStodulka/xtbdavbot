import os
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

keywords = [
    "artificial intelligence", "AI", "machine learning", "deep learning", "tech",
    "semiconductor", "NVIDIA", "Intel", "AMD",
    "US500", "SP500", "NASDAQ100", "US100", "DOW30", "US30",
    "dogecoin", "doge", "Elon Musk"
]

users = [
    "elonmusk", "satyanadella", "JensenHuang", "CathieDWood", "VitalikButerin"
]

positive_words = ["profit", "gain", "bull", "rise"]
negative_words = ["loss", "bear", "drop", "decline"]

async def fetch_tweets_combined():
    query = "(" + " OR ".join([f'"{kw}"' for kw in keywords]) + ")"
    user_queries = [f"from:{user}" for user in users]
    full_query = query + " OR " + " OR ".join(user_queries)

    url = f"https://api.twitter.com/2/tweets/search/recent?query={full_query}&max_results=20"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])
            else:
                return []

def analyze_tweets_weighted(tweets):
    score = 0
    for tweet in tweets:
        text = tweet.get("text", "").lower()
        author = tweet.get("author_id", "")
        
        # Zjistit jestli je autor v seznamu sledovaných podle author_id (musíme mít mapování, zatím ignorujeme)
        # Protože API vrací author_id, pro jednoduchost zvýšíme váhu, pokud text obsahuje jméno osoby
        # (Nedokonalé, ale jednoduché řešení)
        author_weight = 1
        for user in users:
            if user.lower() in text:
                author_weight = 3
                break

        # Klíčová slova ve textu (váha 1)
        keyword_weight = 0
        for kw in keywords:
            if kw.lower() in text:
                keyword_weight = 1
                break

        # Sentiment
        sentiment_score = 0
        for word in positive_words:
            if word in text:
                sentiment_score += 1
        for word in negative_words:
            if word in text:
                sentiment_score -= 1
        
        # Celkový příspěvek do skóre
        score += (author_weight + keyword_weight) * sentiment_score

    return score

def risk_percentage(score):
    # Omezíme skóre do rozmezí -10 až +10
    if score < -10:
        score = -10
    if score > 10:
        score = 10
    
    # Převedeme na riziko 0–100 %, kde záporné skóre znamená vyšší riziko
    # -10 -> 100%, 0 -> 50%, +10 -> 0%
    risk = int(((-score + 10) / 20) * 100)
    return risk

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot je online, připraven sledovat Twitter signály z AI, technologií, akciových indexů a Dogecoinu.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tweets = await fetch_tweets_combined()
    if not tweets:
        await update.message.reply_text("Nenalezl jsem žádné nové tweety.")
        return

    score = analyze_tweets_weighted(tweets)
    risk = risk_percentage(score)

    if risk > 70:
        prediction = f"Vysoké riziko poklesu trhu! ⚠️ ({risk} %)"
    elif risk > 40:
        prediction = f"Střední riziko - buďte obezřetní. ({risk} %)"
    else:
        prediction = f"Trh vypadá stabilně, nízké riziko poklesu. ({risk} %)"

    await update.message.reply_text(prediction)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.run_polling()

if __name__ == "__main__":
    main()
