(() => {
  "use strict";

  const state = { items: [], status: null, pageSize: 12, visible: 12 };
  const importanceScore = { "重大": 4, "高": 3, "中": 2, "低": 1 };
  const $ = (selector) => document.querySelector(selector);
  const elements = {
    live: $("#live-state"), updated: $("#updated-at"), radar: $("#radar-count"),
    metricNew: $("#metric-new"), metricHigh: $("#metric-high"),
    metricOfficial: $("#metric-official"), metricMarkets: $("#metric-markets"),
    lead: $("#lead-card"), sources: $("#source-list"), grid: $("#card-grid"),
    count: $("#result-count"), category: $("#category"), region: $("#region"),
    importance: $("#importance"), search: $("#search"), official: $("#official-only"),
    filters: $("#filters"), active: $("#active-filters"), loadMore: $("#load-more"),
  };

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    })[character]);
  }

  function safeUrl(value) {
    try {
      const parsed = new URL(value);
      return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : "#";
    } catch { return "#"; }
  }

  function berlinDate(value, withTime = false) {
    if (!value) return "—";
    const options = withTime
      ? { timeZone: "Europe/Berlin", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }
      : { timeZone: "Europe/Berlin", year: "numeric", month: "2-digit", day: "2-digit" };
    return new Intl.DateTimeFormat("zh-CN", options).format(new Date(value)).replaceAll("/", "-");
  }

  function sourceLabel(item) {
    const kind = item.source?.kind;
    return kind === "official-law" ? "正式法规" : kind === "official-notice" ? "官方公告" : "行业新闻";
  }

  function optionList(select, values) {
    const current = select.value;
    [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-CN"))
      .forEach((value) => {
        const option = document.createElement("option");
        option.value = value; option.textContent = value; select.append(option);
      });
    select.value = current;
  }

  function renderMetrics() {
    const countries = new Set(state.items.map((item) => item.country).filter(Boolean));
    const high = state.items.filter((item) => ["重大", "高"].includes(item.importance)).length;
    const official = state.items.filter((item) => item.source?.official).length;
    elements.metricNew.textContent = state.status?.new_items ?? 0;
    elements.metricHigh.textContent = high;
    elements.metricOfficial.textContent = official;
    elements.metricMarkets.textContent = countries.size;
    elements.radar.textContent = state.items.length;
  }

  function pickLead() {
    return [...state.items].sort((a, b) => {
      const official = Number(Boolean(b.source?.official)) - Number(Boolean(a.source?.official));
      const importance = (importanceScore[b.importance] || 0) - (importanceScore[a.importance] || 0);
      return importance || official || new Date(b.published_at) - new Date(a.published_at);
    })[0];
  }

  function renderLead() {
    const item = pickLead();
    if (!item) { elements.lead.innerHTML = "<p>暂无重点情报。</p>"; return; }
    elements.lead.innerHTML = `
      <div class="lead-top">
        <span class="lead-label">重点情报 · ${escapeHtml(item.importance)}</span>
        <span class="badge ${item.source?.official ? "official" : ""}">${item.source?.official ? "官方来源" : "媒体来源"}</span>
      </div>
      <h2>${escapeHtml(item.title_zh)}</h2>
      <p class="lead-summary">${escapeHtml(item.summary_zh)}</p>
      <div class="lead-impact"><b>对中国钢厂的影响</b><span>${escapeHtml(item.impact_zh)}</span></div>
      <div class="lead-footer">
        <span class="source-line"><b>${escapeHtml(item.source?.name)}</b><br>${berlinDate(item.published_at)} · ${escapeHtml(item.status)}</span>
        <a class="primary-link" href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer">查看官方/原始全文 <span aria-hidden="true">↗</span></a>
      </div>`;
  }

  function renderSources() {
    const sources = state.status?.sources || [];
    if (!sources.length) { elements.sources.innerHTML = '<p class="source-note">暂无采集状态。</p>'; return; }
    elements.sources.innerHTML = sources.map((source) => `
      <div class="source-item" title="${escapeHtml(source.error || "运行正常")}">
        <i class="source-dot ${source.ok ? "" : "bad"}"></i>
        <span><strong>${escapeHtml(source.name)}</strong><small>${source.ok ? "运行正常" : "本次异常，已保留历史"}</small></span>
        <b class="source-count">${Number(source.count || 0)}</b>
      </div>`).join("");
  }

  function filteredItems() {
    const query = elements.search.value.trim().toLowerCase();
    return state.items.filter((item) => {
      const text = [item.title_zh, item.title_original, item.summary_zh, item.impact_zh, item.country,
        item.region, item.category, ...(item.products || []), ...(item.tags || [])].join(" ").toLowerCase();
      return (!query || text.includes(query))
        && (!elements.category.value || item.category === elements.category.value)
        && (!elements.region.value || item.region === elements.region.value)
        && (!elements.importance.value || item.importance === elements.importance.value)
        && (!elements.official.checked || item.source?.official);
    });
  }

  function card(item) {
    const tags = [...(item.products || []), ...(item.tags || [])].slice(0, 4);
    return `<article class="intel-card" data-importance="${escapeHtml(item.importance)}">
      <div class="card-head">
        <div class="badge-row">
          <span class="badge importance-${escapeHtml(item.importance)}">${escapeHtml(item.importance === "高" ? "高关注" : item.importance)}</span>
          <span class="badge ${item.source?.official ? "official" : ""}">${item.source?.official ? "官方" : escapeHtml(item.status)}</span>
          <span class="badge">${escapeHtml(item.category)}</span>
        </div>
        <time class="card-date" datetime="${escapeHtml(item.published_at)}">${berlinDate(item.published_at)}</time>
      </div>
      <h3>${escapeHtml(item.title_zh)}</h3>
      <p class="card-summary">${escapeHtml(item.summary_zh)}</p>
      <p class="card-impact"><b>影响：</b>${escapeHtml(item.impact_zh)}</p>
      <div class="card-tags">${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
      <div class="card-bottom">
        <span class="card-source"><strong>${escapeHtml(item.source?.name)}</strong><small>${escapeHtml(item.country)} · ${sourceLabel(item)}</small></span>
        <a class="original-link" href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer" aria-label="打开原文：${escapeHtml(item.title_zh)}">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5M19 5l-9 9m7-1v6H5V7h6" /></svg>
        </a>
      </div>
    </article>`;
  }

  function renderActiveFilters() {
    const chips = [];
    if (elements.search.value.trim()) chips.push(`搜索：${elements.search.value.trim()}`);
    if (elements.category.value) chips.push(elements.category.value);
    if (elements.region.value) chips.push(elements.region.value);
    if (elements.importance.value) chips.push(`级别：${elements.importance.value}`);
    if (elements.official.checked) chips.push("仅官方来源");
    elements.active.innerHTML = chips.map((value) => `<span class="filter-chip">${escapeHtml(value)}</span>`).join("");
  }

  function renderCards() {
    const items = filteredItems();
    const visible = items.slice(0, state.visible);
    elements.count.textContent = `显示 ${visible.length} / ${items.length} 条`;
    elements.grid.innerHTML = visible.length
      ? visible.map(card).join("")
      : $("#empty-template").innerHTML;
    elements.loadMore.hidden = visible.length >= items.length;
    renderActiveFilters();
  }

  function bindFilters() {
    let timer;
    elements.search.addEventListener("input", () => {
      clearTimeout(timer); timer = setTimeout(() => { state.visible = state.pageSize; renderCards(); }, 120);
    });
    [elements.category, elements.region, elements.importance, elements.official].forEach((element) => {
      element.addEventListener("change", () => { state.visible = state.pageSize; renderCards(); });
    });
    elements.filters.addEventListener("reset", () => setTimeout(() => { state.visible = state.pageSize; renderCards(); }, 0));
    elements.loadMore.addEventListener("click", () => { state.visible += state.pageSize; renderCards(); });
  }

  async function load() {
    bindFilters();
    try {
      const [itemsResponse, statusResponse] = await Promise.all([
        fetch("./data/items.json", { cache: "no-store" }),
        fetch("./data/status.json", { cache: "no-store" }),
      ]);
      if (!itemsResponse.ok || !statusResponse.ok) throw new Error("data unavailable");
      const payload = await itemsResponse.json();
      state.status = await statusResponse.json();
      state.items = (payload.items || []).sort((a, b) => {
        const score = (importanceScore[b.importance] || 0) - (importanceScore[a.importance] || 0);
        return score || new Date(b.published_at) - new Date(a.published_at);
      });
      elements.live.classList.add(state.status.run_ok ? "ok" : "error");
      elements.live.innerHTML = `<i></i>${state.status.run_ok ? "监控运行正常" : "部分来源异常"}`;
      elements.updated.textContent = berlinDate(payload.generated_at, true);
      optionList(elements.category, state.items.map((item) => item.category));
      optionList(elements.region, state.items.map((item) => item.region));
      renderMetrics(); renderLead(); renderSources(); renderCards();
    } catch (error) {
      elements.live.classList.add("error"); elements.live.innerHTML = "<i></i>数据载入失败";
      elements.grid.innerHTML = '<div class="empty-state"><span>!</span><h3>暂时无法读取数据</h3><p>请稍后刷新页面。</p></div>';
      elements.lead.innerHTML = "<p>重点情报暂不可用。</p>";
    }
  }

  load();
})();
