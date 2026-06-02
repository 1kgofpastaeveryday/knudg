#!/usr/bin/env python3

DOMAIN_POLICY_SCHEMA_VERSION = "domain-policy-registry-v0"
TECHNICAL_WORK_DOMAIN = "technical_work"

DOMAIN_KEYS = (
    "technical_work",
    "personal_reasoning",
    "career_private",
    "place_service_experience",
    "public_experience_candidate",
    "public_aggregate_signal",
)

TECHNICAL_DEFAULT_RETRIEVAL_DOMAINS = (TECHNICAL_WORK_DOMAIN,)

NON_INGEST_DOMAINS = (
    "personal_reasoning",
    "career_private",
    "place_service_experience",
    "public_experience_candidate",
    "public_aggregate_signal",
)


class DomainPolicyError(ValueError):
    pass


def normalize_retrieval_domains(value):
    if value is None:
        return list(TECHNICAL_DEFAULT_RETRIEVAL_DOMAINS)
    if not isinstance(value, list):
        raise DomainPolicyError("domain policy rejected")
    result = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            raise DomainPolicyError("domain policy rejected")
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    if tuple(result) != TECHNICAL_DEFAULT_RETRIEVAL_DOMAINS:
        raise DomainPolicyError("domain policy rejected")
    return result
