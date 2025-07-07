import logging
import os
import json
from typing import List, Dict, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# --- Logování ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Načtení proměnných prostředí ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
CHAT_ID = int(os.getenv("CHAT_ID"))

# --- Slovníky pro filtraci ---
CATEGORIES = {
    "crypto": ["bitcoin", "ethereum", "dogecoin", "stablecoin", "crypto", "blockchain", "wallet", "nubit", "kas"],
    "ai": ["openai", "chatgpt", "gpt", "ai", "artificial intelligence", "machine learning", "symphony"],
    "geo": ["trump", "biden", "putin", "ukraine", "russia", "election", "nato"],
    "tech": ["apple", "microsoft", "tesla", "spacex", "elon musk", "nvidia", "amd"],
    "disaster": ["earthquake", "flood", "fire", "hurricane", "storm", "tornado", "disaster"],
    "macro": ["inflation", "interest rates", "fed", "recession", "jobless", "cpi", "rate hike"]
}

# --- Duplicitní ID ---
sent_ids = set()

# --- GNews API ---
async def fetch_gnews() -> List[Dict[str, Any]]:
    url = "https://gnews.io/api/v4/search"
    params = {
        "token": GNEWS_API_KEY,
        "lang": "en",
        "q": " OR ".join([w for cat in CATEGORIES.values() for w in cat]),
        "max": 10
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get("articles", [])
        except Exception as e:
            logger.error(f"Chyba při načítání GNews: {e}")
            return []

# --- X (Twitter) API ---
async def fetch_tweets() -> List[Dict[str, Any]]:
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    params = {
        "query": " OR ".join([w for cat in CATEGORIES.values() for w in cat]) + " lang:en -is:retweet",
        "tweet.fields": "id,text,created_at"
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            logger.error(f"Chyba při načítání tweetů: {e}")
            return []

# --- 1. stupeň filtru ---
def keyword_score(text: str) -> int:
    score = 0
    for category, words in CATEGORIES.items():
        hits = sum(word.lower() in text.lower() for word in words)
        if hits:
            score += hits * 2
    return min(score, 10)

# --- 2. stupeň + GPT ---
def format_simple_output(item: Dict[str, Any], score: int) -> str:
    return f"\n⭐ *Surová zpráva:* {item.get('title') or item.get('text')}\n▶ Hodnocení: {score}/10\n→ *Filtr 2. stupně bez GPT*\n{item.get('url') or 'bez odkazu'}"

def format_gpt_output(raw_gpt: str, score: int, url: str) -> str:
    tag = "\n🔥 *AKCE!* Nasyp to tam!" if score == 10 else ""
    return f"\n✨ *Zpráva prošla přes GPT filtr*\n▶ Hodnocení: {score}/10\n{raw_gpt.strip()}{tag}\n{url}"

async def analyze_with_gpt(texts: List[str]) -> str:
    prompt = [{"role": "system", "content": "Jsi přímý tržní stratég. Z každé zprávy napiš konkrétní komentář, dopad a co s tím obchodně udělat. Vždy zvol směr a komoditu. Bez omáčky."}]
    user_input = "\n".join(texts)
    prompt.append({"role": "user", "content": user_input})

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": "gpt-4o", "messages": prompt, "max_tokens": 600, "temperature": 0.6},
                timeout=20
            )
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"GPT chyba: {e}")
            return "[Chyba při načítání analýzy]"

# --- Celkový proces ---
async def process_news(app: Application):
    news = await fetch_gnews()
    tweets = await fetch_tweets()

    combined = news + tweets
    filtered = [item for item in combined if item.get("title") or item.get("text")]

    messages_simple, messages_gpt, texts_for_gpt = [], [], []

    for item in filtered:
        uid = item.get("url") or item.get("id")
        if uid in sent_ids:
            continue
        sent_ids.add(uid)

        content = item.get("title") or item.get("text")
        score = keyword_score(content)

        if 5 <= score < 8:
            messages_simple.append(format_simple_output(item, score))
        elif score >= 8:
            messages_gpt.append((item, score))
            texts_for_gpt.append(content)

    for msg in messages_simple:
        await app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

    if messages_gpt:
        gpt_response = await analyze_with_gpt(texts_for_gpt)
        for i, (item, score) in enumerate(messages_gpt):
            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=format_gpt_output(gpt_response.split('\n')[i], score, item.get("url") or "bez odkazu"),
                parse_mode="Markdown"
            )

# --- Příkazy ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot jede. Použij /check pro ruční kontrolu trhů.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📡 Kontroluji zprávy...")
    await process_news(context.application)

# --- Main ---
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(process_news, "interval", minutes=15, args=[app])
    scheduler.start()

    logger.info("DavideTradingBot je připraven.")
    app.run_polling()

if __name__ == "__main__":
    main()
