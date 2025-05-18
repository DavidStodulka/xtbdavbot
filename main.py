import os
import requests
import telegram
from telegram.ext import Updater, CommandHandler
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "realDonaldTrump")

bot = telegram.Bot(token=TELEGRAM_TOKEN)

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Bot je online!")

def get_tweet():
    headers = {
        "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"
    }
    url = f"https://api.twitter.com/2/users/by/username/{TWITTER_USERNAME}?user.fields=public_metrics"
    user_resp = requests.get(url, headers=headers).json()
    user_id = user_resp["data"]["id"]

    tweet_url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    tweet_resp = requests.get(tweet_url, headers=headers).json()
    tweet_text = tweet_resp["data"][0]["text"]
    return tweet_text

def send_latest_tweet(update, context):
    try:
        tweet = get_tweet()
        context.bot.send_message(chat_id=CHAT_ID, text=f"Nový tweet: {tweet}")
    except Exception as e:
        context.bot.send_message(chat_id=CHAT_ID, text=f"Chyba: {str(e)}")

def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("tweet", send_latest_tweet))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
