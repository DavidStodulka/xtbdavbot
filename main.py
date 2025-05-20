import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
)
import aiohttp
import json
import os

# --- Logování ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Proměnné z Renderu ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # přidej do Renderu

# --- Klíčová slova ---
WATCHED_TOPICS = [
    "world leaders", "weather", "disaster", "terrorism", "AI", "artificial intelligence",
    "Elon Musk", "Dogecoin", "technology", "software", "hardware", "electric vehicles",
    "USD/EUR", "USD/JPY", "GBP/USD", "US30", "US100", "US500", "Nasdaq100"
]

# --- Telegram příkazy ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot spuštěn. Budu ti posílat trading tipy.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot zastaven. Žádné další tipy nebudou odesílány.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kontrola OK, bot běží.")

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Testovací zpráva dorazila.")

async def manual_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Zadej zprávu pro analýzu, např. /manual_analysis Apple koupil Tesla.")
        return
    result = await analyze_news_with_gpt(text)
    await update.message.reply_text(result)

# --- GNews ---
async def fetch_gnews():
    url = f"https://gnews.io/api/v4/top-headlines?token={GNEWS_API_KEY}&lang=en&max=10"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return [a['title'] + " " + a.get('description', '') for a in data.get('articles', [])]
            else:
                logger.warning(f"GNews API chyba: {response.status}")
                return []

# --- Twitter ---
async def fetch_x_tweets():
    query = "%20OR%20".join(WATCHED_TOPICS)
    url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=10&tweet.fields=text"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return [tweet['text'] for tweet in data.get('data', [])]
            else:
                logger.warning(f"X API chyba: {response.status}")
                return []

# --- GPT analýza ---
async def analyze_news_with_gpt(text):
    prompt = f"""
You are an expert trading analyst. Analyze this news for CFD trading impact:

News: "{text}"

Respond with:
- Is this relevant for CFD trading? (yes/no)
- Suggested CFD instrument (e.g. US30, Nasdaq100, DOGE/USD)
- Entry point price
- Target price
- Stop loss price
- Risk level (low, medium, high)
- Expected profit percentage
- Short market commentary (2-3 sentences)
- Relevance score from 1 to 10

Format your answer in JSON like this:

{{
  "relevant": "yes",
  "instrument": "US30",
  "entry": "34500",
  "target": "35000",
  "stoploss": "34300",
  "risk": "medium",
  "expected_profit": "3.5%",
  "comment": "Due to geopolitical tensions, US30 may rise shortly.",
  "score": 7
}}

If not relevant, respond with:

{{
  "relevant": "no"
}}
"""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 400
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status == 200:
                result = await resp.json()
                content = result['choices'][0]['message']['content']
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    logger.error("GPT odpověď není validní JSON.")
                    return "Chyba: GPT odpověď nebyla validní JSON."
                if parsed.get("relevant") == "yes":
                    return (
                        f"**Trading tip:**\n"
                        f"Instrument: {parsed['instrument']}\n"
                        f"Entry: {parsed['entry']}\n"
                        f"Target: {parsed['target']}\n"
                        f"Stoploss: {parsed['stoploss']}\n"
                        f"Riziko: {parsed['risk']}\n"
                        f"Očekávaný zisk: {parsed['expected_profit']}\n"
                        f"Komentář: {parsed['comment']}\n"
                        f"Relevance skóre: {parsed['score']}/10"
                    )
                else:
                    return "Zpráva není relevantní pro CFD trading."
            else:
                logger.error(f"OpenAI API chyba: {resp.status}")
                return "Chyba: Nepodařilo se analyzovat zprávu."

# --- Pravidelná úloha ---
async def job_fetch_and_send(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Spouštím kontrolu zpráv...")
    gnews = await fetch_gnews()
    tweets = await fetch_x_tweets()
    messages = gnews + tweets
    for msg in messages:
        result = await analyze_news_with_gpt(msg)
        if "Trading tip" in result:
            await context.bot.send_message(chat_id=CHAT_ID, text=result)

# --- Hlavní funkce ---
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("manual_analysis", manual_analysis))

    job_queue: JobQueue = app.job_queue
    job_queue.run_repeating(
        job_fetch_and_send,
        interval=900,  # každých 15 minut
        first=10,
        chat_id=CHAT_ID
    )

    app.run_polling()

if __name__ == "__main__":
    main()
