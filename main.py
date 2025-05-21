import logging
import os
import json
from typing import List, Dict, Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import httpx
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
CHAT_ID = int(os.getenv("CHAT_ID"))  # Tvůj chat ID

sent_tweet_ids = set()
sent_gnews_titles = set()

async def fetch_tweets() -> List[Dict[str, Any]]:
    url = "https://api.twitter.com/2/tweets/search/recent"
    query = "Bitcoin lang:en -is:retweet"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    params = {
        "query": query,
        "tweet.fields": "id,text,created_at"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except httpx.HTTPStatusError as e:
            logger.warning(f"X API chyba: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Chyba při získávání tweetů: {e}")
            return []

async def fetch_gnews() -> List[Dict[str, Any]]:
    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "token": GNEWS_API_KEY,
        "q": "Bitcoin",
        "lang": "en",
        "max": 5
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("articles", [])
        except Exception as e:
            logger.error(f"Chyba při získávání GNews: {e}")
            return []

async def analyze_with_gpt(messages: List[Dict[str, str]]) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.7
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            try:
                parsed = json.loads(content)
                return parsed.get("summary", content)
            except json.JSONDecodeError:
                return content
        except Exception as e:
            logger.error(f"Chyba GPT API: {e}")
            return "Analýza se nezdařila."

def create_gpt_prompt(tweets: List[Dict[str, Any]], news: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    combined_text = ""
    for t in tweets:
        combined_text += f"Tweet: {t['text']}\n"
    for article in news:
        combined_text += f"News: {article['title']} - {article.get('description', '')}\n"

    system_message = {
        "role": "system",
        "content": (
            "Jsi tržní analytik. Na základě následujících tweetů a novinek vytvoř stručnou "
            "a jasnou analýzu trhu se zaměřením na Bitcoin."
        )
    }
    user_message = {
        "role": "user",
        "content": combined_text
    }
    return [system_message, user_message]

async def job_fetch_and_send(app: Application):
    tweets = await fetch_tweets()
    news = await fetch_gnews()

    new_tweets = [t for t in tweets if t["id"] not in sent_tweet_ids]
    new_news = [n for n in news if n["title"] not in sent_gnews_titles]

    if not new_tweets and not new_news:
        logger.info("Žádné nové zprávy k odeslání.")
        return

    sent_tweet_ids.update(t["id"] for t in new_tweets)
    sent_gnews_titles.update(n["title"] for n in new_news)

    prompt = create_gpt_prompt(new_tweets, new_news)
    analysis = await analyze_with_gpt(prompt)

    try:
        await app.bot.send_message(chat_id=CHAT_ID, text=analysis)
        logger.info("Zpráva odeslána.")
    except Exception as e:
        logger.error(f"Chyba při odesílání zprávy: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot běží, používej /check pro manuální kontrolu.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Spouštím manuální kontrolu...")
    await job_fetch_and_send(context.application)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(job_fetch_and_send, "interval", minutes=15, args=[app])
    scheduler.start()

    logger.info("Bot startuje...")
    app.run_polling()

if __name__ == "__main__":
    main()
