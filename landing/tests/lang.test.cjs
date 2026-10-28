// Run with: node --test landing/tests/lang.test.cjs
const assert = require("node:assert/strict");
const test = require("node:test");
const { resolveLanguage } = require("../js/lang.js");

test("English browser gives English", () => {
  assert.equal(resolveLanguage(null, null, "en-GB"), "en");
});

test("Swedish browser gives Swedish", () => {
  assert.equal(resolveLanguage(null, null, "sv-SE"), "sv");
});

test("unsupported browser languages give Swedish", () => {
  assert.equal(resolveLanguage(null, null, "de-DE"), "sv");
  assert.equal(resolveLanguage(null, null, "pt-BR"), "sv");
  assert.equal(resolveLanguage(null, null, ""), "sv");
});

test("stored choice wins over the browser", () => {
  assert.equal(resolveLanguage("sv", null, "en-US"), "sv");
});

test("query wins over the stored choice", () => {
  assert.equal(resolveLanguage("sv", "en", "sv-SE"), "en");
});

test("unknown query and stored values fall through", () => {
  assert.equal(resolveLanguage("xx", "fr", "en-US"), "en");
});
