/**
 * Voice markup: select-and-speak + free dictation with proposed marks.
 */
(function () {
  "use strict";

  var api = null;
  var dictationRecognizer = null;
  var selectionRecognizer = null;
  var proposed = [];
  var dictationTranscript = "";

  function $(id) {
    return document.getElementById(id);
  }

  function bindApi(detail) {
    api = detail;
    wireUi();
  }

  function wireUi() {
    var micSel = $("voice-mic-selection");
    var micDict = $("voice-mic-dictation");
    var dictBar = $("voice-dictation-bar");
    if (micSel) {
      micSel.addEventListener("click", startSelectionVoice);
    }
    if (micDict) {
      micDict.addEventListener("click", toggleDictation);
    }
    if (dictBar) {
      dictBar.addEventListener("click", function (ev) {
        if (ev.target.closest("[data-voice-stop]")) stopDictation(true);
        if (ev.target.closest("[data-voice-resolve]")) resolveDictation();
      });
    }
    document.addEventListener("click", function (ev) {
      var accept = ev.target.closest("[data-proposal-accept]");
      var reject = ev.target.closest("[data-proposal-reject]");
      var edit = ev.target.closest("[data-proposal-edit]");
      if (accept) acceptProposal(accept.getAttribute("data-proposal-accept"));
      if (reject) rejectProposal(reject.getAttribute("data-proposal-reject"));
      if (edit) editProposal(edit.getAttribute("data-proposal-edit"));
    });
  }

  function ensureSuggesting() {
    if (api.mode() !== "suggesting") api.setMode("suggesting");
  }

  function startSelectionVoice() {
    if (!api || !window.SteerSpeech || !SteerSpeech.isSupported()) {
      api.toast("Voice input is not available in this browser.", true);
      return;
    }
    ensureSuggesting();
    var range = api.getPopRange();
    if (!range) {
      api.toast("Select text or tap a paragraph first.", true);
      return;
    }
    stopDictation(false);
    if (selectionRecognizer) selectionRecognizer.abort();
    selectionRecognizer = SteerSpeech.createRecognizer({ continuous: false });
    api.toast("Listening…");
    setMicActive($("voice-mic-selection"), true);
    selectionRecognizer.start(
      null,
      function (text) {
        setMicActive($("voice-mic-selection"), false);
        if (!text) return;
        api.applyVoiceComment(text);
      },
      function () {
        setMicActive($("voice-mic-selection"), false);
        api.toast("Could not capture speech.", true);
      }
    );
  }

  function toggleDictation() {
    if (!api || !window.SteerSpeech || !SteerSpeech.isSupported()) {
      api.toast("Voice input is not available in this browser.", true);
      return;
    }
    ensureSuggesting();
    if (dictationRecognizer) {
      stopDictation(true);
      return;
    }
    dictationTranscript = "";
    updateDictationUi("");
    dictationRecognizer = SteerSpeech.createRecognizer({
      continuous: true,
      interimResults: true
    });
    setMicActive($("voice-mic-dictation"), true);
    $("voice-dictation-bar").hidden = false;
    api.toast("Dictation on — talk through your edits");
    dictationRecognizer.start(
      function (partial) {
        updateDictationUi(dictationTranscript + " " + partial);
      },
      function (finalChunk) {
        dictationTranscript = (dictationTranscript + " " + finalChunk).trim();
        updateDictationUi(dictationTranscript);
      },
      function () {
        setMicActive($("voice-mic-dictation"), false);
      }
    );
  }

  function stopDictation(resolve) {
    if (dictationRecognizer) {
      dictationRecognizer.stop();
      dictationRecognizer = null;
    }
    setMicActive($("voice-mic-dictation"), false);
    if (resolve && dictationTranscript.trim()) {
      resolveDictation();
    }
  }

  function updateDictationUi(text) {
    var el = $("voice-dictation-text");
    if (el) el.textContent = text || "…";
  }

  function setMicActive(btn, on) {
    if (!btn) return;
    btn.classList.toggle("is-recording", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  }

  async function resolveDictation() {
    var transcript = dictationTranscript.trim();
    if (!transcript) {
      api.toast("Say something first.", true);
      return;
    }
    $("voice-dictation-bar").hidden = true;
    dictationRecognizer = null;
    setMicActive($("voice-mic-dictation"), false);
    api.toast("Resolving marks…");
    try {
      var res = await fetch("/steer/api/resolve-voice", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: transcript,
          markdown: api.getMarkdown()
        })
      });
      var data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "Resolve failed");
      proposed = (data.proposals || []).map(function (p, i) {
        p._pid = "p" + i + "-" + Date.now();
        p._status = "proposed";
        return p;
      });
      dictationTranscript = "";
      renderProposals();
      if (!proposed.length) api.toast("No marks resolved — try shorter instructions.");
      else api.toast(proposed.length + " proposed mark(s) — review below");
    } catch (err) {
      api.toast(err.message || "Resolve failed", true);
    }
  }

  function renderProposals() {
    var list = $("voice-proposals");
    var wrap = $("voice-proposals-wrap");
    if (!list || !wrap) return;
    list.innerHTML = "";
    var active = proposed.filter(function (p) {
      return p._status === "proposed";
    });
    wrap.hidden = !proposed.length;
    proposed.forEach(function (p) {
      var li = document.createElement("li");
      li.className = "voice-proposal";
      if (p._status !== "proposed") li.classList.add("is-" + p._status);
      var head = document.createElement("div");
      head.className = "voice-proposal-head";
      var kind = p.kind === "replace" ? "Replace" : p.kind === "general" ? "General note" : "Comment";
      head.textContent =
        kind +
        (p.confidence != null ? " · " + Math.round(p.confidence * 100) + "%" : "");
      var body = document.createElement("p");
      body.className = "voice-proposal-body";
      body.textContent = p.kind === "replace" ? (p.excerpt || "") + " → " + (p.replace_with || p.body) : p.body;
      if (p.excerpt && p.kind === "comment") {
        var ex = document.createElement("p");
        ex.className = "voice-proposal-excerpt";
        ex.textContent = p.excerpt.replace(/\s+/g, " ").slice(0, 120);
        li.appendChild(ex);
      }
      var actions = document.createElement("div");
      actions.className = "voice-proposal-actions";
      if (p._status === "proposed") {
        var acc = document.createElement("button");
        acc.type = "button";
        acc.className = "btn btn-touch btn-primary";
        acc.textContent = "Accept";
        acc.setAttribute("data-proposal-accept", p._pid);
        var rej = document.createElement("button");
        rej.type = "button";
        rej.className = "btn btn-touch";
        rej.textContent = "Reject";
        rej.setAttribute("data-proposal-reject", p._pid);
        actions.appendChild(acc);
        actions.appendChild(rej);
      } else {
        actions.textContent = p._status === "accepted" ? "Accepted" : "Rejected";
      }
      li.appendChild(head);
      li.appendChild(body);
      li.appendChild(actions);
      list.appendChild(li);
    });
    if (api && api.syncDrawer) api.syncDrawer();
  }

  function findProposal(pid) {
    for (var i = 0; i < proposed.length; i++) {
      if (proposed[i]._pid === pid) return proposed[i];
    }
    return null;
  }

  function acceptProposal(pid) {
    var p = findProposal(pid);
    if (!p || p._status !== "proposed") return;
    api.applyVoiceProposal(p);
    p._status = "accepted";
    renderProposals();
  }

  function rejectProposal(pid) {
    var p = findProposal(pid);
    if (!p) return;
    p._status = "rejected";
    renderProposals();
  }

  function editProposal(pid) {
    var p = findProposal(pid);
    if (!p) return;
    var next = window.prompt("Edit note", p.body);
    if (next != null && next.trim()) p.body = next.trim();
    renderProposals();
  }

  window.addEventListener("steer:ready", function (ev) {
    bindApi(ev.detail);
  });

  /** QA / demo: inject resolver output without microphone. */
  window.__steerInjectVoiceProposals = function (items) {
    if (!api) return;
    proposed = (items || []).map(function (p, i) {
      p._pid = "p" + i + "-" + Date.now();
      p._status = "proposed";
      return p;
    });
    renderProposals();
  };
})();
