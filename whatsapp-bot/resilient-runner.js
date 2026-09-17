"use strict";

const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");

function replaceOnce(source, before, after, label) {
  const first = source.indexOf(before);
  if (first < 0) throw new Error(`Patch do WhatsApp não encontrou: ${label}`);
  if (source.indexOf(before, first + before.length) >= 0) {
    throw new Error(`Patch do WhatsApp encontrou mais de uma ocorrência: ${label}`);
  }
  return source.slice(0, first) + after + source.slice(first + before.length);
}

function patchSource(input) {
  let source = input;

  source = replaceOnce(
    source,
    'const { ContactQueue } = require("./contact-queue");',
    'const { ContactQueue } = require("./contact-queue");\nconst { createRecoveryStore } = require("./recovery-store");',
    "import recovery-store",
  );

  source = replaceOnce(
    source,
    'let halted = null, lastLeaseSuccess = 0, leaseRenewing = null;',
    'let halted = null, lastLeaseSuccess = 0, leaseRenewing = null;\nlet recovery = null, recoveryDrain = null;',
    "recovery state",
  );

  source = replaceOnce(
    source,
    '    auth = await usePersistentAuth({ baileys, request: storageRequest, secret });\n    if (closing) return;',
    '    auth = await usePersistentAuth({ baileys, request: storageRequest, secret });\n    try { recovery = await createRecoveryStore({ request: storageRequest, secret }); }\n    catch (e) { recovery = null; console.warn("Memória de recuperação indisponível:", e.message); }\n    if (closing) return;',
    "initialize recovery",
  );

  source = replaceOnce(
    source,
    '      markOnlineOnConnect: false,',
    '      markOnlineOnConnect: true,',
    "online presence",
  );

  source = replaceOnce(
    source,
    '        halted = null;\n        console.log("WhatsApp conectado; sessão persistente ativa.");',
    '        halted = null;\n        current.sendPresenceUpdate("available").catch(() => {});\n        recovery?.recordReconnect().catch(e => console.warn("Falha ao registrar reconexão:", e.message));\n        drainRecoveryReplies(current).catch(e => console.warn("Falha ao recuperar respostas pendentes:", e.message));\n        console.log("WhatsApp conectado; sessão persistente ativa.");',
    "connection open recovery",
  );

  source = replaceOnce(
    source,
    '        console.warn("Conexão do WhatsApp fechada; código:", code ?? "desconhecido");\n        disconnectTransport(); starting = false;',
    '        console.warn("Conexão do WhatsApp fechada; código:", code ?? "desconhecido");\n        recovery?.recordDisconnect().catch(e => console.warn("Falha ao registrar desconexão:", e.message));\n        disconnectTransport(); starting = false;',
    "connection close recovery",
  );

  const safeSendBlock = `function safeSend(phone, jid, payload, dedupeKey = null) {
  return guard.send(phone, payload, () => {
    if (!connected || !sock || !hasLease || halted) throw new Error("WhatsApp indisponível");
    return sock.sendMessage(jid, payload);
  }, { dedupeKey });
}`;

  const safeSendWithRecovery = `${safeSendBlock}

function recoveryText(data, reply) {
  if (process.env.WHATSAPP_INTERACTIVE_LISTS !== "1" && data?.ui) return uiTextFallback(data.ui, reply);
  return String(reply || "");
}

async function drainRecoveryReplies(current) {
  if (!recovery || recoveryDrain || !connected || current !== sock || closing) return recoveryDrain;
  recoveryDrain = (async () => {
    for (const item of recovery.pendingReplies()) {
      if (!connected || current !== sock || closing) break;
      if (Date.now() - Number(item.created_at || 0) > 24 * 60 * 60 * 1000) {
        console.warn("Resposta pendente antiga descartada da fila de recuperação:", item.id);
        await recovery.markDelivered(item.id).catch(() => {});
        continue;
      }
      await recovery.noteAttempt(item.id).catch(() => {});
      const showPresence = !guard.blocked.has(item.phone);
      if (showPresence) await current.sendPresenceUpdate("composing", item.jid).catch(() => {});
      try {
        await safeSend(item.phone, item.jid, { text: item.text }, "recovery:" + item.id);
        await apiRequest("/whatsapp/memory/outgoing", "POST", { phone: item.phone, text: item.text }).catch(() => {});
        await recovery.markDelivered(item.id);
        console.log("Resposta recuperada após reconexão:", item.id);
      } catch (e) {
        console.warn("Resposta continua pendente após reconexão:", e.message);
        break;
      } finally {
        if (showPresence && current === sock) await current.sendPresenceUpdate("paused", item.jid).catch(() => {});
      }
    }
  })().finally(() => { recoveryDrain = null; });
  return recoveryDrain;
}`;

  source = replaceOnce(source, safeSendBlock, safeSendWithRecovery, "durable recovery helpers");

  source = replaceOnce(
    source,
    '  if (!guard.accept(jid, msg.key.id)) return;\n  const alt = msg.key.remoteJidAlt || msg.key.senderPn || msg.key.participantAlt || "";',
    '  const recoveryId = `${jid}:${msg.key.id || "unknown"}`;\n  if (recovery?.hasSeen(recoveryId)) return;\n  if (!guard.accept(jid, msg.key.id)) return;\n  const alt = msg.key.remoteJidAlt || msg.key.senderPn || msg.key.participantAlt || "";',
    "persistent incoming dedupe",
  );

  source = replaceOnce(
    source,
    '  const current = sock;\n  if (!current || !connected) return;\n  // Presence reflects actual processing; no fake human identity or artificial typing delay.\n  const showTyping = !guard.blocked.has(phone);',
    '  const current = sock;\n  if (!current) return;\n  // Presence reflects real processing only. No artificial delay is used.\n  const showTyping = connected && !guard.blocked.has(phone);',
    "process during reconnect",
  );

  source = replaceOnce(
    source,
    '      await sendBotReply(phone, jid, data, reply, msg.key.id);\n      await apiRequest("/whatsapp/memory/outgoing", "POST", { phone, text: reply }).catch(() => {});',
    '      const persistedReply = recoveryText(data, reply);\n      await recovery?.queueReply({ id: recoveryId, phone, jid, text: persistedReply }).catch(e => console.warn("Falha ao guardar resposta pendente:", e.message));\n      if (!connected || current !== sock) {\n        console.log("Mensagem processada durante reconexão; resposta guardada para envio:", recoveryId);\n        return;\n      }\n      await sendBotReply(phone, jid, data, reply, msg.key.id);\n      await apiRequest("/whatsapp/memory/outgoing", "POST", { phone, text: persistedReply }).catch(() => {});\n      await recovery?.markDelivered(recoveryId).catch(e => console.warn("Falha ao confirmar entrega na memória:", e.message));',
    "queue reply before send",
  );

  source = replaceOnce(
    source,
    '      introduced.add(phone);\n    }\n  } catch (e) {',
    '      introduced.add(phone);\n    } else {\n      await recovery?.markHandled(recoveryId).catch(() => {});\n    }\n  } catch (e) {',
    "mark no-reply handled",
  );

  source = replaceOnce(
    source,
    '    const fallback = "Tive um probleminha para processar sua mensagem agora 😅 Pode me mandar de novo em alguns segundos?";\n    await safeSend(phone, jid, { text: fallback }, (msg.key.id || crypto.randomUUID()) + ":error").catch(sendError => {\n      console.error("Falha também ao enviar resposta de contingência:", sendError.message);\n    });',
    '    const fallback = "Tive um probleminha para processar sua mensagem agora 😅 Pode me mandar de novo em alguns segundos?";\n    await recovery?.queueReply({ id: recoveryId, phone, jid, text: fallback }).catch(() => {});\n    if (connected && current === sock) {\n      await safeSend(phone, jid, { text: fallback }, (msg.key.id || crypto.randomUUID()) + ":error").then(async () => {\n        await apiRequest("/whatsapp/memory/outgoing", "POST", { phone, text: fallback }).catch(() => {});\n        await recovery?.markDelivered(recoveryId).catch(() => {});\n      }).catch(sendError => {\n        console.error("Falha também ao enviar resposta de contingência; ficou na fila de recuperação:", sendError.message);\n      });\n    }',
    "persist fallback",
  );

  source = replaceOnce(
    source,
    '  protections: {\n    enabled: true,',
    '  recovery: recovery?.status() || { pending_replies: 0, remembered_message_ids: 0 },\n  presence: connected ? "available" : "offline",\n  protections: {\n    enabled: true,',
    "status recovery metrics",
  );

  return source;
}

function run() {
  const filename = path.join(__dirname, "index.js");
  const source = patchSource(fs.readFileSync(filename, "utf8"));
  const target = new Module(filename, module.parent);
  target.filename = filename;
  target.paths = Module._nodeModulePaths(__dirname);
  target._compile(source, filename);
}

if (require.main === module) run();

module.exports = { patchSource, run };
