# Security Policy

Knudg handles agent experience data, so privacy and consent boundaries are core
security concerns.

## Supported Versions

This repository is pre-1.0. Security fixes apply to the `main` branch until
versioned releases are published.

## Reporting a Vulnerability

Please report vulnerabilities through GitHub private vulnerability reporting.
Do not open public issues, pull requests, or discussions with exploit details,
secrets, tokens, raw logs, personal data, or sensitive reproduction material.

If private vulnerability reporting is unavailable on a fork, ask the fork owner
to enable a private reporting channel before sharing details.

## Sensitive Data Rules

Do not include the following in issues, pull requests, fixtures, or examples:

- API keys, tokens, passwords, private keys, or credentials.
- Raw chat logs, raw transcripts, or raw model/tool output.
- Local database dumps or browser/session state.
- Private repository names, hostnames, usernames, SSH details, or absolute local
  paths.
- Unredacted personal, career, company, place, or service experience.

Use synthetic fixtures. When real material is unavoidable for a private report,
redact aggressively and share only through the agreed private channel.

## Design Expectations

- Default visibility is private.
- Search authorization happens before ranking/reranking.
- Retrieved cards are untrusted evidence, not instructions.
- Publication requires explicit approval for the exact redacted artifact.
- Revocation and purge paths must remain testable.
- Hosted deployments must keep secrets outside the repository.
