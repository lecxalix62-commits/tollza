// ─── State ───────────────────────────────────────────────────────────────────
const state = {
  communities:     [],
  drafts:          [],
  draftFilter:     "all",
  imageAttachment: null,
  vkSearchResults: [],
  monitorResults:  [],
  selectedIdx:     null,
  parseTypeFilter: "all",
  aiModal: { photoUrl: null, authorId: null, attachment: null },
  captchaModal: { draftId: null, ownerId: null, postId: null, challengeId: null },
};

// ─── Elements ────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const el = {
  commList:        $("communities-list"),
  commCount:       $("comm-count"),
  commCheckboxes:  $("community-checkboxes"),
  commUrlInput:    $("comm-url-input"),
  commUrlBtn:      $("comm-url-btn"),
  commUrlStatus:   $("comm-url-status"),
  commSearchInput: $("comm-search-input"),
  commSearchBtn:   $("comm-search-btn"),
  commSearchStatus:$("comm-search-status"),
  vkSearchResults: $("vk-search-results"),
  draftsList:      $("drafts-list"),
  draftFilters:    $("draft-filters"),
  commentText:     $("comment-text"),
  charCounter:     $("char-counter"),
  imageUpload:     $("image-upload"),
  imgLabel:        $("img-upload-label"),
  imgName:         $("image-upload-name"),
  clearImg:        $("clear-image"),
  uploadStatus:    $("upload-status"),
  submitBtn:       $("submit-draft-btn"),
  selectAll:       $("select-all-comm"),
  refreshBtn:      $("refresh-all"),
  scanBtn:         $("scan-btn"),
  scanStatus:      $("scan-status"),
  keywordsInput:   $("keywords-input"),
  postsCount:      $("posts-count"),
  monitorList:     $("monitor-results-list"),
  resultsCount:    $("results-count"),
  parseFilters:    $("parse-filters"),
  exportCsvBtn:    $("export-csv-btn"),
  dmText:          $("dm-text"),
  dmSelected:      $("dm-selected-btn"),
  dmAll:           $("dm-all-btn"),
  dmStatus:        $("dm-status"),
  sPending:        $("s-pending"),
  sPublished:      $("s-published"),
  sComm:           $("s-comm"),
  sApStatus:       $("s-ap-status"),
  apDot:           $("ap-dot"),
  statApWrap:      $("stat-ap-wrap"),
  apNavPill:       $("ap-nav-pill"),
  // autopilot
  apEnabled:       $("ap-enabled"),
  apKeywords:      $("ap-keywords"),
  apInterval:      $("ap-interval"),
  apPosts:         $("ap-posts"),
  apSendDm:        $("ap-send-dm"),
  apDmMsg:         $("ap-dm-msg"),
  apDmGroup:       $("ap-dm-group"),
  apSendComment:   $("ap-send-comment"),
  apCommentMsg:    $("ap-comment-msg"),
  apCommentGroup:  $("ap-comment-group"),
  apSaveBtn:       $("ap-save-btn"),
  apRunBtn:        $("ap-run-btn"),
  apStatus:        $("ap-status"),
  apClearBtn:      $("ap-clear-btn"),
  apContactedCount:$("ap-contacted-count"),
  apLogList:       $("ap-log-list"),
  captchaModal:    $("captcha-modal"),
  captchaImg:      $("captcha-img"),
  captchaKey:      $("captcha-key"),
  captchaStatus:   $("captcha-status"),
  captchaReloadBtn:$("captcha-reload-btn"),
  captchaSubmitBtn:$("captcha-submit-btn"),
};

// ─── Toast ───────────────────────────────────────────────────────────────────
function toast(msg, type = "default") {
  const c = $("toast-container");
  const t = document.createElement("div");
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = "0"; t.style.transition = "opacity .2s"; setTimeout(() => t.remove(), 200); }, 3200);
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

async function api(path, opts = {}) {
  const isForm = opts.body instanceof FormData;
  const res = await fetch(path, {
    headers: isForm ? undefined : { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) { const m = await res.text(); throw new Error(JSON.parse(m)?.detail ?? m ?? "Ошибка"); }
  if (res.status === 204) return null;
  return res.json();
}

function fmt(v) {
  return new Intl.DateTimeFormat("ru-RU", { day:"2-digit", month:"2-digit", year:"2-digit", hour:"2-digit", minute:"2-digit" }).format(new Date(v));
}

function setBtnLoading(btn, loading, text) {
  if (loading) {
    btn._origText = btn.innerHTML;
    btn.innerHTML = `<span class="spin"></span> ${text || ""}`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn._origText || btn.innerHTML;
    btn.disabled = false;
  }
}

function setStatus(el, msg, type = "") {
  el.textContent = msg;
  el.className = "pane-status " + (type ? type + "-text" : "muted-text");
}

const STATUS_LABEL = { pending_review:"На проверке", published:"Опубликовано", publish_failed:"Ошибка публикации", rejected:"Отклонено" };
const STATUS_BADGE  = { pending_review:"badge-pending", published:"badge-published", publish_failed:"badge-failed", rejected:"badge-rejected" };

// ─── Section tabs ─────────────────────────────────────────────────────────────
document.querySelectorAll(".stab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".stab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".section").forEach(s => s.classList.add("hidden"));
    $(`sec-${btn.dataset.section}`).classList.remove("hidden");
    if (btn.dataset.section === "autopilot") {
      loadAutopilotConfig();
      loadAutopilotLog();
    }
  });
});

