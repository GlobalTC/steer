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

  function buildVisibleIndex(src) {
    var vis = [];
    var map = [];
    var used = [];
    var i = 0;
    var cmDepth = 0;
    var n = src.length;

    function starts(s) {
      return src.substr(i, s.length) === s;
    }

    while (i < n) {
      if (starts("{id=")) {
        var brace = src.indexOf("}", i);
        if (brace !== -1) {
          i = brace + 1;
          continue;
        }
      }
      if (starts("{>>")) {
        var cend = src.indexOf("<<}", i);
        if (cend !== -1) {
          i = cend + 3;
          continue;
        }
      }
      if (starts("{==") || starts("{++") || starts("{--") || starts("{~~")) {
        cmDepth += 1;
        i += 3;
        continue;
      }
      if (starts("==}") || starts("++}") || starts("--}") || starts("~~}")) {
        cmDepth = Math.max(0, cmDepth - 1);
        i += 3;
        continue;
      }
      if (starts("~>") && cmDepth > 0) {
        i += 2;
        continue;
      }
      if ((i === 0 || src.charAt(i - 1) === "\n") && src.charAt(i) === "#") {
        while (i < n && src.charAt(i) === "#") i += 1;
        if (src.charAt(i) === " ") i += 1;
        continue;
      }
      if (src.charAt(i) === "\\" && i + 1 < n) {
        i += 1;
        vis.push(src.charAt(i));
        map.push(i);
        used.push(cmDepth > 0);
        i += 1;
        continue;
      }
      if (starts("**") || starts("__")) {
        i += 2;
        continue;
      }
      var ch = src.charAt(i);
      if (ch === "*" || ch === "_" || ch === "`") {
        i += 1;
        continue;
      }
      vis.push(ch);
      map.push(i);
      used.push(cmDepth > 0);
      i += 1;
    }
    return { vis: vis.join(""), map: map, used: used };
  }

  function findUnused(vis, used, needle) {
    var hits = [];
    if (!needle) return hits;
    var pos = 0;
    while (pos <= vis.length - needle.length) {
      var at = vis.indexOf(needle, pos);
      if (at < 0) break;
      var blocked = false;
      for (var k = 0; k < needle.length; k++) {
        if (used[at + k]) {
          blocked = true;
          break;
        }
      }
      if (!blocked) hits.push(at);
      pos = at + 1;
    }
    return hits;
  }

  function visBlockRange(vis, index) {
    var a = vis.lastIndexOf("\n\n", index);
    a = a === -1 ? 0 : a + 2;
    var b = vis.indexOf("\n\n", index);
    b = b === -1 ? vis.length : b;
    return [a, b];
  }

  function expandMarkup(src, start, end) {
    var pairs = ["**", "__", "*", "_", "`"];
    for (var i = 0; i < pairs.length; i++) {
      var w = pairs[i];
      if (start >= w.length && src.slice(start - w.length, start) === w && src.slice(start, end).indexOf(w) !== -1) {
        start -= w.length;
      }
      if (src.slice(end, end + w.length) === w && src.slice(start, end).indexOf(w) !== -1) {
        end += w.length;
      }
    }
    return [start, end];
  }

  function mapSelection(selected, src, context) {
    var idx = buildVisibleIndex(src);
    var raw = selected;
    var trimmed = selected.replace(/\s+/g, " ").trim();
    var needle = raw;
    var hits = findUnused(idx.vis, idx.used, raw);
    if (!hits.length && trimmed && trimmed !== raw) {
      needle = trimmed;
      hits = findUnused(idx.vis, idx.used, trimmed);
    }
    if (!hits.length && trimmed) {
      var visNorm = idx.vis.replace(/[ \t]+/g, " ");
      // Fall through: try original paragraph-local search below via context only.
      hits = findUnused(idx.vis, idx.used, trimmed.replace(/\n/g, "\n\n"));
      if (hits.length) needle = trimmed.replace(/\n/g, "\n\n");
    }
    if (!hits.length) {
      return {
        error: "Could not map that selection back to the source. Try a unique phrase inside one paragraph, and avoid text that is already marked."
      };
    }
    if (hits.length > 1 && context) {
      var ctx = context.replace(/\s+/g, " ").trim();
      var filtered = hits.filter(function (at) {
        var range = visBlockRange(idx.vis, at);
        var block = idx.vis.slice(range[0], range[1]).replace(/\s+/g, " ").trim();
        return block === ctx || block.indexOf(ctx) !== -1 || (ctx && ctx.indexOf(block) !== -1);
      });
      if (filtered.length) hits = filtered;
    }
    var at = hits[0];
    var srcStart = idx.map[at];
    var lastVis = at + needle.length - 1;
    if (lastVis >= idx.map.length) {
      return { error: "Could not map that selection back to the source." };
    }
    var srcEnd = idx.map[lastVis] + 1;
    var expanded = expandMarkup(src, srcStart, srcEnd);
    return {
      start: expanded[0],
      end: expanded[1],
      text: src.slice(expanded[0], expanded[1])
    };
  }
