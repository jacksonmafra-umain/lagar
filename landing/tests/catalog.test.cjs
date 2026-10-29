const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const { filterRows, sortRows, paginate, PAGE_SIZE } = require("../js/catalog.js");

const STATUSES = ["collected", "partial", "no_adapter"];
const ROWS = [
  { name: "Örebro", code: "1880", county: "Örebro län", status: "no_adapter", documents: 0 },
  { name: "Ale", code: "1440", county: "Västra Götalands län", status: "no_adapter", documents: 0 },
  { name: "Stockholm", code: "0180", county: "Stockholms län", status: "partial", documents: 5 },
  { name: "Göteborg", code: "1480", county: "Västra Götalands län", status: "partial", documents: 7 },
];

test("filter matches every word, ignoring case and diacritics", () => {
  assert.deepStrictEqual(filterRows(ROWS, "vastra GOT").map((r) => r.name), ["Ale", "Göteborg"]);
  assert.deepStrictEqual(filterRows(ROWS, "0180").map((r) => r.name), ["Stockholm"]);
  assert.strictEqual(filterRows(ROWS, "  ").length, ROWS.length);
});

test("name order is Swedish: Ö after the other letters", () => {
  assert.deepStrictEqual(sortRows(ROWS, "name", STATUSES).map((r) => r.name), ["Ale", "Göteborg", "Stockholm", "Örebro"]);
});

test("status and document orders", () => {
  assert.deepStrictEqual(sortRows(ROWS, "status", STATUSES).map((r) => r.name), ["Göteborg", "Stockholm", "Ale", "Örebro"]);
  assert.deepStrictEqual(sortRows(ROWS, "documents", STATUSES).map((r) => r.name), ["Göteborg", "Stockholm", "Ale", "Örebro"]);
});

test("pages are clamped", () => {
  const rows = Array.from({ length: 45 }, (_, i) => ({ name: String(i) }));
  assert.deepStrictEqual([paginate(rows, 1, 20).pages, paginate(rows, 3, 20).rows.length], [3, 5]);
  assert.strictEqual(paginate(rows, 9, 20).page, 3);
  assert.strictEqual(paginate([], 1, 20).pages, 1);
  assert.strictEqual(PAGE_SIZE, 20);
});

test("the committed catalog has every section the page has a tab for", () => {
  const root = path.join(__dirname, "..");
  const catalog = JSON.parse(fs.readFileSync(path.join(root, "data", "sources.json"), "utf8"));
  const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
  const tabs = [...html.matchAll(/role="tab"[^>]*data-section="([a-z]+)"/g)].map((m) => m[1]);
  assert.deepStrictEqual(tabs.sort(), Object.keys(catalog.sections).sort());
  for (const status of catalog.statuses) {
    assert.ok(html.includes(`data-i18n="catalog.status.${status}"`), status);
  }
  for (const rows of Object.values(catalog.sections)) {
    for (const row of rows) {
      if (row.url) assert.match(row.url, /^https?:\/\//, row.name);
      assert.ok(catalog.statuses.includes(row.status), row.name);
    }
  }
});
