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

  function protectCritic(md) {
    var tokens = [];
    function store(html) {
      var key = "@@CM" + tokens.length + "@@";
      tokens.push({ key: key, html: html });
      return key;
    }
    function flag(id, kind) {
      if (!id) return "";
      var label = String(id).replace(/^[cs]/, "");
      return '<button type="button" class="cm-flag" data-jump="' +
        escapeHtml(id) + '" title="' + escapeHtml(kind) + '">' +
        escapeHtml(label) + "</button>";
    }
    function wrapId(inner, id) {
      if (!id) return inner;
      return '<span data-cm-id="' + escapeHtml(id) + '">' + inner + "</span>";
    }

    var out = md;
    out = out.replace(
      /\{==([\s\S]*?)==\}\{>>([\s\S]*?)<<\}(?:\{id="([^"]*)"\s+by="([^"]*)"\s+at="([^"]*)"\})?/g,
      function (_, text, comment, id) {
        var html = wrapId(
          '<mark class="cm-hl">' + parseInline(text) + "</mark>" + flag(id, comment || "Comment"),
          id
        );
        return store(html);
      }
    );
    out = out.replace(
      /\{~~([\s\S]*?)~>([\s\S]*?)~~\}(?:\{id="([^"]*)"\s+by="([^"]*)"\s+at="([^"]*)"\})?/g,
      function (_, oldT, newT, id) {
        var html = wrapId(
          '<del class="cm-del">' + parseInline(oldT) + "</del>" +
          '<ins class="cm-ins">' + parseInline(newT) + "</ins>" +
          flag(id, "Replace"),
          id
        );
        return store(html);
      }
    );
    out = out.replace(
      /\{>>([\s\S]*?)<<\}(?:\{id="([^"]*)"\s+by="([^"]*)"\s+at="([^"]*)"\})?/g,
      function (_, comment, id) {
        var html = wrapId(flag(id || "c", comment || "Comment"), id);
        return store(html);
      }
    );
    out = out.replace(/\{\+\+([\s\S]*?)\+\+\}/g, function (_, text) {
      return store('<ins class="cm-ins">' + parseInline(text) + "</ins>");
    });
    out = out.replace(/\{--([\s\S]*?)--\}/g, function (_, text) {
      return store('<del class="cm-del">' + parseInline(text) + "</del>");
    });
    out = out.replace(/\{==([\s\S]*?)==\}/g, function (_, text) {
      return store('<mark class="cm-hl">' + parseInline(text) + "</mark>");
    });
    return { text: out, tokens: tokens };
  }

  function renderArticle(md) {
    var protectedMd = protectCritic(md);
    var html = parseMarkdown(protectedMd.text);
    for (var i = 0; i < protectedMd.tokens.length; i++) {
      var tok = protectedMd.tokens[i];
      html = html.split(tok.key).join(tok.html);
    }
    return html;
  }
