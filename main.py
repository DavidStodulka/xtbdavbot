import asyncio
import logging
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from openai import OpenAI
import requests

# --- Nastavení loggeru ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Proměnné z prostředí (Render Variables) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Kam posílat zprávy

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")      # Twitter API token
# Přidej další proměnné, pokud chceš

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not OPENAI_API_KEY or not X_BEARER_TOKEN:
    logging.error("Některé potřebné proměnné chybí, ukončuji.")
    exit(1)

# --- Inicializace OpenAI klienta ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Stav pro periodickou úlohu ---
task = None
task_running = False

# --- Funkce pro rozhodování, jestli zprávu poslat ---
def should_send_message(score: float) -> bool:
    return score > 5.0  # Použij škálu podle svých potřeb

# --- Funkce pro získání zpráv z X (Twitter) - příklad ---
async def fetch_twitter_messages():
    # Jednoduchý příklad, dej si to podle X API, co máš
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    url = "https://api.twitter.com/2/tweets/search/recent?query=bitcoin"  # Přizpůsob
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        logging.warning(f"Twitter API error: {resp.status_code}")
        return []
    data = resp.json()
    tweets = [t["text"] for t in data.get("data", [])]
    return tweets

# --- Funkce pro získání zpráv z GNews (přes REST, protože gnewsclient nefunguje) ---
async def fetch_gnews_messages():
    # Nahraď svou vlastní GNews API logikou, zde je mock
    # Pokud nemáš API, můžeš použít jiný zdroj
    return ["Zpráva z GNews #1", "Zpráva z GNews #2"]

# --- Funkce pro vyhodnocení zprávy přes OpenAI GPT ---
async def evaluate_message(message: str) -> dict:
    prompt = f"Posuď tuto zprávu z hlediska tržního potenciálu a relevance pro obchodování:\n\n{message}\n\nOhodnoť ji skóre 1-10 a přidej krátký komentář."
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Jsi zkušený tržní analytik."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150,
        )
        content = response.choices[0].message.content.strip()
        # Předpokládáme, že GPT odpoví ve formátu: "Skóre: X\nKomentář: text"
        lines = content.splitlines()
        score = 0
        comment = ""
        for line in lines:
            if "skóre" in line.lower():
                parts = line.split(":")
                if len(parts) > 1:
                    try:
                        score = float(parts[1].strip())
                    except:
                        pass
            elif "komentář" in line.lower():
                parts = line.split(":", 1)
                if len(parts) > 1:
                    comment = parts[1].strip()
        return {"score": score, "comment": comment, "raw": content}
    except Exception as e:
        logging.error(f"Chyba při vyhodnocení zprávy: {e}")
        return {"score": 0, "comment": "", "raw": ""}

# --- Periodická úloha pro kontrolu zpráv ---
async def periodic_check(app):
    global task_running
    logging.info("Periodická úloha spuštěna.")
    while task_running:
        try:
            twitter_msgs = await fetch_twitter_messages()
            gnews_msgs = await fetch_gnews_messages()
            all_msgs = twitter_msgs + gnews_msgs

            for msg in all_msgs:
                eval_res = await evaluate_message(msg)
                if should_send_message(eval_res["score"]):
                    text = (
                        f"Nová zpráva s potenciálem:\n"
                        f"Skóre: {eval_res['score']}\n"
                        f"Komentář: {eval_res['comment']}\n\n"
                        f"Originál:\n{msg}"
                    )
                    await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
                    logging.info(f"Odeslána zpráva: {msg[:50]}...")
                else:
                    logging.info(f"Zpráva zamítnuta (score {eval_res['score']}): {msg[:50]}...")
        except Exception as e:
            logging.error(f"Chyba v periodické úloze: {e}")

        await asyncio.sleep(900)  # 15 minut

# --- Handlery příkazů ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global task, task_running
    if task_running:
        await update.message.reply_text("Periodická kontrola už běží.")
        return
    task_running = True
    task = asyncio.create_task(periodic_check(context.application))
    await update.message.reply_text("Spuštěna periodická kontrola zpráv.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global task, task_running
    if not task_running:
        await update.message.reply_text("Periodická kontrola neběží.")
        return
    task_running = False
    if task:
        task.cancel()
        task = None
    await update.message.reply_text("Periodická kontrola zastavena.")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Probíhá manuální kontrola zpráv...")
    try:
        twitter_msgs = await fetch_twitter_messages()
        gnews_msgs = await fetch_gnews_messages()
        all_msgs = twitter_msgs + gnews_msgs
        sent_count = 0
        for msg in all_msgs:
            eval_res = await evaluate_message(msg)
            if should_send_message(eval_res["score"]):
                text = (
                    f"Manuální zpráva s potenciálem:\n"
                    f"Skóre: {eval_res['score']}\n"
                    f"Komentář: {eval_res['comment']}\n\n"
                    f"Originál:\n{msg}"
                )
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
                sent_count += 1
        await update.message.reply_text(f"Manuální kontrola hotova. Odesláno {sent_count} zpráv.")
    except Exception as e:
        await update.message.reply_text(f"Chyba během manuální kontroly: {e}")

# --- Hlavní funkce ---

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("check", check))

    logging.info("Bot spuštěn")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
