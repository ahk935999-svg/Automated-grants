import os
import sys
import csv
import json
import sqlite3
import smtplib
import ssl
import re
import time
import random
import hashlib
import logging
import urllib.request
import urllib.parse
from enum import Enum
from datetime import datetime, timezone
from email.message import EmailMessage

# ==========================================
# 1. إعداد السجلات (Logging)
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("execution.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ScholarshipEngine")

# ==========================================
# 2. ملف المتقدم (User Context Profile)
# ==========================================
USER_PROFILE = {
    "full_name": "أنور وليد عبدالرقيب الحكيمي",
    "name_en": "Anwar Al-Hakimi",
    "degree": "Bachelor of Biomedical Engineering",
    "university": "Sana'a University",
    "skills": "Clinical Engineering, Medical Equipment Maintenance, Embedded Systems, Signal Processing, Control Systems, MATLAB, AI in Healthcare",
    "interests": "Biomedical Signal Processing, Medical Image Analysis, Embedded Systems for Healthcare, Smart Medical Devices"
}

# ==========================================
# 3. حالات الحفظ وحالات دورة الحياة (FSM)
# ==========================================
class ExecutionEnv(Enum):
    PRODUCTION = "PRODUCTION"
    TEST = "TEST"
    DRY_RUN = "DRY_RUN"

class ApplicationState(Enum):
    DISCOVERED = "DISCOVERED"
    VALIDATED = "VALIDATED"
    SCORED = "SCORED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SENDING = "SENDING"
    SMTP_ACCEPTED = "SMTP_ACCEPTED"
    FAILED = "FAILED"

