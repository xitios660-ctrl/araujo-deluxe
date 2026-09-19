const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { patchSource } = require("./resilient-runner");

test("recovery persists menu choices as text even when interactive lists are enabled", () => {
  const source = fs.readFileSync(path.join(__dirname, "index.js"), "utf8");
  const patched = patchSource(source);

  assert.match(patched, /function recoveryText\(data, reply\)/);
  assert.match(patched, /if \(data\?\.ui\) return uiTextFallback\(data\.ui, reply\);/);
  assert.doesNotMatch(patched, /WHATSAPP_INTERACTIVE_LISTS !== "1" && data\?\.ui/);
  assert.match(patched, /await recovery\?\.queueReply\(\{ id: recoveryId, phone, jid, text: persistedReply \}\)/);
});
