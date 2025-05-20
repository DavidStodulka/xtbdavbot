import os import logging import openai import requests from telegram import Update from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes from datetime import datetime, timedelta import time

Načti environmentální proměnné

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

Nastav OpenAI

openai.api_key = OPENAI_API_KEY MODEL_NAME = "gpt-4o"

Klíčová slova a témata

KEYWORDS = [ "Trump", "Biden", "Putin", "terror", "explosion", "earthquake", "AI", "NVIDIA", "Tesla", "NASDAQ", "US100", "US30", "SP500", "interest rates", "inflation", "Dogecoin", "USD", "EUR", "weather disaster", "tsunami", "hurricane" ]

LAST_CHECK = datetime.utcnow() - timedelta(minutes=30)

logging.basicConfig(level=logging.INFO)

async def analyze_and_decide(text): prompt = f""" Zhodnoť následující zprávu: - Je relevantní pro finanční trhy? (ano/ne) - Má potenciál ovlivnit trh? (0-10) - Pokud ano, jaký pohyb může způsobit (long/short/jiné)? - Přidej vlastní komentář k dopadu.

Zpráva:
{text}
"""

try:
    response = openai.ChatCompletion.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    analysis = response["choices"][0]["message"]["content"]
    return analysis
except Exception as e:
    logging.error(f"Chyba při volání OpenAI: {e}")
    return "Chyba při analýze zprávy."

def get_x_news(): headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"} query = " OR ".join(KEYWORDS) url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=10&tweet.fields=created_at,text"

try:
    response = requests.get(url, headers=headers)
    tweets = response.json().get("data", [])
    return [t["text"] for t in tweets]
except Exception as e:
    logging.error(f"Chyba při stahování z X: {e}")
    return []

def get_gnews(): try: query = " OR ".join(KEYWORDS) url = f"https://gnews.io/api/v4/search?q={query}&token={os.getenv('GNEWS_API_KEY')}&lang=en" response = requests.get(url) articles = response.json().get("articles", []) return [a["title"] + " - " + a["description"] for a in articles] except Exception as e: logging.error(f"Chyba při stahování z GNews: {e}") return []

async def check_news(context: ContextTypes.DEFAULT_TYPE): global LAST_CHECK now = datetime.utcnow() if now - LAST_CHECK < timedelta(minutes=15): return LAST_CHECK = now

messages = get_x_news() + get_gnews()

for msg in messages:
    analysis = await analyze_and_decide(msg)
    if "0" in analysis or "1" in analysis or "2" in analysis or "3" in analysis or "4" in analysis or "5" in analysis:
        continue  # nerelevantní nebo slabý potenciál
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"Zpráva:

{msg}

Analýza: {analysis}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("Bot je aktivní. Provádím monitoring zpráv každých 15 minut.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("Bot pozastaven (zatím neumím pauzovat automatiku).")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("Provádím manuální kontrolu...") await check_news(context)

if name == 'main': app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stop", stop))
app.add_handler(CommandHandler("check", check))

job_queue = app.job_queue
job_queue.run_repeating(check_news, interval=900, first=10)  # každých 15 minut

print("XTBDavBot běží...")
app.run_polling()

