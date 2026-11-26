/* Position-size simulator for the brief and pre-open pages. No dependencies.
   Rows and cards carry data-entry, data-stop, data-direction, data-risk-mult (and data-limit, data-cap-pct on some);
   this script recomputes share counts, amounts and maximum loss from the reader's own account and risk %,
   and rewrites the order-parameter text in the chosen broker format. Settings stay in this browser only. */
(function () {
  "use strict";
  var KEY = "pmb-sizer-v1";
  var meta = document.getElementById("sizer-meta");
  var bar = document.getElementById("sizer");
  if (!meta || !bar) { return; }

  var lang = (document.documentElement.getAttribute("lang") || "zh-Hant").toLowerCase();
  var L = lang.indexOf("en") === 0 ? "en" : (lang.indexOf("hans") >= 0 || lang === "zh-cn") ? "sc" : "tc";
  var TXT = {
    tc: { eff: "有效風險：做多 {l}%・做空 {s}%", effFlat: "有效風險：每單位 {l}%（未按 Regime 縮放）", buy: "買入", sellShort: "賣出（沽空）",
      long: "做多", short: "做空", borrow: "｜沽空要融資戶口，並確認有貨可借" },
    sc: { eff: "有效风险：做多 {l}%・做空 {s}%", effFlat: "有效风险：每单位 {l}%（未按 Regime 缩放）", buy: "买入", sellShort: "卖出（沽空）",
      long: "做多", short: "做空", borrow: "｜沽空要融资账户，并确认有货可借" },
    en: { eff: "Effective risk: long {l}% · short {s}%", effFlat: "Effective risk: {l}% per unit (no Regime scaling)", buy: "Buy",
      sellShort: "Sell short", long: "Long", short: "Short", borrow: " | Needs a margin account and shares to borrow" }
  }[L];

  function num(x, d) { var v = parseFloat(x); return isFinite(v) ? v : d; }
  function fmt0(x) { return Math.round(x).toLocaleString("en-US"); }
  function fmt2(x) { return x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function fill(tpl, o) { return tpl.replace(/\{(\w+)\}/g, function (_, k) { return o[k]; }); }

  var eq0 = num(meta.getAttribute("data-equity0"), 100000);
  var r0 = num(meta.getAttribute("data-risk0"), 0.75);
  var multLong = num(meta.getAttribute("data-mult-long"), 1);
  var multShort = num(meta.getAttribute("data-mult-short"), 1);
  var state = { equity: eq0, risk: r0, scale: true, broker: "futu" };
  try {
    var saved = JSON.parse(window.localStorage.getItem(KEY) || "null");
    if (saved && typeof saved === "object") {
      if (num(saved.equity, 0) > 0) { state.equity = num(saved.equity, eq0); }
      if (num(saved.risk, 0) > 0) { state.risk = num(saved.risk, r0); }
      if (typeof saved.scale === "boolean") { state.scale = saved.scale; }
      if (["generic", "futu", "ibkr"].indexOf(saved.broker) >= 0) { state.broker = saved.broker; }
    }
  } catch (e) { /* storage unavailable: defaults */ }
  function save() {
    try { window.localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* ignore */ }
  }

  var inEq = document.getElementById("sz-eq");
  var inRisk = document.getElementById("sz-risk");
  var inScale = document.getElementById("sz-scale");
  var inBroker = document.getElementById("sz-broker");
  var outEff = document.getElementById("sz-eff");

  function effRisk(mult) { return state.equity * state.risk / 100 * (state.scale ? mult : 1); }

  function sharesFor(el) {
    var entry = num(el.getAttribute("data-entry"), NaN), stop = num(el.getAttribute("data-stop"), NaN);
    var mult = num(el.getAttribute("data-risk-mult"), 1);
    var rps = Math.abs(entry - stop);
    if (!(rps > 0) || !(entry > 0)) { return 0; }
    var sh = Math.floor(effRisk(mult) / rps);
    var cap = el.getAttribute("data-cap-pct");
    if (cap !== null && el.getAttribute("data-direction") === "long") {
      var c = Math.floor(num(cap, 100) / 100 * state.equity / entry);
      if (c >= 0) { sh = Math.min(sh, c); }
    }
    var lim = el.getAttribute("data-limit");
    if (lim !== null) {
      var per = Math.abs(num(lim, entry) - stop);
      if (per > 0) { sh = Math.min(sh, Math.floor(sh * rps / per)); }
    }
    return Math.max(sh, 0);
  }

  function orderLine(el, sh) {
    var sym = el.getAttribute("data-sym") || el.getAttribute("data-ticker") || "";
    var lg = el.getAttribute("data-direction") === "long";
    var open = el.getAttribute("data-mode") === "open";
    var trig = fmt2(num(el.getAttribute("data-trigger"), 0)), lim = fmt2(num(el.getAttribute("data-limit"), 0));
    var stop = fmt2(num(el.getAttribute("data-stop"), 0)), piv = fmt2(num(el.getAttribute("data-pivot"), 0));
    var q = sh.toLocaleString("en-US");
    if (state.broker === "ibkr") {
      var s = sym.replace("-", " ");
      if (open) {
        return (lg ? "BUY " : "SELL ") + q + " " + s + " LMT " + lim + " · after the first 30 min, only if " + (lg ? "above" : "below") +
          " pivot " + piv + " · TIF DAY · RTH · attached STP " + stop + " GTC";
      }
      return (lg ? "BUY " : "SELL ") + q + " " + s + " STP LMT · stop " + trig + " · limit " + lim + " · TIF DAY · RTH · attached STP " + stop + " GTC";
    }
    if (state.broker === "generic") {
      var dir = lg ? TXT.long : TXT.short;
      if (L === "en") {
        return sym + " | " + dir + " | " + (open ? "Pivot " + piv + " (after the open)" : "Trigger " + trig) + " | Limit " + lim +
          " | Invalidation " + stop + " | Qty " + q;
      }
      var g = L === "sc" ? ["触发位 ", "pivot ", "（开盘后判定）", "限价 ", "形态失效位 ", "试算数量 "] : ["觸發位 ", "pivot ", "（開市後判定）", "限價 ", "形態失效位 ", "試算數量 "];
      return sym + "｜" + dir + "｜" + (open ? g[1] + piv + g[2] : g[0] + trig) + "｜" + g[3] + lim + "｜" + g[4] + stop + "｜" + g[5] + q;
    }
    var t = sym.replace("-", ".");                                  /* Futu writes BRK-B as BRK.B */
    if (L === "en") {
      if (open) {
        return t + " | After the open: if it holds above pivot " + piv + " for the first 30 minutes, limit buy at no more than " + lim +
          ", qty " + q + "; then a sell stop at " + stop;
      }
      return t + " | " + (lg ? TXT.buy : TXT.sellShort) + " | Stop limit | Trigger " + trig + " | Price " + lim + " | Qty " + q +
        " | Day | Regular hours only | Attached: stop " + stop + ", GTC" + (lg ? "" : TXT.borrow);
    }
    if (open) {
      return L === "sc"
        ? t + "｜开盘后判定：首 30 分钟站在 pivot " + piv + " 之上，限价买入，价格不高于 " + lim + "，数量 " + q + "；成交后设卖出止损单，止损价 " + stop
        : t + "｜開市後判定：首 30 分鐘企在 pivot " + piv + " 之上，限價買入，價格不高於 " + lim + "，數量 " + q + "；成交後設賣出止損單，止損價 " + stop;
    }
    if (L === "sc") {
      return t + "｜" + (lg ? TXT.buy : TXT.sellShort) + "｜止损限价单｜触发价 " + trig + "｜价格 " + lim + "｜数量 " + q +
        "｜期限 当日有效｜只在常规时段触发（不选盘前盘后）｜附加订单：止损单，止损价 " + stop + "，子单期限 撤单前有效" + (lg ? "" : TXT.borrow);
    }
    return t + "｜" + (lg ? TXT.buy : TXT.sellShort) + "｜止損限價單｜觸發價 " + trig + "｜價格 " + lim + "｜數量 " + q +
      "｜期限 當日有效｜只在常規時段觸發（不選盤前盤後）｜附加訂單：止損單，止損價 " + stop + "，子單期限 撤單前有效" + (lg ? "" : TXT.borrow);
  }

  function setAll(root, f, text) {
    var list = root.querySelectorAll('[data-f="' + f + '"]');
    for (var i = 0; i < list.length; i++) { list[i].textContent = text; }
  }

  function recalc() {
    var rows = document.querySelectorAll("[data-entry]");
    for (var i = 0; i < rows.length; i++) {
      var el = rows[i];
      var sh = sharesFor(el);
      var entry = num(el.getAttribute("data-entry"), 0), stop = num(el.getAttribute("data-stop"), 0);
      var calc = el.getAttribute("data-limit") !== null ? num(el.getAttribute("data-limit"), entry) : entry;
      var notional = sh * entry;
      setAll(el, "shares", sh.toLocaleString("en-US"));
      setAll(el, "notional", fmt0(notional));
      setAll(el, "pct", (state.equity > 0 ? notional / state.equity * 100 : 0).toFixed(1));
      setAll(el, "loss", fmt0(sh * Math.abs(calc - stop)));
      if (el.hasAttribute("data-order")) { el.textContent = orderLine(el, sh); }
    }
    var risks = document.querySelectorAll("[data-risk]");
    for (var j = 0; j < risks.length; j++) { risks[j].textContent = fmt0(effRisk(num(risks[j].getAttribute("data-risk-mult"), 1))); }
    var rp = document.querySelectorAll("[data-riskpct]");
    for (var k = 0; k < rp.length; k++) {
      rp[k].textContent = (state.equity > 0 ? effRisk(num(rp[k].getAttribute("data-risk-mult"), 1)) / state.equity * 100 : 0).toFixed(2);
    }
    if (outEff) {
      outEff.textContent = state.scale
        ? fill(TXT.eff, { l: (state.risk * multLong).toFixed(2), s: (state.risk * multShort).toFixed(2) })
        : fill(TXT.effFlat, { l: state.risk.toFixed(2) });
    }
  }

  function readInputs() {
    var e = num(inEq && inEq.value, NaN), r = num(inRisk && inRisk.value, NaN);
    var okE = e >= 100 && e <= 1e10, okR = r > 0 && r <= 10;
    if (inEq) { inEq.setAttribute("aria-invalid", okE ? "false" : "true"); }
    if (inRisk) { inRisk.setAttribute("aria-invalid", okR ? "false" : "true"); }
    if (okE) { state.equity = e; }
    if (okR) { state.risk = r; }
    if (inScale) { state.scale = !!inScale.checked; }
    if (inBroker && ["generic", "futu", "ibkr"].indexOf(inBroker.value) >= 0) { state.broker = inBroker.value; }
    save();
    recalc();
  }

  if (inEq) { inEq.value = String(state.equity); inEq.addEventListener("input", readInputs); }
  if (inRisk) { inRisk.value = String(state.risk); inRisk.addEventListener("input", readInputs); }
  if (inScale) { inScale.checked = state.scale; inScale.addEventListener("change", readInputs); }
  if (inBroker) { inBroker.value = state.broker; inBroker.addEventListener("change", readInputs); }
  var presets = bar.querySelectorAll("[data-eq]");
  for (var p = 0; p < presets.length; p++) {
    presets[p].addEventListener("click", function (ev) {
      if (inEq) { inEq.value = ev.currentTarget.getAttribute("data-eq"); }
      readInputs();
    });
  }
  bar.hidden = false;
  recalc();
}());
