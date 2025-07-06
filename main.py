import logging
import os
import json
from typing import List, Dict, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import asyncio

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ENVIRONMENT ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
CHAT_ID = int(os.getenv("CHAT_ID"))

# --- KLÍČOVÁ SLOVA & SLOVNÍK PRO FILTRACI (ROZŠÍŘENÝ) ---
KEYWORDS_DICT = {
    # Politika a světoví lídři
    "politics": ["Trump", "Biden", "Putin", "Ukraine", "sanctions", "election", "government", "policy", "legislation", "Congress"],
    # Technologie a AI
    "technology": ["AI", "OpenAI", "Tesla", "Elon Musk", "Microsoft", "Apple", "NVIDIA", "AMD", "software", "hardware", "electromobility", "blockchain", "crypto", "Bitcoin", "Ethereum", "Dogecoin", "CBDC"],
    # Trhy a ekonomika
    "markets": ["Nasdaq100", "S&P500", "US30", "inflation", "Federal Reserve", "interest rates", "currency volatility", "forex", "commodities", "gold", "oil"],
    # Bezpečnost a katastrofy
    "security": ["disaster", "earthquake", "terror", "cyberattack", "war", "conflict", "protests"],
    # Další klíčové fráze s vyšším významem
    "high_impact": ["crash", "bubble", "default", "recession", "bankruptcy", "merger", "acquisition", "scandal", "lawsuit"]
}

# --- HISTORIE A DUPLIKÁTY ---
sent_tweet_ids = set()
sent_gnews_titles = set()
recent_messages_signatures = set()  # Pro detekci podobných zpráv

# --- FUNKCE PRO HODNOCENÍ ZPRÁV ---
def score_text(text: str) -> int:
    """
    Boduje text podle přítomnosti klíčových slov ze slovníku.
    Každé slovo v dané kategorii přidá určitý počet bodů.
    Vyšší váha pro high_impact kategorie.
    """
    text_lower = text.lower()
    score = 0
    for category, keywords in KEYWORDS_DICT.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                if category == "high_impact":
                    score += 3
                else:
                    score += 1
    return min(score, 10)  # max skóre 10

def create_message_signature(text: str) -> str:
    """
    Jednoduchý hash/signatura pro zjištění duplicit.
    """
    return str(hash(text.strip().lower()))

# --- ZÍSKÁNÍ DAT ---
async def fetch_tweets() -> List[Dict[str, Any]]:
    query = " OR ".join([kw for kws in KEYWORDS_DICT.values() for kw in kws])
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    params = {
        "query": f"({query}) lang:en -is:retweet",
        "tweet.fields": "id,text,created_at",
        "max_results": 30
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            logger.error(f"Chyba při získávání tweetů: {e}")
            return []

async def fetch_gnews() -> List[Dict[str, Any]]:
    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "token": GNEWS_API_KEY,
        "q": " OR ".join([kw for kws in KEYWORDS_DICT.values() for kw in kws]),
        "lang": "en",
        "max": 10
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get("articles", [])
        except Exception as e:
            logger.error(f"Chyba při získávání GNews: {e}")
            return []

# --- VÝSTUPY PRO UŽIVATELE ---
def format_raw_message(link: str, score: int, influence: str) -> str:
    return (
        f"🟡 *Zpráva zpracována (Filtr 2.st.)*\n\n"
        f"📰 [Zdroj]({link})\n"
        f"📊 Skóre relevance: {score}/10\n"
        f"📈 Možný vliv: {influence}\n"
        f"\n#BezGPT #Filtr2"
    )

def format_gpt_message(link: str, gpt_comment: str, score: int, recommendation: str, urgency: bool) -> str:
    urgency_text = "🔥 *NEVÁHEJ, NASYP TO TAM, VOLE!*" if urgency else ""
    return (
        f"🔴 *Kritická zpráva – GPT analýza*\n\n"
        f"📰 [Zdroj]({link})\n\n"
        f"🧠 GPT komentář: {gpt_comment}\n"
        f"📊 Skóre relevance: {score}/10\n"
        f"📈 Doporučení: {recommendation}\n\n"
        f"{urgency_text}\n"
        f"#FiltrGPT"
    )

# --- KOMUNIKACE S GPT ---
def create_gpt_prompt_for_message(text: str) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Jsi ostrý tržní analytik. "
                "Na základě jediné zprávy vytvoř konkrétní krátký komentář, "
                "uveď přesné skóre relevantnosti 8-10, "
                "a doporuč směr investice (komodita, long/short, časový horizont). "
                "Výstup musí být stručný, jasný, bez obecností."
            )
        },
        {
            "role": "user",
            "content": text
        }
    ]

async def analyze_with_gpt_single(text: str) -> Dict[str, Any]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "gpt-4o",
        "messages": create_gpt_prompt_for_message(text),
        "max_tokens": 300,
        "temperature": 0.7
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=body, timeout=20)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            # Očekáváme json strukturu ve formátu {"score": int, "comment": str, "recommendation": str}
            try:
                parsed = json.loads(content)
                return parsed
            except json.JSONDecodeError:
                # fallback na text
                return {"comment": content}
        except Exception as e:
            logger.error(f"Chyba GPT API: {e}")
            return {"comment": "Analýza se nepodařila načíst."}

# --- Hlavní pracovní smyčka ---
async def job_fetch_and_send(app: Application):
    tweets = await fetch_tweets()
    news = await fetch_gnews()

    # Filtrace nových a neodeslaných tweetů / zpráv
    new_tweets = [t for t in tweets if t["id"] not in sent_tweet_ids]
    new_news = [n for n in news if n["title"] not in sent_gnews_titles]

    if not new_tweets and not new_news:
        logger.info("Žádné nové zprávy.")
        return

    messages_to_send = []

    # Zpracování tweetů
    for t in new_tweets:
        text = t["text"]
        score = score_text(text)
        signature = create_message_signature(text)
        if signature in recent_messages_signatures:
            # Duplicitní zpráva, přeskočit
            continue
        recent_messages_signatures.add(signature)
        sent_tweet_ids.add(t["id"])

        link = f"https://twitter.com/i/web/status/{t['id']}"
        influence = "Trhy, komodity, měny (závisí na obsahu)"  # Zjednodušeno, může se upravit dle tématu

        # 2. stupeň: skóre 5-7 => odeslat bez GPT
        if 5 <= score <= 7:
            msg = format_raw_message(link, score, influence)
            messages_to_send.append(msg)
            continue

        # Finální filtr (8-10) => GPT analýza
        if score >= 8:
            analysis = await analyze_with_gpt_single(text)
            comment = analysis.get("comment", "Žádný komentář.")
            recommendation = analysis.get("recommendation", "Bez doporučení.")
            urgency = score == 10
            msg = format_gpt_message(link, comment, score, recommendation, urgency)
            messages_to_send.append(msg)
            continue

    # Zpracování zpráv GNews
    for n in new_news:
        title = n["title"]
        description = n.get("description", "")
        combined_text = title + " " + description
        score = score_text(combined_text)
        signature = create_message_signature(combined_text)
        if signature in recent_messages_signatures:
            continue
        recent_messages_signatures.add(signature)
        sent_gnews_titles.add(title)

        link = n.get("url", "https://gnews.io/")
        influence = "Trhy, komodity, měny (závisí na obsahu)"

        if 5 <= score <= 7:
            msg = format_raw_message(link, score, influence)
            messages_to_send.append(msg)
            continue

        if score >= 8:
            analysis = await analyze_with_gpt_single(combined_text)
            comment = analysis.get("comment", "Žádný komentář.")
            recommendation = analysis
