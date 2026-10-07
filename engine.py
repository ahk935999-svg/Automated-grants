import json
import logging

from core.ai import evaluate_with_ai
from core.config import Settings
from core.db import connect, init_db, record_event
from core.email_monitor import unread_messages
from core.notifications import telegram_send
from core.profile import load_profile, validate_profile
from core.scoring import deterministic_evaluation
from core.sources import discover_rss

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def run():
    settings = Settings()
    init_db(settings.db_path)
    profile = load_profile()
    errors = validate_profile(profile)
    if errors:
        raise RuntimeError("Invalid applicant profile: " + "; ".join(errors))
    opportunities = discover_rss()
    logging.info("Discovered %d RSS opportunities", len(opportunities))
    priority = []
    with connect(settings.db_path) as conn:
        for op in opportunities:
            deterministic = deterministic_evaluation(op, profile)
            ai_eval = evaluate_with_ai(op, profile, settings.gemini_api_key)
            evaluation = ai_eval.__dict__ if ai_eval else deterministic
            conn.execute("""
                INSERT INTO opportunities
                (title,url,source,summary,country,deadline,funding,opportunity_type,
                 eligibility_score,profile_match_score,funding_score,urgency_score,
                 competitiveness_score,confidence_score,overall_priority,decision,status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(url) DO UPDATE SET
                  title=excluded.title, summary=excluded.summary, source=excluded.source,
                  eligibility_score=excluded.eligibility_score,
                  profile_match_score=excluded.profile_match_score,
                  funding_score=excluded.funding_score, urgency_score=excluded.urgency_score,
                  competitiveness_score=excluded.competitiveness_score,
                  confidence_score=excluded.confidence_score,
                  overall_priority=excluded.overall_priority, decision=excluded.decision,
                  status="VERIFIED", updated_at=CURRENT_TIMESTAMP
            """, (op.title, op.url, op.source, op.summary, op.country, op.deadline, op.funding,
                   op.opportunity_type, evaluation["eligibility_score"],
                   evaluation["profile_match_score"], evaluation["funding_score"],
                   evaluation["urgency_score"], evaluation["competitiveness_score"],
                   evaluation["confidence_score"], evaluation["overall_priority"],
                   evaluation["decision"], "VERIFIED"))
            record_event(settings.db_path, "OPPORTUNITY_EVALUATED", "opportunity", op.url, json.dumps(evaluation))
            if evaluation["decision"] == "PRIORITY":
                priority.append((op.title, op.url, evaluation["overall_priority"]))
    if priority and not settings.dry_run:
        message = "🎯 فرص ذات أولوية\n\n" + "\n".join(f"• {t} | {s:.0f}/100\n{u}" for t,u,s in priority[:10])
        telegram_send(settings.telegram_token, settings.telegram_chat_id, message)
    emails = unread_messages(settings.imap_host, settings.imap_port, settings.imap_username, settings.imap_password)
    for item in emails:
        logging.info("Email: %s | %s | %s", item["category"], item["sender"], item["subject"])
        record_event(settings.db_path, "EMAIL_RECEIVED", "email", item["message_id"], json.dumps(item))
    logging.info("Run complete: %d priority opportunities, %d unread emails", len(priority), len(emails))

if __name__ == "__main__":
    run()