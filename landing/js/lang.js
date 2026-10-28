// Swedish / English switch for the landing page. The Swedish text is in the HTML,
// so the page is complete without JavaScript; this script swaps strings from
// i18n/<lang>.json and remembers the choice on the device.
(function () {
  "use strict";

  var SUPPORTED = ["sv", "en"];
  var STORAGE_KEY = "lagar.lang";

  function supported(lang) {
    return SUPPORTED.indexOf(lang) !== -1 ? lang : null;
  }

  // Query parameter first, then the stored choice, then the browser language.
  // English only for an English browser; every other language gets Swedish.
  function resolveLanguage(stored, query, navigatorLanguage) {
    return (
      supported(query) ||
      supported(stored) ||
      (/^en\b/i.test(navigatorLanguage || "") ? "en" : "sv")
    );
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { resolveLanguage: resolveLanguage };
    return;
  }

  function readStored() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function store(lang) {
    try {
      window.localStorage.setItem(STORAGE_KEY, lang);
    } catch (e) {
      // Storage blocked: the choice lasts for this page view only.
    }
  }

  var swedish = null; // strings read from the HTML, so switching back needs no request

  function snapshot() {
    var strings = {};
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      strings[el.getAttribute("data-i18n")] = el.textContent;
    });
    document.querySelectorAll("[data-i18n-attr]").forEach(function (el) {
      el.getAttribute("data-i18n-attr").split(";").forEach(function (pair) {
        var parts = pair.split(":");
        strings[parts[1]] = el.getAttribute(parts[0]);
      });
    });
    return strings;
  }

  function apply(strings, lang) {
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var value = strings[el.getAttribute("data-i18n")];
      if (value) el.textContent = value;
    });
    document.querySelectorAll("[data-i18n-attr]").forEach(function (el) {
      el.getAttribute("data-i18n-attr").split(";").forEach(function (pair) {
        var parts = pair.split(":");
        var value = strings[parts[1]];
        if (value) el.setAttribute(parts[0], value);
      });
    });
    document.documentElement.lang = lang;
    var toggle = document.getElementById("lang-toggle");
    toggle.textContent = lang === "sv" ? "EN" : "SV";
  }

  function load(lang) {
    if (lang === "sv") return Promise.resolve(swedish);
    return fetch("i18n/" + lang + ".json").then(function (response) {
      if (!response.ok) throw new Error("i18n " + response.status);
      return response.json();
    });
  }

  function setQuery(lang) {
    var url = new URL(window.location.href);
    if (lang === "sv") url.searchParams.delete("lang");
    else url.searchParams.set("lang", lang);
    window.history.replaceState(null, "", url);
  }

  function show(lang, remember) {
    return load(lang).then(function (strings) {
      apply(strings, lang);
      setQuery(lang);
      if (remember) store(lang);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    swedish = snapshot();
    var toggle = document.getElementById("lang-toggle");
    var current = resolveLanguage(
      readStored(),
      new URLSearchParams(window.location.search).get("lang"),
      navigator.language
    );

    toggle.hidden = false;
    toggle.addEventListener("click", function () {
      current = document.documentElement.lang === "sv" ? "en" : "sv";
      show(current, true).catch(function () {
        current = "sv";
      });
    });

    if (current !== "sv") {
      show(current, false).catch(function () {
        // Strings unavailable: stay on the Swedish page.
      });
    }
  });
})();
