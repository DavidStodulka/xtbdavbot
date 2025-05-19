
import os
import logging
import openai
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime

# Nastavení z .env nebo prostředí Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

openai.api_key = OPENAI_API_KEY

logging.basicConfig(level=logging.INFO)

KEYWORDS = ["Trump", "Biden", "Putin", "Ukraine", "Russia", "terror", "explosion", "AI", "Dow Jones", 
            "Nasdaq", "US500", "US30", "US100", "interest rates", "inflation", "Dogecoin", 
            "Euro", "Dollar", "EURUSD", "USDJPY", "war", "attack", "weather", "disaster"]

LAST_HEADLINES = set()

# Proměnná pro přepínání minimálního prahu dopadu
MINIMUM_IMPACT_LEVEL = ["střední", "vysoký"]

async def analyze_article(article_text):
    prompt = f"""
Zpráva: {article_text}

Zhodnoť tuto zprávu z hlediska dopadu na finanční trhy (indexy, měny, komodity, CFD). Vyhodnoť:

1. Má tato zpráva potenciální dopad na trh? (ANO/NE)
2. Pokud ano, jaký je potenciální dopad: Nízký / Střední / Vysoký
3. Jaký trh nebo instrument ovlivní? (např. US500, EURUSD, ropa, zlato)
4. Doporučený směr: LONG / SHORT / NIC
5. Doporučený časový rámec (např. 1h, 1 den, 1 týden)
6. Riziko (Nízké / Střední / Vysoké)
7. Potenciál zisku slovně
8. Komentář k logice doporučení – stručně, prakticky.

Pokud zpráva není relevantní pro CFD trhy, napiš pouze:
"NE – zpráva nemá dopad na obchodovatelné instrumenty."
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    analysis = response.choices[0].message.content.strip()
    return analysis

async def check_news(context: ContextTypes.DEFAULT_TYPE):
    logging.info("Kontroluji zprávy...")
    url = f"https://gnews.io/api/v4/top-headlines?token={GNEWS_API_KEY}&lang=en"
    response = requests.get(url)
    data = response.json()

    for article in data.get("articles", []):
        title = article["title"]
        content = article.get("content", "")
        full_text = f"{title} {content}"

        if title in LAST_HEADLINES:
            continue
        if not any(keyword.lower() in full_text.lower() for keyword in KEYWORDS):
            continue

        LAST_HEADLINES.add(title)
        analysis = await analyze_article(full_text)

        if "NE – zpráva nemá dopad" in analysis:
            continue  # přeskočíme nerelevantní zprávy

        impact_line = next((line for line in analysis.splitlines() if "dopad:" in line.lower()), "")
        if any(level in impact_line.lower() for level in MINIMUM_IMPACT_LEVEL):
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"Zpráva:
{title}

Analýza:
{analysis}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot je aktivní a sleduje zprávy.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.job_queue.run_repeating(check_news, interval=300, first=5)

    logging.info("Bot spuštěn.")
    app.run_polling()
