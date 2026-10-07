from core.email_monitor import classify_subject

def test_email_categories():
    assert classify_subject('Interview invitation')=='interview'
    assert classify_subject('Congratulations, you are admitted')=='acceptance'
    assert classify_subject('Application unsuccessful')=='rejection'
    assert classify_subject('Additional documents required')=='document_request'
    assert classify_subject('Application received')=='general'