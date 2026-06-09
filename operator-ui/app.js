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

refreshStatus();
