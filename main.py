import os
import logging
import requests
import openai
import telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime

# Nastavení loggingu
logging.basicConfig(level=logging.INFO)

# Načtení proměnných z prostředí
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

# Inicializace OpenAI
openai.api_key = OPENAI_API_KEY

# Klíčová slova k detekci relevantních zpráv
RELEVANT_KEYWORDS = [
    "Trump", "Putin", "Biden", "China", "Taiwan", "Ukraine", "Russia", "inflation",
    "interest rates", "AI", "Federal Reserve", "Nasdaq", "S&P", "US30", "US500",
    "US100", "gold", "oil", "natural gas", "Dogecoin", "USD", "EUR", "GBP", "JPY",
    "terror", "earthquake", "crisis", "explosion", "bank", "NATO"
]

async def fetch_news():
    url = f"https://gnews.io/api/v4/top-headlines?token={GNEWS_API_KEY}&lang=en&max=10"
    response = requests.get(url)
    articles = response.json().get("articles", [])
    return articles

def is_relevant(text):
    return any(keyword.lower() in text.lower() for keyword in RELEVANT_KEYWORDS)

async def analyze_and_summarize(article):
    prompt = f"""
Zvaž následující zprávu a rozhodni:

1. Je relevantní pro finanční trhy?
2. Pokud ano, napiš přehledný krátký komentář.
3. Navrhni konkrétní akci: LONG/SHORT, co koupit/prodat, na jak dlouho.
4. Uveď potenciální výnos slovně a míru rizika.
Zpráva: "{article['title']}" - {article['description'] or ''}"
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=500
    )
    return response.choices[0].message.content.strip()

async def check_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Kontroluju novinky...")
    articles = await fetch_news()
    for article in articles:
        text = f"{article['title']} - {article.get('description', '')}"
        if is_relevant(text):
            summary = await analyze_and_summarize(article)
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"""Relevantní zpráva:
{article['title']}
{article.get('url', '')}

Komentář AI:
{summary}
""")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Bot je připraven. Použij příkaz /check pro kontrolu zpráv.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Bot se nyní vypíná.")
    os._exit(0)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_news))
    app.add_handler(CommandHandler("stop", stop))
    app.run_polling()
