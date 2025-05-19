import logging
import os
import time
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import openai

# Logging pro ladění
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ENV proměnné
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

# Nastavení OpenAI
openai.api_key = OPENAI_API_KEY

# Klíčová slova
KEYWORDS = [
    "Trump", "Biden", "Putin", "Xi Jinping", "World Leader", "AI", "Technology",
    "US30", "US100", "US500", "Nasdaq100", "Dogecoin", "USD", "EUR", "JPY", "GBP",
    "Volatility", "Earthquake", "Flood", "Tornado", "Hurricane", "Explosion", "Terrorist"
]

# Duplikáty
sent_articles = set()

# Filtrovaná detekce důležitosti zprávy
def is_important(article):
    title = article.get("title", "").lower()
    description = article.get("description", "").lower()
    combined = f"{title} {description}"
    return any(keyword.lower() in combined for keyword in KEYWORDS)

# Dotaz na GPT pro vytvoření komentáře
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
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "Nepodařilo se vytvořit komentář."

# Odesílání zprávy do Telegramu
def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        logger.error(f"Telegram error: {e}")

# Hlavní funkce - pravidelně dotazuje GNews
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

# Hlavní funkce aplikace
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    # Spuštění smyčky pro kontrolu zpráv každé 3 minuty
    async def news_loop():
        while True:
            check_news()
            await asyncio.sleep(180)

    # Spuštění asynchronně
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(news_loop())
    application.run_polling()

if __name__ == "__main__":
    main()
