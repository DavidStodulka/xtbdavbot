import logging
import os
from datetime import datetime, timedelta
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import openai
import asyncio

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GNEWS_API_KEY = os.getenv('GNEWS_API_KEY')
CHAT_ID = int(os.getenv('CHAT_ID'))

KEYWORDS = [
    "Trump", "world leader", "AI", "technology", "US30", "US100", "US500",
    "Nasdaq100", "Dogecoin", "currency volatility", "disaster", "weather impact", "terrorism"
]

openai.api_key = OPENAI_API_KEY

def fetch_news():
    url = (
        f"https://gnews.io/api/v4/search?q={' OR '.join(KEYWORDS)}&"
        f"token={GNEWS_API_KEY}&lang=en&max=10"
    )
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("articles", [])
    except Exception as e:
        logger.error(f"Chyba při stahování zpráv: {e}")
        return []

already_sent = set()

def is_duplicate(title):
    return title in already_sent

def mark_sent(title):
    already_sent.add(title)

async def generate_analysis(text):
    prompt = (
        "Jsi drsný buran, který rozumí trhu a nebere si servítky. "
        "Zprávu analyzuj, napiš co koupit nebo prodat, v jakém časovém horizontu, "
        "a přidej stručný komentář, jestli to bude velký průser nebo pecka na trhu. "
        "Nepoužívej odborné kecy, ale buď jasný a přímočarý.\n\n"
        f"Zpráva: {text}\n\nAnalýza:"
    )
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI chyba: {e}")
        return "Nepodařilo se vytvořit komentář."

async def check_news_and_notify(app):
    logger.info("Spouštím kontrolu zpráv...")
    articles = fetch_news()
    for article in articles:
        title = article.get("title", "")
        url = article.get("url", "")
        description = article.get("description", "")
        content = f"{title}\n{description}\n{url}"

        if not any(k.lower() in title.lower() + description.lower() for k in KEYWORDS):
            continue

        if is_duplicate(title):
            continue

        mark_sent(title)

        analysis = await generate_analysis(content)

        message = (
            f"Nová zpráva:\n{title}\n{url}\n\n"
            f"Analýza: {analysis}"
        )
        try:
            await app.bot.send_message(chat_id=CHAT_ID, text=message)
            logger.info(f"Zpráva odeslána: {title}")
        except Exception as e:
            logger.error(f"Chyba při odesílání zprávy: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Čau, jsem tvůj tržní pes. Budu sledovat svět a dávat vědět, kdy to bude stát za to.")

async def checknow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ok, jdu zkontrolovat zprávy...")
    await check_news_and_notify(context.application)

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checknow", checknow))

    # START aplikace a až potom použij job queue
    await app.start()

    # Po startu už je job_queue připravená
    app.job_queue.run_repeating(
        callback=lambda ctx: asyncio.create_task(check_news_and_notify(app)),
        interval=600,
        first=10,
    )

    # Spustit polling a čekat na ukončení
    await app.updater.start_polling()
    logger.info("Bot běží...")
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
