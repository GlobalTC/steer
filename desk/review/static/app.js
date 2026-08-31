(function () {
  "use strict";

  var AUTHOR = "You";
  var TITLE_FALLBACK = "Draft";

  if (isLearn()) {
    window.STEER_LEARN = true;
    AUTHOR = "You";
  }

  function isLearn() {
    try {
      if (window.STEER_LEARN === true) return true;
      if (/(?:^|[?&])learn=1(?:&|$)/.test(location.search)) return true;
      if (/\/learn\/?$/.test(location.pathname)) return true;
    } catch (e) {}
    return false;
  }

  var state = {
    markdown: "",
    savedMarkdown: "",
    mode: "viewing",
    savedAt: null,
    productionReady: false,
    generation: 0,
    dirty: false,
    popKind: null,
    popRange: null,
    idle: false,
    docId: "",
    catalogOpen: false
  };

  var els = {};

  function $(id) {
    return document.getElementById(id);
  }

  function isoNow() {
    return new Date().toISOString();
  }

  function toast(message, isError) {
    els.toast.hidden = false;
    els.toast.textContent = message;
    els.toast.classList.toggle("is-error", !!isError);
    clearTimeout(toast._t);
    toast._t = setTimeout(function () {
      els.toast.hidden = true;
    }, isError ? 5600 : 2800);
  }

  function formatSaved(iso) {
    if (!iso) return "Not saved yet";
    try {
      var d = new Date(iso);
      return d.toLocaleString("en-US", {
        timeZone: "America/Denver",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit"
      }) + " MT";
    } catch (e) {
      return iso;
    }
  }

  function parseMarkdown(src) {
    if (window.marked && typeof marked.parse === "function") {
      return marked.parse(src);
    }
    return "<p>" + escapeHtml(src) + "</p>";
  }

  function parseInline(src) {
    if (window.marked && typeof marked.parseInline === "function") {
      return marked.parseInline(src);
    }
    return escapeHtml(src);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function nextId(md, prefix) {
    var re = new RegExp('id="' + prefix + '(\\d+)"', "g");
    var max = 0;
    var m;
    while ((m = re.exec(md))) {
      max = Math.max(max, parseInt(m[1], 10));
    }
    return prefix + (max + 1);
  }

  function extractMarks(md) {
    var items = [];
    var used = [];

    function markUsed(start, end) {
      used.push([start, end]);
    }
    function overlaps(start, end) {
      return used.some(function (span) {
        return start < span[1] && end > span[0];
      });
    }

    var reHC = /\{==([\s\S]*?)==\}\{>>([\s\S]*?)<<\}(?:\{id="([^"]*)"\s+by="([^"]*)"\s+at="([^"]*)"\})?/g;
    var m;
    while ((m = reHC.exec(md))) {
      items.push({
        type: "comment",
        id: m[3] || "",
        by: m[4] || AUTHOR,
        at: m[5] || "",
        excerpt: m[1],
        body: m[2]
      });
      markUsed(m.index, m.index + m[0].length);
    }

    var reSub = /\{~~([\s\S]*?)~>([\s\S]*?)~~\}(?:\{id="([^"]*)"\s+by="([^"]*)"\s+at="([^"]*)"\})?/g;
    while ((m = reSub.exec(md))) {
      items.push({
        type: "replace",
        id: m[3] || "",
        by: m[4] || AUTHOR,
        at: m[5] || "",
        excerpt: m[1],
        body: m[2]
      });
      markUsed(m.index, m.index + m[0].length);
    }

    var reC = /\{>>([\s\S]*?)<<\}(?:\{id="([^"]*)"\s+by="([^"]*)"\s+at="([^"]*)"\})?/g;
    while ((m = reC.exec(md))) {
      if (overlaps(m.index, m.index + m[0].length)) continue;
      items.push({
        type: "comment",
        id: m[2] || "",
        by: m[3] || AUTHOR,
        at: m[4] || "",
        excerpt: "",
        body: m[1]
      });
    }

    items.sort(function (a, b) {
      var na = parseInt(String(a.id).replace(/\D/g, ""), 10) || 0;
      var nb = parseInt(String(b.id).replace(/\D/g, ""), 10) || 0;
      return na - nb;
    });
    return items;
  }
