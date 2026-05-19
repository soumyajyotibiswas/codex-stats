(function () {
  const STORAGE_KEY = "codexUsageDashboardPrefs";
  const RANGE_OPTIONS = {
    "7d": { days: 7, label: "7 days", shortLabel: "7D", chartWidth: 920, chartHeight: 340 },
    "30d": { days: 30, label: "1 month", shortLabel: "1M", chartWidth: 980, chartHeight: 340 },
    "180d": { days: 180, label: "6 months", shortLabel: "6M", chartWidth: 1180, chartHeight: 380 },
    "365d": { days: 365, label: "1 year", shortLabel: "1Y", chartWidth: 1480, chartHeight: 420 },
  };
  const RANGE_ORDER = Object.keys(RANGE_OPTIONS);
  const TOKEN_KEYS = ["input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"];
  const data = window.CODEX_USAGE_DATA;
  const fmt = new Intl.NumberFormat();
  const pct = (value) => `${Math.round((Number(value) || 0) * 100)}%`;
  const byId = (id) => document.getElementById(id);
  const query = new URLSearchParams(window.location.search);
  const apiToken = query.get("token") || "";
  const prefs = loadPrefs();
  const initialTheme = queryTheme() || normalizeTheme(prefs.theme) || preferredTheme();
  let selectedRange = queryRange() || normalizeRange(prefs.range) || "7d";

  applyTheme(initialTheme);

  function setText(id, value) {
    const el = byId(id);
    if (el) el.textContent = value;
  }

  function number(value) {
    return fmt.format(Number(value) || 0);
  }

  function renderEmpty() {
    byId("empty-state").hidden = false;
    setText("freshness-pill", "No generated data");
  }

  function loadPrefs() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch {
      return {};
    }
  }

  function savePrefs(nextPrefs) {
    Object.assign(prefs, nextPrefs);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch {
      // Browsers can disable storage; the dashboard still works without persistence.
    }
  }

  function preferredTheme() {
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function normalizeTheme(value) {
    return value === "dark" || value === "light" ? value : "";
  }

  function queryTheme() {
    return normalizeTheme(query.get("theme"));
  }

  function normalizeRange(value) {
    return RANGE_OPTIONS[value] ? value : "";
  }

  function queryRange() {
    return normalizeRange(query.get("range"));
  }

  function applyTheme(theme) {
    const safeTheme = normalizeTheme(theme) || "light";
    document.documentElement.dataset.theme = safeTheme;
    const button = byId("theme-button");
    if (button) {
      button.textContent = safeTheme === "dark" ? "☀" : "☾";
      button.title = safeTheme === "dark" ? "Switch to day theme" : "Switch to night theme";
      button.setAttribute("aria-label", button.title);
    }
  }

  function installThemeToggle() {
    byId("theme-button")?.addEventListener("click", () => {
      const current = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
      const next = current === "dark" ? "light" : "dark";
      applyTheme(next);
      savePrefs({ theme: next });
    });
  }

  function installRangeToggle(summary) {
    const controls = [...document.querySelectorAll("#range-toggle [data-range]")];
    function syncRangeButtons() {
      controls.forEach((button) => {
        const active = button.dataset.range === selectedRange;
        button.setAttribute("aria-checked", active ? "true" : "false");
      });
    }
    controls.forEach((button) => {
      button.addEventListener("click", () => {
        const nextRange = normalizeRange(button.dataset.range);
        if (!nextRange || nextRange === selectedRange) return;
        selectedRange = nextRange;
        savePrefs({ range: selectedRange });
        syncRangeButtons();
        renderDashboard(summary);
      });
    });
    syncRangeButtons();
  }

  function dateToTime(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value || ""))) return Number.NaN;
    const [year, month, day] = value.split("-").map(Number);
    return Date.UTC(year, month - 1, day);
  }

  function shiftDate(value, offsetDays) {
    const time = dateToTime(value);
    if (!Number.isFinite(time)) return "";
    return new Date(time + offsetDays * 86400000).toISOString().slice(0, 10);
  }

  function latestDailyDate(daily) {
    const active = [...daily].reverse().find((row) => Number(row.total_tokens) || Number(row.turns) || Number(row.sessions));
    return active?.date || daily.at(-1)?.date || "";
  }

  function rowInWindow(row, startDate, endDate) {
    const day = String(row.date || "");
    return day >= startDate && day <= endDate;
  }

  function rangeWindow(daily, rangeKey) {
    const endDate = latestDailyDate(daily);
    const option = RANGE_OPTIONS[rangeKey] || RANGE_OPTIONS["7d"];
    const startDate = endDate ? shiftDate(endDate, -(option.days - 1)) : "";
    return { startDate, endDate, option };
  }

  function rangeCaption(scoped) {
    const { startDate, endDate, option } = scoped.range;
    if (!startDate || !endDate) return `Showing latest ${option.label}; no dated activity found.`;
    return `Showing latest ${option.label}: ${startDate} to ${endDate}.`;
  }

  function totalRows(rows) {
    return rows.reduce(
      (totals, row) => {
        TOKEN_KEYS.forEach((key) => {
          totals[key] += Number(row[key]) || 0;
        });
        totals.sessions += Number(row.sessions) || 0;
        totals.turns += Number(row.turns) || 0;
        return totals;
      },
      {
        sessions: 0,
        turns: 0,
        input_tokens: 0,
        cached_input_tokens: 0,
        output_tokens: 0,
        total_tokens: 0,
      }
    );
  }

  function aggregateEventsBy(events, sessions, key) {
    const grouped = new Map();
    events.forEach((event) => {
      const value = String(event[key] || "unknown");
      if (!grouped.has(value)) {
        grouped.set(value, {
          [key]: value,
          sessions: new Set(),
          turns: 0,
          input_tokens: 0,
          cached_input_tokens: 0,
          output_tokens: 0,
          total_tokens: 0,
        });
      }
      const row = grouped.get(value);
      row.sessions.add(String(event.session_id || "unknown"));
      TOKEN_KEYS.forEach((tokenKey) => {
        row[tokenKey] += Number(event[tokenKey]) || 0;
      });
    });
    sessions.forEach((session) => {
      const value = String(session[key] || "unknown");
      if (!grouped.has(value)) {
        grouped.set(value, {
          [key]: value,
          sessions: new Set(),
          turns: 0,
          input_tokens: 0,
          cached_input_tokens: 0,
          output_tokens: 0,
          total_tokens: 0,
        });
      }
      grouped.get(value).turns += Number(session.turn_count) || 0;
    });
    return [...grouped.values()]
      .map((row) => {
        const sessionsCount = row.sessions.size;
        return {
          ...row,
          sessions: sessionsCount,
          cache_ratio: ratio(row.cached_input_tokens, row.input_tokens),
          output_input_ratio: ratio(row.output_tokens, row.input_tokens),
        };
      })
      .filter((row) => row.total_tokens || row.sessions || row.turns)
      .sort((a, b) => b.total_tokens - a.total_tokens);
  }

  function buildMemorySignals(sessions, projectBreakdown) {
    const citationSessions = sessions
      .filter((session) => session.memory_citation_detected)
      .map((session) => ({
        session_id: session.session_id,
        date: session.date,
        project: session.project,
        total_tokens: session.total_tokens,
        turn_count: session.turn_count,
      }));
    const repeatedProjects = projectBreakdown.filter(
      (row) => row.project !== "Unknown" && row.sessions >= 2 && row.total_tokens > 0
    );
    const candidates = repeatedProjects
      .map((row) => ({
        project: row.project,
        sessions: row.sessions,
        total_tokens: row.total_tokens,
        average_tokens_per_session: Math.floor(row.total_tokens / Math.max(row.sessions, 1)),
        signal: "Repeated high-token project activity may benefit from durable memory or a reusable skill.",
      }))
      .filter((row) => row.average_tokens_per_session >= 50000 || row.total_tokens >= 100000)
      .slice(0, 10);
    return {
      sessions_with_memory_citations: citationSessions,
      high_token_repeated_project_sessions: repeatedProjects.slice(0, 10),
      candidates_for_memory_or_skill_creation: candidates,
      detection_notes: "Memory citation detection uses metadata keys only.",
    };
  }

  function qualitativeCacheLabel(cacheRatio) {
    if (cacheRatio >= 0.65) return "Strong context reuse";
    if (cacheRatio >= 0.35) return "Moderate context reuse";
    if (cacheRatio > 0) return "Low context reuse";
    return "No cache signal";
  }

  function qualitativeOutputLabel(outputInputRatio) {
    if (outputInputRatio >= 0.6) return "Generation-heavy work";
    if (outputInputRatio >= 0.25) return "Balanced collaboration";
    if (outputInputRatio > 0) return "Context-heavy work";
    return "No output/input signal";
  }

  function buildInsights(totals, daily, projectBreakdown, memorySignals) {
    const activeDays = daily.filter((row) => Number(row.total_tokens));
    const peakDay = activeDays.reduce(
      (best, row) => (!best || row.total_tokens > best.total_tokens ? row : best),
      null
    );
    const latestActiveDay = activeDays.at(-1) || null;
    return {
      cache_label: qualitativeCacheLabel(totals.cache_ratio),
      output_input_label: qualitativeOutputLabel(totals.output_input_ratio),
      latest_active_day: latestActiveDay,
      peak_day: peakDay,
      top_project: projectBreakdown[0] || null,
      memory_candidate_count: memorySignals.candidates_for_memory_or_skill_creation.length,
    };
  }

  function buildScopedSummary(summary) {
    const sourceDaily = summary.daily || [];
    const range = rangeWindow(sourceDaily, selectedRange);
    const daily = range.startDate
      ? sourceDaily.filter((row) => rowInWindow(row, range.startDate, range.endDate))
      : sourceDaily;
    const sessions = (summary.sessions || []).filter((row) =>
      range.startDate ? rowInWindow(row, range.startDate, range.endDate) : true
    );
    const tokenEvents = (summary.token_events || []).filter((row) =>
      range.startDate ? rowInWindow(row, range.startDate, range.endDate) : true
    );
    const totals = totalRows(daily);
    totals.sessions = sessions.length;
    totals.turns = sessions.reduce((sum, session) => sum + (Number(session.turn_count) || 0), 0);
    totals.cache_ratio = ratio(totals.cached_input_tokens, totals.input_tokens);
    totals.output_input_ratio = ratio(totals.output_tokens, totals.input_tokens);

    const projectBreakdown = aggregateEventsBy(tokenEvents, sessions, "project");
    const modelBreakdown = aggregateEventsBy(tokenEvents, sessions, "model");
    const memorySignals = buildMemorySignals(sessions, projectBreakdown);
    return {
      ...summary,
      totals,
      daily,
      sessions,
      largest_sessions: [...sessions].sort((a, b) => b.total_tokens - a.total_tokens).slice(0, 20),
      project_breakdown: projectBreakdown,
      model_breakdown: modelBreakdown,
      memory_reuse_signals: memorySignals,
      insights: buildInsights(totals, daily, projectBreakdown, memorySignals),
      range,
    };
  }

  function ratio(numerator, denominator) {
    const bottom = Number(denominator) || 0;
    return bottom > 0 ? Math.round(((Number(numerator) || 0) / bottom) * 10000) / 10000 : 0;
  }

  function chartPoints(rows, key, width, height, pad, maxValue) {
    const usableWidth = width - pad.left - pad.right;
    const usableHeight = height - pad.top - pad.bottom;
    if (!rows.length) return "";
    return rows
      .map((row, index) => {
        const x = pad.left + (rows.length === 1 ? usableWidth / 2 : (index / (rows.length - 1)) * usableWidth);
        const y = pad.top + usableHeight - ((Number(row[key]) || 0) / maxValue) * usableHeight;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }

  function renderLineChart(targetId, rows, series, rangeOption = RANGE_OPTIONS["7d"]) {
    const target = byId(targetId);
    const width = target.classList.contains("compact")
      ? Math.max(760, Math.round(rangeOption.chartWidth * 0.72))
      : rangeOption.chartWidth;
    const height = target.classList.contains("compact") ? 280 : rangeOption.chartHeight;
    const pad = { top: 26, right: 26, bottom: 48, left: 70 };
    const maxValue = Math.max(
      1,
      ...rows.flatMap((row) => series.map((item) => Number(row[item.key]) || 0))
    );
    const yTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => Math.round(maxValue * ratio));
    const labels = rows.map((row) => row.date.slice(5));
    const labelEvery = Math.max(1, Math.ceil(rows.length / (width >= 1400 ? 12 : 8)));
    const legend = series
      .map(
        (item, index) =>
          `<g transform="translate(${pad.left + index * 150},18)"><line x1="0" y1="0" x2="18" y2="0" class="${item.className}" stroke-width="3"/><text x="26" y="4" class="axis">${item.label}</text></g>`
      )
      .join("");

    const grid = yTicks
      .map((tick) => {
        const y = pad.top + (1 - tick / maxValue) * (height - pad.top - pad.bottom);
        return `<line x1="${pad.left}" x2="${width - pad.right}" y1="${y}" y2="${y}" class="grid-line"/><text x="16" y="${y + 4}" class="axis">${number(tick)}</text>`;
      })
      .join("");

    const xLabels = labels
      .map((label, index) => {
        if (index % labelEvery !== 0 && index !== labels.length - 1) return "";
        const x = pad.left + (rows.length === 1 ? 0.5 : index / (rows.length - 1)) * (width - pad.left - pad.right);
        return `<text x="${x}" y="${height - 16}" text-anchor="middle" class="axis">${label}</text>`;
      })
      .join("");

    const lines = series
      .map((item) => {
        const points = chartPoints(rows, item.key, width, height, pad, maxValue);
        return `<polyline fill="none" class="${item.className}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${points}"/>`;
      })
      .join("");
    const hitPoints = series
      .map((item) =>
        rows
          .map((row, index) => {
            const x = pad.left + (rows.length === 1 ? 0.5 : index / (rows.length - 1)) * (width - pad.left - pad.right);
            const y = pad.top + (height - pad.top - pad.bottom) - ((Number(row[item.key]) || 0) / maxValue) * (height - pad.top - pad.bottom);
            const tip = `${item.label}\n${row.date}: ${number(row[item.key])}\nSessions: ${number(row.sessions)}\nTurns: ${number(row.turns)}`;
            return `<circle class="hit-point ${item.className}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5" data-tip="${escapeAttr(tip)}"><title>${escapeHtml(tip)}</title></circle>`;
          })
          .join("")
      )
      .join("");

    target.innerHTML = `<svg viewBox="0 0 ${width} ${height}" style="min-width:${width}px" preserveAspectRatio="none">${grid}${xLabels}${lines}${hitPoints}${legend}</svg>`;
  }

  function renderRankList(id, rows, keyName) {
    const target = byId(id);
    const top = rows.slice(0, 6);
    const max = Math.max(1, ...top.map((row) => Number(row.total_tokens) || 0));
    if (!top.length) {
      target.innerHTML = `<p class="muted">No breakdown metadata available.</p>`;
      return;
    }
    target.innerHTML = top
      .map((row) => {
        const width = Math.round(((Number(row.total_tokens) || 0) / max) * 100);
        return `<div class="rank-item">
          <div class="rank-topline"><strong>${escapeHtml(row[keyName] || "Unknown")}</strong><span>${number(row.total_tokens)}</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
          <div class="muted">${number(row.sessions)} sessions, ${number(row.turns)} turns, cache ${pct(row.cache_ratio)}</div>
        </div>`;
      })
      .join("");
  }

  function renderMemorySignals(signals) {
    const target = byId("memory-signals");
    const citations = signals.sessions_with_memory_citations || [];
    const candidates = signals.candidates_for_memory_or_skill_creation || [];
    const items = [];
    items.push({
      title: `${number(citations.length)} memory-cited sessions`,
      text: "Detected through metadata keys only.",
    });
    candidates.slice(0, 3).forEach((item) => {
      items.push({
        title: `${item.project} candidate`,
        text: `${number(item.total_tokens)} tokens across ${number(item.sessions)} sessions.`,
      });
    });
    if (items.length === 1 && citations.length === 0) {
      items.push({ title: "No strong candidates yet", text: "Repeated high-token project activity will appear here." });
    }
    target.innerHTML = items
      .map(
        (item) => `<div class="signal-item">
          <div class="signal-topline"><strong>${escapeHtml(item.title)}</strong></div>
          <div class="muted">${escapeHtml(item.text)}</div>
        </div>`
      )
      .join("");
  }

  function renderInsights(summary) {
    const insights = summary.insights || {};
    const totals = summary.totals || {};
    const peakDay = insights.peak_day || {};
    const latestDay = insights.latest_active_day || {};
    const topProject = insights.top_project || {};
    const items = [
      {
        title: insights.cache_label || "No cache signal",
        text: `${pct(totals.cache_ratio)} of input tokens were cached. Higher reuse usually means less repeated setup.`,
      },
      {
        title: insights.output_input_label || "No output/input signal",
        text: `Output/input ratio is ${(Number(totals.output_input_ratio) || 0).toFixed(2)}, a rough read on generation versus context loading.`,
      },
      {
        title: peakDay.date ? `Peak day: ${peakDay.date}` : "No peak day yet",
        text: peakDay.date ? `${number(peakDay.total_tokens)} tokens across ${number(peakDay.sessions)} sessions.` : "Generate real data to identify your heaviest day.",
      },
      {
        title: `${number(insights.memory_candidate_count)} reuse candidates`,
        text: topProject.project ? `Top project label: ${topProject.project} with ${number(topProject.total_tokens)} tokens.` : "Repeated high-token work will appear here.",
      },
    ];
    if (latestDay.date && latestDay.date !== peakDay.date) {
      items.push({
        title: `Latest active day: ${latestDay.date}`,
        text: `${number(latestDay.total_tokens)} tokens and ${number(latestDay.turns)} turns.`,
      });
    }
    byId("insight-grid").innerHTML = items
      .slice(0, 4)
      .map((item) => `<div class="insight-item"><strong>${escapeHtml(item.title)}</strong><p class="muted">${escapeHtml(item.text)}</p></div>`)
      .join("");
  }

  function renderTable(rows) {
    const target = byId("largest-sessions");
    target.innerHTML = rows
      .slice(0, 12)
      .map(
        (row) => `<tr>
          <td>${escapeHtml(row.date)}</td>
          <td>${escapeHtml(row.session_id)}</td>
          <td>${escapeHtml(row.project)}</td>
          <td>${escapeHtml(row.model)}</td>
          <td>${number(row.total_tokens)}</td>
          <td>${number(row.input_tokens)}</td>
          <td>${number(row.cached_input_tokens)}</td>
          <td>${number(row.output_tokens)}</td>
          <td>${number(row.turn_count)}</td>
        </tr>`
      )
      .join("");
  }

  function renderDefinitionList(id, rows) {
    byId(id).innerHTML = rows.map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`).join("");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function escapeAttr(value) {
    return escapeHtml(value).replaceAll("\n", "&#10;");
  }

  function tokenQuery() {
    return apiToken ? `?token=${encodeURIComponent(apiToken)}` : "";
  }

  async function api(path, options = {}) {
    const response = await fetch(`/api/${path}${tokenQuery()}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(apiToken ? { "X-Dashboard-Token": apiToken } : {}),
        ...(options.headers || {}),
      },
    });
    const payload = await response.json();
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Request failed: ${response.status}`);
    }
    return payload;
  }

  function installLifecycleHooks() {
    if (window.location.protocol !== "http:" && window.location.protocol !== "https:") return;
    api("page-opened", { method: "POST", body: "{}" }).catch(() => {});
    window.addEventListener("pagehide", () => {
      const url = `/api/page-closed${tokenQuery()}`;
      if (navigator.sendBeacon) {
        navigator.sendBeacon(url, "{}");
      } else {
        fetch(url, { method: "POST", keepalive: true }).catch(() => {});
      }
    });
  }

  function installTooltip() {
    const tooltip = byId("chart-tooltip");
    document.addEventListener("mousemove", (event) => {
      const target = event.target.closest?.("[data-tip]");
      if (!target) {
        tooltip.hidden = true;
        return;
      }
      tooltip.hidden = false;
      tooltip.textContent = target.getAttribute("data-tip") || "";
      tooltip.style.left = `${Math.min(event.clientX + 14, window.innerWidth - 300)}px`;
      tooltip.style.top = `${Math.min(event.clientY + 14, window.innerHeight - 120)}px`;
    });
  }

  function renderDeepDive(summary) {
    const kindSelect = byId("deep-dive-kind");
    const valueSelect = byId("deep-dive-value");
    const detail = byId("deep-dive");
    const sources = {
      project: summary.project_breakdown || [],
      model: summary.model_breakdown || [],
      day: summary.daily || [],
    };
    const labels = {
      project: "project",
      model: "model",
      day: "date",
    };

    function syncOptions() {
      const kind = kindSelect.value;
      const label = labels[kind];
      valueSelect.innerHTML = sources[kind]
        .filter((row) => Number(row.total_tokens) > 0 || kind !== "day")
        .map((row) => `<option value="${escapeAttr(row[label])}">${escapeHtml(row[label])}</option>`)
        .join("");
      if (prefs.deepDiveValue && [...valueSelect.options].some((option) => option.value === prefs.deepDiveValue)) {
        valueSelect.value = prefs.deepDiveValue;
      }
      renderSelected();
    }

    function renderSelected() {
      const kind = kindSelect.value;
      const label = labels[kind];
      const selected = valueSelect.value;
      const row = sources[kind].find((item) => String(item[label]) === selected) || sources[kind][0] || {};
      savePrefs({ deepDiveKind: kind, deepDiveValue: selected });
      const cards = [
        ["Total tokens", number(row.total_tokens)],
        ["Input tokens", number(row.input_tokens)],
        ["Cached input", number(row.cached_input_tokens)],
        ["Output tokens", number(row.output_tokens)],
        [kind === "day" ? "Usage events" : "Sessions", number(kind === "day" ? row.usage_events : row.sessions)],
        ["Turns", number(row.turns)],
        ["Cache ratio", pct(row.cache_ratio)],
        ["Output/input", (Number(row.output_input_ratio) || 0).toFixed(2)],
      ];
      detail.innerHTML = cards
        .map(([labelText, value]) => `<div class="deep-card"><span class="muted">${escapeHtml(labelText)}</span><strong>${escapeHtml(value)}</strong></div>`)
        .join("");
    }

    kindSelect.onchange = syncOptions;
    valueSelect.onchange = renderSelected;
    if (prefs.deepDiveKind && sources[prefs.deepDiveKind]) {
      kindSelect.value = prefs.deepDiveKind;
    }
    syncOptions();
  }

  function installHelpAndRefresh() {
    byId("help-button")?.addEventListener("click", async () => {
      const dialog = byId("help-dialog");
      const content = byId("help-content");
      try {
        const payload = await api("help");
        content.innerHTML = Object.entries(payload.help || {})
          .map(([name, text]) => `<section><h3>${escapeHtml(name)}</h3><pre>${escapeHtml(text)}</pre></section>`)
          .join("");
      } catch (error) {
        content.innerHTML = `<p class="muted">Local API help is available when the dashboard is served by <code>python install.py --quickstart</code> or <code>python install.py --start-server</code>.</p><pre>${escapeHtml("python install.py --help\npython scripts/build_usage_data.py --help\npython scripts/schedule_dashboard.py --help")}</pre>`;
      }
      dialog.showModal();
    });

    byId("refresh-button")?.addEventListener("click", async () => {
      const button = byId("refresh-button");
      button.disabled = true;
      button.textContent = "...";
      try {
        await api("refresh", { method: "POST", body: "{}" });
        window.location.reload();
      } catch (error) {
        alert(`Refresh failed: ${error.message}`);
      } finally {
        button.disabled = false;
        button.textContent = "↻";
      }
    });
  }

  function renderDashboard(summary) {
    const scoped = buildScopedSummary(summary);
    const totals = scoped.totals || {};
    const daily = scoped.daily || [];
    const rangeOption = scoped.range.option;
    setText("freshness-pill", `Last parsed ${summary.freshness?.last_parsed_timestamp || "unknown"}`);
    setText("range-caption", rangeCaption(scoped));
    setText("metric-total-tokens", number(totals.total_tokens));
    setText("metric-rolling", `Selected ${rangeOption.shortLabel}: ${number(totals.total_tokens)}`);
    setText("metric-input-tokens", number(totals.input_tokens));
    setText("metric-cache", `Cache ratio: ${pct(totals.cache_ratio)}`);
    setText("metric-output-tokens", number(totals.output_tokens));
    setText("metric-output-ratio", `Output/input: ${(Number(totals.output_input_ratio) || 0).toFixed(2)}`);
    setText("metric-sessions", number(totals.sessions));
    setText("metric-turns", `Turns: ${number(totals.turns)}`);

    renderLineChart("daily-chart", daily, [
      { key: "total_tokens", label: "Total", className: "series-total" },
      { key: "input_tokens", label: "Input", className: "series-input" },
      { key: "cached_input_tokens", label: "Cached", className: "series-cached" },
      { key: "output_tokens", label: "Output", className: "series-output" },
    ], rangeOption);
    renderLineChart("activity-chart", daily, [
      { key: "sessions", label: "Sessions", className: "series-total" },
      { key: "turns", label: "Turns", className: "series-input" },
    ], rangeOption);
    renderRankList("model-breakdown", scoped.model_breakdown || [], "model");
    renderRankList("project-breakdown", scoped.project_breakdown || [], "project");
    renderInsights(scoped);
    renderDeepDive(scoped);
    renderMemorySignals(scoped.memory_reuse_signals || {});
    renderTable(scoped.largest_sessions || []);
    renderDefinitionList("freshness-list", [
      ["Files scanned", number(summary.freshness?.files_scanned)],
      ["Sessions parsed", number(summary.freshness?.sessions_parsed)],
      ["Records skipped", number(summary.freshness?.records_skipped)],
      ["Generated at", summary.generated_at || "unknown"],
    ]);
    renderDefinitionList("privacy-list", [
      ["Local only", summary.privacy?.local_only ? "Yes" : "No"],
      ["Content ignored", summary.privacy?.content_fields_ignored ? "Yes" : "No"],
      ["Raw text persisted", summary.privacy?.raw_conversation_text_persisted ? "No" : "Check"],
      ["Paths redacted", summary.privacy?.redact_paths ? "Yes" : "No"],
    ]);
    renderDefinitionList("operations-list", [
      ["Build once", "python install.py --real"],
      ["Start server", "python install.py --start-server"],
      ["Stop server", "python install.py --stop-server"],
      ["Schedule", "python scripts/schedule_dashboard.py"],
    ]);
  }

  if (!data) {
    renderEmpty();
    installThemeToggle();
    installHelpAndRefresh();
    return;
  }

  installThemeToggle();
  installRangeToggle(data);
  installTooltip();
  installHelpAndRefresh();
  installLifecycleHooks();
  renderDashboard(data);
})();
