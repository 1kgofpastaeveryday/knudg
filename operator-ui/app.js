const workspace = "closed-beta-operator-ui";
let pendingWrite = null;

const $ = (selector) => document.querySelector(selector);

function splitList(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function renderJson(target, value) {
  target.textContent = JSON.stringify(value, null, 2);
}

function addText(parent, tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  element.textContent = text;
  parent.appendChild(element);
  return element;
}

async function requestJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok && response.status !== 409) {
    throw new Error(JSON.stringify(body));
  }
  return { status: response.status, body };
}

function cardFromForm(form) {
  const data = new FormData(form);
  return {
    source_class: "local_private_dogfood",
    title: data.get("title").trim(),
    problem_summary: data.get("problem_summary").trim(),
    solution_summary: data.get("solution_summary").trim(),
    public_packages: splitList(data.get("public_packages")),
    environment_tags: splitList(data.get("environment_tags")),
    public_reference_urls: splitList(data.get("public_reference_urls")),
    command_labels: splitList(data.get("command_labels")),
    error_fingerprints: splitList(data.get("error_fingerprints")),
    lessons: splitList(data.get("lessons")),
  };
}

function taskProfileFromForm(form) {
  const data = new FormData(form);
  return {
    schema_version: "task_profile.v0",
    intent: data.get("intent"),
    explicit_query: data.get("explicit_query").trim(),
    repo_shape_category: data.get("repo_shape_category").trim(),
    public_packages: splitList(data.get("public_packages")),
    error_fingerprints: splitList(data.get("error_fingerprints")),
    recent_event_kinds: ["task_start"],
  };
}

function experienceRecordFromForm(form) {
  const data = new FormData(form);
  const detailClasses = [
    "selection_status",
    "private_message",
    "private_person_identity",
    "exact_timestamp",
    "raw_source_material",
    "protected_identity_signal",
    "device_or_network_signal",
  ];
  return {
    schema_version: "experience-storage-record-v0",
    record_class: "redacted_private_experience_record",
    domain: data.get("domain"),
    subject: {
      type: data.get("subject_type"),
      public_name: data.get("public_name").trim(),
      aliases: [],
      entity_name_public_allowed: true,
      private_person_refs: [],
    },
    storage_state: {
      mode: "stored_private_redacted",
      activation_required: false,
      database_write_enabled: true,
      record_visible_to_retrieval: false,
    },
    consent: {
      capture_notice_shown: true,
      revocation_supported: true,
      publication_consent: false,
      b2b_contact_consent: false,
      dashboard_aggregation_consent: false,
      private_retention_consent_proof: {
        consent_id: data.get("consent_id").trim(),
        handoff_id: data.get("handoff_id").trim(),
        challenge_id: data.get("challenge_id").trim(),
        card_id: data.get("card_id").trim(),
        card_version_id: data.get("card_version_id").trim(),
        artifact_digest: data.get("artifact_digest").trim(),
        policy_version: data.get("policy_version").trim(),
        policy_digest: data.get("policy_digest").trim(),
        challenge_digest: data.get("challenge_digest").trim(),
        handoff_digest: data.get("handoff_digest").trim(),
      },
    },
    redacted_experience: {
      title: data.get("title").trim(),
      summary: data.get("summary").trim(),
      observations: splitList(data.get("observations")),
      subjective_impressions: splitList(data.get("subjective_impressions")),
      disallowed_detail_classes: detailClasses,
      private_selection_status_present: false,
      raw_quotes_present: false,
      exact_dates_present: false,
      private_person_present: false,
    },
    source_controls: {
      raw_source_retention: "none",
      raw_detail_escrow_ref: null,
      raw_source_available_to_model: false,
      source_digest: `sha256:${"c".repeat(64)}`,
    },
    surface_controls: {
      retrieval_policy: "explicit_or_contextual",
      public_candidate_conversion_enabled: false,
      public_serving_enabled: false,
      b2b_delivery_enabled: false,
      identity_processing_enabled: false,
      raw_detail_escrow_enabled: false,
      dashboard_enabled: false,
    },
    audit: {
      actor_ref: "operator-private:operator-ui",
      created_at: "operator-time:closed-beta-ui",
      redaction_digest: `sha256:${"d".repeat(64)}`,
      redaction_notes: "Public subject name is retained while private status, people, dates, raw messages, and device signals are removed.",
    },
  };
}

async function refreshStatus() {
  const status = $("#api-status");
  try {
    const response = await fetch("/api/status");
    const payload = await response.json();
    status.textContent = `${payload.status}: ${payload.backend_url}`;
  } catch (error) {
    status.textContent = `unavailable: ${error.message}`;
  }
}

