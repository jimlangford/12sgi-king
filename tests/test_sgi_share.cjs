"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const share = require("../assets/sgi-share.js");

test("accepts only explicit HTTPS public hosts", () => {
  assert.equal(share.safePublicUrl("https://12sgi.com/agenda_explainer.html#item"), "https://12sgi.com/agenda_explainer.html");
  assert.equal(share.safePublicUrl("https://elementlotus.com/education"), "https://elementlotus.com/education");
  for (const url of [
    "http://12sgi.com/a", "https://king.tail760750.ts.net/status/explainers.html",
    "https://12sgi.com.evil.test/a", "https://user:pass@12sgi.com/a",
    "https://12sgi.com:8443/a", "javascript:alert(1)", "/relative", ""
  ]) assert.equal(share.safePublicUrl(url), null, url);
});

test("creates manual links, never automatic publication actions", () => {
  const list = share.shareTargets("https://12sgi.com/agenda_explainer.html", "Agenda and housing", "Official records");
  assert.equal(list.length, 7);
  assert.ok(list.every(t => t.href.startsWith("https://") || t.href.startsWith("mailto:")));
  assert.ok(list.find(t => t.id === "x").href.includes("Agenda%20and%20housing"));
  assert.ok(list.find(t => t.id === "telegram").href.includes(encodeURIComponent("https://12sgi.com/agenda_explainer.html")));
  assert.deepEqual(share.shareTargets("http://localhost:8000/private", "Private"), []);
});
