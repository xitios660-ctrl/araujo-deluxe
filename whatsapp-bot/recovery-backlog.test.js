const test = require("node:test");
const assert = require("node:assert/strict");
const { createRecoveryStore } = require("./recovery-store");

function fakeStorage() {
  const database = new Map();
  const request = async (method, body) => {
    if (method === "GET") return { entries: [...database].map(([key, value]) => ({ key, value })) };
    if (method === "POST") {
      for (const entry of body.entries || []) database.set(entry.key, entry.value);
      return { ok: true };
    }
    throw new Error("unsupported method");
  };
  return { request };
}

test("keeps more than 200 pending replies while WhatsApp is offline", async () => {
  const storage = fakeStorage();
  const recovery = await createRecoveryStore({ request: storage.request, secret: "test-secret" });
  for (let i = 0; i < 250; i += 1) {
    await recovery.queueReply({
      id: `jid:msg-${i}`,
      phone: "5511999999999",
      jid: "5511999999999@s.whatsapp.net",
      text: `resposta ${i}`,
    });
  }
  assert.equal(recovery.pendingReplies().length, 250);
  assert.equal(recovery.pendingReplies()[0].id, "jid:msg-0");
  assert.equal(recovery.pendingReplies()[249].id, "jid:msg-249");
});
