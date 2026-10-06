import os
import sqlite3
import logging
import requests
import feedparser
import telebot
import google.generativeai as genai

# Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Environment Variables
RUNTIME_ENV = os.getenv("RUNTIME_ENV", "DEVELOPMENT")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
TEST_RECIPIENT = os.getenv("TEST_RECIPIENT")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Configure Gemini AI
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Database Setup
DB_PATH = "opportunities.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT UNIQUE,
            summary TEXT,
            score INTEGER,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def evaluate_with_gemini(title, summary):
    if not GEMINI_API_KEY:
        logging.warning("No Gemini API key provided. Skipping AI evaluation.")
        return 70  # Default fallback score

    prompt = f"""
    Evaluate the following opportunity for a student.
    Title: {title}
    Summary: {summary}
    
    Give a compatibility score from 0 to 100 based on general relevance and feasibility.
    Respond with ONLY an integer number between 0 and 100.
    """
    
    # Updated Gemini Model name to latest standard
    for model_name in ['gemini-2.5-flash', 'gemini-1.5-flash-latest', 'gemini-pro']:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            score_text = response.text.strip()
            score = int(''.join(filter(str.isdigit, score_text)))
            return score
        except Exception as e:
            logging.error(f"Gemini model {model_name} failed: {e}")
            continue

    return 50  # Fallback if AI call completely fails

def send_telegram_notification(title, link, score):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram credentials missing.")
        return

    try:
        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        message = f"🎯 *فرصة جديدة متوافرة!*\n\n📌 *العنوان:* {title}\n⭐ *التقييم:* {score}%\n🔗 [رابط التفاصيل]({link})"
        bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode="Markdown")
        logging.info("Telegram notification sent successfully!")
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")

def run_engine():
    init_db()
    logging.info("Starting Autonomous Relocation Engine...")

    rss_feeds = [
        "https://opportunitydesk.org/feed/",
        "https://www.scholarshipsads.com/feed/"
    ]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for feed_url in rss_feeds:
        logging.info(f"Processing source: {feed_url}")
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:5]:  # Process latest 5 entries
            title = entry.get('title', 'No Title')
            link = entry.get('link', '')
            summary = entry.get('summary', '')

            # Check if already processed
            cursor.execute("SELECT id FROM opportunities WHERE link = ?", (link,))
            if cursor.fetchone():
                continue

            score = evaluate_with_gemini(title, summary)
            status = "QUALIFIED" if score >= 60 else "DISQUALIFIED"

            cursor.execute('''
                INSERT INTO opportunities (title, link, summary, score, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (title, link, summary, score, status))
            conn.commit()

            logging.info(f"Item: {title} | Score: {score} | Status: {status}")

            if status == "QUALIFIED":
                send_telegram_notification(title, link, score)

    conn.close()

if __name__ == "__main__":
    run_engine()
