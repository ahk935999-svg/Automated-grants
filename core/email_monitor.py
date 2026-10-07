import email
import imaplib
from email.header import decode_header

CATEGORIES = {
    "interview": ("interview", "interview invitation", "interview request"),
    "acceptance": ("congratulations", "accepted", "admitted", "offer"),
    "rejection": ("regret", "rejected", "unsuccessful", "not selected", "application denied"),
    "document_request": (
        "additional documents","provide documents","passport","transcript",
        "upload document","missing document",
    ),
}

def classify_subject(subject):
    lowered=subject.lower()
    for category, terms in CATEGORIES.items():
        if any(term in lowered for term in terms):
            return category
    return "general"

def _decode_subject(value):
    parts=[]
    for part,encoding in decode_header(value or ""):
        if isinstance(part,bytes):
            parts.append(part.decode(encoding or "utf-8",errors="replace"))
        else:
            parts.append(part)
    return "".join(parts).strip()

def unread_messages(host,port,username,password,limit=20):
    if not all((host,username,password)):
        return []
    mail=None
    try:
        mail=imaplib.IMAP4_SSL(host,port)
        mail.login(username,password)
        mail.select("INBOX",readonly=True)
        _,data=mail.search(None,"UNSEEN")
        ids=data[0].split()[-limit:]
        out=[]
        for msg_id in ids:
            _,raw=mail.fetch(msg_id,"(BODY.PEEK[])")
            if not raw or not raw[0]:
                continue
            payload=raw[0][1] if isinstance(raw[0],tuple) else b""
            msg=email.message_from_bytes(payload)
            subject=_decode_subject(msg.get("Subject",""))
            out.append({
                "message_id":msg.get("Message-ID","").strip(),
                "sender":msg.get("From","").strip(),
                "subject":subject,
                "category":classify_subject(subject),
            })
        return out
    finally:
        if mail is not None:
            try:
                mail.logout()
            except (OSError,imaplib.IMAP4.error):
                pass
