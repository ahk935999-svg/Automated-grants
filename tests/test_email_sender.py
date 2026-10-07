from core.email_sender import send_email

def test_email_sender_dry_run_never_opens_smtp():
    result=send_email(
        "smtp.example.org",587,"user@example.org","not-used",
        "recipient@example.org","Test","Body",dry_run=True
    )
    assert result=={"sent":False,"mode":"DRY_RUN"}
