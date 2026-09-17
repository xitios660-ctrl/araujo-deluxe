"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { explicitGenericCategory } = require("./category-reset");

test("generic category switches are detected", () => {
  assert.equal(explicitGenericCategory("quero fazer unha"), "unhas");
  assert.equal(explicitGenericCategory("quero cílios"), "cilios");
  assert.equal(explicitGenericCategory("sobrancelha"), "sobrancelhas");
});

test("specific services do not trigger a category reset", () => {
  assert.equal(explicitGenericCategory("quero fibra de vidro"), null);
  assert.equal(explicitGenericCategory("volume brasileiro"), null);
  assert.equal(explicitGenericCategory("banho em gel"), null);
});

test("negated category messages do not reset the flow", () => {
  assert.equal(explicitGenericCategory("não quero unha"), null);
  assert.equal(explicitGenericCategory("sem cílios"), null);
});
