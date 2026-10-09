(() => {
  "use strict";

  const THEMES = new Set(["gold", "ocean", "jade", "copper", "violet", "pearl"]);
  const THEME_COLORS = {
    gold: "#11130f", ocean: "#07111f", jade: "#071511", copper: "#18100c", violet: "#100d1b", pearl: "#faf8f2",
  };
  const importanceScore = { "重大": 4, "高": 3, "中": 2, "低": 1 };

  const messages = {
    zh: {
      pageTitle: "中国钢铁全球政策情报",
      pageDescription: "每日追踪全球与中国钢铁有关的法规、贸易救济、配额关税、原产地、碳政策与行业新闻。",
      skipLink: "跳至情报列表", brandHome: "返回看板首页", brandSubtitle: "中国钢铁全球政策情报",
      loadingData: "数据载入中", themeLabel: "配色", themeAria: "选择看板配色", rss: "RSS 订阅",
      heroEyebrow: "全球监管雷达 · 每日自动更新",
      heroTitle: "中国钢铁 · <em>全球政策观察</em>",
      heroDeck: "官方政策与行业动态集中跟踪，先看新消息，再看出口业务的重要节点。",
      updatedLabel: "更新：", timezoneLabel: "时区：Europe/Berlin", originalLinks: "保留原文链接",
      radarLabel: "条在库情报", metricsAria: "情报概览", metricNew: "本次新增", metricHigh: "重点 / 待跟进",
      metricOfficial: "官方文件", metricMarkets: "覆盖国家/地区", sourceHealth: "采集状态",
      sourceNote: "单一来源异常不会中断整次更新，历史数据也不会被清空。",
      feedEyebrow: "最新与重点分流，避免重要旧闻压住新动态", allIntelligence: "全部情报", loadingShort: "正在加载…",
      tabLatest: "最新动态", tabPriority: "重点关注", tabAll: "全部归档",
      titleLatest: "最新动态", titlePriority: "重点关注", titleAll: "全部情报",
      firstSeen: "首次收录", sourceDegraded: "降级运行 · 新闻补充暂不可用",
      searchLabel: "搜索情报", searchPlaceholder: "搜索国家、产品、法规或企业…", categoryLabel: "类别",
      regionLabel: "地区", importanceLabel: "重要性", officialOnly: "仅看官方", resetFilters: "清除筛选",
      loadMore: "加载更多", methodEyebrow: "从原文到业务判断",
      methodTitle: "法规优先，新闻补充，<br />每条都能回到原始来源。",
      methodCollect: "<strong>采集</strong>官方公报、政府公告与全球新闻索引",
      methodFilter: "<strong>筛选</strong>中国主体、钢铁品种与普遍性钢铁政策",
      methodAnalyze: "<strong>研判</strong>中英文摘要、状态、重要性与出口影响",
      methodTrace: "<strong>留痕</strong>去重归档，并保留原文链接供复核",
      disclaimer: "机器翻译与摘要仅供业务筛查，不构成法律意见；正式要求以原文及主管机关解释为准。",
      viewGithub: "查看 GitHub 项目", emptyTitle: "没有匹配的情报", emptyCopy: "试试减少筛选条件或使用更短的关键词。",
      allCategories: "全部类别", allRegions: "全部地区", allLevels: "全部级别",
      monitorOk: "监控运行正常", monitorPartial: "部分来源异常", loadFailed: "数据载入失败",
      noLead: "暂无重点情报。", leadLabel: "重点情报", officialSource: "官方来源", mediaSource: "媒体来源",
      impactTitle: "对中国钢厂的影响", readOriginal: "查看官方/原始全文", sourceEmpty: "暂无采集状态。",
      sourceOk: "运行正常", sourceError: "本次异常，已保留历史", official: "官方", impactPrefix: "影响：",
      openOriginal: "打开原文", onlyOfficialChip: "仅官方来源", searchChip: "搜索", levelChip: "级别",
      resultCount: ({ visible, total }) => `显示 ${visible} / ${total} 条`,
      loadErrorTitle: "暂时无法读取数据", loadErrorCopy: "请稍后刷新页面。", leadUnavailable: "重点情报暂不可用。",
      englishPending: "英文分析正在生成，请先查阅原始来源。",
      languageAria: "切换为英文", languageButton: "EN",
      feedbackOpen: "征求意见开放", feedbackOpenUntil: ({ date }) => `征求意见至 ${date}`,
      feedbackUpcoming: "即将征求意见", feedbackUpcomingFrom: ({ date }) => `将于 ${date} 开放`, feedbackClosed: "征求意见已结束",
      themeGold: "黑金", themeOcean: "深海蓝", themeJade: "翡翠绿", themeCopper: "赤铜棕", themeViolet: "紫晶夜", themePearl: "象牙浅色",
    },
    en: {
      pageTitle: "China Steel Global Policy Intelligence",
      pageDescription: "Daily monitoring of global laws, trade remedies, tariff quotas, origin rules, carbon policy and industry news affecting China's steel sector.",
      skipLink: "Skip to intelligence feed", brandHome: "Return to dashboard", brandSubtitle: "China steel global policy intelligence",
      loadingData: "Loading data", themeLabel: "Theme", themeAria: "Choose dashboard theme", rss: "RSS feed",
      heroEyebrow: "Global regulatory radar · Updated daily",
      heroTitle: "China steel. <em>Global policy watch.</em>",
      heroDeck: "Official policy and industry news, with fresh updates and key dates for steel exporters.",
      updatedLabel: "Updated: ", timezoneLabel: "Time zone: Europe/Berlin", originalLinks: "Original links retained",
      radarLabel: "signals on file", metricsAria: "Intelligence overview", metricNew: "New this run", metricHigh: "Priority / follow-up",
      metricOfficial: "Official documents", metricMarkets: "Markets covered", sourceHealth: "Collection status",
      sourceNote: "A single source failure never stops the full update or removes historical records.",
      feedEyebrow: "Separate fresh signals from high-priority items", allIntelligence: "All intelligence", loadingShort: "Loading…",
      tabLatest: "Latest", tabPriority: "Priority", tabAll: "Archive",
      titleLatest: "Latest updates", titlePriority: "Priority watch", titleAll: "All intelligence",
      firstSeen: "First seen", sourceDegraded: "Degraded · news supplement unavailable",
      searchLabel: "Search intelligence", searchPlaceholder: "Search markets, products, rules or companies…", categoryLabel: "Category",
      regionLabel: "Region", importanceLabel: "Priority", officialOnly: "Official only", resetFilters: "Clear filters",
      loadMore: "Load more", methodEyebrow: "From primary source to business judgment",
      methodTitle: "Rules first, news in context,<br />every signal traceable to source.",
      methodCollect: "<strong>Collect</strong>official journals, government notices and global news indexes",
      methodFilter: "<strong>Filter</strong>Chinese entities, steel products and market-wide steel policy",
      methodAnalyze: "<strong>Assess</strong>bilingual briefs, status, priority and export impact",
      methodTrace: "<strong>Trace</strong>deduplicated records with original links for verification",
      disclaimer: "Machine translation and summaries are for business screening only and do not constitute legal advice. Always rely on the original text and the competent authority.",
      viewGithub: "View GitHub project", emptyTitle: "No matching intelligence", emptyCopy: "Try fewer filters or a shorter search term.",
      allCategories: "All categories", allRegions: "All regions", allLevels: "All priorities",
      monitorOk: "Monitor operating normally", monitorPartial: "Some sources need attention", loadFailed: "Data failed to load",
      noLead: "No lead intelligence available.", leadLabel: "Lead intelligence", officialSource: "Official source", mediaSource: "Media source",
      impactTitle: "Impact on Chinese mills", readOriginal: "Open official/original text", sourceEmpty: "No collection status available.",
      sourceOk: "Operating normally", sourceError: "Run failed; history retained", official: "Official", impactPrefix: "Impact: ",
      openOriginal: "Open original source", onlyOfficialChip: "Official sources only", searchChip: "Search", levelChip: "Priority",
      resultCount: ({ visible, total }) => `Showing ${visible} of ${total}`,
      loadErrorTitle: "Data is temporarily unavailable", loadErrorCopy: "Please refresh again shortly.", leadUnavailable: "Lead intelligence is temporarily unavailable.",
      englishPending: "The English analysis is being generated. Please review the original source in the meantime.",
      languageAria: "切换为中文", languageButton: "中文",
      feedbackOpen: "Feedback open", feedbackOpenUntil: ({ date }) => `Feedback until ${date}`,
      feedbackUpcoming: "Feedback upcoming", feedbackUpcomingFrom: ({ date }) => `Opens ${date}`, feedbackClosed: "Feedback closed",
      themeGold: "Black gold", themeOcean: "Deep ocean", themeJade: "Jade green", themeCopper: "Burnished copper", themeViolet: "Violet night", themePearl: "Ivory light",
    },
  };

  Object.assign(messages.zh, {
    topicAll: "全部主题", topicTrade: "关税与贸易救济", topicIndustry: "钢企与市场",
    periodLabel: "时间范围", period7: "近 7 天", period30: "近 30 天", period90: "近 90 天", periodAll: "全部时间",
    sortLabel: "排序依据", sortPublished: "发布时间", sortSeen: "首次收录", newOnly: "仅本次新增",
    notePublished: "按原始发布时间倒序；新发现的旧资料保留在归档中。",
    noteSeen: "按首次收录时间倒序；收录时间不代表新闻发布时间。",
    notePriority: "关注重大、高优先级信息及待跟进节点；重要性为初筛判断。",
    pending: "待补充中文解读", machineTranslated: "机器译文 · 待研判", checked: "已核对原文", excerpt: "查看原文摘录", published: "发布 / 更新",
    followUp: "待跟进", due: "节点", overdue: "已到节点 · 待核对", related: "同题来源",
    analysisOff: "自动摘要未启用；原文采集正常，已核对条目提供中文解读。",
    analysisError: "自动摘要暂不可用；原文照常收录。", analysisOk: "自动摘要已启用。",
    pendingCount: ({count}) => `${count} 条待原文核验`, sourcePartial: "部分渠道异常 · 其余正常",
    machineCount: ({count}) => `${count} 条已附机器译文；业务影响仍待核对。`,
    sourceZero: "运行正常 · 本次无命中", monitorPending: "采集正常 · 摘要待补充",
    pendingCopy: "标题与来源已收录，中文解读待补充。可展开摘录或打开原文。",
    machineCopy: "以下为原文摘录的机器译文，业务影响仍待核对。",
    machineTitleOnly: "标题为机器译文；可展开原文摘录，业务影响仍待核对。",
    lastObserved: "最近收录", lastSuccess: "上次抓取成功",
    sourceTimeout: "接口超时 · 历史保留",
  });
  Object.assign(messages.en, {
    topicAll: "All topics", topicTrade: "Tariffs & trade remedies", topicIndustry: "Companies & markets",
    periodLabel: "Period", period7: "Past 7 days", period30: "Past 30 days", period90: "Past 90 days", periodAll: "All dates",
    sortLabel: "Sort by", sortPublished: "Publication date", sortSeen: "First seen", newOnly: "New this run only",
    notePublished: "Newest publication first. Newly discovered older records remain in the archive.",
    noteSeen: "Newest discovery first. First-seen dates are not publication dates.",
    notePriority: "Critical and high-priority items plus follow-up dates. Priority is an initial assessment.",
    pending: "Brief pending", machineTranslated: "Machine translation · review pending", checked: "Source checked", excerpt: "Source excerpt", published: "Published / updated",
    followUp: "Follow-up", due: "Due", overdue: "Date reached · check outcome", related: "Related source",
    analysisOff: "Automatic briefs are not configured. Source collection continues; checked items have bilingual briefs.",
    analysisError: "Automatic briefs are unavailable. Source collection continues.", analysisOk: "Automatic briefs enabled.",
    pendingCount: ({count}) => `${count} source reviews pending`, sourcePartial: "Some channels failed; others active",
    machineCount: ({count}) => `${count} items have machine translations; business impact still needs review.`,
    sourceZero: "Operating normally · no matches this run", monitorPending: "Collection active · briefs pending",
    pendingCopy: "Title and source collected. Analysis is pending; expand the excerpt or open the original.",
    machineCopy: "Machine translation of the source excerpt. Business impact is under review.",
    machineTitleOnly: "The title is machine translated; expand the source excerpt. Business impact needs review.",
    lastObserved: "Last captured", lastSuccess: "Last successful collection",
    sourceTimeout: "Source timed out · history retained",
  });

  const englishLabels = {
    category: {
      "法规与正式文件": "Laws & official documents", "贸易救济": "Trade remedies", "配额与关税": "Quotas & tariffs",
      "碳与环保": "Carbon & environment", "原产地与海关": "Origin & customs", "产业政策": "Industrial policy",
      "市场与产能": "Market & capacity", "企业与供应链": "Companies & supply chain",
    },
    status: {
      "已生效": "In force", "拟议": "Proposed", "调查中": "Under investigation", "临时措施": "Provisional measure",
      "待核对": "To verify", "终裁": "Final determination", "审查中": "Under review", "新闻": "News",
    },
    importance: { "重大": "Critical", "高": "High", "中": "Medium", "低": "Low" },
    region: {
      "欧洲": "Europe", "北美": "North America", "亚洲": "Asia", "非洲": "Africa", "拉美": "Latin America",
      "中东": "Middle East", "大洋洲": "Oceania", "全球": "Global",
    },
    country: {
      "中国": "China", "欧盟": "European Union", "美国": "United States", "英国": "United Kingdom", "德国": "Germany",
      "法国": "France", "意大利": "Italy", "西班牙": "Spain", "印度": "India", "土耳其": "Türkiye", "加拿大": "Canada",
      "澳大利亚": "Australia", "巴西": "Brazil", "日本": "Japan", "韩国": "South Korea", "墨西哥": "Mexico",
      "越南": "Vietnam", "全球": "Global", "测试国": "Test market",
    },
  };

  const readPreference = (key, fallback) => {
    try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
  };
  const writePreference = (key, value) => {
    try { localStorage.setItem(key, value); } catch { /* Preferences are optional. */ }
  };
  const state = {
    items: [], status: null, generatedAt: "", pageSize: 12, visible: 12, feedMode: "latest", topic: "all",
    lang: readPreference("steelwatch-language", "zh") === "en" ? "en" : "zh",
    theme: THEMES.has(readPreference("steelwatch-theme", "pearl")) ? readPreference("steelwatch-theme", "pearl") : "pearl",
  };
  const $ = (selector) => document.querySelector(selector);
  const elements = {
    live: $("#live-state"), updated: $("#updated-at"), radar: $("#radar-count"),
    metricNew: $("#metric-new"), metricHigh: $("#metric-high"), metricOfficial: $("#metric-official"), metricMarkets: $("#metric-markets"),
    period: $("#period"), sort: $("#sort"), newOnly: $("#new-only"), topicFilters: $("#topic-filters"),
    feedNote: $("#feed-note"), analysis: $("#analysis-state"),
    lead: $("#lead-card"), sources: $("#source-list"), grid: $("#card-grid"), count: $("#result-count"),
    category: $("#category"), region: $("#region"), importance: $("#importance"), search: $("#search"), official: $("#official-only"),
    filters: $("#filters"), active: $("#active-filters"), loadMore: $("#load-more"), theme: $("#theme-select"), language: $("#language-toggle"),
    feedTabs: $("#feed-tabs"), intelligenceTitle: $("#intelligence-title"),
  };

  function t(key, values = {}) {
    const value = messages[state.lang][key] ?? messages.zh[key] ?? key;
    return typeof value === "function" ? value(values) : value;
  }

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

  function label(group, value) {
    return state.lang === "en" ? englishLabels[group]?.[value] || value : value;
  }

  function sourceName(item) {
    const value = item.source?.name || "";
    return state.lang === "en" && value.includes(" / ") ? value.split(" / ")[0] : value;
  }

  function itemTitle(item) {
    return state.lang === "en"
      ? item.title_en || item.title_original || item.title_zh
      : item.translation_state === "complete" ? item.title_zh || item.title_original
        : item.machine_translation?.title_zh || item.title_original;
  }

  function itemSummary(item) {
    if (item.translation_state !== "complete") {
      if (state.lang === "en") return item.source_excerpt || t("pendingCopy");
      return item.machine_translation?.excerpt_zh
        ? `${t("machineCopy")} ${item.machine_translation.excerpt_zh}`
        : item.machine_translation ? t("machineTitleOnly") : t("pendingCopy");
    }
    if (state.lang === "zh") return item.summary_zh || "";
    return item.summary_en || `${sourceName(item)} — ${item.title_original || item.title_zh}`;
  }

  function itemImpact(item) {
    return state.lang === "en" ? item.impact_en || t("englishPending") : item.impact_zh || "";
  }

  function localizedTags(item) {
    if (state.lang === "zh") return [...(item.products || []), ...(item.tags || [])];
    return [...(item.products_en || []), ...(item.tags_en || [])];
  }

  function consultationText(item) {
    const consultation = item.consultation;
    if (!consultation?.status) return "";
    if (consultation.status === "OPEN") {
      return consultation.closes_at
        ? t("feedbackOpenUntil", { date: berlinDate(consultation.closes_at) })
        : t("feedbackOpen");
    }
    if (consultation.status === "UPCOMING") {
      return consultation.opens_at
        ? t("feedbackUpcomingFrom", { date: berlinDate(consultation.opens_at) })
        : t("feedbackUpcoming");
    }
    if (consultation.status === "CLOSED") return t("feedbackClosed");
    return "";
  }

  function consultationBadge(item) {
    const value = consultationText(item);
    if (!value) return "";
    const openClass = item.consultation?.status === "OPEN" ? " feedback-open" : "";
    return `<span class="badge${openClass}">${escapeHtml(value)}</span>`;
  }

  function berlinDate(value, withTime = false) {
    if (!value) return "—";
    const options = withTime
      ? { timeZone: "Europe/Berlin", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }
      : { timeZone: "Europe/Berlin", year: "numeric", month: "2-digit", day: "2-digit" };
    return new Intl.DateTimeFormat(state.lang === "en" ? "en-GB" : "zh-CN", options)
      .format(new Date(value)).replaceAll("/", "-");
  }

  function sourceLabel(item) {
    const kind = item.source?.kind;
    if (state.lang === "en") return kind === "official-law" ? "Formal law" : kind === "official-notice" ? "Official notice" : "Industry news";
    return kind === "official-law" ? "正式法规" : kind === "official-notice" ? "官方公告" : "行业新闻";
  }

  function setOptions(select, values, emptyKey, group) {
    const current = select.value;
    const option = document.createElement("option");
    option.value = ""; option.textContent = t(emptyKey);
    select.replaceChildren(option);
    [...new Set(values.filter(Boolean))]
      .sort((a, b) => label(group, a).localeCompare(label(group, b), state.lang === "en" ? "en" : "zh-CN"))
      .forEach((value) => {
        const next = document.createElement("option");
        next.value = value; next.textContent = label(group, value); select.append(next);
      });
    select.value = [...select.options].some((item) => item.value === current) ? current : "";
  }

  function rebuildFilterOptions() {
    setOptions(elements.category, state.items.map((item) => item.category), "allCategories", "category");
    setOptions(elements.region, state.items.map((item) => item.region), "allRegions", "region");
    setOptions(elements.importance, ["重大", "高", "中", "低"], "allLevels", "importance");
  }

  function translateThemeOptions() {
    const keys = { gold: "themeGold", ocean: "themeOcean", jade: "themeJade", copper: "themeCopper", violet: "themeViolet", pearl: "themePearl" };
    [...elements.theme.options].forEach((option) => { option.textContent = t(keys[option.value]); });
  }

  function applyStaticTranslations() {
    document.documentElement.lang = state.lang === "en" ? "en" : "zh-CN";
    document.title = t("pageTitle");
    const description = document.querySelector('meta[name="description"]');
    if (description) description.content = t("pageDescription");
    document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
    document.querySelectorAll("[data-i18n-html]").forEach((node) => { node.innerHTML = t(node.dataset.i18nHtml); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => { node.placeholder = t(node.dataset.i18nPlaceholder); });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => { node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel)); });
    translateThemeOptions();
    elements.language.textContent = t("languageButton");
    elements.language.setAttribute("aria-label", t("languageAria"));
    elements.language.setAttribute("aria-pressed", String(state.lang === "en"));
  }

  function applyTheme(theme) {
    state.theme = THEMES.has(theme) ? theme : "gold";
    document.documentElement.dataset.theme = state.theme;
    elements.theme.value = state.theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLORS[state.theme]);
    writePreference("steelwatch-theme", state.theme);
  }

  function renderSystemState() {
    if (!state.status) {
      elements.live.innerHTML = `<i></i><span>${escapeHtml(t("loadingData"))}</span>`;
      return;
    }
    const partial = !state.status.run_ok || (state.status.sources || []).some((source) => !source.ok || source.warnings?.length);
    const pending = state.status.pending_analysis > 0;
    elements.live.classList.toggle("ok", !partial && !pending);
    elements.live.classList.toggle("error", partial);
    elements.live.innerHTML = `<i></i><span>${escapeHtml(t(partial ? "monitorPartial" : pending ? "monitorPending" : "monitorOk"))}</span>`;
    const analysisKey = state.status.analysis_status === "available" ? "analysisOk" : state.status.analysis_status === "degraded" ? "analysisError" : "analysisOff";
    const machineCount = state.status.machine_translated_items || 0;
    elements.analysis.textContent = `${t(analysisKey)} ${machineCount ? t("machineCount", {count: machineCount}) : ""} ${t("pendingCount", {count: state.status.pending_analysis || 0})}`;

  }

  function renderMetrics() {
    const countries = new Set(state.items.map((item) => item.country).filter(Boolean));
    const high = state.items.filter(isPriority).length;
    const official = state.items.filter((item) => item.source?.official).length;
    elements.metricNew.textContent = state.status?.new_items ?? 0;
    elements.metricHigh.textContent = high;
    elements.metricOfficial.textContent = official;
    elements.metricMarkets.textContent = countries.size;
    elements.radar.textContent = state.items.length;
  }

  function pickLead() {
    return state.items.filter((item) => item.translation_state === "complete" && isPriority(item)).sort((a, b) => {
      const official = Number(Boolean(b.source?.official)) - Number(Boolean(a.source?.official));
      const importance = (importanceScore[b.importance] || 0) - (importanceScore[a.importance] || 0);
      return new Date(b.published_at) - new Date(a.published_at) || importance || official;
    })[0];
  }

  function renderLead() {
    const item = pickLead();
    if (!item) { elements.lead.innerHTML = `<p>${escapeHtml(t("noLead"))}</p>`; return; }
    elements.lead.innerHTML = `
      <div class="lead-top">
        <span class="lead-label">${escapeHtml(t("leadLabel"))} · ${escapeHtml(label("importance", item.importance))}</span>
        <span class="lead-badges"><span class="badge ${item.source?.official ? "official" : ""}">${escapeHtml(item.source?.official ? t("officialSource") : t("mediaSource"))}</span>${consultationBadge(item)}</span>
      </div>
      <h2>${escapeHtml(itemTitle(item))}</h2>
      <p class="lead-summary">${escapeHtml(itemSummary(item))}</p>
      <div class="lead-impact"><b>${escapeHtml(t("impactTitle"))}</b><span>${escapeHtml(itemImpact(item))}</span></div>
      <div class="lead-footer">
        <span class="source-line"><b>${escapeHtml(sourceName(item))}</b><br>${berlinDate(item.published_at)} · ${escapeHtml(label("status", item.status))}</span>
        <a class="primary-link" href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(t("readOriginal"))} <span aria-hidden="true">↗</span></a>
      </div>`;
  }

  function renderSources() {
    const sources = state.status?.sources || [];
    if (!sources.length) { elements.sources.innerHTML = `<p class="source-note">${escapeHtml(t("sourceEmpty"))}</p>`; return; }
    elements.sources.innerHTML = sources.map((source) => {
      const statusText = !source.ok ? t(/timeout/i.test(source.error || "") ? "sourceTimeout" : "sourceError") : source.warnings?.length ? t("sourcePartial") : t(source.count ? "sourceOk" : "sourceZero");
      return `
      <div class="source-item" title="${escapeHtml(source.error || source.warnings?.join("; ") || statusText)}">
        <i class="source-dot ${source.ok && !source.warnings?.length ? "" : "bad"}"></i>
        <span><strong>${escapeHtml(state.lang === "en" && source.name.includes(" / ") ? source.name.split(" / ")[0] : source.name)}</strong><small>${escapeHtml(statusText)}</small>${!source.ok && (source.last_success_at || source.last_observed_at) ? `<small>${escapeHtml(t(source.last_success_at ? "lastSuccess" : "lastObserved"))} ${berlinDate(source.last_success_at || source.last_observed_at)}</small>` : ""}</span>
        <b class="source-count">${Number(source.count || 0)}</b>
      </div>`;
    }).join("");
  }

  function isPriority(item) {
    return (importanceScore[item.importance] || 0) >= 3 || Boolean(item.follow_up) || Boolean(item.priority_signal);
  }

  function topicMatch(item) {
    const text = [item.title_zh, item.title_original, item.machine_translation?.title_zh,
      ...(item.tags || [])].join(" ").toLowerCase();
    if (state.topic === "cbam") return /cbam|碳边境/.test(text);
    if (state.topic === "ets") return /eu ets|uk ets|emissions trading|排放交易/.test(text);
    if (state.topic === "trade") return ["贸易救济", "配额与关税", "原产地与海关"].includes(item.category);
    if (state.topic === "industry") return ["市场与产能", "企业与供应链", "产业政策"].includes(item.category);
    return true;
  }

  function applyFeedMode(items) {
    const field = elements.sort.value === "seen" ? "first_seen" : "published_at";
    const reference = Date.now();
    const days = Number(elements.period.value);
    return items.filter((item) => {
      const date = new Date(item[field] || item.published_at).getTime();
      return (state.feedMode !== "priority" || isPriority(item))
        && (!days || date >= reference - days * 86400000)
        && date <= reference + 86400000
        && (!elements.newOnly.checked || item.first_seen === state.generatedAt)
        && topicMatch(item);
    }).sort((a, b) => new Date(b[field] || b.published_at) - new Date(a[field] || a.published_at));
  }

  function followUp(item) {
    if (!item.follow_up) return "";
    const task = item.follow_up;
    const overdue = Date.now() > new Date(`${task.due_at}T23:59:59+02:00`).getTime();
    const text = state.lang === "en" ? task.action_en : task.action_zh;
    return `<div class="follow-up"><b>${escapeHtml(t(overdue ? "overdue" : "followUp"))} · ${escapeHtml(task.due_at)}</b><span>${escapeHtml(text)}</span></div>`;
  }

  function filteredItems() {
    const query = elements.search.value.trim().toLowerCase();
    const filtered = state.items.filter((item) => {
      const text = [item.title_zh, item.title_en, item.title_original, item.summary_zh, item.summary_en, item.impact_zh, item.impact_en,
        item.machine_translation?.title_zh, item.machine_translation?.excerpt_zh,
        item.country, item.region, item.category, ...(item.products || []), ...(item.products_en || []), ...(item.tags || []), ...(item.tags_en || [])]
        .join(" ").toLowerCase();
      return (!query || text.includes(query))
        && (!elements.category.value || item.category === elements.category.value)
        && (!elements.region.value || item.region === elements.region.value)
        && (!elements.importance.value || item.importance === elements.importance.value)
        && (!elements.official.checked || item.source?.official);
    });
    return applyFeedMode(filtered);
  }

  function card(item) {
    const tags = localizedTags(item).slice(0, 4);
    const importance = label("importance", item.importance);
    return `<article class="intel-card" data-importance="${escapeHtml(item.importance)}">
      <div class="card-head">
        <div class="badge-row">
          ${item.translation_state === "complete" ? `<span class="badge importance-${escapeHtml(item.importance)}">${escapeHtml(importance)}</span>` : `<span class="badge pending">${escapeHtml(t(item.machine_translation ? "machineTranslated" : "pending"))}</span>`}
          ${item.priority_signal ? `<span class="badge official">${escapeHtml(item.priority_signal[state.lang] || item.priority_signal.zh)}</span>` : ""}
          <span class="badge ${item.source?.official ? "official" : ""}">${escapeHtml(item.source?.official ? t("official") : label("status", item.status))}</span>
          <span class="badge">${escapeHtml(label("category", item.category))}</span>
          ${consultationBadge(item)}
          ${item.review_method === "source_checked" ? `<span class="badge official">${escapeHtml(t("checked"))}</span>` : ""}
        </div>
        <time class="card-date" datetime="${escapeHtml(item.published_at)}">${escapeHtml(t("published"))} ${berlinDate(item.published_at)}</time>
      </div>
      <h3>${escapeHtml(itemTitle(item))}</h3>
      <p class="card-summary">${escapeHtml(itemSummary(item))}</p>
      ${item.translation_state === "complete" ? `<p class="card-impact"><b>${escapeHtml(t("impactPrefix"))}</b>${escapeHtml(itemImpact(item))}</p>` : ""}
      ${item.review_method === "source_checked" ? `<p class="card-evidence"><b>${state.lang === "zh" ? "核验范围：" : "Coverage: "}</b>${escapeHtml(typeof item.coverage === "object" ? (item.coverage[state.lang] || item.coverage.zh || "") : (item.coverage || (state.lang === "zh" ? "未注明，请核对原文" : "Not specified; check the source")))} · ${escapeHtml(item.reviewed_at || "")} ${item.evidence_url ? `<a href="${safeUrl(item.evidence_url)}" target="_blank" rel="noopener noreferrer">${state.lang === "zh" ? "证据原文" : "Evidence"}</a>` : ""}</p>` : ""}
      ${item.review_note_zh ? `<p class="card-evidence"><b>${state.lang === "zh" ? "待核验原因：" : "Review blocker: "}</b>${escapeHtml(state.lang === "en" ? (item.review_note_en || item.review_note_zh) : item.review_note_zh)} · ${escapeHtml(item.review_attempted_at || "")}</p>` : ""}
      ${followUp(item)}
      ${item.source_excerpt ? `<details class="source-excerpt"><summary>${escapeHtml(t("excerpt"))}</summary><p>${escapeHtml(item.source_excerpt)}</p></details>` : ""}
      ${(item.related_sources || []).map((source) => `<a class="related-source" href="${safeUrl(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(t("related"))}: ${escapeHtml(source.name)}</a>`).join("")}

      <div class="card-tags">${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
      <div class="card-bottom">
        <span class="card-source"><strong>${escapeHtml(sourceName(item))}</strong><small>${escapeHtml(label("country", item.country))} · ${escapeHtml(sourceLabel(item))}</small><small>${escapeHtml(t("firstSeen"))} ${berlinDate(item.first_seen || item.published_at)}</small></span>
        <a class="original-link" href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHtml(t("openOriginal"))}: ${escapeHtml(itemTitle(item))}">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5M19 5l-9 9m7-1v6H5V7h6" /></svg>
        </a>
      </div>
    </article>`;
  }

  function renderActiveFilters() {
    const chips = [];
    if (elements.search.value.trim()) chips.push(`${t("searchChip")}：${elements.search.value.trim()}`);
    if (elements.category.value) chips.push(label("category", elements.category.value));
    if (elements.region.value) chips.push(label("region", elements.region.value));
    if (elements.importance.value) chips.push(`${t("levelChip")}：${label("importance", elements.importance.value)}`);
    if (elements.official.checked) chips.push(t("onlyOfficialChip"));
    elements.active.innerHTML = chips.map((value) => `<span class="filter-chip">${escapeHtml(value)}</span>`).join("");
  }

  function emptyState(symbol, title, copy) {
    return `<div class="empty-state"><span>${escapeHtml(symbol)}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(copy)}</p></div>`;
  }

  function renderCards() {
    const titleKey = state.feedMode === "latest" ? "titleLatest" : state.feedMode === "priority" ? "titlePriority" : "titleAll";
    elements.intelligenceTitle.textContent = t(titleKey);
    elements.feedNote.textContent = t(state.feedMode === "priority" ? "notePriority" : elements.sort.value === "seen" ? "noteSeen" : "notePublished");
    elements.topicFilters.querySelectorAll("[data-topic]").forEach((button) => {
      button.classList.toggle("active", button.dataset.topic === state.topic);
      button.setAttribute("aria-pressed", String(button.dataset.topic === state.topic));
    });
    [...elements.feedTabs.querySelectorAll("[data-feed-mode]")].forEach((button) => {
      const active = button.dataset.feedMode === state.feedMode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const items = filteredItems();
    const visible = items.slice(0, state.visible);
    elements.count.textContent = t("resultCount", { visible: visible.length, total: items.length });
    elements.grid.innerHTML = visible.length ? visible.map(card).join("") : emptyState("∅", t("emptyTitle"), t("emptyCopy"));
    elements.loadMore.hidden = visible.length >= items.length;
    renderActiveFilters();
  }

  function renderAll() {
    renderSystemState();
    elements.updated.textContent = berlinDate(state.generatedAt, true);
    renderMetrics(); renderLead(); renderSources(); renderCards();
  }

  function setLanguage(language) {
    state.lang = language === "en" ? "en" : "zh";
    writePreference("steelwatch-language", state.lang);
    applyStaticTranslations();
    if (state.items.length) rebuildFilterOptions();
    renderAll();
  }

  function bindPreferences() {
    elements.theme.addEventListener("change", () => applyTheme(elements.theme.value));
    elements.language.addEventListener("click", () => setLanguage(state.lang === "zh" ? "en" : "zh"));
  }

  function bindFilters() {
    let timer;
    elements.search.addEventListener("input", () => {
      clearTimeout(timer); timer = setTimeout(() => { state.visible = state.pageSize; renderCards(); }, 120);
    });
    [elements.category, elements.region, elements.importance, elements.official, elements.period, elements.sort, elements.newOnly].forEach((element) => {
      element.addEventListener("change", () => { state.visible = state.pageSize; renderCards(); });
    });
    elements.filters.addEventListener("reset", () => setTimeout(() => { state.visible = state.pageSize; state.topic = "all"; elements.newOnly.checked = false; renderCards(); }, 0));
    elements.topicFilters.addEventListener("click", (event) => {
      const button = event.target.closest("[data-topic]");
      if (!button) return;
      state.topic = button.dataset.topic; state.visible = state.pageSize; renderCards();
    });
    document.querySelectorAll("[data-metric]").forEach((button) => button.addEventListener("click", () => {
      elements.filters.reset();
      setTimeout(() => {
        const metric = button.dataset.metric;
        state.feedMode = metric === "priority" ? "priority" : "all";
        elements.period.value = "0"; elements.newOnly.checked = metric === "new";
        elements.official.checked = metric === "official";
        state.visible = state.pageSize; renderCards(); $("#intelligence").scrollIntoView({behavior: "smooth"});
      }, 0);
    }));
    elements.loadMore.addEventListener("click", () => { state.visible += state.pageSize; renderCards(); });
    elements.feedTabs.addEventListener("click", (event) => {
      const button = event.target.closest("[data-feed-mode]");
      if (!button) return;
      state.feedMode = button.dataset.feedMode || "latest";
      elements.period.value = state.feedMode === "latest" ? "7" : "0";
      elements.newOnly.checked = false;
      state.visible = state.pageSize;
      renderCards();
    });
  }

  async function load() {
    bindFilters(); bindPreferences(); applyTheme(state.theme); applyStaticTranslations(); renderSystemState();
    try {
      const [itemsResponse, statusResponse] = await Promise.all([
        fetch("./data/items.json", { cache: "no-store" }), fetch("./data/status.json", { cache: "no-store" }),
      ]);
      if (!itemsResponse.ok || !statusResponse.ok) throw new Error("data unavailable");
      const payload = await itemsResponse.json();
      state.status = await statusResponse.json();
      state.generatedAt = payload.generated_at;
      state.items = (payload.items || []).filter((item) => !["excluded", "duplicate"].includes(item.review_disposition));
      rebuildFilterOptions(); renderAll();
    } catch (error) {
      elements.live.classList.add("error"); elements.live.innerHTML = `<i></i><span>${escapeHtml(t("loadFailed"))}</span>`;
      elements.grid.innerHTML = emptyState("!", t("loadErrorTitle"), t("loadErrorCopy"));
      elements.lead.innerHTML = `<p>${escapeHtml(t("leadUnavailable"))}</p>`;
    }
  }

  load();
})();
