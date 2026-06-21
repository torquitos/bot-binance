const API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || "http://127.0.0.1:5000";
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const store = { marketOptions: { symbols: [], intervals: [] }, strategies: {}, state: null, startTime: Date.now() };

function toMoney(v) {
  if (v == null || Number.isNaN(v)) return "$0.00";
  return new Intl.NumberFormat("es-CO", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(v);
}
function toShort(v, d = 6) {
  if (v == null || Number.isNaN(v)) return "-";
  return Number(v).toLocaleString("es-CO", { maximumFractionDigits: d });
}
function formatPair(s, b, q) { return b && q ? `${b}/${q}` : s ? (s.endsWith("USDT") ? `${s.slice(0, -4)}/USDT` : s) : "-"; }

async function api(path, opts = {}) {
  const { headers: userHeaders, ...rest } = opts;
  const headers = { ...userHeaders };
  if (rest.body) headers["Content-Type"] = "application/json";
  const r = await fetch(`${API_BASE_URL}${path}`, { headers, ...rest });
  const d = await r.json();
  if (!r.ok || !d.ok) throw new Error(d.error || "Error inesperado");
  return d;
}

function showToast(msg, ok = true) {
  const t = $("#toast");
  $("#toastIcon").textContent = ok ? "✓" : "✗";
  $("#toastMsg").textContent = msg.replace(/[✅❌🤖⏹🧹🔬🔑]/g, "").trim();
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 3000);
}

// ── Tab switching ──
function switchTab(tabName) {
  const tabId = "tab-" + tabName;
  // Update sidebar buttons
  $$(".sidebar-nav button[data-tab]").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabName);
  });
  // Update bottom nav buttons
  $$(".bottom-nav button[data-tab]").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabName);
  });
  // Show/hide tabs
  $$(".tab-content").forEach((c) => {
    c.style.display = c.id === tabId ? "block" : "none";
  });
  store.activeTab = tabId;
  if (tabName === "history") loadTrades();
  if (tabName === "portfolio") renderPortfolio();
  // Close drawer on mobile
  closeDrawer();
}

function closeDrawer() {
  $("#drawer").classList.add("hidden");
  $("#drawerOverlay").classList.add("hidden");
}

