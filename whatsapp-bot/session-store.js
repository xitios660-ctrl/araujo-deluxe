const crypto = require("node:crypto");

function codec(secret) {
  const key = crypto.createHash("sha256").update("whatsapp-session-v1:" + secret).digest();
  return {
    encrypt(text) {
      const iv = crypto.randomBytes(12);
      const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
      const body = Buffer.concat([cipher.update(text, "utf8"), cipher.final()]);
      return Buffer.concat([iv, cipher.getAuthTag(), body]).toString("base64");
    },
    decrypt(value) {
      const bytes = Buffer.from(value, "base64");
      if (bytes.length < 28) throw new Error("Invalid encrypted session");
      const decipher = crypto.createDecipheriv("aes-256-gcm", key, bytes.subarray(0, 12));
      decipher.setAuthTag(bytes.subarray(12, 28));
      return Buffer.concat([decipher.update(bytes.subarray(28)), decipher.final()]).toString("utf8");
    },
  };
}

async function usePersistentAuth({ baileys, request, secret, seed }) {
  const crypt = codec(secret);
  const { BufferJSON, initAuthCreds, proto } = baileys;
  const loaded = await request("GET");
  const cache = new Map();
  for (const entry of loaded.entries || []) {
    cache.set(entry.key, JSON.parse(crypt.decrypt(entry.value), BufferJSON.reviver));
  }
  if (!cache.size && seed) {
    for (const [key, value] of Object.entries(seed)) cache.set(key, value);
  }
  if (!cache.has("creds")) cache.set("creds", initAuthCreds());
  const creds = cache.get("creds");
  let tail = Promise.resolve();
  let failed = false;
  function persist(changes) {
    const entries = Object.entries(changes).map(([key, value]) => ({
      key, value: value == null ? null : crypt.encrypt(JSON.stringify(value, BufferJSON.replacer)),
    }));
    const job = tail.then(async () => {
      if (failed) throw new Error("Session persistence paused after storage failure");
      await request("POST", { entries });
    });
    tail = job.catch(() => { failed = true; });
    return job;
  }
  // Persist initial credentials/migration before opening a WhatsApp connection.
  if (!(loaded.entries || []).length) await persist(Object.fromEntries(cache));
  return {
    state: {
      creds,
      keys: {
        async get(type, ids) {
          const result = {};
          for (const id of ids) {
            let value = cache.get(type + "-" + id);
            if (type === "app-state-sync-key" && value) value = proto.Message.AppStateSyncKeyData.fromObject(value);
            result[id] = value;
          }
          return result;
        },
        async set(data) {
          const changes = {};
          for (const [type, keys] of Object.entries(data)) for (const [id, value] of Object.entries(keys)) {
            const key = type + "-" + id;
            changes[key] = value;
          }
          await persist(changes);
          for (const [key, value] of Object.entries(changes)) {
            if (value == null) cache.delete(key); else cache.set(key, value);
          }
        },
      },
    },
    saveCreds: () => persist({ creds }),
    flush: () => tail,
  };
}
module.exports = { codec, usePersistentAuth };
