import os
import time
import logging
import requests
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler
from openai import OpenAI
from datetime import datetime, timedelta

# Nastavení logování
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Načtení proměnných z Render Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

# Inicializace OpenAI
openai = OpenAI(api_key=OPENAI_API_KEY)

# Klíčová slova pro hledání relevantních zpráv
KEYWORDS = [
    "Putin", "Biden", "Trump", "Xi Jinping", "EU", "NATO", "Fed", "ECB",
    "inflation", "interest rates", "terror attack", "earthquake", "tsunami",
    "flood", "AI", "OpenAI", "GPT", "Elon Musk", "SpaceX", "Nasdaq100", "US30",
    "US100", "US500", "Dow Jones", "S&P 500", "currency crash", "USD", "JPY", "EUR"
]

# Uchování ID již odeslaných zpráv, aby se zabránilo duplicitám
sent_messages = set()
active = True

# Funkce pro získání zpráv z GNews
def get_gnews_articles():
    url = f"https://gnews.io/api/v4/top-headlines?token={GNEWS_API_KEY}&lang=en"
    response = requests.get(url)
    articles = response.json().get("articles", [])
    return [
        {
            "title": a["title"],
            "description": a["description"],
            "url": a["url"],
            "source": "GNews"
        } for a in articles if any(k.lower() in a["title"].lower() for k in KEYWORDS)
    ]

# Funkce pro získání tweetů z X
def get_tweets():
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    query = " OR ".join(KEYWORDS)
    url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=10&tweet.fields=text,created_at"
    response = requests.get(url, headers=headers)
    data = response.json().get("data", [])
    return [
        {
            "title": tweet["text"][:100],
            "description": tweet["text"],
            "url": f"https://twitter.com/i/web/status/{tweet['id']}",
            "source": "X"
        } for tweet in data
    ]

# Funkce pro analýzu zprávy pomocí GPT-4o
def analyze_article(article):
    prompt = (
        f"Zpráva: {article['title']}\n\n{article['description']}\n\n"
        f"Je relevantní pro světové trhy? Uveď skóre 1–10. "
        f"Pokud je ≥6, přidej stručný komentář a investiční tip (např. short US30)."
    )
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

# Odeslání zprávy do Telegramu
def send_to_telegram(bot, text):
    try:
        bot.send_message(chat_id=CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"Chyba při odesílání do Telegramu: {e}")

# Hlavní funkce zpracování zpráv
def process_news(bot):
    global sent_messages
    articles = get_gnews_articles() + get_tweets()
    for article in articles:
        if article["url"] in sent_messages:
            continue
        analysis = analyze_article(article)
        if "Skóre" in analysis:
            score = int(''.join(filter(str.isdigit, analysis.split("Skóre")[1][:2])))
            if score > 5:
                message = f"{article['source']} – {article['title']}\n{article['url']}\n\n{analysis}"
                send_to_telegram(bot, message)
                sent_messages.add(article["url"])

# Telegram příkazy
async def start(update, context):
    global active
    active = True
    await update.message.reply_text("Bot je aktivní.")

async def stop(update, context):
    global active
    active = False
    await update.message.reply_text("Bot byl pozastaven.")

async def check(update, context):
    await update.message.reply_text("Kontroluji zprávy...")
    if active:
        process_news(context.bot)

# Spuštění bota
def main():
    if not TELEGRAM_TOKEN or not CHAT_ID or not OPENAI_API_KEY or not GNEWS_API_KEY or not X_BEARER_TOKEN:
        logger.error("Některé potřebné proměnné chybí, ukončuji.")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("check", check))

    # Spuštění cyklu každých 15 minut
    async def job():
        while True:
            if active:
                logger.info("Spouštím kontrolu zpráv...")
                process_news(bot)
            await asyncio.sleep(900)  # 15 minut

    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(job())
    loop.run_until_complete(app.run_polling())

if __name__ == "__main__":
    main()
