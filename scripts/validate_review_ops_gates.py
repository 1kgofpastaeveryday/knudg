#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "review-ops-gates.schema.json"
DECISIONS_PATH = ROOT / "docs" / "decisions" / "README.md"

REQUIRED_FINAL_CHECK_CRITERIA = {
    "undisclosed_sponsorship_or_affiliate_interest",
    "promotional_call_to_action_or_lead_capture",
    "affiliate_referral_or_tracking_incentive",
    "keyword_stuffing_or_reputation_manipulation",
    "fake_or_unverifiable_experience_claim",
    "coordinated_or_repeated_low_signal_submission",
}
REQUIRED_FINAL_FILTER_VERDICTS = {"pass", "hold", "reject"}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dec_018_accepted():
    decisions = DECISIONS_PATH.read_text(encoding="utf-8")
    return "| DEC-018 | Review and verification operations | accepted |" in decisions


def gate_failures(data):
    failures = []
    if data["status"] == "accepted" and not dec_018_accepted():
        failures.append("accepted gate requires authoritative DEC-018 accepted review-ops decision")
    if data["status"] == "accepted":
        artifact = data["accepted_review_ops_artifact"]
        if not artifact or not (ROOT / artifact).exists():
            failures.append("accepted gate requires existing review-ops evidence artifact")
    high_risk_lanes = [lane for lane in data["reviewer_lanes"] if lane["risk_band"] == "high"]
    if not high_risk_lanes:
        failures.append("at least one high-risk lane is required")
    if any(not lane["dual_review_required"] for lane in high_risk_lanes):
        failures.append("every high-risk lane requires dual review")
    final_check = data["final_publication_check"]
    criteria = set(final_check["criteria"])
    missing_criteria = sorted(REQUIRED_FINAL_CHECK_CRITERIA - criteria)
    if missing_criteria:
        failures.append("final publication check missing ad/spam criteria: " + ", ".join(missing_criteria))
    verdicts = set(final_check["llm_verdicts"])
    missing_verdicts = sorted(REQUIRED_FINAL_FILTER_VERDICTS - verdicts)
    if missing_verdicts:
        failures.append("final publication check missing LLM verdicts: " + ", ".join(missing_verdicts))
    repair_loop = final_check["hold_repair_loop"]
    reviewer_outputs = set(repair_loop["reviewer_outputs_required"])
    if reviewer_outputs != {"ok_points", "ng_points", "repair_worthiness"}:
        failures.append("hold repair loop must require ok points, NG points, and repair-worthiness review outputs")
    if repair_loop["parallel_reviewer_count"] != 3:
        failures.append("hold repair loop requires exactly three parallel reviewers")
    if not repair_loop["repair_worthiness_decision_required"]:
        failures.append("hold repair loop requires a repair-worthiness decision before writer repair")
    if repair_loop["writer_receives"] != "ng_points_only":
        failures.append("hold repair loop writer must receive NG points only")
    if repair_loop["max_writer_attempts"] != 3:
        failures.append("hold repair loop requires exactly three writer attempts before reject")
    if repair_loop["pass_condition"] != "all_three_reviewers_pass":
        failures.append("hold repair loop pass condition must require all three reviewers to pass")
    if repair_loop["reject_condition"] != "not_worth_repair_or_three_writer_attempts_without_pass":
        failures.append("hold repair loop reject condition must include not-worth-repair or three failed writer attempts")
    if data["enablement"]["reviewer_publish_enabled"]:
        failures.append("reviewer publish must remain disabled in this scaffold")
    if data["enablement"]["public_display_enabled"]:
        failures.append("public display must remain disabled in this scaffold")
    if data["enablement"]["high_risk_body_expansion_enabled"]:
        failures.append("high-risk body expansion must remain disabled in this scaffold")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate DEC-018 review operations gate scaffold fixtures.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    schema = load_json(SCHEMA_PATH)
    data = load_json(args.input)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda error: list(error.path))
    if errors:
        print(json.dumps({"status": "rejected", "errors": [error.message for error in errors]}, sort_keys=True))
        return 2
    failures = gate_failures(data)
    if failures:
        print(json.dumps({"status": "blocked", "blocking_gates": failures}, sort_keys=True))
        return 3
    print(json.dumps({
        "ad_or_spam_check_required": True,
        "hold_repair_loop_enabled": True,
        "llm_verdicts": sorted(REQUIRED_FINAL_FILTER_VERDICTS),
        "status": "ok",
        "reviewer_publish_enabled": False,
        "public_display_enabled": False,
        "high_risk_body_expansion_enabled": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
