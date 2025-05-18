from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Sem vlož svůj TELEGRAM bot token
TOKEN = "7970230560:AAH6UDEdxIheReM6WsBkUUEnJC0qMDCdbB4"

# Funkce pro příkaz /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    print(f"CHAT ID: {chat_id}")  # Tohle se vypíše do Render Logs
    await context.bot.send_message(chat_id=chat_id, text="Bot je online. ✅")

# Spuštění bota
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

