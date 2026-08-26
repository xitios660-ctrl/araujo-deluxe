import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Link, useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  MapPin,
  Package,
  Search,
  Send,
  Truck,
  Wallet,
  Wind,
} from "lucide-react";
import { brand, formatBRL } from "../mock";
import { orderWhatsAppUrl } from "../lib/whatsapp";

const API = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/+$/, "");

const STATUS_FLOW = [
  { id: "aguardando_pagamento", label: "Aguardando pagamento", desc: "Finalize o pagamento pelo WhatsApp para liberar o envio.", icon: Wallet },
  { id: "pago", label: "Pagamento confirmado", desc: "Recebemos seu pagamento. Preparando a missão.", icon: CheckCircle2 },
  { id: "em_preparacao", label: "Em preparação", desc: "Sua linha está sendo embalada com todo cuidado.", icon: Package },
  { id: "enviado", label: "Enviado", desc: "A caminho do seu endereço. Segure o carretel.", icon: Truck },
  { id: "entregue", label: "Entregue", desc: "Chegou! Agora é dominar o céu.", icon: Wind },
];

const normalize = (v) => {
  const s = v.toUpperCase().replace(/\s/g, "");
  if (!s) return "";
  return s.startsWith("DDC-") ? s : s.startsWith("DDC") ? `DDC-${s.slice(3)}` : `DDC-${s}`;
};

