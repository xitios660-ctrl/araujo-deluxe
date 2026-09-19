const test = require("node:test");
const assert = require("node:assert/strict");
const { MessageGuard } = require("./message-guard");

test("dedupe cache saturation evicts oldest id instead of dropping new messages", () => {
  let now = 1_000;
  const guard = new MessageGuard({ gapMs: 0, now: () => now, maxSeen: 3 });

  assert.equal(guard.accept("customer", "m1"), true);
  now++;
  assert.equal(guard.accept("customer", "m2"), true);
  now++;
  assert.equal(guard.accept("customer", "m3"), true);
  assert.equal(guard.seen.size, 3);

  now++;
  assert.equal(guard.accept("customer", "m4"), true);
  assert.equal(guard.seen.size, 3);
  assert.equal(guard.seen.has("customer:m1"), false);
  assert.equal(guard.seen.has("customer:m4"), true);

  // A still-cached replay remains blocked.
  assert.equal(guard.accept("customer", "m4"), false);
});
