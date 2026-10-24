/* 나만의 신문 — 지면 인터랙션 (외부 라이브러리 없음, HTML 에 인라인으로 들어감) */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var root = document.documentElement;
  var edition = document.body.dataset.edition || "";

  // localStorage 는 시크릿 창 등에서 막힐 수 있으므로 항상 감싼다.
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };

  var toastTimer;
  function toast(msg) {
    var el = $("#toast"); if (!el) return;
    el.textContent = msg; el.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { el.classList.remove("show"); }, 2200);
  }

  /* ── 테마: 라이트 → 종이(세피아) → 다크 ── */
  var THEMES = [["light", "☀️ 라이트"], ["sepia", "📜 종이"], ["dark", "🌙 다크"]];
  function applyTheme(name) {
    root.dataset.theme = name;
    var label = THEMES.filter(function (t) { return t[0] === name; })[0] || THEMES[0];
    var btn = $("#themeBtn"); if (btn) btn.textContent = label[1];
  }
  function cycleTheme() {
    var i = THEMES.map(function (t) { return t[0]; }).indexOf(root.dataset.theme);
    var next = THEMES[(i + 1) % THEMES.length][0];
    applyTheme(next); store.set("np-theme", next); toast(THEMES[(i + 1) % THEMES.length][1] + " 테마");
  }
  applyTheme(root.dataset.theme || "light");

  /* ── 글자 크기 ── */
  function setFont(delta) {
    var cur = parseFloat(getComputedStyle(root).getPropertyValue("--fs")) || 1;
    var next = Math.min(1.3, Math.max(0.85, Math.round((cur + delta * 0.05) * 100) / 100));
    root.style.setProperty("--fs", next); store.set("np-fs", next); toast("글자 크기 " + Math.round(next * 100) + "%");
  }

  /* ── 읽기 진행 바 · 맨 위로 ── */
  var progress = $("#progress"), toTop = $("#toTop");
  function onScroll() {
    var h = document.documentElement.scrollHeight - innerHeight;
    if (progress) progress.style.width = (h > 0 ? (scrollY / h) * 100 : 0) + "%";
    if (toTop) toTop.classList.toggle("show", scrollY > 600);
  }
  addEventListener("scroll", onScroll, { passive: true }); onScroll();
  if (toTop) toTop.addEventListener("click", function () { scrollTo({ top: 0 }); });

  /* ── 읽음 표시 (발행일별로 브라우저에 저장) ── */
  var READ_KEY = "np-read-" + edition;
  var read = {};
  store.get(READ_KEY, "").split(",").forEach(function (u) { if (u) read[u] = 1; });
  var stories = $$(".story");
  function renderRead() {
    var n = 0;
    stories.forEach(function (s) {
      var on = !!read[s.dataset.uid]; if (on) n++;
      s.classList.toggle("is-read", on);
      var b = $("[data-toggle-read]", s); if (b) { b.classList.toggle("is-on", on); b.textContent = on ? "✓ 읽었음" : "✓ 읽음 표시"; }
    });
    var rc = $("#readCount b"); if (rc) rc.textContent = n;
  }
  function markRead(uid, value) {
    if (!uid) return;
    if (value === false) delete read[uid]; else read[uid] = 1;
    store.set(READ_KEY, Object.keys(read).join(",")); renderRead();
  }
  renderRead();
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-toggle-read]");
    if (t) { var u = t.dataset.toggleRead; markRead(u, !read[u]); return; }
    var link = e.target.closest("a[data-read]");
    if (link) { var s = link.closest(".story"); if (s) markRead(s.dataset.uid); }
  });
  $$("details[data-read-on-open]").forEach(function (d) {
    d.addEventListener("toggle", function () { if (d.open) { var s = d.closest(".story"); if (s) markRead(s.dataset.uid); } });
  });

  /* ── 검색 / 키워드 필터 ── */
  var q = $("#q"), status = $("#searchStatus");
  var titles = $$(".section-title");
  function clearMarks() {
    $$("mark[data-hl]").forEach(function (m) { m.replaceWith(document.createTextNode(m.textContent)); });
    $$(".story h2 a, .story h3 a, .story h4 a, .story .summary").forEach(function (el) { el.normalize(); });
  }
  function highlight(el, term) {
    if (!el || !term) return;
    var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), nodes = [], n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(function (node) {
      var i = node.nodeValue.toLowerCase().indexOf(term); if (i < 0) return;
      var hit = node.splitText(i); hit.splitText(term.length);
      var m = document.createElement("mark"); m.dataset.hl = "1"; m.textContent = hit.nodeValue; hit.replaceWith(m);
    });
  }
  function filter(text) {
    var terms = (text || "").toLowerCase().trim().split(/\s+/).filter(Boolean);
    clearMarks();
    var shown = 0;
    stories.forEach(function (s) {
      var hay = s.dataset.search || "";
      var ok = terms.every(function (t) { return hay.indexOf(t) >= 0; });
      s.classList.toggle("is-hidden", !ok); if (ok) shown++;
      if (ok && terms.length) terms.forEach(function (t) { highlight($("h2 a, h3 a, h4 a", s), t); highlight($(".summary", s), t); });
    });
    titles.forEach(function (t) {
      var any = false, el = t.nextElementSibling;
      while (el && !el.classList.contains("section-title")) { if (!el.classList.contains("is-hidden")) any = true; el = el.nextElementSibling; }
      t.classList.toggle("is-hidden", !any);
    });
    $$(".chip").forEach(function (c) { c.classList.toggle("is-on", terms.length === 1 && c.dataset.filter.toLowerCase() === terms[0]); });
    if (status) status.textContent = terms.length ? "‘" + text.trim() + "’ 검색 결과 " + shown + "건" + (shown ? "" : " — Esc 로 지우기") : "";
  }
  if (q) q.addEventListener("input", function () { filter(q.value); });
  $$(".chip").forEach(function (c) {
    c.addEventListener("click", function () {
      var same = q && q.value.trim().toLowerCase() === c.dataset.filter.toLowerCase();
      if (q) q.value = same ? "" : c.dataset.filter; filter(q ? q.value : "");
      if (!same) { var first = $(".story:not(.is-hidden)"); if (first) first.scrollIntoView({ block: "start" }); }
    });
  });

  /* ── 음성으로 듣기 (Web Speech API) ── */
  var synth = window.speechSynthesis, speakingBtn = null;
  function stopSpeech() {
    if (synth) synth.cancel();
    if (speakingBtn) { speakingBtn.classList.remove("speaking", "is-on"); speakingBtn = null; }
  }
  function speak(text, btn) {
    if (!synth || !window.SpeechSynthesisUtterance) { toast("이 브라우저는 음성 읽기를 지원하지 않습니다"); return; }
    if (speakingBtn === btn) { stopSpeech(); return; }
    stopSpeech();
    var u = new SpeechSynthesisUtterance(text);
    u.lang = "ko-KR"; u.rate = 1.03;
    var ko = synth.getVoices().filter(function (v) { return /^ko/i.test(v.lang); })[0]; if (ko) u.voice = ko;
    u.onend = u.onerror = function () { if (speakingBtn === btn) stopSpeech(); };
    speakingBtn = btn; if (btn) btn.classList.add("speaking", "is-on");
    synth.speak(u);
  }
  function briefingText() {
    var parts = ["오늘의 " + ($(".masthead h1") || {}).textContent + " 브리핑입니다."];
    $$("#briefList li").forEach(function (li, i) { parts.push((i + 1) + ". " + li.textContent + "."); });
    var note = $("#editorNote"); if (note) parts.push("편집장 한마디. " + note.lastChild.textContent);
    parts.push("이상 오늘의 브리핑이었습니다.");
    return parts.join(" ");
  }
  var sb = $("#speakBriefing"); if (sb) sb.addEventListener("click", function () { speak(briefingText(), sb); });
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-speak]"); if (!b) return;
    var s = document.getElementById(b.dataset.speak); if (!s) return;
    speak(s.dataset.speech || "", b); markRead(s.dataset.uid);
  });
  addEventListener("beforeunload", stopSpeech);

  /* ── 공유 / 인쇄 / 도움말 ── */
  var share = $("#shareBtn");
  if (share) share.addEventListener("click", function () {
    var data = { title: document.title, url: location.href };
    if (navigator.share) { navigator.share(data).catch(function () {}); return; }
    if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(function () { toast("링크를 복사했습니다"); }, function () { toast(location.href); });
    else toast(location.href);
  });
  var pb = $("#printBtn"); if (pb) pb.addEventListener("click", function () { print(); });
  var help = $("#help"), hb = $("#helpBtn");
  function openHelp() { if (help && help.showModal && !help.open) help.showModal(); }
  if (hb) hb.addEventListener("click", openHelp);
  $$("[data-font]").forEach(function (b) { b.addEventListener("click", function () { setFont(+b.dataset.font); }); });
  var tb = $("#themeBtn"); if (tb) tb.addEventListener("click", cycleTheme);

  /* ── 단축키 ── */
  function jump(dir) {
    var visible = stories.filter(function (s) { return !s.classList.contains("is-hidden"); });
    var y = scrollY + 80, target = null;
    if (dir > 0) target = visible.filter(function (s) { return s.getBoundingClientRect().top + scrollY > y + 5; })[0];
    else target = visible.filter(function (s) { return s.getBoundingClientRect().top + scrollY < y - 5; }).pop();
    if (target) target.scrollIntoView({ block: "start" });
  }
  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var typing = /INPUT|TEXTAREA|SELECT/.test((e.target || {}).tagName || "");
    if (typing) { if (e.key === "Escape" && q) { q.value = ""; filter(""); q.blur(); } return; }
    switch (e.key) {
      case "/": e.preventDefault(); if (q) q.focus(); break;
      case "t": case "T": cycleTheme(); break;
      case "+": case "=": setFont(1); break;
      case "-": setFont(-1); break;
      case "b": case "B": if (sb) sb.click(); break;
      case "j": case "J": jump(1); break;
      case "k": case "K": jump(-1); break;
      case "p": case "P": print(); break;
      case "?": openHelp(); break;
      case "Escape": stopSpeech(); break;
    }
  });

  /* ── 스크롤 등장 애니메이션 ── */
  var reveals = $$(".reveal");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
    }, { rootMargin: "0px 0px -8% 0px" });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("in"); });
  }
  // 인쇄할 때는 애니메이션 대기 없이 모두 보이게
  addEventListener("beforeprint", function () { reveals.forEach(function (el) { el.classList.add("in"); }); $$("details.fulltext").forEach(function (d) { d.open = false; }); });
})();
