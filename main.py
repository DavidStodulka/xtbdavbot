import logging
import os
from telegram.ext import Application, CommandHandler

# Nastavení logování
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

async def start(update, context):
    await update.message.reply_text("Bot je online a připravený!")

async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # Toto spustí bot správně v rámci existujícího event loopu
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