// ─── Stats ───────────────────────────────────────────────────────────────────
function updateStats() {
  el.sComm.textContent      = state.communities.length;
  el.sPending.textContent   = state.drafts.filter(d => d.status === "pending_review").length;
  el.sPublished.textContent = state.drafts.filter(d => d.status === "published").length;
}

// ─── Communities ─────────────────────────────────────────────────────────────
function renderCommunities() {
  const list = state.communities;
  el.commCount.textContent = list.length || "";
  el.commCount.style.display = list.length ? "" : "none";

  if (!list.length) {
    el.commList.innerHTML = `<div class="empty-state" style="padding:18px 10px">
      <div class="empty-title">Нет сообществ</div>
      <div class="empty-copy">Добавь первое ниже</div>
    </div>`;
    return;
  }

  el.commList.innerHTML = list.map(c =>
    `<div class="community-item">
      <div class="comm-avatar">${esc(c.name[0] ?? "?")}</div>
      <div class="community-info">
        <span class="community-name">${esc(c.name)}</span>
        <span class="community-meta">vk.com/${esc(c.screen_name)}</span>
      </div>
      <button class="btn-icon del-comm" data-id="${c.id}" title="Удалить">✕</button>
    </div>`
  ).join("");
}

function renderCheckboxes() {
  if (!state.communities.length) {
    el.commCheckboxes.innerHTML = '<p class="empty-hint">Добавь сообщества в боковом меню.</p>';
    return;
  }
  el.commCheckboxes.innerHTML = state.communities.map(c =>
    `<label class="checkbox-row">
      <input type="checkbox" name="community_ids" value="${c.id}" />
      <span class="checkbox-label">
        <span>${esc(c.name)}</span>
        <span class="community-meta">vk.com/${esc(c.screen_name)}</span>
      </span>
    </label>`
  ).join("");
}

async function loadCommunities() {
  state.communities = await api("/communities");
  renderCommunities();
  renderCheckboxes();
}

el.commUrlBtn.addEventListener("click", async () => {
  const url = el.commUrlInput.value.trim();
  if (!url) { setStatus(el.commUrlStatus, "Введи ссылку или screen_name", "err"); return; }
  setBtnLoading(el.commUrlBtn, true, "");
  setStatus(el.commUrlStatus, "Загружаю...", "");
  try {
    const comm = await api("/communities/resolve", { method: "POST", body: JSON.stringify({ url }) });
    el.commUrlInput.value = "";
    setStatus(el.commUrlStatus, `Добавлено: ${comm.name}`, "ok");
    await loadCommunities(); updateStats();
    toast(`Добавлено: ${comm.name}`, "ok");
  } catch (e) {
    setStatus(el.commUrlStatus, e.message, "err");
  } finally {
    setBtnLoading(el.commUrlBtn, false);
  }
});
el.commUrlInput.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); el.commUrlBtn.click(); } });

el.commSearchBtn.addEventListener("click", async () => {
  const q = el.commSearchInput.value.trim();
  if (!q) return;
  setBtnLoading(el.commSearchBtn, true, "");
  setStatus(el.commSearchStatus, "", "");
  el.vkSearchResults.innerHTML = "";
  try {
    const groups = await api(`/communities/search-vk?q=${encodeURIComponent(q)}`);
    state.vkSearchResults = groups;
    if (!groups.length) { el.vkSearchResults.innerHTML = '<p class="empty-hint">Ничего не найдено.</p>'; return; }
    el.vkSearchResults.innerHTML = groups.map((g, i) =>
      `<div class="vk-result-item">
        <div class="comm-avatar" style="background:var(--surface-3);color:var(--muted)">${esc(g.name[0] ?? "?")}</div>
        <div class="vk-result-info">
          <div class="vk-result-name">${esc(g.name)}</div>
          <div class="vk-result-meta">vk.com/${esc(g.screen_name)}</div>
        </div>
        <button class="btn btn-xs btn-ghost add-vk-result" data-idx="${i}">+ Добавить</button>
      </div>`
    ).join("");
    setStatus(el.commSearchStatus, `Найдено: ${groups.length}`, "");
  } catch (e) {
    setStatus(el.commSearchStatus, e.message, "err");
  } finally {
    setBtnLoading(el.commSearchBtn, false);
  }
});
el.commSearchInput.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); el.commSearchBtn.click(); } });

el.vkSearchResults.addEventListener("click", async e => {
  const btn = e.target.closest(".add-vk-result");
  if (!btn) return;
  const g = state.vkSearchResults[Number(btn.dataset.idx)];
  btn.disabled = true; btn.textContent = "...";
  try {
    await api("/communities", { method: "POST", body: JSON.stringify({ vk_group_id: g.id, screen_name: g.screen_name, name: g.name }) });
    btn.textContent = "✓"; btn.className = "btn btn-xs btn-ok";
    await loadCommunities(); updateStats();
    toast(`Добавлено: ${g.name}`, "ok");
  } catch (e2) {
    btn.textContent = "Ошибка"; btn.disabled = false;
    toast(e2.message, "err");
  }
});

