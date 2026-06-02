# Governance

Knudg is currently maintained by the project maintainers using a lightweight
maintainer-led model.

## Maintainer Responsibilities

- Keep the self-hosted backend usable without any hosted network, paid plan, or
  private operator dependency.
- Preserve privacy, consent, revocation, and domain-separation guarantees.
- Review schema, migration, and security-sensitive changes carefully.
- Avoid accepting fixtures or examples that contain raw private material.

## Decision Process

Small implementation changes may be accepted through normal pull request
review. Changes that affect privacy, consent, tenant isolation, revocation,
publication, retrieval trust boundaries, public-interest sustainability, or cost
controls should update the relevant architecture docs, schemas, tests, and
decision records in the same change.

## Project Direction

Knudg is open-source and self-hostable. The project direction is public-benefit
infrastructure, not a B2B monetization track. Hosted services, mirrors, or
shared indexes may exist only as optional deployments of the same open
protocols and server code. They must not replace, gate, or weaken the OSS path.
