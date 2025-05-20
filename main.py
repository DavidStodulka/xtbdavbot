import os
import logging
import asyncio
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import requests
import tweepy
import openai
from datetime import datetime, timezone

# --- Nastavení logování ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Proměnné z Renderu (Environment Variables) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # kam to posílat

if not all([TELEGRAM_TOKEN, OPENAI_API_KEY, GNEWS_API_KEY, X_BEARER_TOKEN, TELEGRAM_CHAT_ID]):
    logging.error("Některá z potřebných proměnných prostředí není nastavena!")
    exit(1)

openai.api_key = OPENAI_API_KEY

# --- Klíčová slova pro hledání zpráv ---
KEYWORDS = [
    "Trump", "Biden", "Putin", "Xi", "katastrofa", "AI", "Elon Musk", "Dogecoin",
    "Fed", "CPI", "Tesla", "Nvidia", "Apple", "Microsoft", "OpenAI",
    "Euro", "USD", "JPY", "elektromobilita", "blackout", "terorismus",
    "Google", "Amazon", "Meta", "Facebook", "Tesla", "Intel", "AMD",
    "software", "hardware", "cloud", "5G", "blockchain", "cybersecurity",
    "USD/EUR", "EUR/USD", "USD/JPY", "GBP/USD", "AUD/USD"
]

# --- Hlídání duplicit (během běhu) ---
seen_ids = set()

# --- Inicializace Twitter API přes tweepy ---
client = tweepy.Client(bearer_token=X_BEARER_TOKEN, wait_on_rate_limit=True)

# --- Scheduler ---
scheduler = AsyncIOScheduler()

# --- Funkce pro vytažení zpráv z GNews ---
def fetch_gnews():
    query = " OR ".join(KEYWORDS)
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=10&token={GNEWS_API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", [])
    except Exception as e:
        logging.error(f"GNews fetch error: {e}")
        return []

# --- Funkce pro vytažení zpráv z X (Twitter) ---
def fetch_x():
    query = " OR ".join(KEYWORDS)
    # limit 10 recent tweets
    try:
        tweets = client.search_recent_tweets(query=query, max_results=10, tweet_fields=['id','text','created_at'])
        return tweets.data or []
    except Exception as e:
        logging.error(f"X API fetch error: {e}")
        return []

# --- Funkce pro analýzu zprávy přes GPT-4o ---
async def analyze_message(text):
    prompt = (
        "Jsi zkušený tržní analytik. Zpráva níže je aktuální tržní informace:\n\n"
        f"{text}\n\n"
        "Odhodnoť relevanci této zprávy pro CFD trading na škále 0 až 10.\n"
        "Pokud je relevatní (nad 5), napiš stručný komentář, predikci trhu, a doporučení na CFD obchod:\n"
        "- instrument (např. US30, NASDAQ100, DOGEUSD)\n"
        "- vstupní cena\n"
        "- cílová cena\n"
        "- stoploss\n"
        "- riziko v %\n"
        "- očekávaný výnos v %\n"
        "Pokud relevance pod 5, napiš jen 'Není relevantní'."
    )
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Jsi chytrý a pragmatický tržní analytik."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI API error: {e}")
        return "Analýza se nepodařila."

# --- Posílání zprávy do Telegramu ---
async def send_telegram_message(app, text):
    try:
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        logging.error(f"Telegram send error: {e}")

# --- Zpracování a poslání nových zpráv ---
async def process_news(app):
    logging.info("Kontrola nových zpráv...")
    articles = fetch_gnews()
    tweets = fetch_x()
    messages_to_send = []

    for a in articles:
        # identifikátor pro duplicitní kontrolu
        id_ = a.get("url", "") 
        if id_ in seen_ids:
            continue
        seen_ids.add(id_)
        text = f"{a.get('title','')} - {a.get('description','')}"
        analysis = await analyze_message(text)
        if "Není relevantní" not in analysis:
            message = f"📢 Nová zpráva:\n{text}\n\n🧠 Analýza:\n{analysis}"
            messages_to_send.append(message)

    for t in tweets:
        id_ = str(t.id)
        if id_ in seen_ids:
            continue
        seen_ids.add(id_)
        text = t.text
        analysis = await analyze_message(text)
        if "Není relevantní" not in analysis:
            dt = t.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            message = f"🐦 Tweet ({dt}):\n{text}\n\n🧠 Analýza:\n{analysis}"
            messages_to_send.append(message)

    for msg in messages_to_send:
        await send_telegram_message(app, msg)
    logging.info(f"Odesláno {len(messages_to_send)} zpráv.")

# --- Příkazy bota ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot spuštěn. Budu pravidelně sledovat zprávy a posílat trading tipy.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot zastaven. Přestal budu posílat zprávy.")
    scheduler.remove_job('news_job')

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kontroluji novinky...")
    await process_news(context.application)
    await update.message.reply_text("Hotovo.")

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Test OK!")

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = " ".join(context.args)
    if not user_text:
        await update.message.reply_text("Použití: /analyze text zprávy")
        return
    await update.message.reply_text("Analýza probíhá...")
    result = await analyze_message(user_text)
    await update.message.reply_text(f"Výsledek:\n{result}")

# --- Plánovač pro pravidelnou kontrolu zpráv ---
def schedule_jobs(app):
    scheduler.add_job(lambda: asyncio.create_task(process_news(app)), 'interval', minutes=15, id='news_job')
    scheduler.start()

# --- Hlavní funkce ---
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Nastavení příkazů v Telegramu
    commands = [
        BotCommand("start", "Spustit bota"),
        BotCommand("stop", "Zastavit bota"),
        BotCommand("check", "Okamžitá kontrola zpráv"),
        BotCommand("test", "Test bota"),
        BotCommand("analyze", "Manuální analýza zprávy (např. /analyze Elon Musk uvedl...)")
    ]
    await app.bot.set_my_commands(commands)

    # Registrace handlerů
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("analyze", analyze))

    schedule_jobs(app)

    logging.info("Bot spuštěn.")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
