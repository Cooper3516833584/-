const state = {
  agents: [],
  capabilityTags: [],
  savedSettings: {},
  settingsDirty: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

document.addEventListener("DOMContentLoaded", async () => {
  bindTabs();
  bindReviewMode();
  bindAgentForm();
  bindSettingsForm();
  bindReviewForm();
  await Promise.all([loadAgents(), loadSettings()]);
  updateAgentPickerMode();
});

function bindTabs() {
  $$(".tab").forEach((button) => {
    button.addEventListener("click", async () => {
      const target = button.dataset.tab;
      const current = $(".panel.is-active")?.id;
      if (target === current) return;

      if (current === "settings" && target !== "settings" && isSettingsDirty()) {
        const action = await askSettingsSave();
        if (action === "cancel") return;
        if (action === "save") {
          const saved = await saveSettings();
          if (!saved) return;
        }
        if (action === "discard") {
          restoreSettingsForm();
          setStatus("未保存的设置修改已放弃");
        }
      }

      switchTab(target);
    });
  });
}

function switchTab(target) {
  $$(".tab").forEach((item) => item.classList.toggle("is-active", item.dataset.tab === target));
  $$(".panel").forEach((panel) => panel.classList.toggle("is-active", panel.id === target));
}

function bindReviewMode() {
  $$('input[name="mode"]').forEach((input) => {
    input.addEventListener("change", updateAgentPickerMode);
  });
}

function updateAgentPickerMode() {
  const picker = $("#manualAgents");
  const selectedMode = $("input[name='mode']:checked")?.value || "auto";
  const isManual = selectedMode === "manual";
  picker.hidden = !isManual;
  $$("#manualAgents input[type='checkbox']").forEach((input) => {
    input.disabled = !isManual;
    if (!isManual) input.checked = false;
  });
}

function bindAgentForm() {
  $("#newAgentButton").addEventListener("click", () => {
    $("#agentForm").hidden = false;
    renderCapabilityTags();
    updateAgentKindFields();
    $("#agentForm input[name='agent_id']").focus();
  });

  $("#cancelAgentButton").addEventListener("click", () => {
    $("#agentForm").hidden = true;
  });

  $("#agentKindSelect").addEventListener("change", updateAgentKindFields);

  $("#addCapabilityButton").addEventListener("click", () => {
    const input = $("#newCapabilityInput");
    const tag = normalizeTag(input.value);
    if (!tag) return;
    if (!state.capabilityTags.includes(tag)) {
      state.capabilityTags.push(tag);
      state.capabilityTags.sort();
    }
    renderCapabilityTags([...getSelectedCapabilities(), tag]);
    input.value = "";
  });

  $("#newCapabilityInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      $("#addCapabilityButton").click();
    }
  });

  $("#agentForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    payload.enabled = form.get("enabled") === "on";
    payload.capabilities = getSelectedCapabilities();

    const typedTag = normalizeTag($("#newCapabilityInput").value);
    if (typedTag && !payload.capabilities.includes(typedTag)) {
      payload.capabilities.push(typedTag);
    }

    try {
      const data = await request("/api/agents", { method: "POST", body: payload });
      event.currentTarget.reset();
      $("#newCapabilityInput").value = "";
      updateAgentKindFields();
      $("#agentForm").hidden = true;
      await loadAgents();
      setStatus(data.agent?.already_exists ? "Agent 已存在，已刷新列表" : "Agent 已保存");
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

function updateAgentKindFields() {
  const kind = $("#agentKindSelect")?.value || "reviewer";
  const isPersona = kind === "persona";
  const fields = $("#personaFields");
  const mindset = $("#personaMindsetInput");
  if (fields) fields.hidden = !isPersona;
  if (mindset) mindset.required = isPersona;
}

function bindSettingsForm() {
  const form = $("#settingsForm");
  form.addEventListener("input", () => {
    state.settingsDirty = isSettingsDirty();
  });
  form.addEventListener("change", () => {
    state.settingsDirty = isSettingsDirty();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    await saveSettings();
  });
}

function bindReviewForm() {
  $("#reviewForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("#reviewButton");
    button.disabled = true;
    $("#reviewResult").className = "result";
    $("#reviewResult").textContent = "审稿中...";

    const mode = $("input[name='mode']:checked").value;
    const agentIds =
      mode === "manual"
        ? $$("#manualAgents input[type='checkbox']:checked").map((item) => item.value)
        : [];
    const payload = {
      title: $("#titleInput").value,
      event_background: $("#backgroundInput").value,
      body: $("#bodyInput").value,
      mode,
      agent_ids: agentIds,
    };

    try {
      const result = await request("/api/review", { method: "POST", body: payload });
      $("#reviewResult").className = "result ok";
      $("#reviewResult").innerHTML = [
        `<div>run_id：${escapeHtml(result.run_id)}</div>`,
        `<div>必须修改：${result.summary.must_fix_count ?? 0} 条</div>`,
        `<div>建议修改：${result.summary.should_fix_count ?? 0} 条</div>`,
        `<div>Agent：${escapeHtml((result.selected_agent_ids || []).join(", "))}</div>`,
        `<div><a href="${result.report_docx_url}" target="_blank" rel="noreferrer">打开 DOCX 报告</a></div>`,
      ].join("");
      setStatus("审稿完成");
    } catch (error) {
      $("#reviewResult").className = "result error";
      $("#reviewResult").textContent = error.message;
      setStatus("审稿失败", true);
    } finally {
      button.disabled = false;
    }
  });
}

async function loadAgents() {
  const data = await request("/api/agents");
  state.agents = data.agents || [];
  state.capabilityTags = data.capability_tags || collectCapabilityTags(state.agents);
  renderAgents();
  renderManualAgents();
  renderCapabilityTags();
  updateAgentPickerMode();
}

function renderAgents() {
  const container = $("#agentList");
  container.innerHTML = "";
  state.agents.forEach((agent) => {
    const item = document.createElement("article");
    item.className = "agent-item";
    item.innerHTML = `
      <h3>${escapeHtml(agent.name)}</h3>
      <dl>
        <dt>ID</dt><dd>${escapeHtml(agent.agent_id)}</dd>
        <dt>状态</dt><dd>${agent.enabled ? "启用" : "禁用"}</dd>
        <dt>类型</dt><dd>${escapeHtml(agentKindLabel(agent.kind))}</dd>
        <dt>优先级</dt><dd>${agent.priority}</dd>
        <dt>标签</dt><dd>${escapeHtml((agent.capabilities || []).join(", ") || "无")}</dd>
        ${agent.kind === "persona" ? `<dt>思路</dt><dd>${escapeHtml(agent.persona_profile?.mindset || "未设置")}</dd>` : ""}
      </dl>
    `;
    container.appendChild(item);
  });
}

function renderManualAgents() {
  const container = $("#manualAgents");
  container.innerHTML = "";
  state.agents
    .filter((agent) => agent.enabled && ["reviewer", "persona"].includes(agent.kind))
    .forEach((agent) => {
      const label = document.createElement("label");
      label.className = "agent-check";
      label.innerHTML = `<input type="checkbox" value="${escapeHtml(agent.agent_id)}" /> ${escapeHtml(agent.name)} <span class="agent-kind-pill">${escapeHtml(agentKindLabel(agent.kind))}</span>`;
      container.appendChild(label);
    });
}

function agentKindLabel(kind) {
  if (kind === "persona") return "立场模拟";
  if (kind === "selector") return "选择器";
  if (kind === "reviewer") return "规则审查";
  return kind || "未知";
}

function renderCapabilityTags(selectedValues = getSelectedCapabilities()) {
  const container = $("#capabilityTags");
  if (!container) return;
  const selected = new Set(selectedValues);
  container.innerHTML = "";

  if (!state.capabilityTags.length) {
    const empty = document.createElement("div");
    empty.className = "tag-empty";
    empty.textContent = "暂无标签，可点击新增标签创建。";
    container.appendChild(empty);
    return;
  }

  state.capabilityTags.forEach((tag) => {
    const label = document.createElement("label");
    label.className = "tag-option";
    label.innerHTML = `<input type="checkbox" value="${escapeHtml(tag)}" ${selected.has(tag) ? "checked" : ""} /> ${escapeHtml(tag)}`;
    container.appendChild(label);
  });
}

function getSelectedCapabilities() {
  return $$("#capabilityTags input[type='checkbox']:checked").map((item) => item.value);
}

function collectCapabilityTags(agents) {
  const tags = new Set();
  agents.forEach((agent) => {
    (agent.capabilities || []).forEach((tag) => {
      if (tag) tags.add(tag);
    });
  });
  return Array.from(tags).sort();
}

function normalizeTag(value) {
  return String(value || "").trim().replace(/\s+/g, "_");
}

async function loadSettings() {
  const data = await request("/api/settings");
  state.savedSettings = data.settings || {};
  applySettingsToForm(state.savedSettings);
  state.settingsDirty = false;
}

async function saveSettings() {
  const settings = getSettingsFormValues();
  try {
    const data = await request("/api/settings", { method: "POST", body: { settings } });
    state.savedSettings = data.settings || settings;
    applySettingsToForm(state.savedSettings);
    state.settingsDirty = false;
    $("#settingsResult").className = "result ok";
    $("#settingsResult").textContent = "设置已保存";
    setStatus("设置已保存");
    return true;
  } catch (error) {
    $("#settingsResult").className = "result error";
    $("#settingsResult").textContent = error.message;
    setStatus("设置保存失败", true);
    return false;
  }
}

function getSettingsFormValues() {
  return Object.fromEntries(new FormData($("#settingsForm")).entries());
}

function applySettingsToForm(settings) {
  $$("#settingsForm [name]").forEach((field) => {
    if (Object.prototype.hasOwnProperty.call(settings, field.name)) {
      field.value = settings[field.name] ?? "";
    }
  });
}

function restoreSettingsForm() {
  applySettingsToForm(state.savedSettings);
  state.settingsDirty = false;
  $("#settingsResult").className = "result";
  $("#settingsResult").textContent = "";
}

function isSettingsDirty() {
  const current = getSettingsFormValues();
  const saved = state.savedSettings || {};
  const keys = new Set([...Object.keys(current), ...Object.keys(saved)]);
  return Array.from(keys).some((key) => String(current[key] ?? "") !== String(saved[key] ?? ""));
}

function askSettingsSave() {
  const dialog = $("#settingsUnsavedDialog");
  if (!dialog || typeof dialog.showModal !== "function") {
    return Promise.resolve(window.confirm("设置有未保存修改，是否保存？") ? "save" : "discard");
  }

  return new Promise((resolve) => {
    const cleanup = () => {
      dialog.removeEventListener("click", onClick);
      dialog.removeEventListener("cancel", onCancel);
      if (dialog.open) dialog.close();
    };
    const finish = (action) => {
      cleanup();
      resolve(action);
    };
    const onClick = (event) => {
      const action = event.target?.dataset?.action;
      if (action) finish(action);
    };
    const onCancel = (event) => {
      event.preventDefault();
      finish("cancel");
    };

    dialog.addEventListener("click", onClick);
    dialog.addEventListener("cancel", onCancel);
    dialog.showModal();
  });
}

async function request(url, options = {}) {
  const init = { method: options.method || "GET", headers: {} };
  if (options.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }
  const response = await fetch(url, init);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "请求失败");
  }
  return data;
}

function setStatus(message, isError = false) {
  const node = $("#statusText");
  node.textContent = message;
  node.style.color = isError ? "var(--red)" : "var(--muted)";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
