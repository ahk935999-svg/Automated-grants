import email
import imaplib
from email.header import decode_header

CATEGORIES = {
    "interview": ("interview", "interview invitation"),
    "acceptance": ("congratulations", "accepted", "admitted", "offer"),
    "rejection": ("regret", "rejected", "unsuccessful", "not selected"),
    "document_request": ("additional documents", "provide documents", "passport", "transcript"),
}

def classify_subject(subject):
    subject = subject.lower()
    for category, terms in CATEGORIES.items():
        if any(term in subject for term in terms):
            return category
    return "general"

def unread_messages(host, port, username, password, limit=20):
    if not all((host, username, password)):
        return []
    mail = imaplib.IMAP4_SSL(host, port)
    mail.login(username, password)
    mail.select("INBOX")
    _, data = mail.search(None, "UNSEEN")
    ids = data[0].split()[-limit:]
    out = []
    for msg_id in ids:
        _, raw = mail.fetch(msg_id, "(RFC822)")
        msg = email.message_from_bytes(raw[0][1])
        subject = decode_header(msg.get("Subject", ""))[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode(errors="replace")
        out.append({
            "message_id": msg.get("Message-ID", ""),
            "sender": msg.get("From", ""),
            "subject": subject,
            "category": classify_subject(subject)
        })
    mail.logout()
    return out