el.commList.addEventListener("click", async e => {
  const btn = e.target.closest(".del-comm");
  if (!btn) return;
  const comm = state.communities.find(c => c.id === btn.dataset.id);
  if (!confirm(`Удалить «${comm?.name ?? "?"}»?`)) return;
  try {
    await api(`/communities/${btn.dataset.id}`, { method: "DELETE" });
    await loadCommunities(); updateStats();
    toast("Сообщество удалено");
  } catch (e) { toast(e.message, "err"); }
});

document.querySelectorAll(".add-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".add-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    const target = tab.dataset.tab;
    $("add-pane-url").classList.toggle("hidden", target !== "url");
    $("add-pane-search").classList.toggle("hidden", target !== "search");
  });
});

// ─── Drafts ──────────────────────────────────────────────────────────────────
function renderDrafts() {
  const list = state.draftFilter === "all"
    ? state.drafts
    : state.drafts.filter(d => d.status === state.draftFilter);

  if (!list.length) {
    el.draftsList.innerHTML = `<div class="empty-state">
      <div class="empty-title">Очередь пуста</div>
      <div class="empty-copy">Черновики появятся после отправки на модерацию</div>
    </div>`;
    return;
  }

  el.draftsList.innerHTML = list.map(d => {
    const comms = d.community_ids.map(id => state.communities.find(c => c.id === id)?.name ?? id).join(", ");
    const attach = d.image_attachment
      ? `<div class="draft-attachment"><span class="attachment-badge">&#128206; ${esc(d.image_attachment)}</span></div>` : "";
    const results = d.publish_results.length
      ? `<div class="publish-results">${d.publish_results.map(r =>
          r.comment_id
            ? `<div class="result-row result-ok">✓ Пост ${r.vk_post_id} → #${r.comment_id}</div>`
            : `<div class="result-row result-err">✗ Пост ${r.vk_post_id}: ${esc(r.error)}${r.captcha_challenge_id ? ` <button class="btn btn-xs btn-ghost" data-captcha-action="solve" data-draft-id="${d.id}" data-owner-id="${r.vk_owner_id}" data-post-id="${r.vk_post_id}" data-challenge-id="${r.captcha_challenge_id}">Решить капчу</button>` : ""}</div>`
        ).join("")}</div>` : "";
    const actions = ["pending_review", "publish_failed"].includes(d.status)
      ? `<input class="field moderation-note" data-id="${d.id}" placeholder="Заметка модератора (необязательно)" style="font-size:0.8rem;padding:7px 11px;margin-top:10px" />
         <div class="draft-actions">
           <button class="btn btn-ok btn-sm" data-action="approve" data-id="${d.id}">${d.status === "publish_failed" ? "↻ Повторить" : "✓ Одобрить"}</button>
           <button class="btn btn-danger btn-sm" data-action="reject" data-id="${d.id}">✕ Отклонить</button>
         </div>` : "";

    return `<article class="draft-card">
      <div class="draft-meta">
        <span class="badge ${STATUS_BADGE[d.status] ?? ""}">${STATUS_LABEL[d.status] ?? d.status}</span>
        <span style="font-size:0.72rem;color:var(--muted-2)">${fmt(d.created_at)}</span>
        <button class="btn-icon del-draft" data-id="${d.id}" title="Удалить черновик" style="margin-left:auto">✕</button>
      </div>
      <p class="draft-text">${esc(d.text)}</p>
      <div class="draft-info">Сообщества: ${esc(comms)}</div>
      ${d.moderation_note ? `<div class="draft-info">Заметка: ${esc(d.moderation_note)}</div>` : ""}
      ${attach}${results}${actions}
    </article>`;
  }).join("");
}

async function loadDrafts() {
  state.drafts = await api("/drafts");
  renderDrafts();
}

el.draftsList.addEventListener("click", async e => {
  const delBtn = e.target.closest(".del-draft");
  if (delBtn) {
    if (!confirm("Удалить черновик?")) return;
    try {
      await api(`/drafts/${delBtn.dataset.id}`, { method: "DELETE" });
      await loadDrafts(); updateStats();
      toast("Черновик удалён");
    } catch (e) { toast(e.message, "err"); }
    return;
  }

  const captchaBtn = e.target.closest("[data-captcha-action='solve']");
  if (captchaBtn) {
    openCaptchaModal({
      draftId: captchaBtn.dataset.draftId,
      ownerId: Number(captchaBtn.dataset.ownerId),
      postId: Number(captchaBtn.dataset.postId),
      challengeId: captchaBtn.dataset.challengeId,
    });
    return;
  }

  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const id = btn.dataset.id;
  const action = btn.dataset.action;
  const note = document.querySelector(`.moderation-note[data-id="${id}"]`)?.value?.trim() || null;
  setBtnLoading(btn, true, action === "approve" ? "Публикую..." : "...");
  try {
    const draft = await api(`/drafts/${id}/${action}`, { method: "POST", body: JSON.stringify({ moderation_note: note }) });
    await loadDrafts(); updateStats();
    if (action === "approve" && draft.publish_results?.some(r => r.captcha_challenge_id)) {
      toast("VK запросил капчу: открой результат и подтверди код", "warn");
    } else {
      toast(action === "approve" ? "Черновик отправлен на публикацию" : "Черновик отклонён");
    }
  } catch (e) { toast(e.message, "err"); setBtnLoading(btn, false); }
});

el.draftFilters.addEventListener("click", e => {
  const btn = e.target.closest(".tab");
  if (!btn) return;
  state.draftFilter = btn.dataset.status;
  document.querySelectorAll("#draft-filters .tab").forEach(t => t.classList.remove("active"));
  btn.classList.add("active");
  renderDrafts();
});

// ─── Image upload ─────────────────────────────────────────────────────────────
el.imageUpload.addEventListener("change", async () => {
  const file = el.imageUpload.files[0];
  if (!file) return;
  el.imgName.textContent = file.name;
  el.imgLabel.className = "img-upload-label uploading";
  el.uploadStatus.textContent = "Загружаю...";
  el.uploadStatus.className = "upload-status";
  const fd = new FormData();
  fd.append("file", file);
  try {
    const data = await api("/drafts/upload-image", { method: "POST", body: fd });
    state.imageAttachment = data.attachment;
    el.imgLabel.className = "img-upload-label has-file";
    el.uploadStatus.textContent = "Загружено";
    el.uploadStatus.className = "upload-status ok";
    el.clearImg.style.display = "inline-flex";
    toast("Фото прикреплено", "ok");
  } catch (e) {
    el.uploadStatus.textContent = "Ошибка: " + e.message;
    el.uploadStatus.className = "upload-status err";
    resetImage();
  }
});
el.clearImg.addEventListener("click", resetImage);

function resetImage() {
  state.imageAttachment = null;
  el.imageUpload.value = "";
  el.imgName.textContent = "Прикрепить фото";
  el.imgLabel.className = "img-upload-label";
  el.clearImg.style.display = "none";
  el.uploadStatus.textContent = "";
}

// ─── Compose ──────────────────────────────────────────────────────────────────
el.commentText.addEventListener("input", () => {
  const n = el.commentText.value.length;
  el.charCounter.textContent = `${n} / 4000`;
  el.charCounter.className = "char-counter" + (n > 4000 ? " over" : "");
});
el.selectAll.addEventListener("click", () => {
  const boxes = document.querySelectorAll('input[name="community_ids"]');
  const allChecked = [...boxes].every(b => b.checked);
  boxes.forEach(b => (b.checked = !allChecked));
});

$("draft-form").addEventListener("submit", async e => {
  e.preventDefault();
  const text = el.commentText.value.trim();
  const ids = [...document.querySelectorAll('input[name="community_ids"]:checked')].map(i => i.value);
  if (!text)   { toast("Напиши текст комментария", "warn"); return; }
  if (!ids.length) { toast("Выбери хотя бы одно сообщество", "warn"); return; }
  setBtnLoading(el.submitBtn, true, "Отправляю...");
  try {
    await api("/drafts", { method: "POST", body: JSON.stringify({ text, community_ids: ids, image_attachment: state.imageAttachment }) });
    el.commentText.value = "";
    el.charCounter.textContent = "0 / 4000";
    document.querySelectorAll('input[name="community_ids"]').forEach(i => (i.checked = false));
    resetImage();
    await loadDrafts(); updateStats();
    toast("Черновик создан и ожидает модерации", "ok");
  } catch (e) { toast(e.message, "err"); }
  finally { setBtnLoading(el.submitBtn, false); }
});

// ─── Monitor ──────────────────────────────────────────────────────────────────
el.scanBtn.addEventListener("click", async () => {
  const raw = el.keywordsInput.value.trim();
  if (!raw) { setStatus(el.scanStatus, "Введи ключевые фразы", "err"); return; }
  const keywords = raw.split(",").map(k => k.trim()).filter(Boolean);
  const posts_per_community = Number(el.postsCount.value) || 10;

  setBtnLoading(el.scanBtn, true, "Сканирую...");
  setStatus(el.scanStatus, "Обрабатываю сообщества...", "");
  el.monitorList.innerHTML = `<div class="empty-state-sm"><span class="spin spin-dark"></span><p>Сканирую...</p></div>`;
  state.monitorResults = [];
  state.selectedIdx = null;
  state.parseTypeFilter = "all";
  el.dmSelected.disabled = true;
  el.exportCsvBtn.style.display = "none";
  el.resultsCount.textContent = "";

  try {
    const results = await api("/monitor/scan", { method: "POST", body: JSON.stringify({ keywords, posts_per_community }) });
    state.monitorResults = results;
    state.parseTypeFilter = "all";
    document.querySelectorAll("#parse-filters .tab").forEach(t => t.classList.toggle("active", t.dataset.type === "all"));
    renderMonitorResults();
    el.resultsCount.textContent = results.length ? `· ${results.length} найдено` : "";
    el.exportCsvBtn.style.display = results.length ? "" : "none";
    setStatus(el.scanStatus, results.length ? `Найдено ${results.length} совпадений` : "Совпадений не найдено", results.length ? "ok" : "");
  } catch (e) {
    el.monitorList.innerHTML = "";
    setStatus(el.scanStatus, e.message, "err");
    toast(e.message, "err");
  } finally {
    setBtnLoading(el.scanBtn, false);
  }
});

function renderMonitorResults() {
  const all = state.monitorResults;
  const pairs = state.parseTypeFilter === "all"
    ? all.map((r, i) => ({ r, i }))
    : all.map((r, i) => ({ r, i })).filter(({ r }) => r.type === state.parseTypeFilter);

  if (!all.length) {
    el.monitorList.innerHTML = `<div class="empty-state-sm">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:var(--border)"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <p>Введи фразы и нажми «Сканировать»</p>
    </div>`;
    return;
  }
  if (!pairs.length) {
    el.monitorList.innerHTML = `<div class="empty-state-sm"><p>Нет результатов для этого фильтра</p></div>`;
    return;
  }

  const TRUNC = 220;
  el.monitorList.innerHTML = pairs.map(({ r, i }) => {
    const date = r.date ? new Date(r.date * 1000).toLocaleString("ru-RU", { day:"2-digit", month:"2-digit", year:"2-digit", hour:"2-digit", minute:"2-digit" }) : "";
    const isPost = r.type === "пост";
    const isLong = r.text.length > TRUNC;
    const displayText = isLong ? r.text.slice(0, TRUNC) + "…" : r.text;
    const initials = (r.author_name || "?")[0].toUpperCase();
    const isSelected = state.selectedIdx === i;

    return `<div class="post-card${isSelected ? " selected" : ""}" data-idx="${i}">
      <div class="post-card-top">
        <span class="community-badge">${esc(r.community)}</span>
        <span class="type-badge type-${isPost ? "post" : "comment"}">${esc(r.type)}</span>
        ${date ? `<span class="post-date">${date}</span>` : ""}
      </div>
      <div class="post-author-row">
        <div class="post-avatar">${esc(initials)}</div>
        <span class="post-author-name">${esc(r.author_name)}</span>
      </div>
      <div class="post-text-wrap">
        <p class="post-text">${esc(displayText)}</p>
        ${isLong ? `<button class="btn-link expand-btn" data-idx="${i}" data-full="${esc(r.text)}">Читать далее</button>` : ""}
      </div>
      ${r.photo_urls && r.photo_urls.length ? `<div class="post-photos" data-count="${r.photo_urls.length}">${r.photo_urls.map(u => `<img class="post-photo" src="${esc(u)}" loading="lazy" alt="" />`).join("")}</div>` : ""}
      <div class="post-footer">
        <div class="post-stats">
          ${r.likes ? `<span>&#9825; ${r.likes}</span>` : ""}
          ${r.comments_count ? `<span>&#128172; ${r.comments_count}</span>` : ""}
        </div>
        <div class="post-actions">
          ${r.vk_link ? `<a href="${r.vk_link}" target="_blank" rel="noopener" class="btn btn-ghost btn-xs">Открыть &#8599;</a>` : ""}
          ${r.photo_urls && r.photo_urls.length ? `<button class="btn btn-xs btn-ghost ai-gen-open" data-idx="${i}" data-photo="${esc(r.photo_urls[0])}">✦ AI фото</button>` : ""}
          <button class="btn btn-xs btn-ok select-for-dm" data-idx="${i}">Написать</button>
        </div>
      </div>
    </div>`;
  }).join("");
}

el.monitorList.addEventListener("click", e => {
  const expandBtn = e.target.closest(".expand-btn");
  if (expandBtn) {
    const wrap = expandBtn.closest(".post-text-wrap");
    const p = wrap.querySelector(".post-text");
    if (expandBtn.dataset.expanded === "1") {
      p.textContent = expandBtn.dataset.full.slice(0, 220) + "…";
      expandBtn.textContent = "Читать далее";
      expandBtn.dataset.expanded = "0";
    } else {
      p.textContent = expandBtn.dataset.full;
      expandBtn.textContent = "Свернуть";
      expandBtn.dataset.expanded = "1";
    }
    return;
  }

  if (e.target.closest("a")) return;

  const aiBtn = e.target.closest(".ai-gen-open");
  if (aiBtn) {
    const idx = Number(aiBtn.dataset.idx);
    const r = state.monitorResults[idx];
    state.aiModal = { photoUrl: aiBtn.dataset.photo, authorId: r.author_id, attachment: null, provider: "nanobanana" };
    $("ai-source-img").src = aiBtn.dataset.photo;
    $("ai-result-block").style.display = "none";
    $("ai-result-img").src = "";
    $("ai-send-dm-btn").style.display = "none";
    $("ai-gen-status").textContent = "";
    $("ai-modal").style.display = "flex";
    return;
  }

  const dmBtn = e.target.closest(".select-for-dm");
  const card  = e.target.closest(".post-card");
  if (!card && !dmBtn) return;

  const idx = Number((dmBtn || card).dataset.idx);
  state.selectedIdx = idx;
  document.querySelectorAll(".post-card").forEach(c => c.classList.remove("selected"));
  card?.classList.add("selected");
  el.dmSelected.disabled = false;
  const r = state.monitorResults[idx];
  setStatus(el.dmStatus, `Выбран: ${r.author_name} (ID ${r.author_id})`, "");
});

// ─── Parse filters ────────────────────────────────────────────────────────────
el.parseFilters.addEventListener("click", e => {
  const btn = e.target.closest(".tab");
  if (!btn) return;
  state.parseTypeFilter = btn.dataset.type;
  document.querySelectorAll("#parse-filters .tab").forEach(t => t.classList.remove("active"));
  btn.classList.add("active");
  renderMonitorResults();
});

// ─── CSV export ───────────────────────────────────────────────────────────────
el.exportCsvBtn.addEventListener("click", () => {
  const rows = state.monitorResults;
  if (!rows.length) return;
  const cols = ["community","type","author_name","author_id","date","likes","comments_count","text","vk_link"];
  const header = cols.join(";");
  const lines = rows.map(r => cols.map(k => {
    let v = k === "date" && r[k] ? new Date(r[k] * 1000).toLocaleString("ru-RU") : (r[k] ?? "");
    return `"${String(v).replace(/"/g,'""')}"`;
  }).join(";"));
  const csv = "\uFEFF" + [header, ...lines].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  a.download = `scan_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
});

// ─── DM ──────────────────────────────────────────────────────────────────────
el.dmSelected.addEventListener("click", async () => {
  if (state.selectedIdx === null) return;
  await sendDm([state.monitorResults[state.selectedIdx]]);
});
el.dmAll.addEventListener("click", async () => {
  if (!state.monitorResults.length) { toast("Сначала выполни сканирование", "warn"); return; }
  const seen = new Set();
  const unique = state.monitorResults.filter(r => { if (seen.has(r.author_id)) return false; seen.add(r.author_id); return true; });
  if (!confirm(`Отправить ЛС ${unique.length} уникальным пользователям?`)) return;
  await sendDm(unique);
});

async function sendDm(targets) {
  const msg = el.dmText.value.trim();
  if (!msg) { toast("Напиши текст сообщения", "warn"); return; }
  el.dmSelected.disabled = true;
  el.dmAll.disabled = true;
  let ok = 0; const errors = [];
  for (const t of targets) {
    setStatus(el.dmStatus, `Отправляю ${ok + errors.length + 1} / ${targets.length}...`, "");
    try {
      await api("/monitor/send-dm", { method: "POST", body: JSON.stringify({ user_id: t.author_id, message: msg }) });
      ok++;
    } catch (e) { errors.push(`${t.author_name}: ${e.message}`); }
  }
  el.dmSelected.disabled = state.selectedIdx === null;
  el.dmAll.disabled = false;
  if (errors.length) {
    setStatus(el.dmStatus, `Отправлено: ${ok}, ошибок: ${errors.length}. ${errors[0]}`, "err");
    toast(`Отправлено: ${ok}, ошибок: ${errors.length}`, "warn");
  } else {
    setStatus(el.dmStatus, `Успешно отправлено: ${ok}`, "ok");
    toast(`Отправлено ${ok} сообщений`, "ok");
  }
}

// ─── Autopilot ────────────────────────────────────────────────────────────────
async function loadAutopilotConfig() {
  try {
    const cfg = await api("/autopilot/config");
    el.apEnabled.checked    = cfg.enabled;
    el.apKeywords.value     = cfg.keywords.join("\n");
    el.apInterval.value     = cfg.interval_minutes;
    el.apPosts.value        = cfg.posts_per_community;
    el.apSendDm.checked     = cfg.send_dm;
    el.apDmMsg.value        = cfg.dm_message;
    el.apSendComment.checked = cfg.send_comment;
    el.apCommentMsg.value   = cfg.comment_message;
    el.apDmGroup.classList.toggle("hidden", !cfg.send_dm);
    el.apCommentGroup.classList.toggle("hidden", !cfg.send_comment);
    updateApStatus(cfg.enabled);

    const cc = await api("/autopilot/contacted-count");
    el.apContactedCount.textContent = `Уже написали: ${cc.count} пользователям`;
  } catch (e) { /* ignore on first load */ }
}

function updateApStatus(enabled) {
  el.apDot.classList.toggle("active", enabled);
  el.sApStatus.textContent = enabled ? "Активен" : "Выкл";
  el.statApWrap.style.display = "";
  el.apNavPill.style.display = enabled ? "" : "none";
}

el.apSendDm.addEventListener("change", () => el.apDmGroup.classList.toggle("hidden", !el.apSendDm.checked));
el.apSendComment.addEventListener("change", () => el.apCommentGroup.classList.toggle("hidden", !el.apSendComment.checked));

el.apSaveBtn.addEventListener("click", async () => {
  const keywords = el.apKeywords.value.split(/[\n,]/).map(k => k.trim()).filter(Boolean);
  const cfg = {
    enabled:             el.apEnabled.checked,
    keywords,
    posts_per_community: Number(el.apPosts.value) || 10,
    interval_minutes:    Number(el.apInterval.value) || 60,
    send_dm:             el.apSendDm.checked,
    dm_message:          el.apDmMsg.value.trim(),
    send_comment:        el.apSendComment.checked,
    comment_message:     el.apCommentMsg.value.trim(),
  };
  setBtnLoading(el.apSaveBtn, true, "Сохраняю...");
  try {
    await api("/autopilot/config", { method: "POST", body: JSON.stringify(cfg) });
    updateApStatus(cfg.enabled);
    setStatus(el.apStatus, cfg.enabled
      ? `Автопилот активен · каждые ${cfg.interval_minutes} мин · ключей: ${keywords.length}`
      : "Автопилот выключен", cfg.enabled ? "ok" : "");
    toast("Настройки сохранены", "ok");
  } catch (e) {
    toast(e.message, "err");
  } finally {
    setBtnLoading(el.apSaveBtn, false);
  }
});

el.apRunBtn.addEventListener("click", async () => {
  setBtnLoading(el.apRunBtn, true, "Запускаю...");
  setStatus(el.apStatus, "Сканирую сообщества...", "");
  try {
    const res = await api("/autopilot/run", { method: "POST" });
    setStatus(el.apStatus,
      `Найдено: ${res.found} · ЛС: ${res.dm_sent} · Комм: ${res.comment_sent} · Пропущено: ${res.skipped}`,
      res.errors.length ? "err" : "ok");
    toast(`Готово · ЛС: ${res.dm_sent}, Комментарии: ${res.comment_sent}`, res.errors.length ? "warn" : "ok");
    await loadAutopilotLog();
    const cc = await api("/autopilot/contacted-count");
    el.apContactedCount.textContent = `Уже написали: ${cc.count} пользователям`;
  } catch (e) {
    setStatus(el.apStatus, e.message, "err");
    toast(e.message, "err");
  } finally {
    setBtnLoading(el.apRunBtn, false);
  }
});

el.apClearBtn.addEventListener("click", async () => {
  if (!confirm("Очистить историю контактов? Автопилот снова напишет всем найденным пользователям.")) return;
  try {
    await api("/autopilot/contacted", { method: "DELETE" });
    el.apContactedCount.textContent = "Уже написали: 0 пользователям";
    toast("История контактов очищена", "ok");
  } catch (e) { toast(e.message, "err"); }
});

async function loadAutopilotLog() {
  try {
    const entries = await api("/autopilot/log");
    if (!entries.length) {
      el.apLogList.innerHTML = `<div class="empty-state"><div class="empty-title">Нет запусков</div><div class="empty-copy">Запуски появятся после первого срабатывания</div></div>`;
      return;
    }
    el.apLogList.innerHTML = entries.map(e => {
      const date = new Date(e.run_at).toLocaleString("ru-RU", { day:"2-digit", month:"2-digit", year:"2-digit", hour:"2-digit", minute:"2-digit" });
      const errHtml = e.errors.length
        ? `<div class="ap-log-errors">${e.errors.slice(0,3).map(err => `<div class="ap-log-err">⚠ ${esc(err)}</div>`).join("")}${e.errors.length > 3 ? `<div class="ap-log-err">...и ещё ${e.errors.length - 3}</div>` : ""}</div>`
        : "";
      return `<div class="ap-log-entry">
        <div class="ap-log-date">${date}</div>
        <div class="ap-log-stats">
          <span class="ap-stat ap-stat--found">&#128270; ${e.found} найдено</span>
          <span class="ap-stat ap-stat--dm ok-text">&#10003; ЛС: ${e.dm_sent}</span>
          <span class="ap-stat ap-stat--comment" style="color:var(--accent)">&#10003; Комм: ${e.comment_sent}</span>
          <span class="ap-stat ap-stat--skip muted-text">&#128683; Пропущено: ${e.skipped}</span>
        </div>
        ${errHtml}
      </div>`;
    }).join("");
  } catch (e) { /* ignore */ }
}

function openCaptchaModal({ draftId, ownerId, postId, challengeId }) {
  state.captchaModal = { draftId, ownerId, postId, challengeId };
  el.captchaKey.value = "";
  setStatus(el.captchaStatus, "", "");
  el.captchaImg.src = `/drafts/captcha/${encodeURIComponent(challengeId)}/image?t=${Date.now()}`;
  el.captchaModal.style.display = "flex";
}

function closeCaptchaModal() {
  el.captchaModal.style.display = "none";
  el.captchaImg.src = "";
  state.captchaModal = { draftId: null, ownerId: null, postId: null, challengeId: null };
}

// ─── AI Generate Modal ────────────────────────────────────────────────────────
$("captcha-modal-close").addEventListener("click", closeCaptchaModal);
$("captcha-modal").addEventListener("click", e => { if (e.target === $("captcha-modal")) closeCaptchaModal(); });
el.captchaReloadBtn.addEventListener("click", () => {
  if (!state.captchaModal.challengeId) return;
  el.captchaImg.src = `/drafts/captcha/${encodeURIComponent(state.captchaModal.challengeId)}/image?t=${Date.now()}`;
});
el.captchaSubmitBtn.addEventListener("click", async () => {
  const captcha_key = el.captchaKey.value.trim();
  if (!captcha_key) { setStatus(el.captchaStatus, "Введи код с картинки", "err"); return; }
  const { draftId, ownerId, postId, challengeId } = state.captchaModal;
  if (!draftId || !challengeId) return;
  setBtnLoading(el.captchaSubmitBtn, true, "Проверяю...");
  setStatus(el.captchaStatus, "Отправляю код в VK...", "");
  try {
    const draft = await api(`/drafts/${draftId}/publish-results/${ownerId}/${postId}/solve-captcha`, {
      method: "POST",
      body: JSON.stringify({ captcha_key, challenge_id: challengeId }),
    });
    await loadDrafts(); updateStats();
    const current = draft.publish_results?.find(r => r.vk_owner_id === ownerId && r.vk_post_id === postId);
    if (current?.captcha_challenge_id) {
      state.captchaModal.challengeId = current.captcha_challenge_id;
      el.captchaImg.src = `/drafts/captcha/${encodeURIComponent(current.captcha_challenge_id)}/image?t=${Date.now()}`;
      el.captchaKey.value = "";
      setStatus(el.captchaStatus, current.error || "Капча не принята", "err");
      toast("VK запросил новую капчу", "warn");
      return;
    }
    closeCaptchaModal();
    toast("Капча подтверждена, комментарий отправлен", "ok");
  } catch (e) {
    setStatus(el.captchaStatus, e.message, "err");
  } finally {
    setBtnLoading(el.captchaSubmitBtn, false);
  }
});

$("ai-modal-close").addEventListener("click", () => { $("ai-modal").style.display = "none"; });
$("ai-modal").addEventListener("click", e => { if (e.target === $("ai-modal")) $("ai-modal").style.display = "none"; });

$("ai-provider-tabs").addEventListener("click", e => {
  const btn = e.target.closest(".add-tab");
  if (!btn) return;
  document.querySelectorAll("#ai-provider-tabs .add-tab").forEach(t => t.classList.remove("active"));
  btn.classList.add("active");
  state.aiModal.provider = btn.dataset.provider;
});

$("ai-gen-btn").addEventListener("click", async () => {
  const prompt = $("ai-prompt").value.trim();
  if (!prompt) { setStatus($("ai-gen-status"), "Введи промпт", "err"); return; }
  const { photoUrl } = state.aiModal;
  if (!photoUrl) return;
  const btn = $("ai-gen-btn");
  const providerLabel = state.aiModal.provider === "nanobanana" ? "NanoBanana" : "OpenAI";
  setBtnLoading(btn, true, "Генерация...");
  $("ai-send-dm-btn").style.display = "none";

  let elapsed = 0;
  const timer = setInterval(() => {
    elapsed++;
    setStatus($("ai-gen-status"), `⏳ ${providerLabel} генерирует... ${elapsed}с`, "");
  }, 1000);
  setStatus($("ai-gen-status"), `⏳ ${providerLabel} генерирует... 0с`, "");

  try {
    const data = await api("/monitor/generate-image", {
      method: "POST",
      body: JSON.stringify({ photo_url: photoUrl, prompt, provider: state.aiModal.provider }),
    });
    state.aiModal.attachment = data.attachment;
    $("ai-result-img").src = "data:image/png;base64," + data.image_b64;
    $("ai-result-block").style.display = "block";
    $("ai-send-dm-btn").style.display = "inline-flex";
    setStatus($("ai-gen-status"), `Готово за ${elapsed}с! Изображение загружено в VK.`, "ok");
  } catch (e) {
    setStatus($("ai-gen-status"), e.message, "err");
  } finally {
    clearInterval(timer);
    setBtnLoading(btn, false);
  }
});

$("ai-send-dm-btn").addEventListener("click", async () => {
  const { authorId, attachment } = state.aiModal;
  if (!authorId || !attachment) return;
  const btn = $("ai-send-dm-btn");
  setBtnLoading(btn, true, "Отправка...");
  try {
    await api("/monitor/send-dm", {
      method: "POST",
      body: JSON.stringify({ user_id: authorId, message: "", attachment }),
    });
    setStatus($("ai-gen-status"), "Отправлено в ЛС!", "ok");
    $("ai-send-dm-btn").style.display = "none";
    setTimeout(() => { $("ai-modal").style.display = "none"; }, 1200);
  } catch (e) {
    setStatus($("ai-gen-status"), e.message, "err");
  } finally {
    setBtnLoading(btn, false);
  }
});

// ─── Init ─────────────────────────────────────────────────────────────────────
el.refreshBtn.addEventListener("click", () => refreshAll());

async function refreshAll() {
  setBtnLoading(el.refreshBtn, true, "");
  try {
    await Promise.all([loadCommunities(), loadDrafts()]);
    updateStats();
  } catch (e) { toast("Не удалось загрузить данные: " + e.message, "err"); }
  finally { setBtnLoading(el.refreshBtn, false); }
}

async function checkAuth() {
  try {
    const status = await api("/auth/status");
    if (!status.configured) {
      $("login-overlay").style.display = "flex";
    }
  } catch (e) { /* ignore */ }
}

// Kate Mobile token paste handler
const kateSubmit = $("kate-token-submit");
if (kateSubmit) {
  kateSubmit.addEventListener("click", async () => {
    const raw = $("kate-token-url").value.trim();
    const errEl = $("kate-token-err");
    errEl.style.display = "none";

    // Extract token from URL hash or query string
    let token = null;
    try {
      const hashPart = raw.includes("#") ? raw.split("#")[1] : raw;
      const params = new URLSearchParams(hashPart);
      token = params.get("access_token");
    } catch (e) { /* ignore */ }

    if (!token) {
      errEl.textContent = "Токен не найден. Убедись что скопировал полный URL.";
      errEl.style.display = "block";
      return;
    }

    setBtnLoading(kateSubmit, true, "Сохранение...");
    try {
      await api("/auth/save-token", { method: "POST", body: JSON.stringify({ token }) });
      window.location.href = "/app";
    } catch (e) {
      errEl.textContent = e.message;
      errEl.style.display = "block";
      setBtnLoading(kateSubmit, false);
    }
  });
}

// Load AP status for nav indicator on startup
api("/autopilot/config").then(cfg => { if (cfg) updateApStatus(cfg.enabled); }).catch(() => {});

checkAuth();
refreshAll();
