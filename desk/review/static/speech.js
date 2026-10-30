/**
 * Swappable speech-to-text adapter. Default: browser Web Speech API.
 * Replace SteerSpeech.createRecognizer via config later (e.g. server STT).
 */
(function (global) {
  "use strict";

  function browserSupported() {
    return !!(
      global.SpeechRecognition ||
      global.webkitSpeechRecognition
    );
  }

  function createBrowserRecognizer(options) {
    var Ctor = global.SpeechRecognition || global.webkitSpeechRecognition;
    if (!Ctor) {
      return {
        start: function (_a, _b, onError) {
          if (onError) onError(new Error("Speech recognition not supported"));
        },
        stop: function () {},
        abort: function () {}
      };
    }
    var rec = new Ctor();
    rec.lang = (options && options.lang) || "en-US";
    rec.interimResults = !!(options && options.interimResults);
    rec.continuous = !!(options && options.continuous);
    var active = false;

    return {
      start: function (onPartial, onFinal, onError) {
        if (active) return;
        active = true;
        rec.onresult = function (ev) {
          var interim = "";
          var final = "";
          for (var i = ev.resultIndex; i < ev.results.length; i++) {
            var chunk = ev.results[i][0].transcript;
            if (ev.results[i].isFinal) final += chunk;
            else interim += chunk;
          }
          if (interim && onPartial) onPartial(interim);
          if (final && onFinal) onFinal(final.trim());
        };
        rec.onerror = function (ev) {
          active = false;
          if (onError) onError(ev.error || ev);
        };
        rec.onend = function () {
          active = false;
        };
        try {
          rec.start();
        } catch (err) {
          active = false;
          if (onError) onError(err);
        }
      },
      stop: function () {
        try {
          rec.stop();
        } catch (e) {}
        active = false;
      },
      abort: function () {
        try {
          rec.abort();
        } catch (e) {}
        active = false;
      }
    };
  }

  global.SteerSpeech = {
    isSupported: browserSupported,
    createRecognizer: function (options) {
      var backend = (options && options.backend) || "browser";
      if (backend === "browser") return createBrowserRecognizer(options);
      return createBrowserRecognizer(options);
    }
  };
})(typeof window !== "undefined" ? window : globalThis);
