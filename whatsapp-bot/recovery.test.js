const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { createRecoveryStore } = require("./recovery-store");
const { patchSource } = require("./resilient-runner");

function fakeStorage() {
  const database = new Map();
  const request = async (method, body) => {
    if (method === "GET") {
      return { entries: [...database].map(([key, value]) => ({ key, value })) };
    }
    if (method === "POST") {
      for (const entry of body.entries || []) {
        if (entry.value == null) database.delete(entry.key);
        else database.set(entry.key, entry.value);
      }
      return { ok: true };
    }
    throw new Error("unsupported method");
  };
  return { database, request };
}

test("recovery memory survives process restart and keeps pending reply", async () => {
  const storage = fakeStorage();
  let now = 1_700_000_000_000;
  const first = await createRecoveryStore({ request: storage.request, secret: "test-secret", now: () => now });

  await first.queueReply({
    id: "jid:msg-1",
    phone: "5511999999999",
    jid: "5511999999999@s.whatsapp.net",
    text: "Seu horário ficou reservado.",
  });
  await first.recordDisconnect();
  await first.flush();

  now += 5_000;
  const restarted = await createRecoveryStore({ request: storage.request, secret: "test-secret", now: () => now });
  assert.equal(restarted.hasSeen("jid:msg-1"), true);
  assert.equal(restarted.pendingReplies().length, 1);
  assert.equal(restarted.pendingReplies()[0].text, "Seu horário ficou reservado.");
  assert.ok(restarted.status().last_disconnect_at);

  await restarted.recordReconnect();
  await restarted.markDelivered("jid:msg-1");

  const third = await createRecoveryStore({ request: storage.request, secret: "test-secret", now: () => now });
  assert.equal(third.pendingReplies().length, 0);
  assert.equal(third.hasSeen("jid:msg-1"), true);
  assert.ok(third.status().last_reconnect_at);
});

test("same incoming message id cannot create a second pending reply", async () => {
  const storage = fakeStorage();
  const recovery = await createRecoveryStore({ request: storage.request, secret: "test-secret" });
  const payload = {
    id: "jid:duplicate",
    phone: "5511888888888",
    jid: "5511888888888@s.whatsapp.net",
    text: "primeira resposta",
  };
  await recovery.queueReply(payload);
  await recovery.queueReply({ ...payload, text: "resposta atualizada" });
  assert.equal(recovery.pendingReplies().length, 1);
  assert.equal(recovery.pendingReplies()[0].text, "resposta atualizada");
  assert.equal(recovery.hasSeen(payload.id), true);
});

test("runtime patch enables real presence and durable reconnect recovery", () => {
  const indexPath = path.join(__dirname, "index.js");
  const patched = patchSource(fs.readFileSync(indexPath, "utf8"));
  assert.match(patched, /markOnlineOnConnect: true/);
  assert.match(patched, /syncFullHistory: true/);
  assert.ok(patched.includes('["notify", "append"].includes(type)'));
  assert.match(patched, /sendPresenceUpdate\("available"\)/);
  assert.match(patched, /createRecoveryStore/);
  assert.match(patched, /queueReply\(\{ id: recoveryId/);
  assert.match(patched, /drainRecoveryReplies/);
  assert.match(patched, /presence: connected \? "available" : "offline"/);
  assert.doesNotMatch(patched, /if \(!current \|\| !connected\) return;/);
});
