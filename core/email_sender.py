import smtplib
from email.message import EmailMessage

class EmailSendError(RuntimeError):
    pass

def send_email(host,port,username,password,to_address,subject,body,dry_run=True):
    if dry_run:
        return {"sent":False,"mode":"DRY_RUN"}
    if not all((host,username,password,to_address,subject)):
        raise EmailSendError("SMTP configuration or recipient is incomplete")

    message=EmailMessage()
    message["From"]=username
    message["To"]=to_address
    message["Subject"]=subject
    message.set_content(body)

    try:
        with smtplib.SMTP(host,port,timeout=30) as server:
            server.starttls()
            server.login(username,password)
            server.send_message(message)
    except (OSError,smtplib.SMTPException) as exc:
        raise EmailSendError(str(exc)) from exc

    return {"sent":True,"mode":"SMTP"}
