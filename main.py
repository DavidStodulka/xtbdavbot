import logging
import os
import json
from typing import List, Dict, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# Nastavení logování
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Načtení proměnných
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
CHAT_ID = int(os.getenv("CHAT_ID"))

# Sledované klíčové výrazy
TRACK_KEYWORDS = [
    "Trump", "Biden", "Putin", "Ukraine", "AI", "OpenAI", "Tesla",
    "Elon Musk", "Nasdaq100", "S&P500", "US30", "Dogecoin", "inflation",
    "Federal Reserve", "disaster", "earthquake", "terror", "Apple",
    "Microsoft", "NVIDIA", "AMD", "Bitcoin", "currency volatility"
]

sent_tweet_ids = set()
sent_gnews_titles = set()

# --- DATOVÉ ZDROJE ---

async def fetch_tweets() -> List[Dict[str, Any]]:
    query = " OR ".join(TRACK_KEYWORDS)
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    params = {
        "query": f"({query}) lang:en -is:retweet",
        "tweet.fields": "id,text,created_at"
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            logger.error(f"Chyba při získávání tweetů: {e}")
            return []

async def fetch_gnews() -> List[Dict[str, Any]]:
    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "token": GNEWS_API_KEY,
        "q": " OR ".join(TRACK_KEYWORDS),
        "lang": "en",
        "max": 10
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get("articles", [])
        except Exception as e:
            logger.error(f"Chyba při získávání GNews: {e}")
            return []

# --- GPT ANALÝZA ---

def create_gpt_prompt(tweets: List[Dict[str, Any]], news: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    messages = [{
        "role": "system",
        "content": (
            "Jsi špičkový tržní analytik. Na základě následujících tweetů a zpráv vytvoř krátkou analýzu dopadů na trhy. "
            "Zaměř se na významné události a uveď, zda očekáváš růst (long) nebo pokles (short) u příslušných aktiv. "
            "Vrať výstup ve formátu:\n"
            "{'summary': 'Stručná analýza a doporučení.'}"
        )
    }]

    user_input = ""
    for t in tweets:
        user_input += f"[Tweet] {t['text']}\n"
    for n in news:
        user_input += f"[News] {n['title']} - {n.get('description', '')}\n"

    messages.append({
        "role": "user",
        "content": user_input
    })
    return messages

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
            resp = await client.post(url, headers=headers, json=body, timeout=20)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            try:
                return json.loads(content).get("summary", content)
            except:
                return content
        except Exception as e:
            logger.error(f"Chyba GPT API: {e}")
            return "Analýza se nepodařila načíst."

# --- HLAVNÍ FUNKCE ---

async def job_fetch_and_send(app: Application):
    tweets = await fetch_tweets()
    news = await fetch_gnews()

    new_tweets = [t for t in tweets if t["id"] not in sent_tweet_ids]
    new_news = [n for n in news if n["title"] not in sent_gnews_titles]

    if not new_tweets and not new_news:
        logger.info("Žádné nové relevantní zprávy.")
        return

    sent_tweet_ids.update(t["id"] for t in new_tweets)
    sent_gnews_titles.update(n["title"] for n in new_news)

    messages = create_gpt_prompt(new_tweets, new_news)
    analysis = await analyze_with_gpt(messages)

    try:
        await app.bot.send_message(chat_id=CHAT_ID, text=analysis)
        logger.info("Zpráva odeslána do Telegramu.")
    except Exception as e:
        logger.error(f"Telegram chyba: {e}")

# --- PŘÍKAZY ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot běží. Použij /check pro ruční kontrolu zpráv.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kontroluji nové zprávy...")
    await job_fetch_and_send(context.application)

# --- START BOTA ---

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(job_fetch_and_send, "interval", minutes=15, args=[app])
    scheduler.start()

    logger.info("XTBDavBot je připraven!")
    app.run_polling()

if __name__ == "__main__":
    main()