# ==========================================
# 4. طبقة قاعدة البيانات السحابية / المحلية
# ==========================================
class DatabaseManager:
    def __init__(self, db_path="scholarships_lifecycle.db"):
        self.db_path = db_path
        self._init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS opportunities (
                    opp_id TEXT PRIMARY KEY,
                    institution TEXT NOT NULL,
                    title TEXT NOT NULL,
                    email_normalized TEXT NOT NULL,
                    deadline_utc TIMESTAMP,
                    match_score INTEGER DEFAULT 0,
                    ai_analysis TEXT,
                    generated_subject TEXT,
                    generated_body TEXT,
                    raw_data_json TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS application_lifecycle (
                    opp_id TEXT PRIMARY KEY,
                    current_state TEXT NOT NULL,
                    env TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (opp_id) REFERENCES opportunities(opp_id) ON DELETE CASCADE
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS execution_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opp_id TEXT NOT NULL,
                    env TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    payload_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (opp_id) REFERENCES opportunities(opp_id)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS suppression_list (
                    email_normalized TEXT PRIMARY KEY,
                    reason TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def transition_state(self, conn, opp_id: str, to_state: ApplicationState, env: ExecutionEnv, payload: dict = None):
        cursor = conn.cursor()
        cursor.execute("SELECT current_state FROM application_lifecycle WHERE opp_id = ?", (opp_id,))
        row = cursor.fetchone()
        from_state = row['current_state'] if row else None

        cursor.execute('''
            INSERT INTO application_lifecycle (opp_id, current_state, env, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(opp_id) DO UPDATE SET
                current_state = excluded.current_state,
                env = excluded.env,
                updated_at = CURRENT_TIMESTAMP
        ''', (opp_id, to_state.value, env.value))

        cursor.execute('''
            INSERT INTO execution_events (opp_id, env, from_state, to_state, payload_json)
            VALUES (?, ?, ?, ?, ?)
        ''', (opp_id, env.value, from_state, to_state.value, json.dumps(payload or {}, ensure_ascii=False)))

    def is_suppressed(self, conn, email_normalized: str) -> bool:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM suppression_list WHERE email_normalized = ?", (email_normalized,))
        return bool(cursor.fetchone())

# ==========================================
# 5. محرك الذكاء الاصطناعي (Google Gemini API)
# ==========================================
class GeminiAIEngine:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"

    def analyze_and_draft(self, opportunity: dict) -> dict:
        if not self.api_key:
            logger.warning("مفتاح Gemini API غير متوفر. استخدام التوليد الافتراضي.")
            return {
                "match_score": 75,
                "reasoning": "تقييم افتراضي بدون ذكاء اصطناعي",
                "subject": f"Application: {opportunity['title']} - {USER_PROFILE['name_en']}",
                "body": f"Dear Admissions Team at {opportunity['institution']},\n\nI am writing to express my interest in {opportunity['title']}..."
            }

        prompt = f"""
        You are an expert academic advisor. Evaluate match and write a professional application email.
        
        APPLICANT PROFILE:
        Name: {USER_PROFILE['name_en']}
        Degree: {USER_PROFILE['degree']} from {USER_PROFILE['university']}
        Skills: {USER_PROFILE['skills']}
        Interests: {USER_PROFILE['interests']}
        
        OPPORTUNITY DETAILS:
        Institution: {opportunity['institution']}
        Title: {opportunity['title']}
        Description/Type: {opportunity.get('type', 'Scholarship/Opportunity')}
        
        TASK:
        1. Calculate a match_score (0 to 100) based on how relevant this opportunity is to Biomedical Engineering/Healthcare Tech.
        2. Provide a short 1-sentence reasoning in Arabic.
        3. Write a highly tailored, convincing application email in English (Subject and Body).

        Return ONLY a JSON object with this EXACT structure (no markdown fences):
        {{
            "match_score": 85,
            "reasoning": "سبب المطابقة بالعربية",
            "subject": "Email Subject",
            "body": "Email Body"
        }}
        """

        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        try:
            req = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
                
                # Cleaning Potential Markdown Formatting
                raw_text = re.sub(r'```json\s*', '', raw_text)
                raw_text = re.sub(r'```\s*$', '', raw_text).strip()
                
                return json.loads(raw_text)
        except Exception as e:
            logger.error(f"خطأ في استدعاء Gemini API: {e}")
            return {
                "match_score": 50,
                "reasoning": "حدث خطأ أثناء الاتصال بالذكاء الاصطناعي",
                "subject": f"Application for {opportunity['title']} - {USER_PROFILE['name_en']}",
                "body": f"Dear Admissions Team at {opportunity['institution']},\n\nI am applying for {opportunity['title']}..."
            }

# ==========================================
# 6. بوت التليجرام التفاعلي (Telegram Bot Gateway)
# ==========================================
class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text: str, reply_markup: dict = None) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("بيانات التليجرام غير متوفرة. تم تجاوز الإشعار.")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            req = urllib.request.Request(
                f"{self.base_url}/sendMessage",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"فشل إرسال إشعار التليجرام: {e}")
            return False

    def send_opportunity_for_review(self, opp: dict):
        text = (
            f"🎓 <b>فرصة جديدة متاحة للمراجعة</b>\n\n"
            f"🏛 <b>المؤسسة:</b> {opp['institution']}\n"
            f"📌 <b>العنوان:</b> {opp['title']}\n"
            f"🎯 <b>نسبة التوافق:</b> {opp['match_score']}%\n"
            f"💡 <b>التحليل:</b> {opp['ai_analysis']}\n"
            f"⏳ <b>الموعد النهائي:</b> {opp['deadline_utc'][:10]}\n\n"
            f"📧 <b>الموضوع:</b> {opp['generated_subject']}\n\n"
            f"📝 <b>المعاينة:</b>\n<i>{opp['generated_body'][:250]}...</i>"
        )
        
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ موافقة وإرسال", "callback_data": f"approve_{opp['opp_id']}"},
                    {"text": "❌ استبعاد", "callback_data": f"reject_{opp['opp_id']}"}
                ]
            ]
        }
        self.send_message(text, reply_markup)

    def process_pending_callbacks(self, db: DatabaseManager, env: ExecutionEnv) -> list:
        """فحص القرارات القادمة من أزرار التليجرام"""
        if not self.token:
            return []

        approved_opp_ids = []
        try:
            req = urllib.request.Request(f"{self.base_url}/getUpdates")
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                
                with db.get_connection() as conn:
                    for update in res.get("result", []):
                        if "callback_query" in update:
                            cb = update["callback_query"]
                            data = cb.get("data", "")
                            cb_id = cb.get("id")

                            if data.startswith("approve_"):
                                opp_id = data.replace("approve_", "")
                                db.transition_state(conn, opp_id, ApplicationState.APPROVED, env, {"by": "Telegram_User"})
                                approved_opp_ids.append(opp_id)
                                self._answer_callback(cb_id, "تمت الموافقة! سيتم الإرسال الآن.")
                                
                            elif data.startswith("reject_"):
                                opp_id = data.replace("reject_", "")
                                db.transition_state(conn, opp_id, ApplicationState.REJECTED, env, {"by": "Telegram_User"})
                                self._answer_callback(cb_id, "تم استبعاد الفرصة.")
        except Exception as e:
            logger.error(f"خطأ في معالجة إجابات التليجرام: {e}")
            
        return approved_opp_ids

    def _answer_callback(self, callback_query_id: str, text: str):
        payload = {"callback_query_id": callback_query_id, "text": text}
        try:
            req = urllib.request.Request(
                f"{self.base_url}/answerCallbackQuery",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass

# ==========================================
# 7. محرك إرسال البريد الموثوق (SMTP Engine)
# ==========================================
class SMTPEngine:
    def __init__(self, config: dict, env: ExecutionEnv):
        self.config = config
        self.env = env

    def send_single(self, draft: dict, db: DatabaseManager) -> bool:
        if self.env == ExecutionEnv.DRY_RUN:
            logger.info(f"[DRY RUN] محاكاة إرسال إلى: {draft['email_normalized']}")
            with db.get_connection() as conn:
                db.transition_state(conn, draft["opp_id"], ApplicationState.SMTP_ACCEPTED, self.env, {"simulated": True})
            return True

        context = ssl.create_default_context()
        target_email = self.config["TEST_RECIPIENT"] if self.env == ExecutionEnv.TEST else draft["email_normalized"]

        msg = EmailMessage()
        subject_prefix = "[TEST] " if self.env == ExecutionEnv.TEST else ""
        msg["Subject"] = f"{subject_prefix}{draft['generated_subject']}"
        msg["From"] = f"{USER_PROFILE['name_en']} <{self.config['SENDER_EMAIL']}>"
        msg["To"] = target_email
        msg.set_content(draft["generated_body"])

        # دعم إرفاق السيرة الذاتية PDF إذا كانت موجودة
        cv_path = self.config.get("CV_PATH", "Anwar_AlHakimi_CV.pdf")
        if os.path.exists(cv_path):
            with open(cv_path, "rb") as f:
                msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(cv_path))

        try:
            with db.get_connection() as conn:
                db.transition_state(conn, draft["opp_id"], ApplicationState.SENDING, self.env, {"target": target_email})

            with smtplib.SMTP(self.config["SMTP_SERVER"], self.config["SMTP_PORT"], timeout=20) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self.config["SENDER_EMAIL"], self.config["APP_PASSWORD"])
                server.send_message(msg)

            with db.get_connection() as conn:
                db.transition_state(conn, draft["opp_id"], ApplicationState.SMTP_ACCEPTED, self.env, {"target": target_email})
            logger.info(f"[SUCCESS] تم الإرسال بنجاح للفرصة: {draft['opp_id']} -> {target_email}")
            return True

        except Exception as e:
            logger.error(f"[FAILURE] فشل الإرسال للفرصة {draft['opp_id']}: {e}")
            with db.get_connection() as conn:
                db.transition_state(conn, draft["opp_id"], ApplicationState.FAILED, self.env, {"error": str(e)})
            return False