export default function TrackOrder() {
  const { orderNumber } = useParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState(orderNumber || "");
  const [loading, setLoading] = useState(false);
  const [order, setOrder] = useState(null);
  const [error, setError] = useState("");

  const search = useCallback(
    async (num) => {
      const code = normalize(num);
      if (code.length < 5) {
        setError("Digite o número do pedido (ex: DDC-A1B2C3).");
        return;
      }
      setLoading(true);
      setError("");
      setOrder(null);
      try {
        const r = await axios.get(`${API}/api/orders/${code}`);
        setOrder(r.data);
        navigate(`/rastreio/${code}`, { replace: true });
      } catch (e) {
        setError("Pedido não encontrado. Confira o número e tente de novo.");
      } finally {
        setLoading(false);
      }
    },
    [navigate]
  );

  useEffect(() => {
    if (orderNumber) search(orderNumber);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentIdx = order
    ? Math.max(0, STATUS_FLOW.findIndex((s) => s.id === order.status))
    : 0;

  return (
    <div className="relative min-h-screen" data-testid="track-order-page">
      <div className="film-grain" />
      <div className="cinema-bg pointer-events-none fixed inset-0 opacity-60" />

      <header className="relative z-10 border-b border-violet-500/20 bg-black/60 backdrop-blur-xl">
        <div className="mx-auto flex max-w-3xl items-center gap-4 px-4 py-4">
          <Link
            to="/"
            data-testid="tracking-back-link"
            className="flex items-center gap-2 rounded-full px-3 py-2 text-sm text-white/70 transition-colors hover:bg-white/5 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" /> Loja
          </Link>
          <div className="mx-auto text-center">
            <p className="text-[10px] font-semibold uppercase tracking-[0.4em] text-amber-300">
              {brand.name} — Siga sua linha
            </p>
            <h1 className="font-display text-2xl tracking-wide text-white sm:text-3xl">
              RASTREIO
            </h1>
          </div>
          <span className="w-[72px]" />
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-3xl px-4 py-10">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="glass rounded-3xl p-6 sm:p-7"
        >
          <p className="font-head text-xs font-600 uppercase tracking-wider text-white/60">
            Onde está meu pedido?
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              search(query);
            }}
            className="mt-3 flex gap-2"
          >
            <div className="relative flex flex-1 items-center">
              <Search className="absolute left-4 h-4 w-4 text-white/40" />
              <input
                data-testid="tracking-search-input"
                value={query}
                onChange={(e) => setQuery(e.target.value.toUpperCase())}
                placeholder="DDC-XXXXXX"
                className="h-12 w-full rounded-xl border border-white/10 bg-white/5 pl-11 pr-4 font-head text-sm tracking-widest text-white placeholder:text-white/30 focus:border-violet-500/60 focus:outline-none focus:ring-2 focus:ring-violet-600/30"
              />
            </div>
            <button
              type="submit"
              data-testid="tracking-search-button"
              disabled={loading}
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-purple-500 px-6 font-head text-sm font-600 uppercase tracking-wider text-white shadow-lg shadow-violet-900/40 transition-transform hover:scale-[1.03] active:scale-95 disabled:opacity-60"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Rastrear
            </button>
          </form>
          {error && (
            <p data-testid="tracking-error" className="mt-3 text-sm text-red-400">
              {error}
            </p>
          )}
        </motion.div>

        {order && (
          <motion.div
            data-testid="tracking-result"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="glass mt-6 rounded-3xl p-6 sm:p-8"
          >
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-amber-300">
                  Missão
                </p>
                <p
                  data-testid="tracking-order-number"
                  className="font-display text-3xl text-gradient"
                >
                  {order.order_number}
                </p>
              </div>
              <div className="text-right text-xs text-white/50">
                <p>
                  {order.shipping.label} • {order.shipping.eta}
                </p>
                <p className="mt-0.5">
                  {order.address.city}/{order.address.state} — CEP {order.address.cep}
                </p>
              </div>
            </div>

            {/* Timeline */}
            <div className="relative mt-8 pl-1">
              <div className="absolute bottom-5 left-[27px] top-5 w-0.5 bg-white/10" />
              <motion.div
                initial={{ scaleY: 0 }}
                animate={{ scaleY: 1 }}
                transition={{ delay: 0.4, duration: 1.2, ease: "easeInOut" }}
                style={{
                  height: `${(currentIdx / (STATUS_FLOW.length - 1)) * 100}%`,
                  transformOrigin: "top",
                }}
                className="absolute left-[27px] top-5 w-0.5 bg-gradient-to-b from-violet-500 to-amber-400"
              />
              <ul className="flex flex-col gap-7">
                {STATUS_FLOW.map((s, i) => {
                  const done = i < currentIdx;
                  const current = i === currentIdx;
                  const Icon = s.icon;
                  return (
                    <motion.li
                      key={s.id}
                      data-testid={`tracking-step-${s.id}`}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.5 + i * 0.15, duration: 0.5 }}
                      className="relative flex items-start gap-4"
                    >
                      <span className="relative z-10">
                        {current && (
                          <motion.span
                            animate={{ scale: [1, 1.6], opacity: [0.5, 0] }}
                            transition={{ duration: 1.6, repeat: Infinity }}
                            className="absolute inset-0 rounded-full bg-amber-400"
                          />
                        )}
                        <span
                          className={`relative flex h-[54px] w-[54px] items-center justify-center rounded-full border-2 transition-colors ${
                            done
                              ? "border-violet-500 bg-violet-600/30 text-violet-200"
                              : current
                              ? "border-amber-400 bg-amber-400/15 text-amber-300"
                              : "border-white/15 bg-black/30 text-white/30"
                          }`}
                        >
                          <Icon className="h-5 w-5" />
                        </span>
                      </span>
                      <div className={`pt-1.5 ${done || current ? "" : "opacity-40"}`}>
                        <p
                          className={`font-head text-sm font-600 uppercase tracking-wide ${
                            current ? "text-amber-300" : "text-white"
                          }`}
                        >
                          {s.label}
                          {current && (
                            <span className="ml-2 rounded-full bg-amber-400/15 px-2 py-0.5 text-[9px] tracking-widest text-amber-300">
                              AGORA
                            </span>
                          )}
                        </p>
                        <p className="mt-0.5 text-xs text-white/50">{s.desc}</p>
                      </div>
                    </motion.li>
                  );
                })}
              </ul>
            </div>

            {/* Summary */}
            <div className="mt-8 rounded-2xl border border-white/10 bg-white/5 p-4">
              <ul className="flex flex-col gap-2">
                {order.items.map((i) => (
                  <li key={i.id} className="flex items-center justify-between gap-3 text-xs">
                    <span className="line-clamp-1 text-white/80">
                      {i.qty}x {i.name}
                    </span>
                    <span className="shrink-0 font-head text-amber-300">
                      {formatBRL(i.price * i.qty)}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-3">
                <span className="font-head text-xs uppercase tracking-wide text-white/60">
                  Total
                </span>
                <span className="font-display text-2xl text-gradient">
                  {formatBRL(order.total)}
                </span>
              </div>
            </div>

            {order.status === "aguardando_pagamento" && (
              <a
                data-testid="tracking-whatsapp-button"
                href={orderWhatsAppUrl(order)}
                target="_blank"
                rel="noreferrer"
                className="mt-5 flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-emerald-500 to-green-600 px-6 py-3.5 font-head text-sm font-600 uppercase tracking-wider text-white shadow-lg shadow-emerald-900/30 transition-transform hover:scale-[1.02]"
              >
                <Send className="h-4 w-4" /> Concluir pagamento no WhatsApp
              </a>
            )}
          </motion.div>
        )}

        {!order && !loading && !error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="mt-10 flex flex-col items-center text-center"
          >
            <div className="relative flex h-24 w-24 items-center justify-center">
              <div className="animate-spin-slow absolute h-24 w-24 rounded-full border border-violet-500/25" />
              <MapPin className="h-9 w-9 text-violet-400/50" />
            </div>
            <p className="mt-4 max-w-xs text-sm text-white/40">
              O número do pedido está na página de confirmação e na mensagem enviada no WhatsApp.
            </p>
          </motion.div>
        )}
      </main>
    </div>
  );
}
