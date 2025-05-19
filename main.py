import logging import os import re import time import telegram import openai import requests from telegram import Update from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

Logování

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

Klíče a ID

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

openai.api_key = OPENAI_API_KEY

Klíčová slova relevantní pro finanční trhy

KEYWORDS = [ "Trump", "Biden", "Putin", "Ukraine", "Russia", "war", "AI", "inflation", "interest rates", "Federal Reserve", "Nasdaq", "S&P", "Dow Jones", "USD", "EUR", "JPY", "Bitcoin", "Dogecoin", "crash", "soar", "plunge", "rally", "China", "Taiwan", "NATO", "ECB", "BoJ", "Fed", "market", "stocks", "weather", "earthquake", "terrorism", "explosion", "attack" ]

Funkce pro získání zpráv z GNews

def fetch_news(): try: response = requests.get( f"https://gnews.io/api/v4/top-headlines?lang=en&token={GNEWS_API_KEY}&max=10" ) news_items = response.json().get("articles", []) filtered = [] for item in news_items: content = f"{item['title']} {item.get('description', '')}" if any(keyword.lower() in content.lower() for keyword in KEYWORDS): filtered.append(content) return filtered except Exception as e: logger.error(f"Chyba při stahování zpráv: {e}") return []

AI generátor shrnutí, investičního doporučení a metrik

def generate_ai_comment(news_text): try: prompt = f""" Zpráva: {news_text}

Vytvoř investiční shrnutí zprávy v tomto formátu:

ZPRÁVA: <stručný popis>

AI KOMENTÁŘ: <stručný dopad na trh, reálný vývoj>

DOPORUČENÍ:

Pozice: long/short/žádná

Nástroje: konkrétní instrumenty (např. EUR/USD, NASDAQ100, ropa)

Riziko: nízké/střední/vysoké

Výnosový potenciál: nízký/střední/vysoký + horizont

Stop-loss: konkrétní nebo přibližná hodnota

Cíl: % nebo přibližná hodnota


Nepiš víc, než je potřeba, jen fakta a přímo. """ response = openai.chat.completions.create( model="gpt-4", messages=[ {"role": "system", "content": "Jsi finanční tržní stratég."}, {"role": "user", "content": prompt} ] ) return response.choices[0].message.content.strip() except Exception as e: logger.error(f"OpenAI error: {e}") return "Chyba při získávání AI komentáře."

Funkce pro odeslání zprávy na Telegram

def send_to_telegram(message): bot = telegram.Bot(token=TELEGRAM_TOKEN) bot.send_message(chat_id=CHAT_ID, text=message)

Základní příkazy bota

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("XTBDavBot aktivní. Použij /check pro novinky, /stop pro ukončení.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE): news_items = fetch_news() if not news_items: await update.message.reply_text("Žádné relevantní zprávy.") return for news in news_items: comment = generate_ai_comment(news) if "Pozice" in comment: send_to_telegram(comment) time.sleep(1)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("XTBDavBot byl zastaven. Pokud běží v cloudu, vypni proces manuálně.")

Hlavní běh aplikace

def main(): app = ApplicationBuilder().token(TELEGRAM_TOKEN).build() app.add_handler(CommandHandler("start", start)) app.add_handler(CommandHandler("check", check)) app.add_handler(CommandHandler("stop", stop)) app.run_polling()

if name == 'main': main()

