import os
import asyncio
import logging
from datetime import datetime
from gnewsclient import GNews
import requests
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Nastavení logování
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Proměnné z prostředí
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")  # pokud bude potřeba později

openai.api_key = OPENAI_API_KEY

client = GNews(language='en', max_results=10, period='1d')

async def analyze_and_send(update=None, context=None, manual=False):
    logger.info(f"{'Manual' if manual else 'Auto'} run started at {datetime.now()}")
    news_items = client.get_news()

    for item in news_items:
        title = item.get('title', '')
        description = item.get('description', '')
        url = item.get('url', '')

        # Základní filtr na nesmysly, sport apod.
        if any(kw in title.lower() for kw in ['football', 'soccer', 'biden', 'cancer', 'match', 'score']):
            continue

        prompt = (
            "You are a financial market analyst.\n"
            "Evaluate this news for its impact on financial markets CFD trading:\n"
            f"Title: {title}\nDescription: {description}\n\n"
            "Give a score 0 to 10 on potential profit opportunity, "
            "a simple actionable advice (buy/sell/hold), duration (short/medium/long term), "
            "risk level (low/medium/high), and a concise comment explaining your reasoning. "
            "If the score is below 5, say it is not worth trading and stop.\n"
            "Respond in JSON with keys: score, action, duration, risk, comment."
        )

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.7,
            )
            result_text = response['choices'][0]['message']['content']
            # Pokusíme se parsovat JSON
            import json
            data = json.loads(result_text)

            score = float(data.get('score', 0))
            if score < 5:
                logger.info(f"Ignored news (score {score}): {title}")
                continue

            message = (
                f"News: {title}\n"
                f"Link: {url}\n"
                f"Score: {score}/10\n"
                f"Action: {data.get('action')}\n"
                f"Duration: {data.get('duration')}\n"
                f"Risk: {data.get('risk')}\n"
                f"Comment: {data.get('comment')}"
            )

            if manual:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
            else:
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

            logger.info(f"Sent news analysis: {title}")

        except Exception as e:
            logger.error(f"OpenAI or Telegram error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot started. Use /check to get latest market news analysis.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await analyze_and_send(update, context, manual=True)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot stopped. You need to restart it manually.")

async def periodic_run(application):
    while True:
        try:
            await analyze_and_send()
        except Exception as e:
            logger.error(f"Error during periodic run: {e}")
        await asyncio.sleep(900)  # 15 minut

def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("stop", stop))

    # Spustit periodickou úlohu na pozadí
    asyncio.create_task(periodic_run(application))

    application.run_polling()

if __name__ == "__main__":
    main()