function renderConsentReview(payload) {
  const summary = $("#consent-summary");
  const target = $("#consent-review");
  target.textContent = "";
  const enabled = payload.enabled_flags.length ? payload.enabled_flags.join(", ") : "none";
  summary.textContent = `${payload.source_gate_id}: ${payload.status}; private retention completion ${payload.private_retention_completion_ready ? "ready" : "disabled"}; enabled flags: ${enabled}`;

  const surfaces = document.createElement("div");
  surfaces.className = "consent-grid";
  for (const surface of payload.surfaces) {
    const item = document.createElement("div");
    item.className = "consent-item";
    addText(item, "strong", null, surface.surface_type);
    addText(item, "span", null, `scope: ${surface.canonical_scope}`);
    addText(item, "span", null, `status: ${surface.status}`);
    addText(item, "span", null, `transport: ${surface.completion_transport}`);
    const action = document.createElement("button");
    action.type = "button";
    action.disabled = surface.completion_action !== "complete_private_retention";
    action.textContent = action.disabled ? "Completion disabled" : "Private retention ready";
    if (!action.disabled) {
      action.addEventListener("click", () => {
        summary.textContent = `${payload.source_gate_id}: private retention consent is available for redacted storage only`;
      });
    }
    item.appendChild(action);
    surfaces.appendChild(item);
  }
  target.appendChild(surfaces);

  const domains = document.createElement("div");
  domains.className = "domain-strip";
  for (const boundary of payload.experience_domain_boundaries) {
    const item = document.createElement("div");
    item.className = "domain-item";
    addText(item, "strong", null, boundary.domain);
    const disabledFlags = [
      "real_ingest_enabled",
      "private_retention_completion_enabled",
      "public_candidate_conversion_enabled",
      "public_publication_completion_enabled",
      "raw_source_retention_enabled",
    ].filter((name) => boundary[name] === false);
    addText(item, "span", null, `${disabledFlags.length} gated flags disabled`);
    addText(item, "span", null, `domain revocation: ${boundary.requires_domain_scoped_revocation ? "required" : "missing"}`);
    domains.appendChild(item);
  }
  target.appendChild(domains);

  const blockers = document.createElement("div");
  blockers.className = "blockers";
  addText(blockers, "strong", null, "Blocked until");
  addText(blockers, "span", null, payload.blocked_until.join(", "));
  target.appendChild(blockers);
}

async function refreshConsentReview() {
  const summary = $("#consent-summary");
  try {
    const response = await fetch("/api/consent-review");
    const payload = await response.json();
    renderConsentReview(payload);
  } catch (error) {
    summary.textContent = `unavailable: ${error.message}`;
  }
}

async function viewCard(cardId) {
  const empty = $("#view-empty");
  const output = $("#view-output");
  empty.classList.add("hidden");
  output.classList.remove("hidden");
  renderJson(output, { status: "loading", card_id: cardId });
  try {
    const { body } = await requestJson(`/api/cards/${cardId}:view`, { workspace });
    renderJson(output, body);
  } catch (error) {
    renderJson(output, { status: "error", detail: error.message });
  }
}

function renderResults(cards) {
  const target = $("#search-results");
  target.textContent = "";
  if (!cards.length) {
    target.innerHTML = '<div class="empty">No cards found.</div>';
    return;
  }
  for (const card of cards) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "result";
    item.innerHTML = `<strong>${card.card_id}</strong><span>${card.coarse_match_reason.join(", ")}</span>`;
    item.addEventListener("click", () => viewCard(card.card_id));
    target.appendChild(item);
  }
}

$("#refresh-status").addEventListener("click", refreshStatus);
$("#refresh-consent").addEventListener("click", refreshConsentReview);

$("#write-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const output = $("#write-output");
  const approve = $("#approve-write");
  pendingWrite = { workspace, card: cardFromForm(event.currentTarget) };
  approve.disabled = true;
  try {
    const { body } = await requestJson("/api/cards:publish", pendingWrite);
    renderJson(output, body);
  } catch (error) {
    renderJson(output, { status: "error", detail: error.message });
  }
});

$("#approve-write").addEventListener("click", async () => {
  const output = $("#write-output");
  renderJson(output, {
    status: "completion_disabled",
    detail: "This browser surface can stage a review digest only.",
  });
});

$("#search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const { body } = await requestJson("/api/search", {
      workspace,
      task_profile: taskProfileFromForm(event.currentTarget),
      limit: 5,
      min_score: 1,
    });
    renderResults(body.result?.cards || []);
  } catch (error) {
    $("#search-results").innerHTML = `<div class="empty">${error.message}</div>`;
  }
});

$("#experience-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const output = $("#experience-output");
  try {
    const { body } = await requestJson("/api/experience-records:store", {
      workspace,
      record: experienceRecordFromForm(event.currentTarget),
    });
    renderJson(output, body);
  } catch (error) {
    renderJson(output, { status: "error", detail: error.message });
  }
});

refreshStatus();
refreshConsentReview();
