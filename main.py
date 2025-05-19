import logging
import os
import re
import time
import telegram
import openai
import requests

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

openai.api_key = OPENAI_API_KEY

ACTIVE = True

FILTER_KEYWORDS = [
    "Biden's cancer", "football", "Premier League", "soccer", "tennis",
    "Liverpool", "Brighton", "NBA", "NFL", "golfer", "goalkeeper", "match", "FIFA",
]

def is_relevant_article(title: str, content: str) -> bool:
    if not content:
        return False
    full_text = f"{title} {content}".lower()
    return not any(word.lower() in full_text for word in FILTER_KEYWORDS)

async def generate_ai_comment(article_text: str) -> str:
    prompt = f"""
Tvoje úloha je analyzovat následující zprávu a:

1. Vyhodnotit její relevanci pro finanční trhy.
2. Navrhnout jasné investiční doporučení (long/short, vstupní směr, délka držení).
3. Odhadnout slovně výnos a riziko.
4. Vše napiš jako od investora investorovi, stručně, přímě.

ZPRÁVA:
{article_text}
    """.strip()

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "Nepodařilo se získat komentář od AI."

async def fetch_and_analyze_news(context: ContextTypes.DEFAULT_TYPE):
    global ACTIVE
    if not ACTIVE:
        return

    url = (
        f"https://gnews.io/api/v4/top-headlines?"
        f"lang=en&country=us&max=5&token={GNEWS_API_KEY}"
    )
    try:
        response = requests.get(url)
        articles = response.json().get("articles", [])
    except Exception as e:
        logger.error(f"Failed to fetch news: {e}")
        return

    for article in articles:
        title = article.get("title", "")
        description = article.get("description", "")
        content = article.get("content", "")
        link = article.get("url", "")

        if not is_relevant_article(title, content):
            continue

        full_text = f"{title}\n\n{description or content}"
        ai_comment = await generate_ai_comment(full_text)
        message = f"**ZPRÁVA:**\n{title}\n{link}\n\n**KOMENTÁŘ:**\n{ai_comment}"

        try:
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode=telegram.constants.ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Telegram send error: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ACTIVE
    ACTIVE = True
    await update.message.reply_text("Bot je aktivní. Budu sledovat tržní zprávy.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ACTIVE
    ACTIVE = False
    await update.message.reply_text("Bot pozastaven. Přestávám sledovat zprávy.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))

    async def news_loop():
        while True:
            try:
                await fetch_and_analyze_news(app)
                await asyncio.sleep(300)  # 5 minut
            except Exception as e:
                logger.error(f"News loop error: {e}")
                await asyncio.sleep(30)

    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(news_loop())
    app.run_polling()
