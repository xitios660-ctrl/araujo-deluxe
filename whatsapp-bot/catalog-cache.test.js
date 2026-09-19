const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

test("AI catalog cache expires so admin price/service changes propagate", () => {
  const source = fs.readFileSync(path.join(__dirname, "ai-hook.js"), "utf8");
  assert.match(source, /CATALOG_CACHE_TTL_MS\s*=\s*60\s*\*\s*1000/);
  assert.match(source, /now\s*-\s*catalogCachedAt\s*<\s*CATALOG_CACHE_TTL_MS/);
  assert.match(source, /catalogCachedAt\s*=\s*now/);
  assert.match(source, /return catalogCache \|\| \[\]/);
});
