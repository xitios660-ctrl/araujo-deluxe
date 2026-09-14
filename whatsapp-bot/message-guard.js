const { createHash } = require("node:crypto");
class MessageGuard {
  constructor({ gapMs = 3000, now = Date.now } = {}) {
    Object.assign(this, { gapMs, now, pending: 0, last: 0, tail: Promise.resolve(), seen: new Map(), sent: new Map(), counts: new Map(), global: [], blocked: new Set(), failures: 0, pausedUntil: 0 });
  }
  accept(jid, id) {
    if (!id) return false;
    for (const [key, time] of this.seen) if (this.now() - time >= 3600000) this.seen.delete(key);
    const key = jid + ":" + id;
    if (this.seen.has(key) || this.seen.size >= 10000) return false;
    this.seen.set(key, this.now()); return true;
  }
  send(contact, payload, deliver) {
    if (this.pending >= 5) return Promise.reject(new Error("Fila cheia"));
    this.pending++;
    const job = this.tail.then(async () => {
      const delay = this.last ? Math.max(0, this.gapMs - (this.now() - this.last)) : 0;
      if (delay) await new Promise(r => setTimeout(r, delay));
      const now = this.now();
      if (this.blocked.has(contact)) throw new Error("Contato pediu para parar");
      if (now < this.pausedUntil) throw new Error("Envios pausados");
      this.global = this.global.filter(t => now - t < 60000);
      for (const [key, times] of this.counts) {
        const recent = times.filter(t => now - t < 60000);
        if (recent.length) this.counts.set(key, recent); else this.counts.delete(key);
      }
      for (const [key, time] of this.sent) if (now - time >= 60000) this.sent.delete(key);
      const times = this.counts.get(contact) || [];
      if (this.global.length >= 15 || times.length >= 6) throw new Error("Limite de mensagens atingido");
      const hash = createHash("sha256").update(contact).update(JSON.stringify(payload)).digest("hex");
      if (this.sent.has(hash)) return { skipped: true };
      this.sent.set(hash, now); this.last = now;
      this.global.push(now); this.counts.set(contact, [...times, now]);
      try { const result = await deliver(); this.failures = 0; return result; }
      catch (e) { if (++this.failures >= 3) this.pausedUntil = now + 300000; throw e; }
    });
    this.tail = job.catch(() => {});
    return job.finally(() => { this.pending--; });
  }
}
module.exports = { MessageGuard };
