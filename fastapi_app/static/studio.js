const $ = (id) => document.getElementById(id);
let token = sessionStorage.getItem("research-token") || "",
  workspace = "0",
  latest = null,
  activeDiagram = null,
  documents = [],
  controller = null,
  previewUrl = null;
let mermaid;
const mermaidReady = import(
  "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs"
)
  .then((module) => {
    mermaid = module.default;
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "neutral",
    });
  })
  .catch(() => {});

const notice = (message) => {
  $("notice").textContent = message;
};
let guestId = localStorage.getItem("research-guest-id");
if (!guestId) {
  guestId = crypto.randomUUID();
  localStorage.setItem("research-guest-id", guestId);
}
let conversationId = "default";
function conversationKey() {
  return `research-conversation:${sessionStorage.getItem("research-user") || "guest"}:${workspace}`;
}
function selectConversation(id) {
  conversationId = id;
  localStorage.setItem(conversationKey(), id);
}
function restoreConversation() {
  conversationId = localStorage.getItem(conversationKey()) || "default";
}
restoreConversation();
function headers(extra = {}) {
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    "X-Workspace-Id": workspace,
    "X-Guest-Id": guestId,
    ...extra,
  };
}
async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: headers(options.headers),
  });
  if (!response.ok) {
    let error;
    try {
      error = (await response.json()).detail;
    } catch {}
    throw Error(
      typeof error === "string"
        ? error
        : `Request failed (${response.status}). Please retry.`,
    );
  }
  return response;
}
async function json(url, options = {}) {
  return (await api(url, options)).json();
}
const post = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
function markdown(element, text) {
  if (window.marked && window.DOMPurify)
    element.innerHTML = DOMPurify.sanitize(marked.parse(text || ""));
  else {
    element.textContent = text || "";
    element.style.whiteSpace = "pre-wrap";
  }
  element.querySelectorAll("a").forEach((link) => {
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  });
}
function button(text, action, secondary = true) {
  const b = document.createElement("button");
  b.textContent = text;
  b.type = "button";
  if (secondary) b.className = "secondary";
  b.onclick = () => Promise.resolve(action()).catch((e) => notice(e.message));
  return b;
}
function switchView(id) {
  document.querySelectorAll(".view").forEach((v) => (v.hidden = v.id !== id));
  document
    .querySelectorAll("[data-view]")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === id));
  $("page-title").textContent = {
    research: "Ask better questions. Find the evidence.",
    library: "Your papers, organized.",
    discover: "Find your next reference.",
    diagrams: "Make complex ideas clear.",
    writing: "From evidence to a project.",
  }[id];
}
document
  .querySelectorAll("[data-view],[data-go]")
  .forEach(
    (b) => (b.onclick = () => switchView(b.dataset.view || b.dataset.go)),
  );
$("theme").onclick = () => {
  document.body.classList.toggle("dark");
  localStorage.setItem(
    "research-dark",
    document.body.classList.contains("dark"),
  );
};
if (localStorage.getItem("research-dark") === "true")
  document.body.classList.add("dark");
