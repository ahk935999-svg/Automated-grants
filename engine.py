import hashlib
import logging
from email.utils import parseaddr

from core.action_queue import build_action_queue
from core.ai import evaluate_with_ai
from core.application_ops import build_plan
from core.config import Settings
from core.detail_fetch import fetch_public_page
from core.db import (
    connect,finish_run,init_db,insert_event,start_run,
    upsert_application,upsert_opportunity,
)
from core.eligibility import assess
from core.email_monitor import unread_messages
from core.notifications import telegram_send
from core.policy import load_policy
from core.profile import load_profile,validate_profile
from core.reporting import write_run_report
from core.scoring import (
    deterministic_evaluation,infer_deadline,infer_funding,merge_ai_scores,
)
from core.sources import discover_sources,load_registry
from core.verification import verify_url

logger=logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def run():
    settings=Settings()
    init_db(settings.db_path)
    profile=load_profile(settings.profile_path,settings.applicant_profile_json)
    errors=validate_profile(profile)
    if errors:
        raise RuntimeError("Invalid applicant profile: "+"; ".join(errors))

    policy=load_policy()
    registry=load_registry()
    trusted_domains={item["domain"]:item["trust"] for item in registry if item.get("domain")}
    report={"status":"RUNNING","sources":[],"opportunities":[],"emails":[],"errors":[],"notification":None}

    with connect(settings.db_path) as conn:
        run_id=start_run(conn)
        try:
            opportunities,source_errors=discover_sources(registry)
            report["sources"]=source_errors
            report["errors"].extend(source_errors)
            logger.info("Discovered %d unique opportunities",len(opportunities))
            priority=0
            intervention=0
            priority_items=[]

            detail_budget=20
            for op in opportunities:
                verification=verify_url(op.url,trusted_domains)
                if verification.status=="VERIFIED" and verification.trust=="official" and detail_budget>0:
                    try:
                        detail=fetch_public_page(op.url, allowed_domains=trusted_domains)
                    except Exception as exc:  # noqa: BLE001
                        detail=None
                        report["errors"].append({"source":op.source,"url":op.url,"error":str(exc)})
                    if detail:
                        op.raw["detail_text"]=detail
                        op.summary=(f"{op.summary} {detail[:6000]}").strip()
                        detail_budget-=1
                combined=f"{op.title} {op.summary}"
                op.funding=infer_funding(combined) or op.funding
                op.deadline=infer_deadline(combined) or op.deadline
                eligibility=assess(op,profile)
                deterministic=deterministic_evaluation(
                    op,profile,eligibility,policy["priority_threshold"]
                )
                ai_data=evaluate_with_ai(op,profile,settings.gemini_api_key)
                evaluation=merge_ai_scores(
                    deterministic,ai_data,eligibility.status,verification.status,
                    policy["priority_threshold"]
                )
                opportunity_id=upsert_opportunity(conn,op,verification,eligibility,evaluation)
                plan=build_plan(op,profile,verification,eligibility)

                if plan.state=="READY" and (
                    evaluation["confidence_score"]<policy["minimum_confidence_for_auto_draft"]
                    or not policy["auto"].get("draft_application",False)
                ):
                    plan=plan.__class__(
                        "INTERVENTION",plan.missing_documents,["unknown_fact"],
                        "Confidence/policy gate prevents automatic draft"
                    )

                application_id,actual_state,transitioned=upsert_application(
                    conn,opportunity_id,plan.state,
                    intervention=",".join(plan.gates) if plan.gates else None,
                    notes=plan.next_action
                )

                if not transitioned:
                    insert_event(
                        conn,"APPLICATION_STATE_PRESERVED","application",str(application_id),
                        {"requested":plan.state,"preserved":actual_state}
                    )

                insert_event(
                    conn,"OPPORTUNITY_EVALUATED","opportunity",str(opportunity_id),
                    {
                        "verification":verification.__dict__,
                        "eligibility":eligibility.__dict__,
                        "evaluation":evaluation,
                        "application_plan":plan.__dict__,
                        "application_state":actual_state,
                    }
                )

                is_priority=evaluation["decision"]=="PRIORITY"
                priority+=is_priority
                intervention+=actual_state=="INTERVENTION"
                if is_priority:
                    priority_items.append((op.title,op.url,evaluation["overall_priority"],actual_state))

                report["opportunities"].append({
                    "id":opportunity_id,"title":op.title,"url":op.url,"source":op.source,
                    "verification":verification.__dict__,"eligibility":eligibility.__dict__,
                    "evaluation":evaluation,"application_id":application_id,
                    "application_state":actual_state,
                    "application_transitioned":transitioned,
                    "application_plan":plan.__dict__,
                })

            emails=unread_messages(
                settings.imap_host,settings.imap_port,
                settings.imap_username,settings.imap_password
            )
            for item in emails:
                _,sender_address=parseaddr(item.get("sender",""))
                sender_domain=sender_address.rsplit("@",1)[-1].lower() if "@" in sender_address else ""
                safe_item={
                    "message_id_hash":hashlib.sha256(item.get("message_id","").encode()).hexdigest(),
                    "sender_domain":sender_domain,
                    "category":item.get("category","general"),
                }
                insert_event(conn,"EMAIL_RECEIVED","email",safe_item["message_id_hash"],safe_item)
                report["emails"].append(safe_item)

            if priority_items and policy["auto"].get("notify_telegram",True):
                if settings.dry_run:
                    report["notification"]={"telegram":"DRY_RUN"}
                else:
                    message="🎯 Opportunity priority\n\n"+"\n".join(
                        f"• {title} | {score:.0f}/100 | {state}\n{url}"
                        for title,url,score,state in priority_items[:10]
                    )
                    sent=telegram_send(settings.telegram_token,settings.telegram_chat_id,message)
                    report["notification"]={"telegram":"SENT" if sent else "FAILED"}
            elif priority_items:
                report["notification"]={"telegram":"DISABLED_BY_POLICY"}

            report_path="data/latest_run.json"
            report["status"]="SUCCESS"
            report["action_queue"]=build_action_queue(report["opportunities"])
            report["summary"]={
                "discovered":len(opportunities),
                "priority":int(priority),
                "intervention":int(intervention),
                "action_queue":len(report["action_queue"]),
                "emails":len(emails),
                "source_errors":len(source_errors),
            }
            write_run_report(report_path,report)
            finish_run(
                conn,run_id,"SUCCESS",len(opportunities),int(priority),
                len(emails),len(source_errors),report_path
            )
            logger.info("Run complete: %s",report["summary"])
            return report
        except Exception as exc:
            report["status"]="FAILED"
            report["errors"].append({"type":type(exc).__name__,"message":str(exc)})
            report_path="data/latest_run.json"
            write_run_report(report_path,report)
            finish_run(
                conn,run_id,"FAILED",len(report["opportunities"]),0,
                len(report["emails"]),1,report_path
            )
            raise

if __name__=="__main__":
    run()
