import logging
from pathlib import Path

from core.ai import evaluate_with_ai
from core.application_ops import build_plan
from core.config import Settings
from core.db import (
    connect,
    finish_run,
    init_db,
    insert_event,
    start_run,
    upsert_application,
    upsert_opportunity,
)
from core.eligibility import assess
from core.email_monitor import unread_messages
from core.profile import load_profile, validate_profile
from core.reporting import write_run_report
from core.scoring import deterministic_evaluation, infer_deadline, infer_funding, merge_ai_scores
from core.sources import discover_rss, load_registry
from core.verification import verify_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def run():
    settings = Settings()
    init_db(settings.db_path)
    profile = load_profile()
    errors = validate_profile(profile)
    if errors:
        raise RuntimeError("Invalid applicant profile: " + "; ".join(errors))

    registry = load_registry()
    trusted_domains = {
        item["domain"]: item["trust"]
        for item in registry
        if item.get("domain")
    }

    report = {
        "status": "RUNNING",
        "sources": [],
        "opportunities": [],
        "emails": [],
        "errors": [],
    }

    with connect(settings.db_path) as conn:
        run_id = start_run(conn)

        try:
            opportunities, source_errors = discover_rss(registry)
            report["sources"] = source_errors
            report["errors"].extend(source_errors)
            logging.info("Discovered %d unique opportunities", len(opportunities))

            priority = 0
            for op in opportunities:
                combined = f"{op.title} {op.summary}"
                if not op.funding:
                    op.funding = infer_funding(combined)
                if not op.deadline:
                    op.deadline = infer_deadline(combined)

                verification = verify_url(op.url, trusted_domains)
                eligibility = assess(op, profile)
                deterministic = deterministic_evaluation(op, profile, eligibility)

                ai_data = evaluate_with_ai(op, profile, settings.gemini_api_key)
                evaluation = merge_ai_scores(
                    deterministic,
                    ai_data,
                    eligibility.status,
                    verification.status,
                )

                opportunity_id = upsert_opportunity(
                    conn, op, verification, eligibility, evaluation
                )

                plan = build_plan(op, profile, verification, eligibility)
                application_id = upsert_application(
                    conn,
                    opportunity_id,
                    plan.state,
                    intervention=",".join(plan.gates) if plan.gates else None,
                    notes=plan.next_action,
                )

                insert_event(
                    conn,
                    "OPPORTUNITY_EVALUATED",
                    "opportunity",
                    str(opportunity_id),
                    {
                        "verification": verification.__dict__,
                        "eligibility": eligibility.__dict__,
                        "evaluation": evaluation,
                        "application_plan": plan.__dict__,
                    },
                )

                if evaluation["decision"] == "PRIORITY":
                    priority += 1

                report["opportunities"].append({
                    "id": opportunity_id,
                    "title": op.title,
                    "url": op.url,
                    "source": op.source,
                    "verification": verification.__dict__,
                    "eligibility": eligibility.__dict__,
                    "evaluation": evaluation,
                    "application_id": application_id,
                    "application_plan": plan.__dict__,
                })

            emails = unread_messages(
                settings.imap_host,
                settings.imap_port,
                settings.imap_username,
                settings.imap_password,
            )
            for item in emails:
                insert_event(conn, "EMAIL_RECEIVED", "email", item["message_id"], item)
                report["emails"].append(item)

            report_path = "data/latest_run.json"
            report["status"] = "SUCCESS"
            report["summary"] = {
                "discovered": len(opportunities),
                "priority": priority,
                "emails": len(emails),
                "source_errors": len(source_errors),
            }
            write_run_report(report_path, report)
            finish_run(
                conn, run_id, "SUCCESS", len(opportunities), priority,
                len(emails), len(source_errors), report_path
            )
            logging.info("Run complete: %s", report["summary"])
            return report

        except Exception as exc:
            report["status"] = "FAILED"
            report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
            report_path = "data/latest_run.json"
            write_run_report(report_path, report)
            finish_run(conn, run_id, "FAILED", len(report["opportunities"]), 0, len(report["emails"]), 1, report_path)
            raise

if __name__ == "__main__":
    run()
