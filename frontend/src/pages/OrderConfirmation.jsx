import React, { useEffect, useState } from "react";
import axios from "axios";
import { Link, useLocation, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Check, Loader2, MapPin, Send, Truck } from "lucide-react";
import { formatBRL } from "../mock";
import { orderWhatsAppUrl } from "../lib/whatsapp";

const API = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/+$/, "");

export default function OrderConfirmation() {
  const { orderNumber } = useParams();
  const location = useLocation();
  const [order, setOrder] = useState(location.state?.order || null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (order) return;
    axios
      .get(`${API}/api/orders/${orderNumber}`)
      .then((r) => setOrder(r.data))
      .catch(() => setError("Pedido não encontrado."));
  }, [orderNumber, order]);

  if (error) {
    return (
      <div className="relative flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <div className="film-grain" />
        <h1 className="font-display text-4xl text-white">Pedido não encontrado</h1>
        <Link to="/" className="mt-6 text-sm text-violet-300 underline">
          Voltar à loja
        </Link>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-violet-400" />
      </div>
    );
  }

  return (
    <div className="relative min-h-screen" data-testid="order-confirmation">
      <div className="film-grain" />
      <div className="cinema-bg pointer-events-none fixed inset-0 opacity-60" />

      <main className="relative z-10 mx-auto max-w-2xl px-4 py-14">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
            className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-green-600 shadow-[0_20px_60px_rgba(16,185,129,0.35)]"
          >
            <Check className="h-12 w-12 text-white" strokeWidth={3} />
          </motion.div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.4em] text-amber-300">
            Cena final concluída
          </p>
          <h1 className="mt-2 font-display text-4xl text-white sm:text-5xl">
            PEDIDO CONFIRMADO
          </h1>
          <p
            data-testid="confirmation-order-number"
            className="mt-3 font-head text-xl font-600 tracking-widest text-gradient"
          >
            {order.order_number}
          </p>
          <p className="mx-auto mt-3 max-w-md text-sm text-white/55">
            Seu pedido foi registrado. Finalize o pagamento pelo WhatsApp — nossa equipe já
            recebeu todos os detalhes.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.6 }}
          className="glass mt-8 rounded-3xl p-6"
        >
          <ul className="flex flex-col gap-3">
            {order.items.map((i) => (
              <li key={i.id} className="flex items-center gap-3">
                {i.image && (
                  <img src={i.image} alt={i.name} className="h-12 w-12 rounded-lg object-cover" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-1 text-xs font-medium text-white">{i.name}</p>
                  <p className="text-[11px] text-white/50">
                    {i.qty}x {formatBRL(i.price)}
                  </p>
                </div>
                <span className="font-head text-sm text-amber-300">
                  {formatBRL(i.price * i.qty)}
                </span>
              </li>
            ))}
          </ul>

          <div className="mt-5 flex flex-col gap-2 border-t border-white/10 pt-4 text-sm">
            <div className="flex justify-between text-white/60">
              <span>Subtotal</span>
              <span>{formatBRL(order.subtotal)}</span>
            </div>
            <div className="flex justify-between text-white/60">
              <span className="flex items-center gap-1.5">
                <Truck className="h-4 w-4 text-emerald-400" /> {order.shipping.label}
              </span>
              <span>{order.shipping.price === 0 ? "GRÁTIS" : formatBRL(order.shipping.price)}</span>
            </div>
            <div className="flex items-end justify-between">
              <span className="font-head text-sm uppercase tracking-wide text-white/80">Total</span>
              <span className="font-display text-3xl text-gradient">{formatBRL(order.total)}</span>
            </div>
          </div>

          <div className="mt-5 rounded-2xl border border-white/10 bg-white/5 p-4 text-xs text-white/60">
            <p className="flex items-start gap-2">
              <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
              {order.address.street}, {order.address.number}
              {order.address.complement ? ` - ${order.address.complement}` : ""} —{" "}
              {order.address.neighborhood ? `${order.address.neighborhood}, ` : ""}
              {order.address.city}/{order.address.state} — CEP {order.address.cep}
            </p>
            <p className="mt-2 pl-6">
              Pagamento: <span className="text-white/85">{order.payment_method}</span>
            </p>
          </div>

          <a
            data-testid="confirmation-whatsapp-button"
            href={orderWhatsAppUrl(order)}
            target="_blank"
            rel="noreferrer"
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-emerald-500 to-green-600 px-6 py-4 font-head text-sm font-600 uppercase tracking-wider text-white shadow-lg shadow-emerald-900/30 transition-transform hover:scale-[1.02]"
          >
            <Send className="h-4 w-4" /> Enviar pedido no WhatsApp
          </a>
          <a
            data-testid="confirmation-track-link"
            href={`/rastreio/${order.order_number}`}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-full border border-violet-400/40 px-6 py-3 font-head text-xs font-600 uppercase tracking-wider text-violet-200 transition-colors hover:bg-violet-500/10"
          >
            <MapPin className="h-4 w-4" /> Rastrear pedido
          </a>
          <Link
            to="/"
            data-testid="confirmation-back-link"
            className="mt-3 block py-2 text-center text-xs text-white/40 transition-colors hover:text-white/70"
          >
            Voltar à loja
          </Link>
        </motion.div>
      </main>
    </div>
  );
}
