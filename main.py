import logging import os import re import asyncio import httpx from telegram import Update from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes from openai import AsyncOpenAI from gnews import GNews

Nastavení logování

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

Inicializace klientů

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BOT_TOKEN = os.getenv("BOT_TOKEN") CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") RELEVANT_KEYWORDS = ["Trump", "Biden", "Putin", "AI", "Nvidia", "inflation", "interest rates", "NASDAQ", "Dow Jones", "terror", "earthquake", "hurricane", "war", "dogecoin", "currency"]

Filtrování nerelevantních zpráv (fotbal, celebrity, atd.)

NONSENSE_KEYWORDS = ["football", "Premier League", "soccer", "Liverpool", "Brighton", "celebrity", "Kim Kardashian", "tennis", "NBA", "FIFA", "movie", "concert", "actor", "Biden cancer"]

GNews klient

gnews = GNews(language='en', max_results=5)

Funkce pro filtrování zpráv

def is_relevant(article): text = (article.title + " " + article.description).lower() if any(keyword.lower() in text for keyword in NONSENSE_KEYWORDS): return False return any(keyword.lower() in text for keyword in RELEVANT_KEYWORDS)

Generování komentáře pomocí OpenAI

async def generate_commentary(title, description): prompt = f""" Jsi zkušený burzovní analytik. Na základě této zprávy:

Rozhodni, zda má vliv na CFD trhy (ANO/NE).

Pokud ANO: napiš 1 odstavec komentáře, navrhni konkrétní směr obchodu (long/short/hold), jaký typ instrumentu (akcie, měna, index, komodita), jaké je riziko (nízké/střední/vysoké), potenciální výdělek (nízký/střední/vysoký), a číselný návrh vstupní ceny, SL a TP.

Pokud NE: napiš pouze: BEZ DOPADU NA TRHY


Zpráva: Nadpis: {title} Obsah: {description} """ try: response = await openai_client.chat.completions.create( model="gpt-4", messages=[ {"role": "system", "content": "Jsi AI analytik specializující se na CFD trhy."}, {"role": "user", "content": prompt} ], temperature=0.5, max_tokens=500 ) commentary = response.choices[0].message.content.strip() logger.info(f"AI COMMENT: {commentary}") return commentary except Exception as e: logger.error(f"OpenAI error: {e}") return None

Funkce pro kontrolu novinek

async def check_news(context: ContextTypes.DEFAULT_TYPE): articles = gnews.get_news("Trump OR Biden OR AI OR inflation OR Nasdaq OR war OR dogecoin OR Putin") for article in articles: if is_relevant(article): logger.info(f"Relevantní zpráva: {article.title}") commentary = await generate_commentary(article.title, article.description) if commentary and "BEZ DOPADU NA TRHY" not in commentary: await context.bot.send_message(chat_id=CHAT_ID, text=f"{article.title}\n{article.description}\n\n{commentary}")

Příkazy Telegram bota

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("XTBDavBot je aktivní a připravený.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("XTBDavBot se nyní vypíná.") os._exit(0)

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE): await check_news(context) await update.message.reply_text("Zprávy zkontrolovány.")

Spuštění bota

async def main(): app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stop", stop))
app.add_handler(CommandHandler("check", check))

job_queue = app.job_queue
job_queue.run_repeating(check_news, interval=300, first=5)

await app.run_polling()

if name == 'main': asyncio.run(main())

