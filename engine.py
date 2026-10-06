import os
import re
import json
import sqlite3
import smtplib
import logging
import requests
import telebot
import google.generativeai as genai
import xml.etree.ElementTree as ET
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# ==============================================================================
# 1. Logging & Global Configuration
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
TEST_RECIPIENT = os.getenv("TEST_RECIPIENT")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ==============================================================================
# 2. Database Manager (Atomic SQLite with Indexing & WAL Mode)
# ==============================================================================
class DatabaseManager:
    def __init__(self, db_path: str = "opportunities.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS opportunities (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    link TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    target_email TEXT,
                    published_date TEXT,
                    status TEXT NOT NULL,
                    score INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON opportunities(status);')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_score ON opportunities(score);')
            conn.commit()

    def exists(self, opp_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM opportunities WHERE id = ?", (opp_id,))
            return cursor.fetchone() is not None

    def save_opportunity(self, opp_data: dict, status: str, score: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO opportunities (id, title, link, source_type, target_email, published_date, status, score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                opp_data['id'], opp_data['title'], opp_data['link'],
                opp_data['type'], opp_data['target_email'],
                opp_data['date'], status, score
            ))
            conn.commit()

# ==============================================================================
# 3. Email Extraction Engine (Strict Regex Filtering)
# ==============================================================================
class EmailExtractor:
    PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    IGNORED_DOMAINS = {
        'example.com', 'schema.org', 'w3.org', 'github.com', 
        'sentry.io', 'google.com', 'facebook.com', 'twitter.com'
    }
    IGNORED_PREFIXES = (
        'noreply', 'no-reply', 'donotreply', 'privacy@', 
        'terms@', 'support@', 'info@github', 'abuse@'
    )

    @classmethod
    def extract_valid_email(cls, text: str, fallback: Optional[str] = None) -> str:
        matches = re.findall(cls.PATTERN, text)
        for email in matches:
            email_lower = email.lower()
            domain = email_lower.split('@')[-1]
            if domain in cls.IGNORED_DOMAINS:
                continue
            if any(email_lower.startswith(prefix) for prefix in cls.IGNORED_PREFIXES):
                continue
            return email
        return fallback or TEST_RECIPIENT

# ==============================================================================
# 4. AI Analyzer Engine (Gemini 1.5 Flash - Structured JSON)
# ==============================================================================
class GeminiAnalyzer:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def analyze_opportunity(self, opp: dict) -> Tuple[int, str, str, str]:
        system_prompt = """
        You are an elite relocation strategy advisor for Anwar Waleed Al-Hakimi.
        
        Candidate Profile:
        - Name: Anwar Waleed Al-Hakimi (Location: Yemen - High priority legal relocation).
        - Field: Biomedical Engineering student (Embedded Systems, Microcontrollers, MATLAB, AI/Automation).
        - Goal: Any legal international path (Master's/Bachelor's scholarship, ESC/UN Volunteering, Engineering/IT Internship, Vocational Training, or Humanitarian Path).

        STRICT RULES FOR EMAIL DRAFTING:
        - DO NOT mention attached files or CVs.
        - State clearly in the text that a detailed CV/portfolio is available upon request if there is mutual interest.
        - The email must be an initial exploratory inquiry/application expressing strong motivation and key technical strengths.

        Respond ONLY in a strict JSON format matching this schema:
        {
            "score": <INTEGER 0-100>,
            "reason": "<SHORT_ARABIC_EXPLANATION>",
            "subject": "<PROFESSIONAL_ENGLISH_SUBJECT_LINE>",
            "cover_letter": "<PROFESSIONAL_ENGLISH_EMAIL_BODY>"
        }
        """

        prompt = f"Source: {opp['type']}\nTitle: {opp['title']}\nDescription: {opp['description']}\nContact: {opp['target_email']}"

        try:
            response = self.model.generate_content(
                f"{system_prompt}\n\nInput Data:\n{prompt}",
                generation_config={"response_mime_type": "application/json"}
            )
            data = json.loads(response.text)
            return (
                int(data.get("score", 0)),
                data.get("reason", "لا توجد تفاصيل"),
                data.get("subject", f"Inquiry: {opp['title']}"),
                data.get("cover_letter", "")
            )
        except Exception as e:
            logging.error(f"Gemini Analysis Failed: {e}")
            return 0, "خطأ في تحليل الذكاء الاصطناعي", "", ""

# ==============================================================================
# 5. Delivery Services (SMTP & Telegram)
# ==============================================================================
class NotificationService:
    def __init__(self):
        self.bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None

    def send_telegram(self, message: str):
        if self.bot and TELEGRAM_CHAT_ID:
            try:
                self.bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='HTML')
            except Exception as e:
                logging.error(f"Failed to send Telegram notification: {e}")

    @staticmethod
    def send_email(recipient: str, subject: str, body: str) -> bool:
        if not SENDER_EMAIL or not APP_PASSWORD:
            logging.warning("SMTP credentials missing. Skipping email delivery.")
            return False

        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        try:
            with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
                server.starttls()
                server.login(SENDER_EMAIL, APP_PASSWORD)
                server.send_message(msg)
            logging.info(f"Email successfully sent to: {recipient}")
            return True
        except Exception as e:
            logging.error(f"SMTP Delivery Failure to {recipient}: {e}")
            return False

