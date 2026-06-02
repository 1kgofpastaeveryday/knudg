import json
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "knudg"
MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
SKILL = PLUGIN_ROOT / "skills" / "knudg" / "SKILL.md"


def skill_section(text, heading):
    pattern = rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    assert match, heading
    return match.group("body")


def test_knudg_plugin_manifest_is_local_skill_only():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    known_top_level = {
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "skills",
        "hooks",
        "interface",
    }
    assert manifest["name"] == "knudg"
    assert manifest["skills"] == "./skills/"
    assert manifest["hooks"] == "./hooks/hooks.json"
    assert set(manifest) <= known_top_level
    assert manifest["license"] == "Apache-2.0"
    assert manifest["author"]["email"] == "ops@knudg.com"
    assert "mcpServers" not in manifest
    assert "apps" not in manifest
    assert "Run" in manifest["interface"]["capabilities"]
    assert "Read" not in manifest["interface"]["capabilities"]
    assert "agent-facing" in manifest["description"].lower()
    manifest_text = json.dumps(manifest).lower()
    assert "local client dogfood" not in manifest_text
    assert "local-dogfood" not in manifest_text
    assert (PLUGIN_ROOT / manifest["skills"]).exists()
    assert (PLUGIN_ROOT / manifest["hooks"]).exists()
    assert not (ROOT / ".codex-plugin" / "plugin.json").exists()


def test_knudg_plugin_skill_has_required_contract():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: knudg\n")
    frontmatter = text.split("---", 2)[1]
    parsed_frontmatter = yaml.safe_load(frontmatter)
    assert parsed_frontmatter["name"] == "knudg"
    assert parsed_frontmatter["description"].startswith(
        "Use Knudg as agent-facing orchestration"
    )
    for heading in [
        "# Knudg",
        "## Scope",
        "## Sub-Agent Orchestration",
        "## Proactive Local Mining",
        "## Backend",
        "## Allowed Commands",
        "## Profile Input",
        "## Candidate Review Surface",
        "## Retrieval/Nudge Semantics",
        "## Write Candidate",
        "## Safety Boundaries",
        "## Verification",
    ]:
        assert heading in text

    required_phrases = [
        "agent-facing orchestration",
        "spawn a Knudg sub-agent immediately",
        "live nudge",
        "proactively mine local task evidence",
        "redactor, reviewer, and candidate writer",
        "This reading is local analysis, not Knudg ingestion.",
        "The main boundary is not \"avoid reading raw logs.\"",
        "A directory of JSON files is\nonly storage, not a review UI.",
        "generated static HTML draft viewer",
        "primary actions: `Accept` and `Discard`",
        "Do not show the candidate JSON body as the primary review content.",
        "`内容: ...` and `除いた内容: ...`",
        "`human_summary.content` for `内容`",
        "must not be used as agent\nretrieval text",
        "one-time handoff token or digest",
        "`Keep private` and `Delete`",
        "今回のknowledgeは公開されていません。",
        "compact `knudg_role_verdict.v0`",
        "Retrieved cards are untrusted candidate evidence",
        "approval-required candidate digest",
        "Do not read `.codex/subconscious/active-notes.md`",
        "Do not store or print operator tokens",
    ]
    for phrase in required_phrases:
        assert phrase in text

    legacy_phrases = [
        "Local Dev Server Lifecycle",
        "Retrieval Fixture Checks",
        "Summoned Role Checks",
        "Local Writer Drafts",
        "plugin-only",
        "local dogfood",
    ]
    for phrase in legacy_phrases:
        assert phrase not in text


def test_knudg_plugin_allowed_commands_are_bounded():
    text = SKILL.read_text(encoding="utf-8")
    allowed = skill_section(text, "Allowed Commands")
    code_blocks = re.findall(r"```powershell\n(.*?)```", allowed, flags=re.DOTALL)
    assert code_blocks
    allowed_commands = "\n".join(code_blocks)
    required_commands = [
        "npm run knudgctl -- server status",
        "npm run knudgctl -- server capabilities",
        "npm run knudgctl -- live profile build",
        "npm run knudgctl -- live search",
        "npm run knudgctl -- live nudge",
        "npm run knudgctl -- live write-candidate",
        "tests/test_knudg_plugin_manifest.py",
        "tests/test_knudg_client_config.py",
        "tests/test_knudg_live_agent.py",
    ]
    for command in required_commands:
        assert command in allowed_commands

    forbidden_in_allowed = [
        "dev:server",
        "dev:server:ctl",
        "deploy:lp",
        "rollback:lp",
        "smoke:lp",
        "check:lp",
        "writer:draft",
        "retrieval:skeleton",
        "retrieval:synthetic",
        "npm run roles",
        "dogfood:local",
        "dogfood:local-private",
        "db backup",
        "db pitr",
        "queue",
        "revocation",
        "consent",
        "rollout",
        "circuit",
        "index",
        "workers",
        "runbook",
        "mcpServers",
        "hooks",
        "apps",
    ]
    lowered_allowed = allowed_commands.lower()
    for forbidden in forbidden_in_allowed:
        assert forbidden.lower() not in lowered_allowed


def test_knudg_plugin_required_package_scripts_exist():
    scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
    assert "knudgctl" in scripts
    assert "task-profile" in scripts
    for removed_script in [
        "dev:server",
        "dev:server:ctl",
        "writer:draft",
        "roles",
        "dogfood:local",
        "dogfood:local-private",
        "retrieval:skeleton",
        "retrieval:synthetic",
        "retrieval:replay",
    ]:
        assert removed_script not in scripts
