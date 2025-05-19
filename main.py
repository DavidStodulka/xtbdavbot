import logging import os from datetime import datetime, timedelta import requests from telegram import Update from telegram.ext import Application, CommandHandler, ContextTypes import openai

ZAPNI LOGOVÁNÍ

logging.basicConfig( format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO )

logger = logging.getLogger(name)

ZÍSKEJ KLÍČE Z ENV

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") GNEWS_API_KEY = os.getenv("GNEWS_API_KEY") CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

openai.api_key = OPENAI_API_KEY

KLÍČOVÁ SLOVA

KEYWORDS = [ "Trump", "Biden", "Putin", "Xi Jinping", "AI", "artificial intelligence", "US30", "US100", "US500", "Nasdaq100", "Dogecoin", "USD", "EUR", "JPY", "GBP", "CHF", "CNY", "CAD", "AUD", "NZD", "earthquake", "flood", "hurricane", "wildfire", "terror attack", "explosion", "storm", "catastrophe" ]

PAMĚŤ NA DUPLIKÁTY

recent_titles = set()

FUNKCE PRO ZPRÁVY

async def fetch_gnews(): url = f"https://gnews.io/api/v4/top-headlines?token={GNEWS_API_KEY}&lang=en" response = requests.get(url) if response.status_code == 200: data = response.json() return data.get("articles", []) else: logger.error(f"GNews error: {response.status_code}") return []

KONTROLA NA KLÍČOVÁ SLOVA

def is_relevant(article): title = article.get("title", "").lower() return any(keyword.lower() in title for keyword in KEYWORDS)

GENERUJ BURANSKOU ANALÝZU

async def generate_comment(article): title = article.get("title", "No title") description = article.get("description", "No description")

prompt = (
    f"Tady je zpráva: '{title}'. Popis: '{description}'."
    f" Zhodnoť, jestli to může pohnout trhem (nahoru/dolu), jestli je to kravina, nebo masakr."
    f" Přidej jestli koupit, prodat, nebo jen čumět. Vystihni to jednoduše, jak burzovní strejda."
)

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "Jsi burzovní parťák s nosem na velký prachy. Mluvíš srozumitelně a lidsky."},
        {"role": "user", "content": prompt}
    ]
)

return response.choices[0].message.content

HLAVNÍ FUNKCE PRO ZPRACOVÁNÍ

async def check_news(update: Update = None, context: ContextTypes.DEFAULT_TYPE = None): articles = await context.application.run_in_executor(None, fetch_gnews) new_alerts = []

for article in articles:
    title = article.get("title")
    if not is_relevant(article) or title in recent_titles:
        continue

    recent_titles.add(title)
    comment = await generate_comment(article)

    message = f"**ZPRÁVA:** {title}\n\n**SHRNUTÍ:** {comment}\n\nOdkaz: {article.get('url')}"
    new_alerts.append(message)

for alert in new_alerts:
    await context.bot.send_message(chat_id=CHAT_ID, text=alert, parse_mode="Markdown")

/start pro ruční spuštění

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("Bot je v provozu. Kdykoli chceš, dej /check.")

/check na vyžádání

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE): await check_news(update, context) await update.message.reply_text("Zprávy byly zkontrolovány.")

VYTVOR APLIKACI

app = Application.builder().token(TELEGRAM_TOKEN).build() app.add_handler(CommandHandler("start", start)) app.add_handler(CommandHandler("check", check))

SPUSŤ

if name == "main": app.run_polling()

