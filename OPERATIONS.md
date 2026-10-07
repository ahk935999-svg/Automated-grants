# Operations Runbook

## Runtime secrets

Optional integrations:
- GEMINI_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- IMAP_HOST
- IMAP_PORT
- IMAP_USERNAME
- IMAP_PASSWORD

The engine remains useful without these integrations: source discovery, deterministic evaluation, verification, eligibility, SQLite state, and reports continue to work.

## Run modes

Scheduled runs keep outbound Telegram notifications disabled.

Manual runs expose a dry_run input. Keep it enabled during validation. Disable it only after reviewing the destination, notification content, and secrets.

## Application state

DISCOVERED -> VERIFIED -> ELIGIBLE -> PREPARING -> READY -> SUBMITTING -> SUBMITTED -> ACKNOWLEDGED -> INTERVIEW -> DECISION -> ACCEPTED/REJECTED/WAITLISTED

Blocked high-risk actions move to INTERVENTION.

## Current execution boundary

GitHub Actions handles discovery, validation, scoring, state updates, email intelligence, and reports.

Persistent browser sessions, CAPTCHA/MFA handling, identity-sensitive uploads, and portal-specific form submission require dedicated adapters and a persistent execution environment.
