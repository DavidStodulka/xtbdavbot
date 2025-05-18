import os
from telegram import Bot
from telegram.ext import Updater, CommandHandler

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN)

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Bot je online!")

def send_message(update, context):
    bot.send_message(chat_id=CHAT_ID, text="Ahoj, tohle je test zpráva!")

def main():
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("send", send_message))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