const shortcuts = {
  Summarize:
    "Summarize the main contributions of the selected papers. Cite filenames and pages.",
  Methodology:
    "Explain the methodology, datasets, baselines and evaluation metrics reported in the selected papers.",
  "Compare papers":
    "Compare the selected papers in a Markdown table with columns: paper, method, datasets, reported results, limitations, and source/page. Use “not reported in retrieved evidence” when needed.",
  "Find limitations":
    "Identify limitations explicitly reported in these papers. Separate reported limitations from your proposed research directions.",
  "Suggest a project":
    "Suggest a feasible project grounded in these papers. Separate paper-supported findings from proposed ideas. Do not invent experiments or measured results.",
};
Object.entries(shortcuts).forEach(([label, q]) =>
  $("shortcuts").append(
    button(label, () => {
      $("question").value = q;
      $("question").focus();
    }),
  ),
);
async function download(url, name, options = {}) {
  const response = await api(url, options);
  const blob = await response.blob();
  const object = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = object;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(object), 1000);
}
async function openPdf(source, page = 1, excerpt = "") {
  const response = await api(
    `/api/documents/${encodeURIComponent(source)}/preview`,
  );
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(await response.blob());
  $("pdf-frame").src = previewUrl + `#page=${Math.max(1, Number(page) || 1)}`;
  $("pdf-title").textContent = `${source} · page ${page}`;
  $("pdf-excerpt").textContent = excerpt;
  $("pdf-dialog").showModal();
}
$("close-pdf").onclick = () => {
  $("pdf-dialog").close();
  $("pdf-frame").src = "about:blank";
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
};
async function loadWorkspaces() {
  const items = await json("/api/workspaces");
  $("workspace-select")?.remove();
  const select = document.createElement("select");
  select.id = "workspace-select";
  select.setAttribute("aria-label", "Current workspace");
  select.add(new Option("Default workspace", "0"));
  items.forEach((item) => select.add(new Option(item.name, item.id)));
  select.value = workspace;
  select.onchange = () => changeWorkspace(select.value);
  $("new-workspace").before(select);
}
async function changeWorkspace(id, persist = true) {
  if (persist) saveDraft();
  workspace = String(id);
  activeDiagram = null;
  latest = null;
  $("diagram-editor").hidden = true;
  $("diagram-preview").replaceChildren();
  $("result").hidden = true;
  notice("");
  loadDraft();
  restoreConversation();
  await reload();
}
async function reload() {
  await Promise.all([loadDocuments(), loadHistory(), loadDiagrams()]);
}
$("new-workspace").onclick = async () => {
  const name = prompt("Workspace name");
  if (!name?.trim()) return;
  try {
    const item = await json("/api/workspaces", post({ name: name.trim() }));
    await changeWorkspace(String(item.id));
    await loadWorkspaces();
  } catch (e) {
    notice(e.message);
  }
};
async function loadDocuments() {
  documents = await json("/api/documents");
  renderDocuments();
  for (const id of ["source", "diagram-source"]) {
    const select = $(id),
      previous = select.value;
    select.replaceChildren(
      new Option(
        id === "source" ? "All workspace papers" : "My description only",
        "",
      ),
    );
    documents.forEach((d) => select.add(new Option(d.source, d.source)));
    if (documents.some((d) => d.source === previous)) select.value = previous;
  }
  $("research-empty").hidden = documents.length > 0;
  $("document-count").textContent =
    `${documents.length} paper${documents.length === 1 ? "" : "s"}`;
}
function renderDocuments() {
  const filtered = documents.filter((d) =>
    d.source.toLowerCase().includes($("document-filter").value.toLowerCase()),
  );
  $("documents").replaceChildren();
  if (!filtered.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "No papers here yet. Upload a PDF above.";
    $("documents").append(p);
  }
  filtered.forEach((d) => {
    const card = document.createElement("article");
    card.className = "card";
    const title = document.createElement("h3");
    title.textContent = d.source;
    const stats = document.createElement("p");
    stats.className = "muted";
    stats.textContent = `${d.pages} pages · ${d.chunks} searchable passages`;
    card.append(
      title,
      stats,
      button("Read PDF", () => openPdf(d.source)),
      button("Remove", async () => {
        if (!confirm(`Remove ${d.source} from this workspace?`)) return;
        await api(`/api/documents/${encodeURIComponent(d.source)}`, {
          method: "DELETE",
        });
        await loadDocuments();
        notice("Paper removed.");
      }),
    );
    $("documents").append(card);
  });
}
$("document-filter").oninput = renderDocuments;
$("upload-form").onsubmit = async (e) => {
  e.preventDefault();
  const files = [...$("pdf").files];
  $("upload-button").disabled = true;
  try {
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (file.size > 25 * 1024 * 1024) {
        $("upload-status").textContent =
          `${file.name} exceeds 25 MB. Choose a smaller PDF.`;
        continue;
      }
      $("upload-status").textContent =
        `Indexing ${i + 1}/${files.length}: ${file.name}…`;
      const data = new FormData();
      data.append("file", file);
      try {
        await json("/api/documents", { method: "POST", body: data });
        $("upload-status").textContent = `${file.name} is ready for questions.`;
      } catch (error) {
        $("upload-status").textContent = `${file.name}: ${error.message}`;
        notice(`${file.name}: ${error.message}`);
      }
    }
    $("pdf").value = "";
    await loadDocuments();
  } catch (error) {
    notice(error.message);
  } finally {
    $("upload-button").disabled = false;
  }
};
async function loadHistory() {
  const items = await json("/api/history");
  const groups = new Map();
  for (const row of items) {
    const id = row.result.conversation_id || "default";
    if (!groups.has(id)) groups.set(id, []);
    groups.get(id).push(row);
  }
  $("history").replaceChildren();
  if (!items.length)
    $("history").textContent = "Your conversations will appear here.";
  for (const [id, rows] of groups) {
    const first = rows[rows.length - 1];
    const b = button(first.question + " · " + rows.length, () => {
      selectConversation(id);
      renderConversation(rows);
      const row = rows[0];
      $("question").value = "";
      showResult({ ...row.result, chat_id: row.id });
      switchView("research");
    });
    b.title = first.question;
    $("history").append(b);
  }
  const current = groups.get(conversationId) || [];
  renderConversation(current);
}
function renderConversation(rows) {
  $("chat-messages").replaceChildren();
  $("conversation").hidden = !rows.length;
  for (const row of [...rows].reverse()) {
    const question = document.createElement("p");
    question.className = "chat-question";
    question.textContent = row.question;
    const answer = document.createElement("div");
    answer.className = "prose chat-answer";
    markdown(answer, row.result.answer);
    const evidence = button("Inspect sources and download", () =>
      showResult({ ...row.result, chat_id: row.id }),
    );
    $("chat-messages").append(question, answer, evidence);
  }
}
$("new-chat").onclick = () => {
  selectConversation(crypto.randomUUID());
  $("question").value = "";
  $("result").hidden = true;
  renderConversation([]);
  switchView("research");
  notice(
    "New conversation started. Follow-up questions will use this conversation only.",
  );
};
$("refresh-history").onclick = () =>
  loadHistory().catch((e) => notice(e.message));
