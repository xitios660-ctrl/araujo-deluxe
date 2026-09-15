class ContactQueue {
  constructor({ warnAt = 50, onWarn = null } = {}) {
    this.warnAt = warnAt;
    this.onWarn = onWarn;
    this.tails = new Map();
    this.pending = 0;
  }

  enqueue(key, task) {
    const queueKey = String(key || "unknown");
    this.pending++;
    if (this.pending === this.warnAt && this.onWarn) this.onWarn(this.pending);

    const previous = this.tails.get(queueKey) || Promise.resolve();
    const job = previous.catch(() => {}).then(task);
    const tail = job.catch(() => {});
    this.tails.set(queueKey, tail);

    return job.finally(() => {
      this.pending--;
      if (this.tails.get(queueKey) === tail) this.tails.delete(queueKey);
    });
  }

  size() {
    return this.tails.size;
  }
}

module.exports = { ContactQueue };
