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

  function currentMarkdown() {
    if (state.mode === "editing") return els.editor.value;
    return state.markdown;
  }

  function setDirty(value) {
    state.dirty = value;
    updateStatus();
  }

  function isIdle() {
    return !!state.idle && !isLearn();
  }

  function catalogShouldShow() {
    if (isLearn()) return false;
    if (state.mode !== "viewing") return false;
    if (state.idle) return true;
    return !!state.catalogOpen;
  }

  function syncCatalogPanel() {
    var show = catalogShouldShow();
    if (els.catalogPanel) els.catalogPanel.hidden = !show;
    if (els.catalogToggle) {
      els.catalogToggle.setAttribute("aria-expanded", show ? "true" : "false");
      els.catalogToggle.classList.toggle("is-open", show && !state.idle);
    }
    if (els.article && state.mode === "viewing") {
      els.article.hidden = show;
    }
  }

  var catalogAssets = [];

  function loadCatalog() {
    if (isLearn()) return Promise.resolve();
    return fetch("/steer/api/catalog")
      .then(function (res) { return res.json(); })
      .then(function (data) {
        catalogAssets = data.assets || [];
        renderCatalog();
      })
      .catch(function () {
        renderCatalog();
      });
  }

  function renderCatalog() {
    if (!els.catalogList) return;
    var q = ((els.catalogSearch && els.catalogSearch.value) || "").trim().toLowerCase();
    var assets = catalogAssets || [];
    var matches = assets.filter(function (a) {
      if (!q) return true;
      var tags = Array.isArray(a.tags) ? a.tags.join(" ") : "";
      var hay = [a.title || "", a.dek || "", a.id || "", tags].join(" ").toLowerCase();
      return hay.indexOf(q) !== -1;
    });
    els.catalogList.innerHTML = "";
    if (!assets.length) {
      var empty = document.createElement("p");
      empty.className = "catalog-empty";
      empty.textContent = "No drafts in the catalog yet.";
      els.catalogList.appendChild(empty);
      return;
    }
    if (!matches.length) {
      var none = document.createElement("p");
      none.className = "catalog-empty";
      none.textContent = "No drafts match.";
      els.catalogList.appendChild(none);
      return;
    }
    matches.forEach(function (a) {
      var row = document.createElement("button");
      row.type = "button";
      row.className = "catalog-row";
      row.setAttribute("role", "listitem");
      var title = document.createElement("div");
      title.className = "catalog-row-title";
      title.textContent = a.title || a.id || "Draft";
      row.appendChild(title);
      if (a.dek) {
        var dek = document.createElement("p");
        dek.className = "catalog-row-dek";
        dek.textContent = a.dek;
        row.appendChild(dek);
      }
      row.addEventListener("click", function () {
        selectCatalogAsset(a.id);
      });
      els.catalogList.appendChild(row);
    });
  }

  async function selectCatalogAsset(id) {
    if (!id || isLearn()) return;
    try {
      var res = await fetch("/steer/api/current", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: id })
      });
      var data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "Could not load that draft");
      state.catalogOpen = false;
      applyDoc(data, true);
    } catch (err) {
      toast(err.message || "Could not load that draft", true);
    }
  }

  function updateStatus() {
    var idle = isIdle();
    var parts = [];
    if (idle) parts.push("Nothing on the desk");
    else if (state.savedAt) parts.push("Saved " + formatSaved(state.savedAt));
    else parts.push("Not saved yet");
    if (!idle) {
      if (state.dirty) parts.push("Unsaved changes");
      else if (state.savedAt) parts.push("All changes saved");
      if (state.productionReady) parts.push("Production ready");
    }
    els.status.textContent = parts.join(" · ");
    els.status.classList.toggle("is-dirty", !idle && state.dirty);
    els.readyBtn.disabled = idle || !state.savedAt || state.dirty;
    els.saveBtn.disabled = idle;
    els.readyBtn.textContent = state.productionReady ? "Production ready" : "Ready for production";
  }


  function removeMark(id) {
    if (!id) return;
    var md = currentMarkdown();
    var escaped = String(id).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    var specs = [
      ["\\{==([\\s\\S]*?)==\\}\\{>>[\\s\\S]*?<<\\}\\{id=\"" + escaped + "\"[^}]*\\}", "$1"],
      ["\\{~~([\\s\\S]*?)~>[\\s\\S]*?~~\\}\\{id=\"" + escaped + "\"[^}]*\\}", "$1"],
      ["\\{>>[\\s\\S]*?<<\\}\\{id=\"" + escaped + "\"[^}]*\\}", ""]
    ];
    var next = md;
    var hit = false;
    for (var i = 0; i < specs.length; i++) {
      var re = new RegExp(specs[i][0]);
      if (re.test(md)) {
        next = md.replace(new RegExp(specs[i][0]), specs[i][1]);
        hit = true;
        break;
      }
    }
    if (!hit || next === md) {
      toast("Could not remove that mark.", true);
      return;
    }
    state.markdown = next;
    if (state.mode === "editing") els.editor.value = next;
    setDirty(next !== state.savedMarkdown);
    paintRendered();
    renderDrawer();
  }

  function renderDrawer() {
    var marks = extractMarks(currentMarkdown());
    els.markList.innerHTML = "";
    if (!marks.length) {
      els.drawer.hidden = state.mode !== "suggesting";
      els.workspace.classList.toggle("has-drawer", !els.drawer.hidden);
      els.drawerCount.textContent = "No comments or replacements yet";
      var empty = document.createElement("p");
      empty.className = "mark-empty";
      empty.textContent = state.mode === "suggesting"
        ? "Select a phrase in the article to comment or replace."
        : "Nothing marked.";
      els.markList.appendChild(empty);
      return;
    }
    els.drawer.hidden = false;
    els.workspace.classList.toggle("has-drawer", true);
    els.drawerCount.textContent = marks.length + (marks.length === 1 ? " mark" : " marks");
    marks.forEach(function (mark) {
      var li = document.createElement("li");
      li.className = "mark-row";
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "mark-item";
      btn.dataset.jump = mark.id;
      var head = document.createElement("div");
      head.className = "mark-head";
      var kind = document.createElement("span");
      kind.className = "mark-kind";
      kind.textContent = (mark.type === "replace" ? "Replace" : "Comment") + (mark.id ? " · " + mark.id : "");
      head.appendChild(kind);
      var body = document.createElement("div");
      body.className = "mark-body";
      body.textContent = mark.type === "replace" ? mark.excerpt + " → " + mark.body : mark.body;
      btn.appendChild(head);
      btn.appendChild(body);
      if (mark.excerpt && mark.type === "comment") {
        var ex = document.createElement("div");
        ex.className = "mark-excerpt";
        ex.textContent = mark.excerpt.replace(/\s+/g, " ").slice(0, 140);
        btn.appendChild(ex);
      }
      var del = document.createElement("button");
      del.type = "button";
      del.className = "mark-delete";
      del.textContent = "Delete";
      del.setAttribute("aria-label", "Delete " + (mark.id || "mark"));
      del.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        removeMark(mark.id);
      });
      li.appendChild(btn);
      li.appendChild(del);
      els.markList.appendChild(li);
    });
  }

  function paintRendered() {
    var html = renderArticle(state.markdown);
    els.article.innerHTML = html;
    els.livePreview.innerHTML = html;
  }

  function setMode(mode) {
    if (state.mode === "editing" && mode !== "editing") {
      state.markdown = els.editor.value;
    }
    state.mode = mode;
    if (mode !== "viewing") state.catalogOpen = false;
    document.querySelectorAll(".mode").forEach(function (btn) {
      var on = btn.getAttribute("data-mode") === mode;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
    var editing = mode === "editing";
    els.article.hidden = editing;
    els.editLayout.hidden = !editing;
    if (editing) {
      els.editor.value = state.markdown;
      els.livePreview.innerHTML = renderArticle(state.markdown);
    } else {
      paintRendered();
    }
    hidePopover();
    els.article.classList.toggle("is-suggesting", mode === "suggesting");
    renderDrawer();
    updateStatus();
    syncCatalogPanel();
  }

  function hidePopover() {
    els.popover.hidden = true;
    els.popoverForm.hidden = true;
    els.popoverActions.hidden = false;
    els.popoverInput.value = "";
    state.popKind = null;
    state.popRange = null;
  }

  function placePopover(x, y) {
    els.popover.hidden = false;
    var pad = 8;
    var w = els.popover.offsetWidth;
    var h = els.popover.offsetHeight;
    var left = Math.min(x, window.innerWidth - w - pad);
    var top = Math.min(y, window.innerHeight - h - pad);
    els.popover.style.left = Math.max(pad, left) + "px";
    els.popover.style.top = Math.max(pad, top) + "px";
  }

  function selectionContext(range) {
    var node = range.commonAncestorContainer;
    if (node.nodeType === 3) node = node.parentElement;
    if (!node || !node.closest) return "";
    var block = node.closest("p, h1, h2, h3, h4, li, blockquote");
    return block ? block.textContent : "";
  }

  function considerSelection(ev) {
    if (state.mode !== "suggesting") return;
    if (els.article.hidden) return;
    if (ev && ev.target) {
      if (els.popover.contains(ev.target)) return;
      if (els.drawer && els.drawer.contains(ev.target)) return;
      if (els.toolbar && els.toolbar.contains(ev.target)) return;
      if (ev.target.closest && ev.target.closest(".tour-coach, .learn-banner")) return;
    }
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) {
      if (!els.popover.hidden) return;
      hidePopover();
      return;
    }
    var range = sel.getRangeAt(0);
    if (!els.article.contains(range.commonAncestorContainer)) {
      if (!els.popover.hidden) return;
      hidePopover();
      return;
    }
    var text = sel.toString();
    if (!text || !text.trim()) {
      if (!els.popover.hidden) return;
      hidePopover();
      return;
    }
    var mapped = mapSelection(text, state.markdown, selectionContext(range));
    if (mapped.error) {
      hidePopover();
      toast(mapped.error, true);
      return;
    }
    state.popRange = mapped;
    if (!state.popKind) {
      els.popoverForm.hidden = true;
      els.popoverActions.hidden = false;
    }
    var rect = range.getBoundingClientRect();
    var x = rect.left;
    var y = rect.bottom + 8;
    if (y + 120 > window.innerHeight) y = Math.max(8, rect.top - 56);
    placePopover(x, y);
  }

  function scheduleSelection(ev) {
    clearTimeout(scheduleSelection._t);
    scheduleSelection._t = setTimeout(function () {
      considerSelection(ev);
    }, 80);
  }

  function openPopForm(kind) {
    state.popKind = kind;
    els.popoverActions.hidden = true;
    els.popoverForm.hidden = false;
    if (kind === "comment") {
      els.popoverInput.placeholder = "Comment";
      els.popoverInput.value = "";
    } else {
      els.popoverInput.placeholder = "Replacement text";
      els.popoverInput.value = state.popRange ? state.popRange.text : "";
    }
    els.popoverInput.focus();
  }

  function applySuggestion(ev) {
    ev.preventDefault();
    if (!state.popRange || !state.popKind) return;
    var note = els.popoverInput.value;
    if (state.popKind === "comment" && !note.trim()) {
      toast("Write a comment first.", true);
      return;
    }
    if (state.popKind === "replace" && note === state.popRange.text) {
      toast("Replacement is the same as the original.", true);
      return;
    }
    var md = state.markdown;
    var chunk = md.slice(state.popRange.start, state.popRange.end);
    if (chunk !== state.popRange.text) {
      toast("The source moved. Select the phrase again.", true);
      hidePopover();
      return;
    }
    var stamp = isoNow();
    var wrapped;
    if (state.popKind === "comment") {
      var cid = nextId(md, "c");
      wrapped = "{==" + chunk + "==}{>>" + note.trim() + "<<}{id=\"" + cid + "\" by=\"" + AUTHOR + "\" at=\"" + stamp + "\"}";
    } else {
      var sid = nextId(md, "s");
      wrapped = "{~~" + chunk + "~>" + note + "~~}{id=\"" + sid + "\" by=\"" + AUTHOR + "\" at=\"" + stamp + "\"}";
    }
    state.markdown = md.slice(0, state.popRange.start) + wrapped + md.slice(state.popRange.end);
    setDirty(state.markdown !== state.savedMarkdown);
    paintRendered();
    renderDrawer();
    hidePopover();
    window.getSelection().removeAllRanges();
  }

  function jumpTo(id) {
    if (!id) return;
    if (state.mode === "editing") setMode("suggesting");
    var target = els.article.querySelector('[data-cm-id="' + id + '"]');
    if (!target) return;
    target.classList.add("cm-focus");
    target.scrollIntoView({ block: "center", behavior: "smooth" });
    setTimeout(function () { target.classList.remove("cm-focus"); }, 1600);
  }

  async function save() {
    if (state.mode === "editing") state.markdown = els.editor.value;
    if (isIdle()) return;
    if (isLearn()) {
      state.savedMarkdown = state.markdown;
      state.savedAt = isoNow();
      setDirty(false);
      toast("Tutorial: not written to the catalog");
      return;
    }
    var comments = extractMarks(state.markdown);
    els.saveBtn.disabled = true;
    try {
      var res = await fetch("/steer/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          markdown: state.markdown,
          mode: state.mode,
          comments: comments
        })
      });
      var data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "Save failed");
      state.savedMarkdown = state.markdown;
      state.savedAt = data.saved_at;
      state.generation = data.generation;
      state.productionReady = false;
      if (data.asset_mtime) state.assetMtime = data.asset_mtime;
      setDirty(false);
      toast("Saved");
    } catch (err) {
      toast(err.message || "Save failed", true);
    } finally {
      els.saveBtn.disabled = isIdle();
    }
  }

  function openReadyModal() {
    if (isIdle()) return;
    if (state.dirty || !state.savedAt) {
      els.modalNote.hidden = false;
      els.modalNote.textContent = "Save first. Ready for production flags the last saved draft.";
      els.modalConfirm.disabled = true;
    } else {
      els.modalNote.hidden = true;
      els.modalConfirm.disabled = false;
    }
    els.modal.hidden = false;
  }

  async function confirmReady() {
    if (isLearn()) {
      state.productionReady = true;
      updateStatus();
      els.modal.hidden = true;
      toast("Tutorial: ready not sent");
      return;
    }
    try {
      var res = await fetch("/steer/api/ready", { method: "POST" });
      var data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "Could not mark ready");
      state.productionReady = true;
      updateStatus();
      els.modal.hidden = true;
      toast("Marked ready for production");
    } catch (err) {
      toast(err.message || "Could not mark ready", true);
    }
  }

  async function applyDoc(data, resetMode) {
    state.markdown = data.markdown || "";
    state.savedMarkdown = state.markdown;
    state.savedAt = data.saved_at || null;
    state.productionReady = !!data.production_ready;
    state.generation = data.generation || 0;
    state.assetMtime = data.asset_mtime || 0;
    state.docId = data.id || "";
    state.idle = !!data.idle;
    state.catalogOpen = false;
    els.docTitle.textContent = data.title || TITLE_FALLBACK;
    document.title = els.docTitle.textContent;
    if (resetMode) setMode("viewing");
    else if (state.mode === "editing") {
      els.editor.value = state.markdown;
      els.livePreview.innerHTML = renderArticle(state.markdown);
    } else {
      paintRendered();
    }
    renderDrawer();
    setDirty(false);
    syncCatalogPanel();
    if (state.idle && !isLearn()) loadCatalog();
  }

  async function loadLearn() {
    var res = await fetch("/steer/static/tutorial.md?v=12");
    if (!res.ok) throw new Error("Could not load the tutorial");
    var md = await res.text();
    window.__TUTORIAL_SRC = md;
    applyDoc({
      markdown: md,
      title: "How Steer works",
      saved_at: null,
      generation: 0,
      production_ready: false
    }, true);
    document.body.classList.add("is-learn");
    var coach = document.getElementById("tour-coach");
    if (coach) coach.hidden = false;
  }

  window.__steerApplyLearn = function (md) {
    applyDoc({
      markdown: md,
      title: "How Steer works",
      saved_at: null,
      generation: 0,
      production_ready: false
    }, true);
  };

  async function load(resetMode) {
    if (isLearn()) return loadLearn();
    var res = await fetch("/steer/api/doc");
    var data = await res.json();
    applyDoc(data, resetMode !== false);
  }

  function watchEvents() {
    if (isLearn()) return;
    if (!window.EventSource) return;
    var primed = false;
    var es = new EventSource("/steer/api/events");
    es.onmessage = function (ev) {
      var data;
      try { data = JSON.parse(ev.data); } catch (e) { return; }
      var processed = data.processed_generation || 0;
      if (!primed) {
        primed = true;
        if (data.asset_mtime) state.assetMtime = data.asset_mtime;
        state.seenProcessed = processed;
        if (data.id) state.docId = data.id;
        return;
      }
      if (data.id && state.docId && data.id !== state.docId) {
        if (state.dirty) return;
        state.docId = data.id;
        load(true).then(function () {
          toast("Draft updated");
        }).catch(function () {});
        return;
      }
      if (data.asset_mtime) state.assetMtime = data.asset_mtime;
      // Own Save bumps generation. That is not a Composer rewrite.
      if (data.generation && data.generation === state.generation && processed === (state.seenProcessed || 0)) {
        return;
      }
      if (state.dirty) return;
      if (processed && processed !== state.seenProcessed) {
        state.seenProcessed = processed;
        load(false).then(function () {
          toast("Draft updated");
        }).catch(function () {});
      }
    };
    es.onerror = function () { /* browser will retry */ };
  }
