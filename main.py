import os
import logging
import asyncio
import openai
import httpx
import time
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime
from gnews import GNews
import tweepy

# Nastavení logování
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Načtení proměnných z Render environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
X_API_KEY = os.environ.get("X_API_KEY")
X_API_SECRET = os.environ.get("X_API_SECRET")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Inicializace klientů
openai.api_key = OPENAI_API_KEY
bot = Bot(token=TELEGRAM_TOKEN)
gnews = GNews(language='cs', country='Czech Republic', max_results=10)
auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
twitter_api = tweepy.API(auth)

# Klíčová slova
KEYWORDS = [
    "Trump", "Putin", "Biden", "Zelenskyj", "Xi Jinping", "terorismus", "výbuch", "katastrofa",
    "tornádo", "záplavy", "zemětřesení", "AI", "umělá inteligence", "GPT", "OpenAI", "Elon Musk",
    "US30", "US100", "US500", "Nasdaq", "inflace", "úrokové sazby", "ekonomika", "FED", "ECB", "Dogecoin"
]

sent_messages = set()
active = True

def get_gnews_articles():
    try:
        news = gnews.get_news(" OR ".join(KEYWORDS))
        return [{"title": n["title"], "description": n["description"], "url": n["url"], "source": "GNews"} for n in news]
    except Exception as e:
        logger.error(f"Chyba při načítání GNews: {e}")
        return []

def get_tweets():
    try:
        tweets = []
        for keyword in KEYWORDS:
            results = twitter_api.search_tweets(q=keyword, lang="en", count=5, result_type="recent")
            for tweet in results:
                tweets.append({
                    "title": tweet.text[:100],
                    "description": tweet.text,
                    "url": f"https://twitter.com/user/status/{tweet.id}",
                    "source": "Twitter"
                })
        return tweets
    except Exception as e:
        logger.error(f"Chyba při načítání tweetů: {e}")
        return []

def analyze_article(article):
    prompt = (
        f"Zpráva: {article['title']}\n\n{article['description']}\n\n"
        f"Je relevantní pro světové trhy? Uveď skóre 1–10. "
        f"Pokud je ≥6, přidej komentář a investiční doporučení (např. short US30, long Dogecoin)."
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Chyba při volání OpenAI: {e}")
        return "Chyba v analýze"

def send_to_telegram(bot, message):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        logger.error(f"Chyba při posílání zprávy na Telegram: {e}")

def process_news(bot):
    global sent_messages
    try:
        articles = get_gnews_articles() + get_tweets()
        for article in articles:
            if article["url"] in sent_messages:
                continue
            analysis = analyze_article(article)
            if "Skóre" in analysis:
                score = int(''.join(filter(str.isdigit, analysis.split("Skóre")[1][:2])))
                if score > 5:
                    message = f"{article['source']} – {article['title']}\n{article['url']}\n\n{analysis}"
                    send_to_telegram(bot, message)
                    sent_messages.add(article["url"])
    except Exception as e:
        logger.error(f"Chyba při zpracování zpráv: {e}")

async def job():
    while True:
        try:
            if active:
                logger.info("Spouštím kontrolu zpráv...")
                process_news(bot)
        except Exception as e:
            logger.error(f"Chyba v job loop: {e}")
        await asyncio.sleep(900)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active
    active = True
    await update.message.reply_text("Bot je aktivní.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active
    active = False
    await update.message.reply_text("Bot byl pozastaven.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    loop = asyncio.get_event_loop()
    loop.create_task(job())
    app.run_polling()

if __name__ == "__main__":
    main()
