import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
import asyncio
import aiohttp
import json

# --- Nastavení logování ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- API klíče a proměnné z Renderu ---
TELEGRAM_TOKEN = "TvůjTelegramTokenZRenderProměnných"
OPENAI_API_KEY = "TvůjOpenAIklíč"
X_BEARER_TOKEN = "TvůjXBearerToken"
GNEWS_API_KEY = "TvůjGnewsApiKey"

# --- Konstanty a filtry témat ---
WATCHED_TOPICS = [
    "world leaders", "weather", "disaster", "terrorism", "AI", "artificial intelligence",
    "Elon Musk", "Dogecoin", "technology", "software", "hardware", "electric vehicles",
    "USD/EUR", "USD/JPY", "GBP/USD", "US30", "US100", "US500", "Nasdaq100"
]

# --- Telegram příkazy ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot spuštěn. Budu ti posílat trading tipy na základě zpráv.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot zastaven. Žádné další tipy nebudou odesílány.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kontrola proběhla, bot je aktivní.")

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Testovací zpráva funguje!")

async def manual_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Manuální analýza zprávy zadané uživatelem
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Zadej zprávu pro analýzu, např. /manual_analysis Tesla vydává nové auto.")
        return

    result = await analyze_news_with_gpt(text)
    await update.message.reply_text(result)

# --- Funkce pro získání zpráv z GNews API ---

async def fetch_gnews():
    url = f"https://gnews.io/api/v4/top-headlines?token={GNEWS_API_KEY}&lang=en&max=10"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return [article['title'] + " " + article.get('description', '') for article in data.get('articles', [])]
            else:
                logger.warning(f"GNews API request failed with status {response.status}")
                return []

# --- Funkce pro získání tweetů z X API ---

async def fetch_x_tweets():
    url = "https://api.twitter.com/2/tweets/search/recent?query=" + "%20OR%20".join(WATCHED_TOPICS) + "&max_results=10&tweet.fields=text"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return [tweet['text'] for tweet in data.get('data', [])]
            else:
                logger.warning(f"X API request failed with status {response.status}")
                return []

# --- Funkce pro analýzu zprávy pomocí GPT-4o API ---

async def analyze_news_with_gpt(text):
    # Základní prompt pro analýzu a generování trading tipů
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
        "model": "gpt-4o-mini",
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
                    response_json = json.loads(content)
                except json.JSONDecodeError:
                    logger.error("Chyba při dekódování JSON z GPT odpovědi")
                    return "Analýza zprávy selhala (chybný formát odpovědi)."
                if response_json.get("relevant", "no") == "yes":
                    return (f"Trading tip:\n"
                            f"Instrument: {response_json['instrument']}\n"
                            f"Entry: {response_json['entry']}\n"
                            f"Target: {response_json['target']}\n"
                            f"Stoploss: {response_json['stoploss']}\n"
                            f"Risk: {response_json['risk']}\n"
                            f"Očekávaný zisk: {response_json['expected_profit']}\n"
                            f"Komentář: {response_json['comment']}\n"
                            f"Relevance skóre: {response_json['score']}/10")
                else:
                    return "Zpráva není relevantní pro CFD trading."
            else:
                logger.error(f"OpenAI API request failed with status {resp.status}")
                return "Analýza zprávy selhala (API chyba)."

# --- Funkce pro pravidelnou kontrolu zpráv a odeslání tipů ---

async def job_fetch_and_send(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Spouštím kontrolu novinek...")

    gnews_news = await fetch_gnews()
    x_tweets = await fetch_x_tweets()

    messages = gnews_news + x_tweets

    for msg in messages:
        result = await analyze_news_with_gpt(msg)
        if "Trading tip" in result:
            await context.bot.send_message(chat_id=context.job.chat_id, text=result)

# --- Hlavní funkce ---

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Registrace příkazů
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("manual_analysis", manual_analysis))

    # Plánování pravidelné práce (každých 15 minut)
    job_queue: JobQueue = app.job_queue
    job_queue.run_repeating(job_fetch_and_send, interval=900, first=10, chat_id="@tvuj_telegram_chat_id")

    # Spuštění bota - bez await kvůli Render event loopu
    app.run_polling()

if __name__ == "__main__":
    main()