function showResult(body) {
  latest = body;
  markdown($("answer"), body.answer);
  markdown($("analysis"), body.analysis);
  $("plan").textContent = JSON.stringify(body.plan, null, 2);
  $("critique").textContent = body.critique?.critique || "";
  $("critic").textContent =
    `Automated review: ${body.critique?.status || "Unavailable"} · ${body.revision_rounds || 0} revision(s). This is an automated check, not a guarantee of correctness.`;
  $("sources").replaceChildren();
  (body.sources || []).forEach(([source, page]) => {
    const evidence = (body.research || []).filter(
      (item) => item.source === source && String(item.page) === String(page),
    );
    const details = document.createElement("details");
    details.className = "card";
    const summary = document.createElement("summary");
    summary.textContent = `${source} · page ${page}`;
    details.append(summary);
    const passage = document.createElement("p");
    passage.textContent =
      evidence.map((item) => item.text).join("\n\n") ||
      "No passage was saved with this older answer.";
    details.append(
      passage,
      button("Open this page", () =>
        openPdf(source, page, passage.textContent),
      ),
    );
    $("sources").append(details);
  });
  $("report-links").replaceChildren();
  if (body.chat_id)
    ["pdf", "docx", "tex", "zip", "json", "txt"].forEach((format) =>
      $("report-links").append(
        button(`Download ${format.toUpperCase()}`, () =>
          download(
            `/api/reports/${body.chat_id}?format=${format}${activeDiagram ? "&diagram_ids=" + activeDiagram.id : ""}`,
            `research.${format}`,
          ),
        ),
      ),
    );
  $("result").hidden = false;
  $("research-empty").hidden = true;
}
$("copy-answer").onclick = () =>
  navigator.clipboard
    .writeText(latest?.answer || "")
    .then(() => notice("Answer copied."))
    .catch(() =>
      notice(
        "Copy is unavailable in this browser. Select and copy the answer text.",
      ),
    );