// Sidebar tab buttons
$$(".sidebar-nav button[data-tab]").forEach((btn) => {
  btn.setAttribute("type", "button");
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

// Bottom nav tab buttons
$$(".bottom-nav button[data-tab]").forEach((btn) => {
  btn.setAttribute("type", "button");
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

// Hamburger + Drawer
$("#hamburgerBtn").addEventListener("click", () => {
  $("#drawer").classList.toggle("hidden");
  $("#drawerOverlay").classList.toggle("hidden");
});
$("#drawerClose").addEventListener("click", closeDrawer);
$("#drawerOverlay").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
$("#drawerBacktest").addEventListener("click", () => {
  closeDrawer();
  switchTab("strategies");
  $("#toggleBacktest").textContent = "Ocultar";
  $("#backtestBody").style.display = "";
});
$("#drawerConfig").addEventListener("click", () => {
  closeDrawer();
  const s = store.state;
  $("#apiKeyInput").value = "";
  $("#apiSecretInput").value = "";
  $("#apiTestnetToggle").checked = s ? s.use_testnet !== false : true;
  $("#apiModal").classList.remove("hidden");
});

// Backtest link + Config link (sidebar)
$("#backtestLink").addEventListener("click", (e) => {
  e.preventDefault();
  switchTab("strategies");
  $("#toggleBacktest").textContent = "Ocultar";
  $("#backtestBody").style.display = "";
});
$("#configLink").addEventListener("click", (e) => {
  e.preventDefault();
  const s = store.state;
  $("#apiKeyInput").value = "";
  $("#apiSecretInput").value = "";
  $("#apiTestnetToggle").checked = s ? s.use_testnet !== false : true;
  $("#apiModal").classList.remove("hidden");
});
$("#apiModalClose").addEventListener("click", () => $("#apiModal").classList.add("hidden"));
$("#apiModal").addEventListener("click", (e) => {
  if (e.target === e.currentTarget) $("#apiModal").classList.add("hidden");
});
$("#apiSaveBtn").addEventListener("click", async () => {
  const key = $("#apiKeyInput").value.trim();
  const secret = $("#apiSecretInput").value.trim();
  try {
    const d = await api("/api/credentials", {
      method: "POST",
      body: JSON.stringify({ api_key: key, api_secret: secret, use_testnet: $("#apiTestnetToggle").checked }),
    });
    renderState(d.state);
    showToast("Credenciales guardadas", true);
    $("#apiModal").classList.add("hidden");
  } catch (e) {
    showToast("Error: " + e.message, false);
  }
});

// ── Chart ──
let lwChart, candleSeries;

function initChart() {
  const el = $("#candlesChart");
  if (!el) return;
  if (typeof LightweightCharts === "undefined") {
    el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--on-surface-variant)">Error cargando librería de gráficos</div>';
    return;
  }
  el.innerHTML = ""; // clear placeholder
  lwChart = LightweightCharts.createChart(el, {
    height: 400,
    layout: { backgroundColor: "#1a160e", textColor: "#d3c5ac" },
    grid: { vertLines: { color: "rgba(255,255,255,0.04)" }, horzLines: { color: "rgba(255,255,255,0.04)" } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#4f4633" },
    timeScale: { borderColor: "#4f4633", timeVisible: true, secondsVisible: false },
  });
  candleSeries = lwChart.addCandlestickSeries({
    upColor: "#0ecb81", downColor: "#f6465d",
    borderUpColor: "#0ecb81", borderDownColor: "#f6465d",
    wickUpColor: "#0ecb81", wickDownColor: "#f6465d",
  });
  lwChart.subscribeCrosshairMove((p) => {
    if (!p || !p.time) return;
    const d = p.seriesData.get(candleSeries);
    if (d) $("#chartLegend").textContent = `O ${toShort(d.open, 2)}  H ${toShort(d.high, 2)}  L ${toShort(d.low, 2)}  C ${toShort(d.close, 2)}`;
  });
  window.addEventListener("resize", () => { if (lwChart && el) lwChart.resize(el.clientWidth, 400); });
}

async function refreshChart(symbol, interval) {
  if (!symbol || !interval) return;
  $("#chartTitle").textContent = `${symbol} · ${interval}`;
  if (!candleSeries) return;
  try {
    const d = await api(`/api/market/klines?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=80`);
    const c = d.candles || [];
    if (!c.length) {
      $("#chartLegend").textContent = "Sin datos de mercado — configura BINANCE_API_KEY en .env";
      return;
    }
    candleSeries.setData(c.map((x) => ({ time: Math.floor(x.open_time / 1000), open: x.open, high: x.high, low: x.low, close: x.close })));
    const last = c[c.length - 1];
    $("#chartLegend").textContent = `O ${toShort(last.open, 2)}  H ${toShort(last.high, 2)}  L ${toShort(last.low, 2)}  C ${toShort(last.close, 2)}`;
    updateVolChart(c);
  } catch (e) { $("#chartLegend").textContent = "⚠️ " + e.message; }
}

function updateVolChart(candles) {
  const bars = $("#volBars");
  if (!bars || !candles.length) return;
  const closes = candles.slice(-20).map((c) => c.close);
  const min = Math.min(...closes), max = Math.max(...closes), range = max - min || 1;
  bars.innerHTML = closes.map((p) => {
    const h = ((p - min) / range * 80 + 10).toFixed(0);
    return `<div style="height:${h}%;background:${p >= closes[closes.length - 1] ? 'var(--green)' : 'var(--red)'};opacity:0.7;border-radius:3px 3px 0 0;transition:height 0.3s"></div>`;
  }).join("");
  $("#volPrice").textContent = toShort(closes[closes.length - 1], 2);
}

// ── Render ──
function renderIndicators(inds) {
  const bar = $("#indicatorBar");
  if (!inds) { bar.innerHTML = "<span>Indicadores no disponibles</span>"; return; }
  const p = [];
  if (inds.sma_fast != null) p.push(`SMA: ${toShort(inds.sma_fast, 2)}`);
  if (inds.rsi != null) {
    const v = inds.rsi.toFixed(1);
    p.push(`RSI: <span style="color:${v < 30 ? 'var(--red)' : v > 70 ? 'var(--green)' : ''}">${v}</span>`);
  }
  if (inds.macd && inds.macd[0] != null) p.push(`MACD: ${toShort(inds.macd[0], 2)}`);
  if (inds.bollinger && inds.bollinger[0] != null) p.push(`BB: ${toShort(inds.bollinger[2], 2)}–${toShort(inds.bollinger[0], 2)}`);
  bar.innerHTML = p.length ? p.map((x) => `<span class="chip">${x}</span>`).join("") : "<span>Calculando...</span>";
}

function renderLogs(logs) {
  const box = $("#logBox");
  if (!logs || !logs.length) { box.textContent = "Sin actividad aún."; return; }
  box.innerHTML = logs.map((e) => {
    const cls = e.level === "error" ? "danger" : e.level === "sell" ? "success" : "";
    return `<div class="log-entry ${cls}">${e.time}  ${e.message}</div>`;
  }).join("");
}

function renderBalances(state) {
  const q = state.quote_asset, b = state.base_asset;
  const bal = state.balances || {};
  const qb = q && bal[q] ? toShort(bal[q].total, 2) : "-";
  const bb = b && bal[b] ? toShort(bal[b].total, 6) : "-";
  $("#balancesValue").textContent = `${q || "USDT"}: ${qb} | ${b || "BTC"}: ${bb}`;
}

function renderStrategyForm(name, params) {
  const def = store.strategies[name];
  if (!def) return;
  const html = Object.entries(def.params).map(([k, p]) => {
    const v = params?.[k] ?? p.default ?? "";
    return `<div class="form-group"><label>${p.label}</label><input data-sparam="${k}" data-stype="${p.type}" type="number" step="${p.type === "int" ? "1" : "any"}" value="${v}" ${p.required ? "required" : ""}></div>`;
  }).join("");
  $("#strategyParams").innerHTML = html;
}

let storeFormValues = {};

function renderState(state) {
  store.state = state;
  const activeTab = store.activeTab || "tab-dashboard";
  const isDashboard = activeTab === "tab-dashboard";
  // Topbar (always update)
  $("#priceValue").textContent = toShort(state.last_price, 2);
  $("#priceLabel").textContent = formatPair(state.symbol, state.base_asset, state.quote_asset);
  $("#modePill").innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/></svg> ${state.bot_active ? "AUTOMATICO" : "MANUAL"}`;
  $("#envValue").textContent = state.use_testnet ? "Testnet" : "Real";
  $("#drawerEnv").textContent = state.use_testnet ? "Testnet" : "Real";
  // Stats (always update)
  $("#pnlValue").textContent = toMoney(state.session_pnl);
  $("#pnlValue").className = `stat-value ${state.session_pnl >= 0 ? "success" : "danger"}`;
  $("#opsValue").textContent = state.operations_count;
  $("#positionValue").textContent = state.position_open ? `${toShort(state.position_qty)} ${state.base_asset || ""}` : "Cerrada";
  $("#envValue2").textContent = state.use_testnet ? "Binance Testnet" : "Binance Live";
  renderBalances(state);
  // Bot card (always update)
  $("#botCardTitle").textContent = formatPair(state.symbol, state.base_asset, state.quote_asset);
  $("#botCardStrategy").textContent = state.strategy_label || state.strategy;
  $("#botCardStatus").textContent = state.bot_active ? "Running" : "Detenido";
  $("#botCardStatus").className = `bot-badge ${state.bot_active ? "running" : "paused"}`;
  $("#botStatusValue").textContent = state.status || "Listo";
  const uptime = Math.floor((Date.now() - store.startTime) / 1000);
  const h = Math.floor(uptime / 3600), m = Math.floor((uptime % 3600) / 60);
  $("#botUptimeValue").textContent = `${h}h ${m}m`;
  $("#botCredentials").textContent = `Credenciales: ${state.credentials_ready ? "Listas" : "Faltan"}`;
  // Controls (always update)
  $("#buyBtn").disabled = !state.credentials_ready || state.position_open;
  $("#sellBtn").disabled = !state.credentials_ready || !state.position_open;
  $("#startAutoBtn").disabled = !state.credentials_ready || state.bot_active;
  $("#stopAutoBtn").disabled = !state.bot_active;
  // Logs (always update)
  renderLogs(state.logs || []);
  renderIndicators(state.indicators);
  // Stepper form — only update when dashboard tab is active
  if (isDashboard) {
    if (store.marketOptions.symbols.length && !store.userChangedPair) {
      $$(".pair-btn").forEach((b) => b.classList.toggle("selected", b.dataset.symbol === state.symbol));
    }
    $("#strategyInterval").value = state.chart_interval || "15m";
    if ($("#strategySelect").value !== state.strategy && store.strategies[state.strategy]) {
      $("#strategySelect").value = state.strategy;
    }
    renderStrategyForm(state.strategy, state.strategy_params);
    $("#configQuoteAmount").value = state.quote_amount || 100;
    if (state.buy_price != null) $("#configBuyPrice").value = state.buy_price;
    if (state.sell_price != null) $("#configSellPrice").value = state.sell_price;
    if (state.stop_loss_price != null) $("#configStopLoss").value = state.stop_loss_price;
    // Phase 5 toggles
    $("#trailingStopToggle").checked = !!state.trailing_stop_active;
    $("#trailingStopBody").style.display = state.trailing_stop_active ? "" : "none";
    $("#trailingStopPct").value = state.trailing_stop_pct || 2;
    $("#trailingStopLabel").textContent = (state.trailing_stop_pct || 2) + "%";
    $("#tpToggle").checked = !!state.tp_active;
    $("#tpBody").style.display = state.tp_active ? "" : "none";
    if (state.tp_levels) $("#tpLevels").value = state.tp_levels;
    if (state.tp_allocations) $("#tpAllocations").value = state.tp_allocations;
    $("#dcaToggle").checked = !!state.dca_active;
    $("#dcaBody").style.display = state.dca_active ? "" : "none";
    if (state.dca_amount != null) $("#dcaAmount").value = state.dca_amount;
    if (state.dca_interval_minutes != null) $("#dcaInterval").value = state.dca_interval_minutes;
  }
  // Save form values from stepper when user changes them (so SSE doesn't eat them)
  if ($("#strategySelect").value) storeFormValues.strategy = $("#strategySelect").value;
  if ($("#strategyInterval").value) storeFormValues.interval = $("#strategyInterval").value;
}

// ── Portfolio ──
let pnlChart, pnlSeries;

function initPnlChart() {
  const el = $("#pnlChart");
  if (!el) return;
  pnlChart = LightweightCharts.createChart(el, {
    height: 300,
    layout: { backgroundColor: "#171309", textColor: "#d3c5ac" },
    grid: { vertLines: { color: "rgba(255,255,255,0.04)" }, horzLines: { color: "rgba(255,255,255,0.04)" } },
    rightPriceScale: { borderColor: "#4f4633" },
    timeScale: { borderColor: "#4f4633", timeVisible: true, secondsVisible: false },
  });
  pnlSeries = pnlChart.addLineSeries({ color: "#f0b90b", lineWidth: 2 });
  window.addEventListener("resize", () => { if (pnlChart && el) pnlChart.resize(el.clientWidth, 300); });
}

async function renderPortfolio() {
  const s = store.state;
  if (!s) return;
  const q = s.quote_asset || "USDT", b = s.base_asset || "BTC";
  const bal = s.balances || {};
  $("#portfolioUsdt").textContent = bal[q] ? toShort(bal[q].total, 2) : "0.00";
  $("#portfolioBase").textContent = bal[b] ? toShort(bal[b].total, 6) : "0.00";
  $("#portfolioPnl").textContent = toMoney(s.session_pnl);
  $("#portfolioPnl").className = `stat-value ${s.session_pnl >= 0 ? "success" : "danger"}`;
  $("#portfolioPosition").textContent = s.position_open ? `${toShort(s.position_qty)} ${b} @ ${toShort(s.position_entry_price, 2)}` : "Cerrada";
  const bd = $("#balancesDetail");
  const entries = Object.entries(bal).filter(([, v]) => v.total > 0);
  if (!entries.length) { bd.innerHTML = "<span style='color:var(--on-surface-variant)'>Sin balances</span>"; return; }
  bd.innerHTML = entries.map(([asset, v]) =>
    `<div class="balance-item"><span class="balance-asset">${asset}</span><span class="balance-free">${toShort(v.free, 6)}</span><span class="balance-total">${toShort(v.total, 6)}</span></div>`
  ).join("");
  try {
    const d = await api("/api/trades?limit=100");
    const trades = d.trades || [];
    if (trades.length && pnlSeries) {
      let cumPnl = 0;
      const data = trades.slice().reverse().map((t) => {
        cumPnl += t.pnl || 0;
        return { time: Math.floor(new Date(t.timestamp).getTime() / 1000), value: Math.round(cumPnl * 100) / 100 };
      }).filter((x) => x.time > 0);
      if (data.length) pnlSeries.setData(data);
    }
  } catch (e) { /* ignore */ }
}

// ── Sessions ──
async function loadSessions() {
  try {
    const d = await api("/api/sessions");
    const rows = d.sessions || [];
    const body = $("#sessionsBody");
    if (!rows.length) { body.innerHTML = `<tr><td colspan="6" class="empty">Sin sesiones</td></tr>`; return; }
    body.innerHTML = rows.map((s) => `
      <tr>
        <td>${s.start_time ? new Date(s.start_time).toLocaleString("es-CO") : "-"}</td>
        <td>${s.end_time ? new Date(s.end_time).toLocaleString("es-CO") : "En curso"}</td>
        <td>${s.symbol || "-"}</td>
        <td>${s.trades_count || 0}</td>
        <td class="${(s.pnl || 0) >= 0 ? "success" : "danger"}">${toMoney(s.pnl)}</td>
        <td><span class="badge ${s.status === "active" ? "badge-active" : ""}">${s.status === "active" ? "Activa" : "Cerrada"}</span></td>
      </tr>
    `).join("");
  } catch (e) { /* ignore */ }
}

// ── Trades ──
async function loadTrades() {
  try {
    const d = await api("/api/trades?limit=50");
    renderTrades(d.trades || []);
  } catch (e) {
    $("#tradeBody").innerHTML = `<tr><td colspan="8" class="empty">Error: ${e.message}</td></tr>`;
  }
}

function renderTrades(trades) {
  const body = $("#tradeBody");
  $("#tradesCount").textContent = `${trades.length} trades`;
  if (!trades.length) { body.innerHTML = `<tr><td colspan="8" class="empty">Sin operaciones aún</td></tr>`; return; }
  body.innerHTML = trades.map((t) => {
    const buy = t.side === "BUY";
    const pc = t.pnl != null ? (t.pnl >= 0 ? "success" : "danger") : "";
    const time = t.timestamp ? new Date(t.timestamp).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }) : "-";
    return `<tr><td>${time}</td><td>${t.symbol || "-"}</td><td class="${buy ? "buy" : "sell"}">${buy ? "COMPRA" : "VENTA"}</td><td>${toShort(t.price, 2)}</td><td>${toShort(t.quantity, 6)}</td><td>${toShort(t.quote_qty, 2)}</td><td class="${pc}">${t.pnl != null ? toMoney(t.pnl) : "-"}</td><td>${t.reason || "-"}</td></tr>`;
  }).join("");
}

// ── Strategy params getter ──
function getStrategyParams() {
  const p = {};
  $$("#strategyParams [data-sparam]").forEach((el) => {
    const name = el.getAttribute("data-sparam"), type = el.getAttribute("data-stype") || "float";
    if (el.value === "" || el.value === undefined) return;
    p[name] = type === "int" ? parseInt(el.value, 10) : parseFloat(el.value);
  });
  return p;
}

function getFormPayload() {
  return {
    symbol: $$(".pair-btn.selected").length ? $$(".pair-btn.selected")[0].dataset.symbol : "BTCUSDT",
    chart_interval: $("#strategyInterval").value,
    strategy: $("#strategySelect").value,
    strategy_params: getStrategyParams(),
    quote_amount: parseFloat($("#configQuoteAmount").value) || 100,
    buy_price: parseFloat($("#configBuyPrice").value) || undefined,
    sell_price: parseFloat($("#configSellPrice").value) || undefined,
    stop_loss_price: parseFloat($("#configStopLoss").value) || undefined,
    trailing_stop_active: $("#trailingStopToggle").checked,
    trailing_stop_pct: parseFloat($("#trailingStopPct").value) || 2,
    tp_active: $("#tpToggle").checked,
    tp_levels: $("#tpLevels").value.trim() || "3,5,10",
    tp_allocations: $("#tpAllocations").value.trim() || "33,33,34",
    dca_active: $("#dcaToggle").checked,
    dca_amount: parseFloat($("#dcaAmount").value) || 100,
    dca_interval_minutes: parseInt($("#dcaInterval").value, 10) || 60,
  };
}

// ── Strategy form load ──
let strategiesLoaded = false;
async function loadStrategies() {
  try {
    const d = await api("/api/strategies");
    store.strategies = d.strategies || {};
    const opts = Object.keys(store.strategies).map((k) => `<option value="${k}">${store.strategies[k].label}</option>`).join("");
    $("#strategySelect").innerHTML = opts;
    $("#btStrategy").innerHTML = opts;
    renderBTStrategyForm($("#btStrategy").value);
    if (!strategiesLoaded) {
      $("#strategySelect").addEventListener("change", () => {
        if (store.strategies[$("#strategySelect").value]) renderStrategyForm($("#strategySelect").value, {});
      });
      strategiesLoaded = true;
    }
  } catch (e) { /* ignore */ }
}

async function loadMarketOptions() {
  try {
    const d = await api("/api/market/options");
    store.marketOptions = d;
    const so = d.symbols.map((s) => `<option value="${s}">${s}</option>`).join("");
    const io = d.intervals.map((i) => `<option value="${i}">${i}</option>`).join("");
    // Populate selects
    $$("#chartSymbol, #btSymbol").forEach((el) => { el.innerHTML = so; el.value = "BTCUSDT"; });
    $$("#chartInterval, #btInterval").forEach((el) => { el.innerHTML = io; el.value = "15m"; });
    // Populate pair grid
    const grid = $("#pairGrid");
    grid.innerHTML = d.symbols.slice(0, 8).map((s) =>
      `<div class="pair-btn ${s === "BTCUSDT" ? "selected" : ""}" data-symbol="${s}">${s.startsWith("BTC") ? "₿" : s.startsWith("ETH") ? "Ξ" : s.startsWith("SOL") ? "◎" : "◆"} ${s.replace("USDT", "/USDT")}</div>`
    ).join("");
    if (!store.pairListenersAdded) {
      $$(".pair-btn").forEach((btn) => btn.addEventListener("click", () => {
        store.userChangedPair = true;
        $$(".pair-btn").forEach((b) => b.classList.remove("selected"));
        btn.classList.add("selected");
        const sym = btn.dataset.symbol;
        $("#chartSymbol").value = sym;
        refreshChart(sym, $("#chartInterval").value);
      }));
      store.pairListenersAdded = true;
    }
  } catch (e) { /* ignore */ }
}

// ── Stepper ──
let currentStep = 1;

function goToStep(n) {
  currentStep = n;
  $$(".step-content").forEach((el) => el.classList.remove("active"));
  $(`#step${n}`).classList.add("active");
  $$(".stepper-circle").forEach((el, i) => {
    el.classList.toggle("active", i + 1 === n);
    el.classList.toggle("done", i + 1 < n);
  });
  $$(".stepper-label").forEach((el, i) => el.classList.toggle("active", i + 1 <= n));
}

$("#step1Next").addEventListener("click", () => goToStep(2));
$("#step2Prev").addEventListener("click", () => goToStep(1));
$("#step2Next").addEventListener("click", () => goToStep(3));
$("#step3Prev").addEventListener("click", () => goToStep(2));

$("#deployBtn").addEventListener("click", async () => {
  try {
    const d = await api("/api/config", { method: "POST", body: JSON.stringify(getFormPayload()) });
    renderState(d.state);
    showToast("Configuracion guardada", true);
    goToStep(1);
  } catch (e) { showToast("Error: " + e.message, false); }
});

// ── Actions ──
async function runAction(path, msg) {
  try {
    const payload = path.includes("auto/start") ? getFormPayload() : undefined;
    const d = await api(path, { method: "POST", body: payload ? JSON.stringify(payload) : undefined });
    renderState(d.state);
    showToast(msg || d.message, true);
  } catch (e) { showToast("Error: " + e.message, false); }
}

$("#buyBtn").addEventListener("click", () => runAction("/api/manual/buy", "Compra ejecutada"));
$("#sellBtn").addEventListener("click", () => runAction("/api/manual/sell", "Venta ejecutada"));
$("#startAutoBtn").addEventListener("click", () => runAction("/api/auto/start", "Bot iniciado"));
$("#stopAutoBtn").addEventListener("click", () => runAction("/api/auto/stop", "Bot detenido"));
$$("#clearLogsBtn, #clearLogsBtn2").forEach((el) => el.addEventListener("click", () => runAction("/api/logs/clear", "Logs limpiados")));

// Trailing stop range sync
$("#trailingStopPct").addEventListener("input", () => {
  $("#trailingStopLabel").textContent = $("#trailingStopPct").value + "%";
});

// ── Chart controls ──
$("#chartSymbol").addEventListener("change", () => {
  store.userChangedPair = true;
  refreshChart($("#chartSymbol").value, $("#chartInterval").value);
  // Sync pair grid
  $$(".pair-btn").forEach((b) => b.classList.toggle("selected", b.dataset.symbol === $("#chartSymbol").value));
});
$("#chartInterval").addEventListener("change", () => refreshChart($("#chartSymbol").value, $("#chartInterval").value));

// ── Backtest ──
$("#toggleBacktest").addEventListener("click", () => {
  const body = $("#backtestBody");
  const btn = $("#toggleBacktest");
  if (body.style.display === "none") {
    body.style.display = "";
    btn.textContent = "Ocultar";
  } else {
    body.style.display = "none";
    btn.textContent = "Mostrar";
  }
});

function getBTStrategyParams() {
  const p = {};
  $$("#btStrategyParams [data-btparam]").forEach((el) => {
    const name = el.getAttribute("data-btparam"), type = el.getAttribute("data-bttype") || "float";
    if (el.value === "" || el.value === undefined) return;
    p[name] = type === "int" ? parseInt(el.value, 10) : parseFloat(el.value);
  });
  return p;
}

function renderBTStrategyForm(name) {
  const def = store.strategies[name];
  if (!def) return;
  $("#btStrategyParams").innerHTML = Object.entries(def.params).map(([k, p]) =>
    `<div class="form-group"><label>${p.label}</label><input data-btparam="${k}" data-bttype="${p.type}" type="number" step="${p.type === "int" ? "1" : "any"}" value="${p.default ?? ""}"></div>`
  ).join("");
}

$("#btStrategy").addEventListener("change", () => renderBTStrategyForm($("#btStrategy").value));

$("#backtestForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const sn = fd.get("bt_strategy") || "threshold";
  const payload = { symbol: fd.get("bt_symbol"), interval: fd.get("bt_interval"), strategy: sn, strategy_params: getBTStrategyParams(), quote_amount: fd.get("bt_amount"), kline_limit: parseInt(fd.get("bt_limit"), 10) };
  const res = $("#backtestResults"), stats = $("#btStats"), body = $("#btTradeBody");
  res.classList.add("hidden");
  try {
    const d = await api("/api/backtest", { method: "POST", body: JSON.stringify(payload) });
    const bt = d.backtest;
    stats.innerHTML = `
      <div class="stat-card"><span class="stat-label">PnL</span><strong class="stat-value ${bt.total_pnl >= 0 ? "success" : "danger"}">${toMoney(bt.total_pnl)}</strong></div>
      <div class="stat-card"><span class="stat-label">Retorno</span><strong class="stat-value ${bt.return_pct >= 0 ? "success" : "danger"}">${bt.return_pct.toFixed(2)}%</strong></div>
      <div class="stat-card"><span class="stat-label">Trades</span><strong class="stat-value">${bt.total_trades}</strong></div>
      <div class="stat-card"><span class="stat-label">Win Rate</span><strong class="stat-value">${bt.win_rate.toFixed(1)}%</strong></div>
      <div class="stat-card"><span class="stat-label">Drawdown</span><strong class="stat-value danger">${bt.max_drawdown.toFixed(2)}%</strong></div>`;
    body.innerHTML = bt.trades?.length
      ? bt.trades.map((t, i) => {
          const buy = t.side === "BUY";
          return `<tr><td>${i + 1}</td><td class="${buy ? "buy" : "sell"}">${buy ? "COMPRA" : "VENTA"}</td><td>${toShort(t.price, 2)}</td><td>${toShort(t.quantity, 6)}</td><td>${toShort(t.quote_qty, 2)}</td><td class="${t.pnl != null ? (t.pnl >= 0 ? "success" : "danger") : ""}">${t.pnl != null ? toMoney(t.pnl) : "-"}</td><td>${t.reason || "-"}</td></tr>`;
        }).join("")
      : '<tr><td colspan="7" class="empty">Sin trades</td></tr>';
    res.classList.remove("hidden");
  } catch (err) {
    stats.innerHTML = `<div class="error-msg">Error: ${err.message}</div>`;
    body.innerHTML = "";
    res.classList.remove("hidden");
  }
});

// ── SSE ──
let sseSource;
let sseRetry = 0;
function startSSE() {
  if (sseSource) sseSource.close();
  sseSource = new EventSource(`${API_BASE_URL}/api/stream`);
  sseSource.onmessage = (e) => {
    sseRetry = 0;
    try { const d = JSON.parse(e.data); if (d && d.last_price != null) renderState(d); } catch (_) { }
  };
  sseSource.onerror = () => {
    sseSource.close();
    sseRetry++;
    const delay = Math.min(1000 * Math.pow(2, sseRetry), 30000);
    setTimeout(startSSE, delay);
  };
}

// ── Boot ──
async function bootstrap() {
  // Ensure dashboard visible on load
  $("#tab-dashboard").style.display = "block";
  store.activeTab = "tab-dashboard";
  await loadMarketOptions();
  await loadStrategies();
  initChart();
  initPnlChart();
  try { const d = await api("/api/state"); renderState(d.state); } catch (e) { /* ignore */ }
  await refreshChart("BTCUSDT", "15m");
  startSSE();
  setInterval(() => {
    if (store.activeTab !== "tab-dashboard") return;
    refreshChart($("#chartSymbol").value, $("#chartInterval").value);
  }, 15000);
  setInterval(() => {
    if (store.activeTab !== "tab-history") return;
    loadSessions();
  }, 10000);
}

bootstrap();
