// Corpus figures for the landing page, read from data/statistics.json (written by
// collector/stats.py and copied in by scripts/build-site.sh). The HTML carries the
// figures of the last edit, so the page is complete without JavaScript or the file;
// this script refreshes them and formats them for the page language.
(function () {
  "use strict";

  // The value at a dotted path such as "layers.sfs.documents", or undefined.
  function lookup(stats, path) {
    return path.split(".").reduce(function (value, key) {
      return value == null ? undefined : value[key];
    }, stats);
  }

  function sum(values) {
    return Object.keys(values || {}).reduce(function (total, key) {
      return total + (values[key] || 0);
    }, 0);
  }

  // The statistics plus the totals the page shows: publishers, words and texts read from PDFs.
  function derive(stats) {
    var layers = stats.layers || {};
    var words = 0;
    Object.keys(layers).forEach(function (layer) {
      var types = layers[layer].types || {};
      Object.keys(types).forEach(function (type) {
        words += types[type].words || 0;
      });
    });
    var text = stats.text || {};
    var result = Object.assign({}, stats);
    result.issuers = sum(stats.issuers);
    result.words = words;
    result.from_pdf = (text.pdf || 0) + (text.ocr || 0);
    return result;
  }

  // Each part of text.web, text.pdf, ... as a percentage of all texts, one decimal.
  function shares(text) {
    var total = sum(text);
    var result = {};
    Object.keys(text || {}).forEach(function (key) {
      result[key] = total ? Math.round((text[key] / total) * 1000) / 10 : 0;
    });
    return result;
  }

  function locale(lang) {
    return lang === "en" ? "en-GB" : "sv-SE";
  }

  function format(value, kind, lang) {
    var loc = locale(lang);
    if (kind === "date") {
      return new Date(value).toLocaleDateString(loc, { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
    }
    if (kind === "percent") {
      return new Intl.NumberFormat(loc, { style: "percent", maximumFractionDigits: 0 }).format(value);
    }
    if (kind === "millions") {
      return new Intl.NumberFormat(loc, { maximumFractionDigits: 0 }).format(value / 1e6);
    }
    return new Intl.NumberFormat(loc).format(value);
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { lookup: lookup, derive: derive, shares: shares, format: format };
    return;
  }

  function render(stats) {
    var lang = document.documentElement.lang;
    document.querySelectorAll("[data-stat]").forEach(function (el) {
      var value = lookup(stats, el.getAttribute("data-stat"));
      if (value == null) return;
      el.textContent = format(value, el.getAttribute("data-format"), lang);
      if (el.tagName === "TIME") el.setAttribute("datetime", String(value).slice(0, 10));
    });
    var parts = shares(stats.text);
    document.querySelectorAll("[data-share]").forEach(function (el) {
      var key = el.getAttribute("data-share").replace(/^text\./, "");
      if (key in parts) el.style.setProperty("--share", parts[key] + "%");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    fetch("data/statistics.json")
      .then(function (response) {
        if (!response.ok) throw new Error("statistics " + response.status);
        return response.json();
      })
      .then(function (raw) {
        var stats = derive(raw);
        render(stats);
        // lang.js switches the page language by setting <html lang>; format again when it does.
        new MutationObserver(function () {
          render(stats);
        }).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
      })
      .catch(function () {
        // No statistics file (a plain checkout of landing/): keep the figures in the HTML.
      });
  });
})();