$("edit-answer").onclick = () => {
  $("writing-content").value = latest?.answer || "";
  saveDraft();
  switchView("writing");
};
function setProgress(event) {
  const labels = {
    started: "Preparing your question…",
    plan: "Planning the research…",
    research_started: "Finding relevant passages…",
    research_completed: "Evidence found. Analyzing…",
    analysis_completed: "Analysis complete. Reviewing…",
    critic_started: "Checking claims against the papers…",
    critic_completed: "Review complete…",
    revision_completed: "Revisions complete…",
    synthesis_completed: "Writing the final answer…",
    completed: "Research complete.",
  };
  if (labels[event]) $("status").textContent = labels[event];
  const steps = [...$("steps").children];
  const stage = {
    research_completed: 1,
    analysis_completed: 2,
    critic_completed: 3,
    synthesis_completed: 4,
    completed: 4,
  }[event];
  if (stage) steps.forEach((li, i) => li.classList.toggle("done", i < stage));
}
$("research-form").onsubmit = async (e) => {
  e.preventDefault();
  if (!documents.length) {
    notice("Add at least one PDF in your paper library first.");
    switchView("library");
    return;
  }
  controller = new AbortController();
  for (const id of [
    "workspace-select",
    "new-workspace",
    "new-chat",
    "account-button",
    "logout",
  ])
    if ($(id)) $(id).disabled = true;
  $("research-button").disabled = true;
  $("cancel").hidden = false;
  $("progress").hidden = false;
  [...$("steps").children].forEach((li) => li.classList.remove("done"));
  notice("");
  setProgress("started");
  const started = Date.now();
  const timer = setInterval(
    () =>
      ($("elapsed").textContent =
        `${Math.floor((Date.now() - started) / 1000)}s elapsed`),
    1000,
  );
  try {
    const params = new URLSearchParams({
      question: $("question").value,
      workspace_id: workspace,
      mode: $("answer-mode").value,
      conversation_id: conversationId,
    });
    if ($("source").value) params.set("source", $("source").value);
    const response = await api("/api/research/stream?" + params, {
      signal: controller.signal,
    });
    const reader = response.body.getReader(),
      decoder = new TextDecoder();
    let buffer = "",
      completed = false;
    function consume(frame) {
      const line = frame
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trimStart())
        .join("\n");
      if (!line) return;
      const item = JSON.parse(line);
      if (item.event === "error")
        throw Error(item.data || "Research failed. Please retry.");
      setProgress(item.event);
      if (item.event === "completed") {
        completed = true;
        showResult(item.data);
      }
    }
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        buffer += decoder.decode();
        if (buffer.trim()) consume(buffer);
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() || "";
      frames.forEach(consume);
    }
    if (!completed)
      throw Error(
        "The connection ended before the answer was ready. Check history before retrying.",
      );
    await loadHistory();
    $("question").value = "";
  } catch (error) {
    $("status").textContent =
      error.name === "AbortError"
        ? "Stopped waiting. The server may finish the current model call."
        : error.message;
    notice($("status").textContent);
  } finally {
    for (const id of [
      "workspace-select",
      "new-workspace",
      "new-chat",
      "account-button",
      "logout",
    ])
      if ($(id)) $(id).disabled = false;
    clearInterval(timer);
    $("research-button").disabled = false;
    $("cancel").hidden = true;
    controller = null;
  }
};
$("cancel").onclick = () => controller?.abort();
async function loadDiagrams() {
  const items = await json(`/api/workspaces/${workspace}/diagrams`);
  $("diagram-list").replaceChildren(
    ...items.map((d) => button(d.title, () => showDiagram(d))),
  );
}
async function previewDiagram() {
  const source = $("diagram-mermaid").value;
  $("diagram-preview").replaceChildren();
  if (!mermaid) {
    $("diagram-preview").textContent =
      "Live preview needs access to the Mermaid library. Your editable source is available below.";
    return;
  }
  try {
    const rendered = await mermaid.render("diagram-" + Date.now(), source);
    $("diagram-preview").innerHTML = rendered.svg;
  } catch {
    $("diagram-preview").textContent =
      "This diagram has a syntax error. Edit its source or describe a correction.";
  }
}
async function showDiagram(diagram) {
  activeDiagram = diagram;
  $("diagram-editor").hidden = false;
  $("diagram-title").value = diagram.title;
  $("diagram-mermaid").value = diagram.mermaid_source;
  $("diagram-assumptions").textContent = (diagram.assumptions || []).join(
    " · ",
  );
  const versions = await json(`/api/diagrams/${diagram.id}/versions`);
  $("diagram-version").replaceChildren(
    ...versions.map((v) => new Option(`Version ${v.version}`, v.version)),
  );
  $("diagram-downloads").replaceChildren();
  $("diagram-downloads").append(
    button("Mermaid source", () =>
      download(
        `/api/diagrams/${diagram.id}/download?format=mmd`,
        "diagram.mmd",
      ),
    ),
    button("SVG image", async () => {
      await previewDiagram();
      const svg = $("diagram-preview").querySelector("svg");
      if (!svg) throw Error("A valid preview is required.");
      const url = URL.createObjectURL(
        new Blob([svg.outerHTML], { type: "image/svg+xml" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "diagram.svg";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }),
  );
  for (const format of ["png", "pdf"])
    $("diagram-downloads").append(
      button(format.toUpperCase(), () =>
        download(
          `/api/diagrams/${diagram.id}/download?format=${format}`,
          `diagram.${format}`,
        ),
      ),
    );
  await previewDiagram();
}
$("diagram-preview-button").onclick = previewDiagram;
$("diagram-form").onsubmit = async (e) => {
  e.preventDefault();
  $("diagram-generate").disabled = true;
  notice("Generating your diagram…");
  try {
    const d = await json(
      `/api/workspaces/${workspace}/diagrams`,
      post({
        description: $("diagram-description").value,
        diagram_type: $("diagram-type").value,
        source: $("diagram-source").value || null,
      }),
    );
    await showDiagram(d);
    await loadDiagrams();
    notice("Diagram ready. You can edit, refine, or export it.");
  } catch (error) {
    notice(error.message);
  } finally {
    $("diagram-generate").disabled = false;
  }
};
async function mutateDiagram(path, method, body) {
  if (!activeDiagram) return;
  const d = await json(`/api/diagrams/${activeDiagram.id}${path}`, {
    ...post(body),
    method,
  });
  await showDiagram(d);
  await loadDiagrams();
  notice("Diagram saved.");
}
$("diagram-save").onclick = () =>
  mutateDiagram("/source", "PUT", {
    mermaid_source: $("diagram-mermaid").value,
  }).catch((e) => notice(e.message));
$("diagram-rename").onclick = () =>
  mutateDiagram("", "PATCH", { title: $("diagram-title").value }).catch((e) =>
    notice(e.message),
  );
$("diagram-refine").onclick = async () => {
  $("diagram-refine").disabled = true;
  try {
    await mutateDiagram("/refine", "POST", {
      instruction: $("diagram-refinement").value,
    });
  } catch (e) {
    notice(e.message);
  } finally {
    $("diagram-refine").disabled = false;
  }
};
$("diagram-restore").onclick = () =>
  mutateDiagram("/restore/" + $("diagram-version").value, "POST", {}).catch(
    (e) => notice(e.message),
  );
$("account-button").onclick = () => $("auth-dialog").showModal();
$("close-auth").onclick = () => $("auth-dialog").close();
function account() {
  const username = sessionStorage.getItem("research-user");
  $("account-name").textContent = token
    ? `Signed in as ${username || "researcher"}`
    : "Guest · local workspace";
  $("logout").hidden = !token;
  $("account-button").hidden = !!token;
}
$("auth-form").onsubmit = async (e) => {
  e.preventDefault();
  $("auth-error").textContent = "";
  const payload = {
    username: $("username").value,
    password: $("password").value,
  };
  try {
    if (e.submitter?.value === "register")
      await json("/api/auth/register", post(payload));
    const auth = await json("/api/auth/login", post(payload));
    saveDraft();
    token = auth.token;
    sessionStorage.setItem("research-token", token);
    sessionStorage.setItem("research-user", payload.username);
    $("password").value = "";
    $("auth-dialog").close();
    workspace = "0";
    account();
    await loadWorkspaces();
    await changeWorkspace("0", false);
    notice("Signed in. Your personal workspace is ready.");
  } catch (error) {
    $("auth-error").textContent = error.message;
  }
};
$("logout").onclick = async () => {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch {}
  saveDraft();
  token = "";
  sessionStorage.removeItem("research-token");
  sessionStorage.removeItem("research-user");
  account();
  workspace = "0";
  await loadWorkspaces();
  await changeWorkspace("0", false);
};
const draftKey = () =>
  `research-draft:${sessionStorage.getItem("research-user") || "guest"}:${workspace}`;
let draft = { sections: {} };
function saveDraft() {
  draft.title = $("writing-title").value;
  draft.sections[$("writing-section").value] = $("writing-content").value;
  try {
    localStorage.setItem(draftKey(), JSON.stringify(draft));
  } catch {
    notice("Browser storage is unavailable. Export your draft to keep a copy.");
  }
  $("writing-saved").textContent =
    "Saved in this browser · " + new Date().toLocaleTimeString();
}
function loadDraft() {
  try {
    draft = JSON.parse(localStorage.getItem(draftKey())) || { sections: {} };
  } catch {
    draft = { sections: {} };
  }
  $("writing-title").value = draft.title || "";
  $("writing-content").value = draft.sections[$("writing-section").value] || "";
}
$("writing-section").onchange = () => {
  $("writing-content").value = draft.sections[$("writing-section").value] || "";
};
$("writing-content").oninput = saveDraft;
$("writing-title").oninput = saveDraft;
function fullDocument() {
  return (
    "# " +
    (draft.title || "Research project") +
    "\n\n" +
    [...$("writing-section").options]
      .map((o) =>
        draft.sections[o.value]
          ? `## ${o.value}\n\n${draft.sections[o.value]}`
          : "",
      )
      .filter(Boolean)
      .join("\n\n")
  );
}
$("writing-preview").onclick = () => {
  saveDraft();
  markdown($("writing-document"), fullDocument());
  $("writing-document").hidden = !$("writing-document").hidden;
};
$("writing-generate").onclick = async () => {
  if (!$("writing-title").value.trim()) {
    notice("Enter your project topic or title first.");
    return;
  }
  if ($("writing-content").value.trim() && !confirm("Replace this section with a new AI draft? Your other sections will be kept.")) return;
  $("writing-generate").disabled = true;
  $("writing-generate").textContent = "Writing your draft…";
  try {
    const data = await json(
      "/api/writing/draft",
      post({
        title: $("writing-title").value,
        section: $("writing-section").value,
        instruction: $("writing-instruction").value,
        source: $("source").value || null,
        tone: $("writing-tone").value,
        length: $("writing-length").value,
        use_evidence: $("writing-evidence").checked && documents.length > 0,
      }),
    );
    $("writing-content").value = data.text;
    saveDraft();
    notice(data.evidence_based ? "Draft ready. Review the writing and check its cited evidence." : "Topic-based draft ready. Review it and add verified references and your project details.");
  } catch (error) {
    notice(error.message);
  } finally {
    $("writing-generate").disabled = false;
    $("writing-generate").textContent = "Generate natural draft";
  }
};
$("writing-download").onclick = async () => {
  saveDraft();
  const format = $("writing-format").value;
  try {
    await download(
      "/api/writing/export",
      `research-project.${format}`,
      post({ text: fullDocument(), format }),
    );
  } catch (error) {
    notice(error.message);
  }
};
$("discovery-form").onsubmit = async (e) => {
  e.preventDefault();
  const b = e.target.querySelector("button");
  b.disabled = true;
  $("discovery-results").textContent = "Searching arXiv…";
  try {
    const params = new URLSearchParams({ query: $("discovery-query").value });
    if ($("discovery-year").value)
      params.set("year", $("discovery-year").value);
    const items = await json("/api/discover?" + params);
    $("discovery-results").replaceChildren();
    if (!items.length)
      $("discovery-results").textContent = "No results. Try a shorter topic.";
    items.forEach((p) => {
      const card = document.createElement("article");
      card.className = "card";
      const h = document.createElement("h3");
      h.textContent = p.title;
      const meta = document.createElement("p");
      meta.className = "muted";
      meta.textContent = `${p.authors.join(", ")} · ${p.published.slice(0, 10)}`;
      const abstract = document.createElement("p");
      abstract.textContent = p.summary;
      const a = document.createElement("a");
      a.textContent = "Read paper / Download PDF ↗";
      a.href = p.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      card.append(h, meta, abstract, a);
      $("discovery-results").append(card);
    });
  } catch (error) {
    $("discovery-results").textContent = error.message;
  } finally {
    b.disabled = false;
  }
};
account();
loadDraft();
loadWorkspaces()
  .then(reload)
  .catch((error) => notice(error.message));
