import requests
import time
import os
from dotenv import load_dotenv

# Načti proměnné z prostředí nebo .env souboru (Render si to vezme ze svého systému)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWITTER_BEARER = os.getenv("TWITTER_BEARER")

# Účet, který chceš sledovat – zadej jeho Twitter ID (ne username!)
TWITTER_USER_ID = "44196397"  # Elon Musk, jako příklad

# Funkce pro získání tweetů

def get_latest_tweets():
    url = f"https://api.twitter.com/2/users/{TWITTER_USER_ID}/tweets"
    headers = {
        "Authorization": f"Bearer {TWITTER_BEARER}"
    }
    params = {
        "max_results": 5,
        "tweet.fields": "created_at"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        tweets = response.json()
        return tweets.get("data", [])
    else:
        print(f"Chyba při načítání tweetů: {response.status_code}")
        return []

# Funkce pro odeslání zprávy do Telegramu

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    response = requests.post(url, data=data)
    if response.status_code != 200:
        print(f"Chyba při odesílání zprávy do Telegramu: {response.text}")

# Hlavní smyčka

def main():
    print("Bot je spuštěn a sleduje Twitter...")
    last_seen_id = None
    while True:
        tweets = get_latest_tweets()
        if tweets:
            new_tweets = []
            for tweet in tweets:
                if tweet['id'] == last_seen_id:
                    break
                new_tweets.append(tweet)
            for tweet in reversed(new_tweets):
                text = f"Nový tweet: https://twitter.com/user/status/{tweet['id']}"
                send_to_telegram(text)
                last_seen_id = tweet['id']
        time.sleep(60)

if __name__ == "__main__":
    main()
