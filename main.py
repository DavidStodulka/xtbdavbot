import logging
import os
import json
import asyncio
from typing import List, Dict, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx
from datetime import datetime

# Nastavení logování
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ENV proměnné
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
CHAT_ID = int(os.getenv("CHAT_ID"))

# Filtr - Klíčová slova 1. úrovně
KEYWORDS = {
    "crypto": ["bitcoin", "ethereum", "crypto", "dogecoin", "stablecoin", "altcoin", "ledger", "defi", "blockchain", "btc", "eth"],
    "stocks": ["apple", "microsoft", "nvidia", "tesla", "nasdaq", "s&p", "us30", "us500"],
    "ai": ["openai", "chatgpt", "gpt", "artificial intelligence", "machine learning", "deep learning", "AGI"],
    "geo": ["ukraine", "russia", "nato", "china", "taiwan", "iran", "israel", "gaza", "north korea"],
    "macro": ["inflation", "interest rates", "fed", "european central bank", "euro", "usd", "currency", "volatility"],
    "disasters": ["earthquake", "flood", "wildfire", "hurricane", "tornado", "disaster", "explosion"],
    "politics": ["trump", "biden", "election", "sanctions", "congress", "regulation"]
}

SCORE_WEIGHTS = {
    "crypto": 2,
    "stocks": 2,
    "ai": 2,
    "geo": 1,
    "macro": 1.5,
    "disasters": 1.5,
    "politics": 1
}

sent_ids = set()

# Filtrování zpráv podle skóre
def evaluate_score(text: str) -> (int, List[str]):
    score = 0
    matched_categories = []
    text_lower = text.lower()
    for category, words in KEYWORDS.items():
        if any(word in text_lower for word in words):
            score += SCORE_WEIGHTS[category]
            matched_categories.append(category)
    return round(score), matched_categories

# GPT volání
async def analyze_with_gpt(text: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "Jsi velmi konkrétní burzovní stratég. Reaguj jen na jednu zprávu. Formátuj takto: 1) Krátký komentář. 2) Ovlivněné aktivum. 3) Doporučení: směr (long/short), komodita, délka. Pokud skóre = 10, přidej výzvu typu: 'Neváhej, násyp to tam!'"},
            {"role": "user", "content": text}
        ],
        "max_tokens": 300,
        "temperature": 0.5
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Chyba GPT: {e}")
            return "Chyba v analýze."

# GNews API
def clean_text(item: Dict[str, Any]) -> str:
    return f"{item.get('title', '')} - {item.get('description', '')}"

async def fetch_gnews():
    url = "https://gnews.io/api/v4/top-headlines"
    params = {"token": GNEWS_API_KEY, "lang": "en", "max": 10}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json().get("articles", [])
        except Exception as e:
            logger.error(f"GNews error: {e}")
            return []

# Hlavní zpracování
async def job_fetch_and_send(app: Application):
    zpravy = await fetch_gnews()
    for z in zpravy:
        if z['title'] in sent_ids:
            continue
        sent_ids.add(z['title'])

        text = clean_text(z)
        score, categories = evaluate_score(text)

        msg_header = f"\n\u2B50 *Hodnocení:* {score}/10\n*Kategorie:* {', '.join(categories)}\n\u1F517 *Odkaz:* {z['url']}\n"

        if score >= 8:
            ai_msg = await analyze_with_gpt(text)
            final_msg = f"\n\u2757 *GPT Filtr:* Ano\n{msg_header}\n{ai_msg}"
        elif score >= 5:
            final_msg = f"\n\u2753 *GPT Filtr:* Ne\n{msg_header}*Zpráva:* {text}"
        else:
            continue  # ignoruj nerelevantní

        try:
            await app.bot.send_message(chat_id=CHAT_ID, text=final_msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Telegram error: {e}")

# Telegram příkazy
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot je aktivní. Použij /check pro ruční analýzu.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Provádím kontrolu zpráv...")
    await job_fetch_and_send(context.application)

# Spuštění bota
if __name__ == "__main__":
    async def main():
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("check", check))

        scheduler = AsyncIOScheduler()
        scheduler.add_job(job_fetch_and_send, "interval", minutes=3, args=[app])
        scheduler.start()

        print("\n\u2705 Bot spuštěn a běží!")
        await app.run_polling()

    asyncio.run(main())
