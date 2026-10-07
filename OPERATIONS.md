# Operations Runbook

## Runtime secrets

Optional integrations:
- APPLICANT_PROFILE_JSON
- GEMINI_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- SMTP_HOST / SMTP_PORT / SMTP_USERNAME / SMTP_PASSWORD
- IMAP_HOST / IMAP_PORT / IMAP_USERNAME / IMAP_PASSWORD

The public profile file is a safe template. Real private applicant facts should live in APPLICANT_PROFILE_JSON or an ignored local profile.

The engine remains useful without these integrations: source discovery, deterministic evaluation, verification, eligibility, SQLite state, and reports continue to work.

## Run modes

Scheduled runs keep outbound Telegram notifications disabled.

Manual runs expose a dry_run input. Keep it enabled during validation. Disable it only after reviewing the destination, notification content, and credentials.

## Application state

DISCOVERED -> VERIFIED -> ELIGIBLE -> PREPARING -> READY -> SUBMITTING -> SUBMITTED -> ACKNOWLEDGED -> INTERVIEW -> DECISION -> ACCEPTED/REJECTED/WAITLISTED

Blocked high-risk actions move to INTERVENTION.

Application states never regress automatically. A later scan cannot turn an already submitted application back into an earlier state.

## Current execution boundary

GitHub Actions handles discovery, validation, scoring, state updates, email intelligence, notifications, and reports.

SMTP support is implemented as a safety-gated service but is disabled by policy until explicit operational configuration.

Persistent browser sessions, CAPTCHA/MFA handling, identity-sensitive uploads, and portal-specific form submission require dedicated adapters and a persistent execution environment.

## State persistence

CI keeps a lightweight SQLite continuity cache and a per-run report artifact. The cache is best-effort and must not be treated as a durable backup or the long-term source of truth.
