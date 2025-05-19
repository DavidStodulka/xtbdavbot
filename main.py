import logging
import os
from datetime import datetime, timedelta
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from openai import OpenAI

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Klíče a nastavení
GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GNEWS_URL = f"https://gnews.io/api/v4/search?lang=en&max=10&token={GNEWS_API_KEY}"

# Klíčová slova
KEYWORDS = [
    "Trump", "Biden", "Putin", "Xi Jinping", "von der Leyen",
    "AI", "chip", "semiconductor", "quantum computing", "OpenAI", "Nvidia",
    "US30", "US100", "US500", "Nasdaq100",
    "Dogecoin",
    "EUR/USD", "USD/JPY", "GBP/USD", "currency crash",
    "earthquake", "hurricane", "flood", "terror attack", "explosion", "mass shooting"
]

sent_articles = set()

def is_relevant_article(title, description):
    text = f"{title} {description}".lower()
    return any(keyword.lower() in text for keyword in KEYWORDS)

def fetch_gnews_articles():
    try:
        time_from = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        url = f"{GNEWS_URL}&from={time_from}"
        response = requests.get(url)
        articles = response.json().get("articles", [])
        return articles
    except Exception as e:
        logger.error(f"Chyba při získávání článků: {e}")
        return []

def analyze_article_and_generate_comment(article):
    try:
        prompt = f"""
Představ si, že jsi burzovní spekulant, co ví, co dělá. Na základě této zprávy řekni:
- Jestli je to důležitá událost, nebo jen šum
- Co koupit/prodat (long/short)
- Jak silný dopad to může mít (1-10)
- Odhadni, kdy se to na trhu projeví
- Přidej lidský komentář s trochou nadsázky nebo sarkasmu

Zpráva:
{article}
"""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI chyba: {e}")
        return "Nepodařilo se vytvořit komentář."

async def check_news_and_notify(context: ContextTypes.DEFAULT_TYPE):
    articles = fetch_gnews_articles()
    for article in articles:
        article_id = article.get("url")
        title = article.get("title")
        description = article.get("description")

        if not article_id or article_id in sent_articles:
            continue

        if not is_relevant_article(title, description):
            continue

        message = f"*{title}*\n{description}\n[Otevřít článek]({article.get('url')})"
        comment = analyze_article_and_generate_comment(f"{title}\n{description}")
        full_message = f"{message}\n\n{comment}"

        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=full_message, parse_mode="Markdown")
        sent_articles.add(article_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot je připraven. Zkontroluj /check.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kontroluji novinky...")
    await check_news_and_notify(context)

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))

    # Spustíme kontrolu každých 10 minut
    job_queue = app.job_queue
    job_queue.run_repeating(callback=check_news_and_notify, interval=600, first=10)

    logger.info("XTBDavBot běží...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
