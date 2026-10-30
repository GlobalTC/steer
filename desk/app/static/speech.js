/**
 * Swappable speech-to-text: Web Speech API or server transcription (MediaRecorder).
 */
(function (global) {
  "use strict";

  var CFG = global.STEER_CONFIG || {};
  var BASE = typeof CFG.base === "string" ? CFG.base : "/steer";

  var configPromise = null;
  var cachedConfig = null;

  function browserSupported() {
    return !!(
      global.SpeechRecognition ||
      global.webkitSpeechRecognition
    );
  }

  function loadConfig() {
    if (cachedConfig) return Promise.resolve(cachedConfig);
    if (configPromise) return configPromise;
    configPromise = fetch(BASE + "/api/voice-config")
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        cachedConfig = data || {};
        return cachedConfig;
      })
      .catch(function () {
        cachedConfig = { server_stt_configured: false };
        return cachedConfig;
      });
    return configPromise;
  }

  function pickBackend(cfg) {
    if (browserSupported()) return "browser";
    if (cfg && cfg.server_stt_configured) return "server";
    return null;
  }

  function unavailableRecognizer(message) {
    return {
      start: function (_a, _b, onError) {
        if (onError) onError(new Error(message));
      },
      stop: function () {},
      abort: function () {}
    };
  }

  function createBrowserRecognizer(options) {
    var Ctor = global.SpeechRecognition || global.webkitSpeechRecognition;
    if (!Ctor) {
      return unavailableRecognizer("Speech recognition not supported in this browser.");
    }
    var rec = new Ctor();
    rec.lang = (options && options.lang) || "en-US";
    rec.interimResults = !!(options && options.interimResults);
    rec.continuous = !!(options && options.continuous);
    var active = false;

    return {
      backend: "browser",
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

  function createServerRecognizer(options) {
    var uploadUrl =
      (options && options.uploadUrl) ||
      (cachedConfig && cachedConfig.transcribe_path) ||
      BASE + "/api/transcribe-voice";
    var stream = null;
    var recorder = null;
    var chunks = [];
    var active = false;
    var mimeType = "audio/webm";

    function pickMime() {
      if (global.MediaRecorder && MediaRecorder.isTypeSupported) {
        if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
          return "audio/webm;codecs=opus";
        }
        if (MediaRecorder.isTypeSupported("audio/webm")) return "audio/webm";
        if (MediaRecorder.isTypeSupported("audio/mp4")) return "audio/mp4";
      }
      return "audio/webm";
    }

    return {
      backend: "server",
      start: function (onPartial, onFinal, onError) {
        if (active) return;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          if (onError) onError(new Error("Microphone not available in this browser."));
          return;
        }
        active = true;
        chunks = [];
        mimeType = pickMime();
        navigator.mediaDevices
          .getUserMedia({ audio: true })
          .then(function (s) {
            stream = s;
            recorder = new MediaRecorder(s, { mimeType: mimeType });
            recorder.ondataavailable = function (ev) {
              if (ev.data && ev.data.size) chunks.push(ev.data);
            };
            recorder.onerror = function (ev) {
              active = false;
              if (onError) onError(ev.error || ev);
            };
            recorder.onstop = function () {
              active = false;
              if (stream) {
                stream.getTracks().forEach(function (t) {
                  t.stop();
                });
              }
              stream = null;
              var blob = new Blob(chunks, { type: mimeType.split(";")[0] });
              chunks = [];
              if (!blob.size) {
                if (onError) onError(new Error("No audio captured."));
                return;
              }
              var form = new FormData();
              form.append("audio", blob, "clip.webm");
              fetch(uploadUrl, { method: "POST", body: form })
                .then(function (res) {
                  return res.json().then(function (data) {
                    return { res: res, data: data };
                  });
                })
                .then(function (out) {
                  if (!out.res.ok || !out.data.ok) {
                    throw new Error(
                      out.data.error || "Server transcription failed."
                    );
                  }
                  if (onFinal) onFinal(out.data.transcript || "");
                })
                .catch(function (err) {
                  if (onError) onError(err);
                });
            };
            recorder.start(250);
            if (onPartial) onPartial("Recording…");
          })
          .catch(function (err) {
            active = false;
            if (onError) onError(err);
          });
      },
      stop: function () {
        if (recorder && recorder.state !== "inactive") {
          try {
            recorder.stop();
          } catch (e) {}
        } else {
          active = false;
        }
      },
      abort: function () {
        chunks = [];
        if (recorder && recorder.state !== "inactive") {
          try {
            recorder.stop();
          } catch (e) {}
        }
        if (stream) {
          stream.getTracks().forEach(function (t) {
            t.stop();
          });
        }
        stream = null;
        active = false;
      }
    };
  }

  function createRecognizer(options) {
    var backend = (options && options.backend) || "browser";
    if (backend === "server") return createServerRecognizer(options);
    return createBrowserRecognizer(options);
  }

  function createAutoRecognizer(options) {
    return loadConfig().then(function (cfg) {
      var backend = pickBackend(cfg);
      if (!backend) {
        return unavailableRecognizer(
          "Voice input is unavailable. Use a browser with speech recognition or configure server STT (VOICE_STT_URL)."
        );
      }
      return createRecognizer(
        Object.assign({}, options || {}, {
          backend: backend,
          uploadUrl: cfg.transcribe_path || BASE + "/api/transcribe-voice"
        })
      );
    });
  }

  function isSupportedSync() {
    return browserSupported();
  }

  function isSupported() {
    return loadConfig().then(function (cfg) {
      return !!pickBackend(cfg);
    });
  }

  global.SteerSpeech = {
    browserSupported: browserSupported,
    isSupported: isSupported,
    isSupportedSync: isSupportedSync,
    loadConfig: loadConfig,
    pickBackend: function () {
      return loadConfig().then(pickBackend);
    },
    createRecognizer: createRecognizer,
    createAutoRecognizer: createAutoRecognizer
  };
})(typeof window !== "undefined" ? window : globalThis);