# ==========================================
# 8. متحكم دورة الحياة والمهمة (Lifecycle Controller)
# ==========================================
class AutonomousController:
    def __init__(self, config: dict):
        self.config = config
        self.env = ExecutionEnv(config.get("ENV", "DRY_RUN"))
        self.db = DatabaseManager()
        self.ai = GeminiAIEngine(config.get("GEMINI_API_KEY", ""))
        self.telegram = TelegramNotifier(config.get("TELEGRAM_BOT_TOKEN", ""), config.get("TELEGRAM_CHAT_ID", ""))
        self.smtp = SMTPEngine(config, self.env)

    def process_csv_and_sync(self, csv_filepath: str):
        if not os.path.exists(csv_filepath):
            logger.error(f"ملف المصدر غير موجود: {csv_filepath}")
            return

        logger.info("--- بدء معالجة ومزامنة البيانات ---")
        
        with open(csv_filepath, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            with self.db.get_connection() as conn:
                for row in reader:
                    clean_row = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items()}
                    opp_id = clean_row.get("id")
                    email = clean_row.get("email", "").lower().strip()
                    deadline_str = clean_row.get("deadline")

                    if not opp_id or not email or self.db.is_suppressed(conn, email):
                        continue

                    try:
                        deadline_dt = datetime.strptime(deadline_str, "%Y-%m-%d").replace(
                            hour=23, minute=59, second=59, tzinfo=timezone.utc
                        )
                        if deadline_dt < datetime.now(timezone.utc):
                            continue # تجاوز المنتهية
                    except ValueError:
                        continue

                    # فحص إذا كانت موجودة سابقاً
                    cursor = conn.cursor()
                    cursor.execute("SELECT current_state FROM application_lifecycle WHERE opp_id = ?", (opp_id,))
                    state_row = cursor.fetchone()

                    if state_row:
                        continue # تم استكشافها سابقاً

                    # تحليل الذكاء الاصطناعي والتوليد
                    ai_result = self.ai.analyze_and_draft(clean_row)
                    source_hash = hashlib.sha256(json.dumps(clean_row, sort_keys=True).encode()).hexdigest()

                    conn.execute('''
                        INSERT INTO opportunities 
                        (opp_id, institution, title, email_normalized, deadline_utc, match_score, ai_analysis, generated_subject, generated_body, raw_data_json, source_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        opp_id, clean_row.get("institution", ""), clean_row.get("title", ""),
                        email, deadline_dt.isoformat(), ai_result["match_score"],
                        ai_result["reasoning"], ai_result["subject"], ai_result["body"],
                        json.dumps(clean_row, ensure_ascii=False), source_hash
                    ))

                    self.db.transition_state(conn, opp_id, ApplicationState.AWAITING_APPROVAL, self.env)
                    
                    # إرسال إشعار تليجرام للمراجعة
                    opp_record = {
                        "opp_id": opp_id,
                        "institution": clean_row.get("institution", ""),
                        "title": clean_row.get("title", ""),
                        "match_score": ai_result["match_score"],
                        "ai_analysis": ai_result["reasoning"],
                        "deadline_utc": deadline_dt.isoformat(),
                        "generated_subject": ai_result["subject"],
                        "generated_body": ai_result["body"]
                    }
                    self.telegram.send_opportunity_for_review(opp_record)

    def execute_approved_applications(self):
        """فحص الموافقات وإرسال البريد فوراً"""
        approved_ids = self.telegram.process_pending_callbacks(self.db, self.env)
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT o.* FROM opportunities o
                JOIN application_lifecycle l ON o.opp_id = l.opp_id
                WHERE l.current_state = ?
            ''', (ApplicationState.APPROVED.value,))
            
            approved_drafts = [dict(row) for row in cursor.fetchall()]

        for draft in approved_drafts:
            success = self.smtp.send_single(draft, self.db)
            if success:
                self.telegram.send_message(f"✅ <b>تم التقديم بنجاح!</b>\nالفرصة: {draft['title']}\nالجهة: {draft['institution']}")

# ==========================================
# 9. نقطة التشغيل الرئيسية (Main)
# ==========================================
if __name__ == "__main__":
    CONFIG = {
        "ENV": os.getenv("ENGINE_ENV", "PRODUCTION"), # DRY_RUN | TEST | PRODUCTION
        "SENDER_EMAIL": os.getenv("SENDER_EMAIL", ""),
        "APP_PASSWORD": os.getenv("APP_PASSWORD", ""),
        "SMTP_SERVER": "smtp.gmail.com",
        "SMTP_PORT": 587,
        "TEST_RECIPIENT": os.getenv("TEST_RECIPIENT", ""),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
        "CV_PATH": "Anwar_AlHakimi_CV.pdf"
    }

    controller = AutonomousController(CONFIG)
    
    # 1. المزامنة والتحليل من المصدر
    controller.process_csv_and_sync("opportunities_sample.csv")
    
    # 2. تنفيذ التقديمات المعالجة والموافق عليها
    controller.execute_approved_applications()
