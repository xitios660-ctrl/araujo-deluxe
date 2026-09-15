const test = require("node:test");
const assert = require("node:assert/strict");
const { codec, usePersistentAuth } = require("./session-store");
const { MessageGuard } = require("./message-guard");
test("credentials and binary keys survive restart", async () => {
  const baileys = await import("baileys");
  const database = new Map();
  const request = async (method, body) => {
    if (method === "GET") return { entries: [...database].map(([key, value]) => ({key, value})) };
    for (const entry of body.entries) {
      if (entry.value === null) database.delete(entry.key); else database.set(entry.key, entry.value);
    }
    return { ok: true };
  };
  const first = await usePersistentAuth({ baileys, request, secret: "test-only" });
  first.state.creds.me = { id: "test@s.whatsapp.net" };
  await first.saveCreds();
  await first.state.keys.set({ session: { alpha: Buffer.from([1,2,3]), obsolete: Buffer.from([4]) } });
  await first.state.keys.set({ session: { obsolete: null } });
  const restarted = await usePersistentAuth({ baileys, request, secret: "test-only" });
  assert.equal(restarted.state.creds.me.id, "test@s.whatsapp.net");
  const keys = await restarted.state.keys.get("session", ["alpha", "obsolete"]);
  assert.deepEqual(Buffer.from(keys.alpha), Buffer.from([1,2,3]));
  assert.equal(keys.obsolete, undefined);
  assert.equal([...database.values()].some(v => v.includes("test@s.whatsapp.net")), false);
});
test("encryption rejects wrong key and tampering", () => {
  const a = codec("a"), b = codec("b");
  const value = a.encrypt("private");
  assert.throws(() => b.decrypt(value));
  const changed = Buffer.from(value, "base64"); changed[changed.length-1] ^= 1;
  assert.throws(() => a.decrypt(changed.toString("base64")));
});
test("storage error never silently creates a replacement session", async () => {
  await assert.rejects(usePersistentAuth({
    baileys: await import("baileys"), secret: "test",
    request: async () => { throw new Error("database unavailable"); },
  }), /database unavailable/);
});
test("replays are suppressed by message id while distinct messages may receive the same reply", async () => {
  const g = new MessageGuard({ gapMs: 0 });
  assert.equal(g.accept("a", "1"), true);
  assert.equal(g.accept("a", "1"), false);
  let count = 0;
  await g.send("a", "same", async () => count++, { dedupeKey: "incoming-1" });
  await g.send("a", "same", async () => count++, { dedupeKey: "incoming-1" });
  await g.send("a", "same", async () => count++, { dedupeKey: "incoming-2" });
  assert.equal(count, 2);
});
test("failed delivery can be retried with the same dedupe key", async () => {
  const g = new MessageGuard({ gapMs: 0 });
  let attempts = 0;
  await assert.rejects(g.send("a", "reply", async () => { attempts++; throw new Error("network"); }, { dedupeKey: "incoming-3" }));
  await g.send("a", "reply", async () => { attempts++; }, { dedupeKey: "incoming-3" });
  assert.equal(attempts, 2);
});
test("transient storage failure does not poison later credential saves", async () => {
  const baileys = await import("baileys");
  const database = new Map();
  let failNext = false;
  const request = async (method, body) => {
    if (method === "GET") return { entries: [...database].map(([key, value]) => ({ key, value })) };
    if (failNext) { failNext = false; throw new Error("temporary database error"); }
    for (const entry of body.entries) {
      if (entry.value === null) database.delete(entry.key); else database.set(entry.key, entry.value);
    }
    return { ok: true };
  };
  const auth = await usePersistentAuth({ baileys, request, secret: "test-recovery" });
  failNext = true;
  await assert.rejects(auth.saveCreds(), /temporary database error/);
  await auth.saveCreds();
  assert.equal(database.has("creds"), true);
});
test("contact and global limits are enforced", async () => {
  const g = new MessageGuard({ gapMs: 0 });
  for (let i=0; i<6; i++) await g.send("a", i, async () => {});
  await assert.rejects(g.send("a", 7, async () => {}), /Limite/);
  for (let i=0; i<9; i++) await g.send("b"+i, i, async () => {});
  await assert.rejects(g.send("c", 1, async () => {}), /Limite/);
});
test("user-initiated replies bypass outbound rate caps but still dedupe", async () => {
  const g = new MessageGuard({ gapMs: 0 });
  for (let i = 0; i < 6; i++) await g.send("a", i, async () => {});
  let delivered = 0;
  await g.send("a", "reply", async () => { delivered++; }, { dedupeKey: "incoming-7" });
  await g.send("a", "reply", async () => { delivered++; }, { dedupeKey: "incoming-7" });
  assert.equal(delivered, 1);
  await assert.rejects(g.send("a", "system", async () => {}), /Limite/);
});

test("opt-out and circuit breaker prevent delivery", async () => {
  const g = new MessageGuard({ gapMs: 0 });
  const pending = g.send("a", "one", async () => assert.fail());
  g.blocked.add("a");
  await assert.rejects(pending, /parar/);
  for (let i=0; i<3; i++) await assert.rejects(g.send("b", i, async () => { throw Error("network"); }));
  await assert.rejects(g.send("c", "next", async () => assert.fail()), /pausados/);
});

const { ContactQueue } = require("./contact-queue");

test("incoming messages stay ordered per contact", async () => {
  const queue = new ContactQueue();
  const events = [];
  const first = queue.enqueue("a", async () => {
    events.push("a1-start");
    await new Promise(resolve => setTimeout(resolve, 20));
    events.push("a1-end");
  });
  const second = queue.enqueue("a", async () => {
    events.push("a2");
  });
  await Promise.all([first, second]);
  assert.deepEqual(events, ["a1-start", "a1-end", "a2"]);
  assert.equal(queue.pending, 0);
  assert.equal(queue.size(), 0);
});

test("different contacts can be processed concurrently", async () => {
  const queue = new ContactQueue();
  let release;
  const blocker = new Promise(resolve => { release = resolve; });
  let bStarted = false;

  const a = queue.enqueue("a", async () => {
    await blocker;
  });
  const b = queue.enqueue("b", async () => {
    bStarted = true;
  });

  await new Promise(resolve => setTimeout(resolve, 5));
  assert.equal(bStarted, true);
  release();
  await Promise.all([a, b]);
});

test("one contact failure does not poison later messages", async () => {
  const queue = new ContactQueue();
  await assert.rejects(queue.enqueue("a", async () => {
    throw new Error("boom");
  }));
  let ran = false;
  await queue.enqueue("a", async () => {
    ran = true;
  });
  assert.equal(ran, true);
});
