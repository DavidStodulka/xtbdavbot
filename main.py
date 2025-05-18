import os
import logging
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

# Logging nastavení, abychom měli přehled o chybách a běhu bota
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Načteme token z env proměnné
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
print("DEBUG: TELEGRAM_BOT_TOKEN =", TOKEN)  # pro kontrolu, jestli vůbec je načtený

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

# Jednoduchý command handler pro /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Ahoj! Jsem připravený bot.")

async def main() -> None:
    # Vytvoříme aplikaci
    app = Application.builder().token(TOKEN).build()

    # Přidáme handlery
    app.add_handler(CommandHandler("start", start))

    # Spustíme bot bez explicitního asyncio.run(), Render se o loop postará
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