# ==============================================================================
# 6. Core Orchestrator Engine
# ==============================================================================
class RelocationEngine:
    SOURCES = [
        {"url": "https://reliefweb.int/jobs/rss.xml", "type": "UN / NGO International Jobs & Volunteering"},
        {"url": "https://www.scholarshipsads.com/category/country/europe/feed/", "type": "European Scholarships & Grants"},
        {"url": "https://www.opportunitydesk.org/feed/", "type": "Global Fellowships & Grants"},
        {"url": "https://remotive.com/remote-jobs/feed", "type": "International Tech & Engineering Jobs"}
    ]

    def __init__(self):
        self.db = DatabaseManager()
        self.analyzer = GeminiAnalyzer()
        self.notifier = NotificationService()

    def fetch_feed(self, source: dict) -> List[dict]:
        items = []
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        try:
            response = requests.get(source['url'], headers=headers, timeout=15)
            root = ET.fromstring(response.content)
            for item in root.findall('.//item')[:5]:
                title = item.find('title').text if item.find('title') is not None else "Untitled"
                link = item.find('link').text if item.find('link') is not None else ""
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else str(datetime.now())
                desc = item.find('description').text if item.find('description') is not None else ""
                
                clean_desc = re.sub(r'<[^>]+>', ' ', desc)
                opp_id = str(hash(title + link))
                target_email = EmailExtractor.extract_valid_email(clean_desc)

                items.append({
                    "id": opp_id,
                    "title": title.strip(),
                    "link": link.strip(),
                    "type": source['type'],
                    "date": pub_date,
                    "description": clean_desc[:2500],
                    "target_email": target_email
                })
        except Exception as e:
            logging.error(f"Error fetching feed {source['url']}: {e}")
        return items

    def run(self):
        logging.info("Starting Autonomous Relocation Engine v4.0...")
        
        for source in self.SOURCES:
            logging.info(f"Processing source: {source['type']}")
            opportunities = self.fetch_feed(source)
            
            for opp in opportunities:
                if self.db.exists(opp['id']):
                    continue

                score, reason, subject, cover_letter = self.analyzer.analyze_opportunity(opp)
                
                # Threshold for action
                if score >= 65:
                    email_sent = NotificationService.send_email(opp['target_email'], subject, cover_letter)
                    status = "APPLIED_VIA_EMAIL" if email_sent else "EMAIL_FAILED"

                    msg = (
                        f"🎯 <b>فرصة استكشافية عالية التقييم ({score}%)</b>\n\n"
                        f"<b>المصدر:</b> {opp['type']}\n"
                        f"<b>العنوان:</b> {opp['title']}\n"
                        f"<b>الجهة:</b> <code>{opp['target_email']}</code>\n\n"
                        f"<b>تحليل الاستراتيجية:</b>\n{reason}\n\n"
                        f"✉️ <i>تنزيل السيرة الذاتية مُعطل - تم إرسال خطاب استفسار مبدئي وتوفير السيرة عند الطلب.</i>\n\n"
                        f"🔗 <a href='{opp['link']}'>رابط تفاصيل الفرصة</a>"
                    )
                    self.notifier.send_telegram(msg)
                else:
                    status = "DISQUALIFIED_BY_AI"

                self.db.save_opportunity(opp, status, score)

if __name__ == "__main__":
    engine = RelocationEngine()
    engine.run()
