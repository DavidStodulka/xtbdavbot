import os
import logging
import requests
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
import time
import asyncio

# Načti proměnné z .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

openai.api_key = OPENAI_API_KEY
logging.basicConfig(level=logging.INFO)

def fetch_from_x():
    url = "https://api.twitter.com/2/tweets/search/recent?query=trump OR AI OR us500 OR nasdaq OR terrorism OR disaster lang:en&max_results=10"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        tweets = response.json().get("data", [])
        return [tweet["text"] for tweet in tweets]
    return []

def fetch_from_gnews():
    url = f"https://gnews.io/api/v4/top-headlines?lang=en&token={GNEWS_API_KEY}&max=10"
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        return [article["title"] + " - " + article["description"] for article in articles]
    return []

async def analyze_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    messages = fetch_from_x() + fetch_from_gnews()
    for msg in messages:
        try:
            system_prompt = "Jsi tržní analytik. Vyhodnoť dopad této zprávy na trh. Dej číslo 0-10 (0 = nerelevantní, 10 = silný dopad). Pak napiš krátký komentář proč."
            user_prompt = f"Zpráva: {msg}"
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            answer = response.choices[0].message.content
            lines = answer.splitlines()
            rating = None
            for line in lines:
                if any(char.isdigit() for char in line):
                    rating = int("".join(filter(str.isdigit, line)))
                    break
            if rating and rating > 5:
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"Zpráva: {msg}\n\nAI analýza: {answer}")
        except Exception as e:
            logging.error(f"Chyba v analýze zprávy: {e}")

async def periodic_check(app):
    while True:
        await analyze_and_send(Update(update_id=0), ContextTypes.DEFAULT_TYPE(application=app))
        await asyncio.sleep(900)  # 15 minut

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Bot je aktivní.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await analyze_and_send(update, context)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Zastavuji bot (ale jen v rámci příkazu, ne proces).")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("stop", stop))

    app.job_queue.run_repeating(lambda context: asyncio.create_task(analyze_and_send(Update(update_id=0), context)), interval=900, first=5)
    app.run_polling()
