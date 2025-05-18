from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Vlož sem svůj Telegram Bot Token (od BotFather)
TOKEN = "tvůj_telegram_token"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot je online a připraven!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tady pomohu, napiš /start.")

if __name__ == "__main__":
    # vytvoření aplikace s tokenem
    app = ApplicationBuilder().token(TOKEN).build()

    # registrace příkazů
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # spustit bota
    app.run_polling()
