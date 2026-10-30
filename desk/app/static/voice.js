/**
 * Voice markup: select-and-speak + free dictation with proposed marks.
 */
(function () {
  "use strict";

  var CFG = window.STEER_CONFIG || {};
  var BASE = typeof CFG.base === "string" ? CFG.base : "/steer";

  var api = null;
  var dictationRecognizer = null;
  var selectionRecognizer = null;
  var selectionRecording = false;
  var proposed = [];
  var dictationTranscript = "";
  var dictationBackend = null;

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
      micSel.addEventListener("click", onSelectionMic);
    }
    if (micDict) {
      micDict.addEventListener("click", toggleDictation);
    }
    if (dictBar) {
      dictBar.addEventListener("click", function (ev) {
        if (ev.target.closest("[data-voice-done]")) finishDictation();
      });
    }
    document.addEventListener("click", function (ev) {
      var accept = ev.target.closest("[data-proposal-accept]");
      var reject = ev.target.closest("[data-proposal-reject]");
      if (accept) acceptProposal(accept.getAttribute("data-proposal-accept"));
      if (reject) rejectProposal(reject.getAttribute("data-proposal-reject"));
    });
  }

  function ensureSuggesting() {
    if (api.mode() !== "suggesting") api.setMode("suggesting");
  }

  function speechUnavailableMessage() {
    return "Voice input is unavailable. Use Chrome for built-in speech, or configure server STT (VOICE_STT_URL).";
  }

  function onSelectionMic() {
    if (!api || !window.SteerSpeech) {
      api.toast(speechUnavailableMessage(), true);
      return;
    }
    SteerSpeech.isSupported().then(function (ok) {
      if (!ok) {
        api.toast(speechUnavailableMessage(), true);
        return;
      }
      if (selectionRecording && selectionRecognizer) {
        selectionRecognizer.stop();
        return;
      }
      ensureSuggesting();
      var range = api.getPopRange();
      if (!range) {
        api.toast("Select text or tap a paragraph first.", true);
        return;
      }
      stopDictation(false);
      SteerSpeech.createAutoRecognizer({ continuous: false }).then(function (rec) {
        selectionRecognizer = rec;
        selectionRecording = true;
        api.toast(rec.backend === "server" ? "Recording… tap Mic when done" : "Listening…");
        setMicActive($("voice-mic-selection"), true);
        rec.start(
          null,
          function (text) {
            selectionRecording = false;
            setMicActive($("voice-mic-selection"), false);
            selectionRecognizer = null;
            if (!text) return;
            api.applyVoiceComment(text);
          },
          function (err) {
            selectionRecording = false;
            setMicActive($("voice-mic-selection"), false);
            selectionRecognizer = null;
            api.toast((err && err.message) || "Could not capture speech.", true);
          }
        );
      });
    });
  }

  function toggleDictation() {
    if (!api || !window.SteerSpeech) {
      api.toast(speechUnavailableMessage(), true);
      return;
    }
    SteerSpeech.isSupported().then(function (ok) {
      if (!ok) {
        api.toast(speechUnavailableMessage(), true);
        return;
      }
      if (dictationRecognizer) {
        finishDictation();
        return;
      }
      ensureSuggesting();
      dictationTranscript = "";
      updateDictationUi("");
      SteerSpeech.createAutoRecognizer({
        continuous: true,
        interimResults: true
      }).then(function (rec) {
        dictationRecognizer = rec;
        dictationBackend = rec.backend;
        setMicActive($("voice-mic-dictation"), true);
        $("voice-dictation-bar").hidden = false;
        api.toast(
          rec.backend === "server"
            ? "Recording — tap Done when finished"
            : "Dictation on — tap Done when finished"
        );
        rec.start(
          function (partial) {
            if (rec.backend === "server") {
              updateDictationUi("Recording… " + (partial || ""));
            } else {
              updateDictationUi((dictationTranscript + " " + partial).trim());
            }
          },
          function (finalChunk) {
            if (rec.backend === "browser") {
              dictationTranscript = (dictationTranscript + " " + finalChunk).trim();
              updateDictationUi(dictationTranscript);
            } else {
              dictationTranscript = (finalChunk || "").trim();
              updateDictationUi(dictationTranscript);
              resolveDictation();
            }
          },
          function () {
            setMicActive($("voice-mic-dictation"), false);
          }
        );
      });
    });
  }

  function finishDictation() {
    if (!dictationRecognizer) return;
    var rec = dictationRecognizer;
    dictationRecognizer = null;
    setMicActive($("voice-mic-dictation"), false);
    if (rec.backend === "browser") {
      rec.stop();
      setTimeout(function () {
        resolveDictation();
      }, 350);
    } else {
      rec.stop();
    }
  }

  function stopDictation(_resolve) {
    if (dictationRecognizer) {
      dictationRecognizer.abort();
      dictationRecognizer = null;
    }
    setMicActive($("voice-mic-dictation"), false);
    $("voice-dictation-bar").hidden = true;
    dictationTranscript = "";
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

  function scopeLabel(p) {
    if (p.anchor_scope === "phrase" || (p.anchor && p.kind !== "general")) {
      return "Phrase anchor";
    }
    return "General note (unanchored)";
  }

  async function resolveDictation() {
    var transcript = dictationTranscript.trim();
    $("voice-dictation-bar").hidden = true;
    dictationRecognizer = null;
    setMicActive($("voice-mic-dictation"), false);
    if (!transcript) {
      api.toast("Say something first.", true);
      return;
    }
    api.toast("Resolving marks…");
    try {
      var res = await fetch(BASE + "/api/resolve-voice", {
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
    wrap.hidden = !proposed.length;
    proposed.forEach(function (p) {
      var li = document.createElement("li");
      li.className = "voice-proposal";
      if (p._status !== "proposed") li.classList.add("is-" + p._status);
      var head = document.createElement("div");
      head.className = "voice-proposal-head";
      var kind =
        p.kind === "replace" ? "Replace" : p.kind === "general" ? "General note" : "Comment";
      var conf =
        p.confidence != null ? Math.round(p.confidence * 100) + "% confidence" : "";
      head.textContent = [kind, conf, scopeLabel(p)].filter(Boolean).join(" · ");
      var body = document.createElement("p");
      body.className = "voice-proposal-body";
      body.textContent =
        p.kind === "replace"
          ? (p.excerpt || "") + " → " + (p.replace_with || p.body)
          : p.body;
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
    if (proposed.length && api && api.ensureDrawerVisible) {
      api.ensureDrawerVisible();
    }
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

  window.addEventListener("steer:ready", function (ev) {
    bindApi(ev.detail);
  });

})();
