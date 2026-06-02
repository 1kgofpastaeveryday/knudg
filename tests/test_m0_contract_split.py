from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "architecture" / "m0-contract-split.md"


def test_m0_contract_split_documents_local_only_boundaries():
    text = DOC.read_text(encoding="utf-8")
    required = [
        "Stable M0 Foundation",
        "Local-Only M0 Pieces",
        "Verifier Swap Boundary",
        "Protected-Data Gate",
        "HS256 request-context verification inside Postgres",
        "must not be used for non-synthetic\nprivate/team protected data",
        "asymmetric or external KMS/Vault-style verification",
        "fail if local HS256 is enabled outside the\n  local development profile",
        "WEDGE-001 is accepted",
        "Private-use notice and acknowledgement are implemented",
        "Protected-data durability gate passes",
    ]
    for phrase in required:
        assert phrase in text


def test_m0_contract_split_does_not_authorize_public_or_protected_shortcuts():
    text = DOC.read_text(encoding="utf-8").lower()
    forbidden_claims = [
        "hs256 is production ready",
        "public publication is enabled",
        "non-synthetic data may be stored",
        "skip the protected-data durability gate",
    ]
    for phrase in forbidden_claims:
        assert phrase not in text
