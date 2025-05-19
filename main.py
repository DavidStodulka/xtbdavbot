import logging
import os
import time
import requests
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# Upravená klíčová slova, odstraněný “nonsense”
KEYWORDS = [
    "Trump", "Putin", "Xi Jinping", "World Leader", "AI", "Technology",
    "US30", "US100", "US500", "Nasdaq100", "Dogecoin", "USD", "EUR", "JPY", "GBP",
    "Volatility", "Earthquake", "Flood", "Tornado", "Hurricane", "Explosion", "Terrorist"
]

# Přidáme blacklist výrazů, které nechceme vůbec pouštět dál
BLACKLIST = [
    "football", "soccer", "goal", "match", "Biden cancer", "cancer", "illness", "disease",
    "hospital", "sick", "injury", "injured", "vaccine", "vaccination", "covid"
]

sent_articles = set()

def is_important(article):
    title = article.get("title", "").lower()
    description = article.get("description", "").lower()
    combined = f"{title} {description}"

    # Odfiltruj blacklistový slova
    if any(bad_word in combined for bad_word in BLACKLIST):
        logger.info(f"Filtered out nonsense: {title}")
        return False

    # Klasický filtr na klíčová slova
    return any(keyword.lower() in combined for keyword in KEYWORDS)

def generate_market_comment(title, description):
    prompt = f"""
Právě vyšla zpráva:
Název: {title}
Popis: {description}

1. Co to znamená pro trh (akcie, indexy, měny)?
2. Co by měl běžný burzovní střelec udělat? (nákup, prodej, držet)
3. Přidej srozumitelný komentář – jako bys to vysvětloval kamarádovi v hospodě.
4. Uveď časový výhled dopadu (např. 1h, 4h, 1 den).
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        content = response.choices[0].message.content.strip()
        logger.info(f"OpenAI response: {content}")
        return content
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "Nepodařilo se vytvořit komentář."

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Telegram error: {e}")

# Stále stejná hlavní funkce pro zprávy
def check_news():
    url = f"https://gnews.io/api/v4/top-headlines?lang=en&max=10&token={GNEWS_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        articles = data.get("articles", [])

        for article in articles:
            title = article.get("title", "")
            description = article.get("description", "")
            url = article.get("url", "")

            if not title or not description:
                continue

            article_id = f"{title}|{description}"
            if article_id in sent_articles:
                continue

            if is_important(article):
                sent_articles.add(article_id)
                comment = generate_market_comment(title, description)
                message = f"*{title}*\n{description}\n[Otevřít článek]({url})\n\n{comment}"
                send_to_telegram(message)

    except Exception as e:
        logger.error(f"News check error: {e}")

# /start příkaz
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("XTBDavBot aktivní. Sleduju trh, žádný blábol mi neuteče.")

# Nový /stop příkaz pro vypnutí bota (vypne polling)
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("XTBDavBot se vypíná. Měj se!")
    logger.info("Bot zastaven přes příkaz /stop")
    # ukončí polling a smyčku
    context.application.stop()
    # pokud chceš, můžeš přidat sys.exit() nebo nějaký shutdown

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))

    async def news_loop():
        while True:
            check_news()
            await asyncio.sleep(180)

    loop = asyncio.get_event_loop()
    loop.create_task(news_loop())
    application.run_polling()

if __name__ == "__main__":
    main()
