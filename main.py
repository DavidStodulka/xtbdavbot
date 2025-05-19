import logging
import os
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from gnewsclient import GNewsClient
import tweepy
import openai
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

# Nastavení logů
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Proměnné z .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Inicializace OpenAI
openai.api_key = OPENAI_API_KEY

# Inicializace Twitter klienta
twitter_client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

# Inicializace GNews klienta
gnews_client = GNewsClient(language='english', max_results=10)

# Scheduler
scheduler = AsyncIOScheduler()

async def analyze_and_send_news(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Spouštím analýzu zpráv")

    # Vytáhni zprávy z GNews
    news_list = gnews_client.get_news()
    # Vytáhni tweetů (příklad s hledáním posledních 10 tweetů o finančních trzích)
    query = "(finance OR market OR stock OR crypto OR bitcoin) -is:retweet lang:en"
    tweets = twitter_client.search_recent_tweets(query=query, max_results=10, tweet_fields=['text'])

    combined_messages = []

    # Zpracování zpráv z GNews
    for item in news_list:
        combined_messages.append(item['title'] + ". " + item['description'])

    # Zpracování tweetů
    if tweets.data:
        for tweet in tweets.data:
            combined_messages.append(tweet.text)

    # Pro každou zprávu spustit analýzu
    for message in combined_messages:
        prompt = (
            f"You are a financial market expert. Analyze the following news or tweet:\n\n{message}\n\n"
            "Is this relevant for trading CFDs? Rate relevance from 1 to 10. "
            "If relevance is 5 or less, skip. If relevant, provide: "
            "- Suggested action (buy/hold/sell), "
            "- Estimated risk level (low/medium/high), "
            "- Expected profit potential in percent, "
            "- Short comment why.\n\n"
            "Respond in this exact format:\n"
            "Relevance: X/10\n"
            "Action: buy/hold/sell\n"
            "Risk: low/medium/high\n"
            "Expected profit: Y%\n"
            "Comment: ...\n"
        )

        try:
            response = await openai.chat.completions.acreate(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200,
            )
            answer = response.choices[0].message.content.strip()

            # Z parsování odpovědi vyber relevance
            if "Relevance:" in answer:
                relevance_line = [line for line in answer.split('\n') if "Relevance:" in line][0]
                relevance_score = int(relevance_line.split(":")[1].strip().split("/")[0])
                if relevance_score < 6:
                    logger.info("Zpráva ignorována kvůli nízké relevanci")
                    continue
            else:
                logger.info("Odpověď neobsahuje relevanci, přeskočeno")
                continue

            # Poslat zprávu na Telegram
            final_message = f"Nová tržní analýza:\n\n{message}\n\nVýsledek analýzy:\n{answer}"
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=final_message)
            await asyncio.sleep(1)  # Pro jistotu, aby se to nezahltí

        except Exception as e:
            logger.error(f"Chyba při volání OpenAI API: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot spuštěn. Čekám na zprávy a analýzy.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot zastavuje plánovač a ukončuje práci.")
    scheduler.remove_all_jobs()
    await context.application.stop()

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot je v chodu a kontroluje zprávy každých 15 minut.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("check", check))

    # Naplánuj spouštění analýzy každých 15 minut
    scheduler.add_job(analyze_and_send_news, "interval", minutes=15, args=[app.bot])
    scheduler.start()

    app.run_polling()

if __name__ == "__main__":
    main()
