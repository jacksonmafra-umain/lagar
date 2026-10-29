// Catalog of every legal source lagar tracks, read from data/sources.json (written
// by collector/agencies.py). One tab per section; each lists its entries with a
// filter, a sort order and pages of PAGE_SIZE rows. Labels come from hidden
// data-i18n elements in the page, so the language switch in lang.js covers them.
(function () {
  "use strict";

  var PAGE_SIZE = 20;

  function fold(text) {
    return String(text || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");
  }

  // Rows matching every word of the query in their name, code, agency, county or text.
  function filterRows(rows, query) {
    var words = fold(query).split(/\s+/).filter(Boolean);
    if (!words.length) return rows.slice();
    return rows.filter(function (row) {
      var haystack = fold(
        [row.name, row.code, row.agency, row.county, row.published_in, row.series, row.description, row.note].join(" ")
      );
      return words.every(function (word) {
        return haystack.indexOf(word) !== -1;
      });
    });
  }

  function byName(a, b) {
    // Swedish collation: Å, Ä and Ö after Z.
    return String(a.name).localeCompare(String(b.name), "sv", { sensitivity: "base" });
  }

  // "name": A to Ö; "status": the order of `statuses`, then name; "documents": most first, then name.
  function sortRows(rows, order, statuses) {
    var sorted = rows.slice();
    if (order === "status") {
      sorted.sort(function (a, b) {
        return statuses.indexOf(a.status) - statuses.indexOf(b.status) || byName(a, b);
      });
    } else if (order === "documents") {
      sorted.sort(function (a, b) {
        return (b.documents || 0) - (a.documents || 0) || byName(a, b);
      });
    } else {
      sorted.sort(byName);
    }
    return sorted;
  }

  // The rows of one page (1-based, clamped) and the page count.
  function paginate(rows, page, size) {
    var pages = Math.max(1, Math.ceil(rows.length / size));
    var current = Math.min(Math.max(1, page), pages);
    return { rows: rows.slice((current - 1) * size, current * size), page: current, pages: pages };
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { filterRows: filterRows, sortRows: sortRows, paginate: paginate, PAGE_SIZE: PAGE_SIZE };
    return;
  }

  var catalog = null;
  var state = { section: "series", query: "", order: "name", page: 1 };

  function label(key) {
    var el = document.querySelector('#catalog-labels [data-i18n="' + key + '"]');
    return el ? el.textContent : key;
  }

  function format(key, values) {
    return label(key).replace(/\{(\w+)\}/g, function (_, name) {
      return values[name];
    });
  }

  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (name) {
      node.setAttribute(name, attrs[name]);
    });
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function detail(row) {
    var parts = [];
    if (row.agency) parts.push(row.agency);
    if (row.published_in) parts.push(format("catalog.published_in", { series: row.published_in }));
    if (row.county && row.code) parts.push(row.county + " · " + row.code);
    else if (row.code) parts.push(row.code);
    if (row.years) parts.push(row.years);
    return parts.join(" · ");
  }

  function renderRow(row) {
    var item = el("li", { class: "entry" });
    var head = el("div", { class: "entry__head" });
    var name = row.url
      ? el("a", { href: row.url, class: "entry__name", rel: "noopener", target: "_blank" }, row.name)
      : el("span", { class: "entry__name" }, row.name);
    head.appendChild(name);
    var status = el("span", { class: "status status--" + row.status }, label("catalog.status." + row.status));
    head.appendChild(status);
    item.appendChild(head);
    var meta = detail(row);
    if (meta) item.appendChild(el("p", { class: "entry__meta" }, meta));
    if (row.description) item.appendChild(el("p", { class: "entry__desc", lang: "sv" }, row.description));
    else if (row.note) item.appendChild(el("p", { class: "entry__desc", lang: "en" }, row.note));
    var foot = el("p", { class: "entry__foot" });
    if (row.documents) foot.appendChild(el("span", null, format("catalog.documents", { n: row.documents.toLocaleString("sv-SE") })));
    if (row.issue) {
      var number = row.issue.split("/").pop();
      foot.appendChild(el("a", { href: row.issue, rel: "noopener", target: "_blank" }, format("catalog.issue", { n: number })));
    }
    if (foot.childNodes.length) item.appendChild(foot);
    return item;
  }

  function render() {
    if (!catalog) return;
    var rows = sortRows(filterRows(catalog.sections[state.section] || [], state.query), state.order, catalog.statuses);
    var view = paginate(rows, state.page, PAGE_SIZE);
    state.page = view.page;
    var list = document.getElementById("catalog-list");
    list.textContent = "";
    view.rows.forEach(function (row) {
      list.appendChild(renderRow(row));
    });
    document.getElementById("catalog-count").textContent = format("catalog.count", { n: rows.length });
    document.getElementById("catalog-page").textContent = format("catalog.page", { page: view.page, pages: view.pages });
    document.getElementById("catalog-prev").disabled = view.page <= 1;
    document.getElementById("catalog-next").disabled = view.page >= view.pages;
  }

  function select(section) {
    state.section = section;
    state.page = 1;
    document.querySelectorAll("#catalog [role=tab]").forEach(function (tab) {
      var selected = tab.getAttribute("data-section") === section;
      tab.setAttribute("aria-selected", selected ? "true" : "false");
      tab.tabIndex = selected ? 0 : -1;
    });
    document.querySelectorAll("#catalog [role=tabpanel] .catalog__about").forEach(function (about) {
      about.hidden = about.getAttribute("data-section") !== section;
    });
    render();
  }

  document.addEventListener("DOMContentLoaded", function () {
    var root = document.getElementById("catalog");
    if (!root) return;
    var tabs = Array.prototype.slice.call(root.querySelectorAll("[role=tab]"));
    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () {
        select(tab.getAttribute("data-section"));
      });
      tab.addEventListener("keydown", function (event) {
        var step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
        if (!step) return;
        var next = tabs[(i + step + tabs.length) % tabs.length];
        next.focus();
        select(next.getAttribute("data-section"));
      });
    });
    document.getElementById("catalog-filter").addEventListener("input", function (event) {
      state.query = event.target.value;
      state.page = 1;
      render();
    });
    document.getElementById("catalog-order").addEventListener("change", function (event) {
      state.order = event.target.value;
      state.page = 1;
      render();
    });
    document.getElementById("catalog-prev").addEventListener("click", function () {
      state.page -= 1;
      render();
    });
    document.getElementById("catalog-next").addEventListener("click", function () {
      state.page += 1;
      render();
    });
    // lang.js swaps the hidden labels and then the page language; render again in the new language.
    new MutationObserver(render).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });

    fetch("data/sources.json")
      .then(function (response) {
        if (!response.ok) throw new Error("catalog " + response.status);
        return response.json();
      })
      .then(function (data) {
        catalog = data;
        root.querySelector(".catalog__browser").hidden = false;
        root.querySelector(".catalog__fallback").hidden = true;
        select(state.section);
      })
      .catch(function () {
        // The fallback link to AGENCIES.md stays visible.
      });
  });
})();
