# Automated Grants / Opportunity Operations System

This repository is the foundation for an autonomous, human-in-the-loop opportunity and relocation operations system.

## Mission

Continuously discover legal opportunities relevant to the applicant: fully funded study, scholarships, research, fellowships, work, volunteering, exchanges, and lawful immigration pathways.

The system must never invent applicant facts, fabricate documents, forge evidence, or make false legal declarations.

## Architecture

Applicant Profile -> Discovery -> Verification -> Deterministic Eligibility -> AI Evaluation -> Priority -> Application Preparation -> Human Gate -> Submission -> Email Intelligence -> Tracking

## production-v3

- Structured applicant profile
- RSS discovery
- Deterministic scoring before optional AI
- Separate eligibility, profile match, funding, urgency, competitiveness, confidence, and overall priority metrics
- SQLite opportunity, application, event, and email state
- Email classification for common application outcomes
- Telegram priority notifications
- GitHub Actions daily execution
- Automated tests
- Dry-run default for outbound Telegram behavior

## Human gates

The system pauses before legal declarations, CAPTCHA/MFA, signatures, payments, identity-sensitive uploads to unverified destinations, or any answer requiring a missing applicant fact.

## Security

Never commit passports, credentials, API keys, email passwords, or private keys. Use GitHub Secrets or secure external storage.

## Next modules

1. Official-source registry and verification adapters
2. Deterministic eligibility rules per opportunity
3. Application state machine and artifact vault
4. Playwright adapters for supported application portals
5. SMTP sending and reply-to-application matching
6. Human intervention queue
7. Source health and deadline monitoring
8. Dashboard and operational metrics
