# Automated Grants / Opportunity Operations System

An autonomous, human-in-the-loop opportunity operations system for legal international study, work, research, fellowships, volunteering, exchanges, and relocation pathways.

## Architecture

Applicant Profile -> Source Discovery -> Verification -> Deterministic Eligibility -> AI Context -> Priority -> Application Plan -> Human Gate -> Submission Adapter -> Email Intelligence -> Tracking

## Production-v3

- Registry-driven source discovery with RSS adapters
- Official-source registry and destination verification
- Conservative deterministic eligibility checks
- Separate scores for eligibility, profile match, funding, urgency, competitiveness, confidence, and overall priority
- Optional Gemini context scoring that cannot override deterministic ineligibility
- SQLite state for opportunities, applications, events, emails, and run history
- Explicit application state machine and Human Gates
- Private applicant profile support through CI secrets
- Preflight validation, linting, and tests
- GitHub Actions validation and scheduled execution
- Run-report artifacts for auditability
- Dependabot for maintenance

## Decision integrity

A high overall_priority is an operations-priority score, not an admission probability.
A PRIORITY result never means submitted.
Unverified destinations, missing facts, missing documents, CAPTCHA, MFA, signatures, payments, legal declarations, and identity-sensitive uploads remain Human Gates.

## Security boundary

The public profile file is a safe template only. Put real private applicant facts in the APPLICANT_PROFILE_JSON secret or a local ignored profile file.
Never commit passports, credentials, API keys, session cookies, private documents, or recovery codes.

## Trusted-source seed

The registry currently includes official Erasmus Mundus and EURES entry points plus aggregator RSS feeds. Official domains are treated as trusted for destination verification; aggregator links remain review-required until independently verified.

## Current execution boundary

GitHub Actions is the discovery, validation, scoring, state, email-intelligence, and reporting worker.
Full browser automation requires portal-specific adapters and a persistent execution environment. Generic blind form submission is intentionally disabled.

See OPERATIONS.md for the runbook.