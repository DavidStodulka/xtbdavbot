import os
import asyncio
import logging
import aiohttp
import openai
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Proměnné z env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not all([TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, GNEWS_API_KEY, TELEGRAM_CHAT_ID]):
    raise RuntimeError("Některá env proměnná chybí: TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, GNEWS_API_KEY, TELEGRAM_CHAT_ID")

openai.api_key = OPENAI_API_KEY

# Klíčová slova dle zadání
KEYWORDS = [
    "trump", "putin", "biden", "world leader", "AI", "dogecoin",
    "us30", "us100", "us500", "nasdaq100",
    "disaster", "weather", "terrorism",
    "forex", "currency", "usd", "eur", "gbp", "jpy", "chf", "cad", "aud", "nzd"
]

# Pro eliminaci duplicit
seen_news = set()

async def fetch_gnews():
    query = " OR ".join(KEYWORDS)
    url = f"https://gnews.io/api/v4/search?q={query}&token={GNEWS_API_KEY}&lang=en&max=10"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                data = await resp.json()
                articles = data.get("articles", [])
                results = []
                for a in articles:
                    title = a.get("title", "")
                    desc = a.get("description", "")
                    combined = (title + " " + desc).lower()
                    if any(k.lower() in combined for k in KEYWORDS):
                        results.append(combined)
                return results
        except Exception as e:
            logger.error(f"Chyba při volání GNews: {e}")
            return []

async def generate_commentary_openai(news_text: str) -> str:
    prompt = (
        f"Jsi buran na trhu a teď čteš toto:\n'{news_text}'\n"
        "Řekni mi jednoduše, jestli koupit, prodat nebo držet. "
        "Přidej vtipnej komentář, jasně řekni váhu signálu (silná, střední, slabá) a odhaduj, jak dlouho to bude působit (minuty/hodiny/dny). "
        "Když je velká volatilita, řekni, že je to velká věc, z drobností si nic nedělej."
    )
    try:
        response = await asyncio.to_thread(lambda: openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=120,
            temperature=0.7,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        ))
        return response.choices[0].text.strip()
    except Exception as e:
        logger.error(f"Chyba při volání OpenAI: {e}")
        return "AI má blackout, žádnej komentář."

async def send_telegram_message(app, text: str):
    try:
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"Chyba při posílání zprávy na Telegram: {e}")

async def news_polling_loop(app):
    global seen_news
    while True:
        news_items = await fetch_gnews()
        for news in news_items:
            if news in seen_news:
                continue
            seen_news.add(news)
            commentary = await generate_commentary_openai(news)
            message = f"Novinka:\n{news}\n\nAnalýza:\n{commentary}"
            await send_telegram_message(app, message)
            # Dej pauzu po každé zprávě, ať to nepřepaluješ
            await asyncio.sleep(10)
        # Čekej 1 minutu na další várku
        await asyncio.sleep(60)

# Telegram příkazy
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Čau, jdu sledovat trhy a zprávy. Zprávy s komentářem ti budu posílat rovnou sem.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Beru zprávy, počkej chvíli...")

async def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    # Spuštění paralelní smyčky
    asyncio.create_task(news_polling_loop(app))
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "already running" in str(e):
            # Render má vlastní event loop, takže tady prostě nic nevypínáme
            logger.info("Event loop už běží, tak pokračujem.")
        else:
            raise
