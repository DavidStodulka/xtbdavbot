import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import openai
import requests
from datetime import datetime

# --- Nastavení proměnných z .env ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

openai.api_key = OPENAI_API_KEY

CHECK_INTERVAL = 15 * 60  # 15 minut v sekundách

# --- Stav bota ---
bot_running = False


# --- Funkce pro vyhodnocení relevance a tipy ---
async def analyze_news(text: str) -> dict:
    prompt = (
        f"Jsi finanční analytik. Zprávu shrň na 1 odstavec, "
        f"uvedení, zda koupit long nebo short, jaké riziko, a potenciál zisku slovně a "
        f"číselně na škále 1-10. Pokud je zpráva irelevantní, napiš to jasně."
        f"\n\nZpráva: {text}\n\nOdpověď:"
    )
    response = await openai.Completion.acreate(
        model="text-davinci-003",
        prompt=prompt,
        max_tokens=200,
        temperature=0.7,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )
    result = response.choices[0].text.strip()
    # Očekáváme formát např.:
    # "Zpráva je relevantní. Doporučuji long na 7/10 riziko střední, potenciál výdělku 6/10."
    return {"text": result}


# --- Funkce pro získání zpráv z X (Twitter) ---
async def fetch_twitter_news():
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    query = "(Russia OR Ukraine OR Trump OR AI OR Nasdaq OR Bitcoin OR Dogecoin) lang:en -is:retweet"
    params = {"query": query, "max_results": 10}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        return []
    data = resp.json()
    tweets = data.get("data", [])
    return [tweet["text"] for tweet in tweets]


# --- Funkce pro získání zpráv z GNews ---
async def fetch_gnews():
    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "token": GNEWS_API_KEY,
        "lang": "en",
        "max": 10,
        "topic": "business",
    }
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        return []
    data = resp.json()
    articles = data.get("articles", [])
    return [article["title"] + ". " + article.get("description", "") for article in articles]


# --- Hlavní cyklus, co kontroluje zprávy a posílá tipy ---
async def news_loop(application):
    global bot_running
    while bot_running:
        try:
            twitter_news = await fetch_twitter_news()
            gnews_news = await fetch_gnews()
            all_news = twitter_news + gnews_news

            for news in all_news:
                analysis = await analyze_news(news)
                text = analysis.get("text", "")
                # Pokud relevance nad 5 (řekněme že v textu je explicitní info o relevantnosti)
                if "irrelevant" in text.lower():
                    continue  # přeskočit nerelevantní

                message = f"Tip z trhu:\n{news}\n\nAnalýza AI:\n{text}"
                await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                # Malé zpoždění mezi zprávami, aby nebyl spam
                await asyncio.sleep(5)
        except Exception as e:
            print(f"Chyba ve smyčce: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


# --- Příkazy bota ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_running
    if bot_running:
        await update.message.reply_text("Bot už běží.")
        return
    bot_running = True
    await update.message.reply_text("Bot spuštěn, začínám sledovat zprávy.")
    # Spustíme smyčku
    asyncio.create_task(news_loop(context.application))


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_running
    if not bot_running:
        await update.message.reply_text("Bot už neběží.")
        return
    bot_running = False
    await update.message.reply_text("Bot zastaven.")


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Jsem připraven sledovat zprávy a posílat tipy.")


# --- Hlavní funkce ---
def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("check", check))

    print("Bot startuje...")
    application.run_polling()


if __name__ == "__main__":
    main()
