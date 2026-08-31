(function () {
  "use strict";

  if (!window.STEER_LEARN) return;

  var STEPS = [
    {
      id: "sandbox",
      title: "Sandbox",
      body: "This is the real desk, with the catalog unplugged. Marks, Save, and Ready stay in this tab.",
      spot: null,
      mode: "viewing"
    },
    {
      id: "viewing",
      title: "Viewing",
      body: "Read the paper. You cannot type here. Switch modes with the pills in the middle of the toolbar.",
      spot: "modes",
      mode: "viewing"
    },
    {
      id: "editing",
      title: "Editing",
      body: "The source. Change a word if you want — it will not stick after a reload.",
      spot: "modes",
      mode: "editing"
    },
    {
      id: "suggesting",
      title: "Suggesting",
      body: "Select the slop phrase in the paper, then Comment or Replace. That is the spec.",
      spot: "modes",
      mode: "suggesting"
    },
    {
      id: "save",
      title: "Save",
      body: "On a real draft this writes the file and wakes Steer. Here it only pretends. Try it.",
      spot: "save",
      mode: null
    },
    {
      id: "ready",
      title: "Ready",
      body: "Ready means shippable. Publishing is a later ask. Here it is also pretend.",
      spot: "ready",
      mode: null
    },
    {
      id: "done",
      title: "That’s the loop",
      body: "Mark. Save. Rewrite. You stay the authority. Reset the tutorial anytime, or leave Learn for the live desk.",
      spot: null,
      mode: "viewing"
    }
  ];

  var step = 0;

  function $(id) { return document.getElementById(id); }

  function spotEl(name) {
    if (name === "modes") return document.querySelector(".modes");
    if (name === "save") return $("save-btn");
    if (name === "ready") return $("ready-btn");
    return null;
  }

  function clearSpot() {
    document.querySelectorAll(".tour-spot").forEach(function (el) {
      el.classList.remove("tour-spot");
    });
  }

  function show(i) {
    step = Math.max(0, Math.min(STEPS.length - 1, i));
    var s = STEPS[step];
    $("tour-title").textContent = s.title;
    $("tour-body").textContent = s.body;
    $("tour-step").textContent = (step + 1) + " / " + STEPS.length;
    $("tour-prev").disabled = step === 0;
    $("tour-next").textContent = step === STEPS.length - 1 ? "Done" : "Next";
    clearSpot();
    var el = spotEl(s.spot);
    if (el) el.classList.add("tour-spot");
    if (s.mode) {
      var btn = document.querySelector('.mode[data-mode="' + s.mode + '"]');
      if (btn) btn.click();
    }
  }

  function resetTutorial() {
    var src = window.__TUTORIAL_SRC;
    if (!src) return;
    if (typeof window.__steerApplyLearn === "function") {
      window.__steerApplyLearn(src);
    }
  }

  function mount() {
    document.body.classList.add("is-learn");
    $("tour-prev").addEventListener("click", function () { show(step - 1); });
    $("tour-next").addEventListener("click", function () {
      if (step >= STEPS.length - 1) {
        clearSpot();
        $("tour-coach").hidden = true;
        return;
      }
      show(step + 1);
    });
    $("tour-reset").addEventListener("click", resetTutorial);
    show(0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
