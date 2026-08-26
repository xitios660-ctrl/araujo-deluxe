import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Star, Minus, Plus, ShoppingCart, Truck, ShieldCheck, Wind } from "lucide-react";
import { formatBRL, brand } from "../mock";
import { useCart } from "../context/CartContext";

export default function ProductModal({ product, onClose }) {
  const { addItem } = useCart();
  const [qty, setQty] = useState(1);

  useEffect(() => {
    setQty(1);
  }, [product]);

  useEffect(() => {
    if (!product) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [product, onClose]);

  return (
    <AnimatePresence>
      {product && (
        <motion.div
          className="fixed inset-0 z-[70] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div
            className="absolute inset-0 bg-black/80 backdrop-blur-md"
            onClick={onClose}
          />
          <motion.div
            initial={{ scale: 0.9, y: 40, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.9, y: 40, opacity: 0 }}
            transition={{ type: "spring", stiffness: 220, damping: 24 }}
            className="relative z-10 grid max-h-[90vh] w-full max-w-4xl grid-cols-1 overflow-hidden overflow-y-auto rounded-3xl border border-violet-500/25 bg-[#0d0a18] md:grid-cols-2"
          >
            <button
              onClick={onClose}
              className="absolute right-4 top-4 z-20 flex h-10 w-10 items-center justify-center rounded-full bg-black/50 text-white transition-colors hover:bg-violet-600"
              aria-label="Fechar"
            >
              <X className="h-5 w-5" />
            </button>

            {/* Cinematic image side */}
            <div className="relative flex items-center justify-center overflow-hidden bg-gradient-to-br from-[#1a1330] to-[#0a0715] p-8">
              <div className="animate-spin-slow absolute h-80 w-80 rounded-full border border-violet-500/20" />
              <div className="absolute h-60 w-60 rounded-full bg-violet-600/20 blur-3xl" />
              {product.off > 0 && (
                <span className="absolute left-5 top-5 z-10 rounded-full bg-gradient-to-r from-amber-400 to-amber-500 px-3 py-1 text-sm font-bold text-black">
                  {product.off}% OFF
                </span>
              )}
              <motion.img
                initial={{ scale: 0.8, rotate: -6, opacity: 0 }}
                animate={{ scale: 1, rotate: 0, opacity: 1 }}
                transition={{ delay: 0.1, type: "spring", stiffness: 120 }}
                src={product.art || product.image}
                alt={product.name}
                onError={(e) => {
                  e.currentTarget.src = product.image;
                }}
                className="relative z-10 max-h-[320px] w-auto rounded-2xl object-contain drop-shadow-2xl"
              />
            </div>

            {/* Info side */}
            <div className="flex flex-col p-7">
              {product.badge && (
                <span className="mb-3 w-fit rounded-full border border-violet-400/40 bg-violet-600/20 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-violet-200">
                  {product.badge}
                </span>
              )}
              <h2 className="font-display text-3xl leading-tight text-white">
                {product.name}
              </h2>
              <div className="mt-3 flex items-center gap-2">
                <div className="flex">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <Star
                      key={n}
                      className={`h-4 w-4 ${
                        n <= Math.round(product.rating)
                          ? "fill-amber-400 text-amber-400"
                          : "text-white/25"
                      }`}
                    />
                  ))}
                </div>
                <span className="text-xs text-white/50">
                  {product.rating} • {product.reviews} avaliações
                </span>
              </div>

              {/* Specs presentation */}
              <div className="mt-5 grid grid-cols-3 gap-2">
                {Object.entries(product.specs).map(([k, v]) => (
                  <div
                    key={k}
                    className="rounded-xl border border-white/10 bg-white/5 p-3 text-center"
                  >
                    <p className="text-[10px] uppercase tracking-wider text-white/40">
                      {k}
                    </p>
                    <p className="mt-1 font-head text-sm font-600 text-white">{v}</p>
                  </div>
                ))}
              </div>

              <div className="mt-6 flex items-end gap-3">
                {product.off > 0 && (
                  <span className="text-sm text-white/40 line-through">
                    {formatBRL(product.oldPrice)}
                  </span>
                )}
                <span className="font-display text-4xl text-gradient">
                  {formatBRL(product.price)}
                </span>
              </div>
              <p className="mt-1 text-xs text-white/50">
                ou 12x de {formatBRL(product.price / 12)} sem juros
              </p>

              {/* Qty + add */}
              <div className="mt-6 flex items-center gap-3">
                <div className="flex items-center rounded-full border border-white/15">
                  <button
                    onClick={() => setQty((q) => Math.max(1, q - 1))}
                    className="flex h-11 w-11 items-center justify-center text-white/80 hover:text-white"
                  >
                    <Minus className="h-4 w-4" />
                  </button>
                  <span className="w-8 text-center font-head text-lg text-white">
                    {qty}
                  </span>
                  <button
                    onClick={() => setQty((q) => q + 1)}
                    className="flex h-11 w-11 items-center justify-center text-white/80 hover:text-white"
                  >
                    <Plus className="h-4 w-4" />
                  </button>
                </div>
                <button
                  onClick={() => {
                    addItem(product, qty);
                    onClose();
                  }}
                  className="flex flex-1 items-center justify-center gap-2 rounded-full bg-gradient-to-r from-violet-600 to-purple-500 px-6 py-3.5 font-head text-sm font-600 uppercase tracking-wider text-white shadow-lg shadow-violet-900/40 transition-transform hover:scale-[1.02] active:scale-95"
                >
                  <ShoppingCart className="h-4 w-4" /> Adicionar
                </button>
              </div>

              <a
                href={`https://wa.me/${brand.whatsapp}`}
                target="_blank"
                rel="noreferrer"
                className="mt-3 flex items-center justify-center gap-2 rounded-full border border-amber-400/40 px-6 py-3 font-head text-sm font-600 uppercase tracking-wider text-amber-300 transition-colors hover:bg-amber-400/10"
              >
                <Wind className="h-4 w-4" /> Comprar pelo WhatsApp
              </a>

              <div className="mt-5 flex flex-wrap gap-4 border-t border-white/10 pt-4 text-xs text-white/60">
                <span className="flex items-center gap-1.5">
                  <Truck className="h-4 w-4 text-emerald-400" /> Frete grátis acima de R$250
                </span>
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="h-4 w-4 text-violet-300" /> Compra segura
                </span>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
