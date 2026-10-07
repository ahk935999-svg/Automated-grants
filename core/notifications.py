import urllib.parse
import urllib.request

def telegram_send(token, chat_id, text):
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=20) as response:
            return 200 <= response.status < 300
    except Exception:
        return False
