import React from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, Minus, Plus, Trash2, ShoppingBag, Wind, CreditCard } from "lucide-react";
import { formatBRL, brand } from "../mock";
import { useCart } from "../context/CartContext";
import ShippingCalculator from "./ShippingCalculator";

export default function CartDrawer() {
  const { items, open, setOpen, updateQty, removeItem, subtotal, count, clear } =
    useCart();
  const navigate = useNavigate();

  const checkoutMsg = encodeURIComponent(
    `Olá! Quero finalizar meu pedido:\n${items
      .map((i) => `• ${i.qty}x ${i.name} - ${formatBRL(i.price * i.qty)}`)
      .join("\n")}\n\nTotal: ${formatBRL(subtotal)}`
  );

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm"
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 260, damping: 30 }}
            className="fixed right-0 top-0 z-[90] flex h-full w-full max-w-md flex-col border-l border-violet-500/25 bg-[#0b0817]"
          >
            <div className="flex items-center justify-between border-b border-white/10 p-5">
              <div className="flex items-center gap-2">
                <ShoppingBag className="h-5 w-5 text-violet-300" />
                <h3 className="font-head text-lg font-600 uppercase tracking-wide text-white">
                  Carrinho
                </h3>
                <span className="rounded-full bg-violet-600/30 px-2 py-0.5 text-xs text-violet-100">
                  {count}
                </span>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="flex h-9 w-9 items-center justify-center rounded-full text-white/70 hover:bg-white/5 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5">
              {items.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-violet-600/10">
                    <ShoppingBag className="h-9 w-9 text-violet-400/60" />
                  </div>
                  <p className="font-head text-lg text-white">Carrinho vazio</p>
                  <p className="mt-1 text-sm text-white/50">
                    Escolha sua linha e prepare o cortante.
                  </p>
                  <button
                    onClick={() => setOpen(false)}
                    className="mt-5 rounded-full bg-violet-600 px-6 py-2.5 font-head text-sm font-600 uppercase tracking-wide text-white"
                  >
                    Ver linhas
                  </button>
                </div>
              ) : (
                <ul className="flex flex-col gap-4">
                  {items.map((i) => (
                    <li
                      key={i.id}
                      className="flex gap-3 rounded-2xl border border-white/10 bg-white/5 p-3"
                    >
                      <img
                        src={i.image}
                        alt={i.name}
                        className="h-16 w-16 shrink-0 rounded-xl object-cover"
                      />
                      <div className="flex min-w-0 flex-1 flex-col">
                        <p className="line-clamp-2 text-xs font-medium text-white">
                          {i.name}
                        </p>
                        <p className="mt-1 font-head text-sm text-amber-300">
                          {formatBRL(i.price)}
                        </p>
                        <div className="mt-auto flex items-center justify-between">
                          <div className="flex items-center rounded-full border border-white/15">
                            <button
                              onClick={() => updateQty(i.id, i.qty - 1)}
                              className="flex h-7 w-7 items-center justify-center text-white/70"
                            >
                              <Minus className="h-3 w-3" />
                            </button>
                            <span className="w-6 text-center text-sm text-white">
                              {i.qty}
                            </span>
                            <button
                              onClick={() => updateQty(i.id, i.qty + 1)}
                              className="flex h-7 w-7 items-center justify-center text-white/70"
                            >
                              <Plus className="h-3 w-3" />
                            </button>
                          </div>
                          <button
                            onClick={() => removeItem(i.id)}
                            className="flex h-7 w-7 items-center justify-center rounded-full text-white/40 hover:text-red-400"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {items.length > 0 && (
              <div className="border-t border-white/10 p-5">
                <ShippingCalculator subtotal={subtotal} collapsible className="mb-4" />
                <div className="mb-4 flex items-center justify-between">
                  <span className="text-sm text-white/60">Subtotal</span>
                  <span className="font-display text-2xl text-white">
                    {formatBRL(subtotal)}
                  </span>
                </div>
                <button
                  data-testid="cart-checkout-button"
                  onClick={() => {
                    setOpen(false);
                    navigate("/checkout");
                  }}
                  className="flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-violet-600 to-purple-500 px-6 py-3.5 font-head text-sm font-600 uppercase tracking-wider text-white shadow-lg shadow-violet-900/40 transition-transform hover:scale-[1.02] active:scale-95"
                >
                  <CreditCard className="h-4 w-4" /> Finalizar compra
                </button>
                <a
                  data-testid="cart-whatsapp-link"
                  href={`https://wa.me/${brand.whatsapp}?text=${checkoutMsg}`}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 flex items-center justify-center gap-1.5 py-2 text-xs text-emerald-400/80 transition-colors hover:text-emerald-300"
                >
                  <Wind className="h-3.5 w-3.5" /> ou finalize direto no WhatsApp
                </a>
                <button
                  onClick={clear}
                  className="mt-1 w-full py-1 text-center text-xs text-white/40 hover:text-white/70"
                >
                  Esvaziar carrinho
                </button>
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
