const test = require("node:test");
const assert = require("node:assert/strict");
const { lookup, derive, shares, format } = require("../js/stats.js");

const stats = {
  documents: 10,
  issuers: { sfs: 2, municipality: 3 },
  text: { web: 6, pdf: 3, ocr: 1, none: 0 },
  layers: {
    sfs: { documents: 7, types: { act: { documents: 4, words: 1000 }, ordinance: { documents: 3, words: 500 } } },
    municipality: { documents: 3, types: { municipal_regulation: { documents: 3, words: 250 } } },
  },
};

test("lookup follows a dotted path and tolerates gaps", () => {
  assert.equal(lookup(stats, "layers.sfs.types.act.documents"), 4);
  assert.equal(lookup(stats, "layers.eu.documents"), undefined);
});

test("derive adds the publisher, word and PDF totals", () => {
  const derived = derive(stats);
  assert.equal(derived.issuers, 5);
  assert.equal(derived.words, 1750);
  assert.equal(derived.from_pdf, 4);
  assert.equal(derived.documents, 10);
});

test("shares are percentages of all texts", () => {
  assert.deepEqual(shares(stats.text), { web: 60, pdf: 30, ocr: 10, none: 0 });
});

test("numbers follow the page language", () => {
  assert.equal(format(54786, null, "en"), "54,786");
  assert.equal(format(54786, null, "sv").replace(/\s/g, " "), "54 786");
  assert.equal(format(0.9554, "percent", "en"), "96%");
  assert.equal(format(119115458, "millions", "en"), "119");
  assert.match(format("2026-10-31T23:41:28Z", "date", "sv"), /^31 oktober 2026$/);
});
