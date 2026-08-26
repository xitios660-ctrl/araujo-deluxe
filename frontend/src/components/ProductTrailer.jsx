import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  RotateCcw,
  Star,
  Minus,
  Plus,
  ShoppingCart,
  Wind,
  Truck,
  ShieldCheck,
} from "lucide-react";
import { formatBRL, brand } from "../mock";
import { useCart } from "../context/CartContext";
import ShippingCalculator from "./ShippingCalculator";

// Cinematic "presentation video": the line NAME reveals, then its ART appears,
// finishing on a buy scene. Pure in-app motion graphic (no external video files).
export default function ProductTrailer({ product, onClose }) {
  const { addItem } = useCart();
  const [phase, setPhase] = useState(0); // 0 name, 1 image reveal, 2 buy
  const [qty, setQty] = useState(1);
  const [runId, setRunId] = useState(0);

  const play = useCallback(() => {
    setPhase(0);
    setQty(1);
    setRunId((r) => r + 1);
  }, []);

  useEffect(() => {
    if (!product) return;
    play();
  }, [product, play]);

  // Timeline
  useEffect(() => {
    if (!product) return;
    const t1 = setTimeout(() => setPhase(1), 2200);
    const t2 = setTimeout(() => setPhase(2), 4300);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [runId, product]);

  // Esc + scroll lock
  useEffect(() => {
    if (!product) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [product, onClose]);

  if (!product) return null;
  const words = product.name.split(" ");

  return (
    <AnimatePresence>
      {product && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center overflow-hidden bg-black"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {/* Cinematic backdrop */}
          <div className="cinema-bg absolute inset-0" />
          <div className="film-grain" />

          {/* Letterbox bars */}
          <motion.div
            initial={{ height: "18%" }}
            animate={{ height: phase >= 2 ? "6%" : "12%" }}
            transition={{ duration: 0.8 }}
            className="absolute inset-x-0 top-0 z-30 bg-black"
          />
          <motion.div
            initial={{ height: "18%" }}
            animate={{ height: phase >= 2 ? "6%" : "12%" }}
            transition={{ duration: 0.8 }}
            className="absolute inset-x-0 bottom-0 z-30 bg-black"
          />

          {/* Controls */}
          <div className="absolute right-5 top-5 z-40 flex gap-2">
            <button
              onClick={play}
              className="flex h-11 w-11 items-center justify-center rounded-full bg-white/10 text-white backdrop-blur transition-colors hover:bg-violet-600"
              aria-label="Repetir"
            >
              <RotateCcw className="h-5 w-5" />
            </button>
            <button
              onClick={onClose}
              className="flex h-11 w-11 items-center justify-center rounded-full bg-white/10 text-white backdrop-blur transition-colors hover:bg-violet-600"
              aria-label="Fechar"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Progress bar */}
          <div className="absolute inset-x-0 bottom-0 z-40 h-1 bg-white/10">
            <motion.div
              key={runId}
              initial={{ width: "0%" }}
              animate={{ width: phase >= 2 ? "100%" : "100%" }}
              transition={{ duration: 4.3, ease: "linear" }}
              className="h-full bg-gradient-to-r from-violet-500 to-amber-400"
            />
          </div>

          {/* STAGE */}
          <div className="relative z-20 flex h-full w-full max-w-5xl items-center justify-center px-6">
            {/* Spotlight */}
            <div className="pointer-events-none absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-600/20 blur-3xl" />

            {/* PHASE 0 & 1: name */}
            <motion.div
              className="absolute inset-0 flex flex-col items-center justify-center text-center"
              animate={{
                y: phase >= 1 ? "-30vh" : 0,
                scale: phase >= 1 ? 0.55 : 1,
                opacity: phase >= 2 ? 0 : 1,
              }}
              transition={{ duration: 0.9, ease: "easeInOut" }}
            >
              <motion.p
                initial={{ opacity: 0, letterSpacing: "0.1em" }}
                animate={{ opacity: 1, letterSpacing: "0.5em" }}
                transition={{ duration: 1 }}
                className="mb-5 text-[11px] font-semibold uppercase text-amber-300 sm:text-sm"
              >
                {brand.name} apresenta
              </motion.p>
              <h1 className="flex max-w-3xl flex-wrap justify-center gap-x-4 gap-y-1 font-display text-4xl leading-[0.95] text-white sm:text-6xl md:text-7xl">
                {words.map((w, i) => (
                  <motion.span
                    key={`${runId}-${i}`}
                    initial={{ opacity: 0, y: 40, filter: "blur(12px)" }}
                    animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                    transition={{ delay: 0.3 + i * 0.14, duration: 0.6 }}
                    className="glow-purple inline-block"
                  >
                    {w}
                  </motion.span>
                ))}
              </h1>
            </motion.div>

            {/* PHASE 1: art reveal */}
            <AnimatePresence>
              {phase >= 1 && (
                <motion.div
                  className="relative flex items-center justify-center"
                  initial={{ opacity: 0, scale: 0.6, y: phase >= 2 ? 0 : 40 }}
                  animate={{
                    opacity: 1,
                    scale: 1,
                    y: phase >= 2 ? "-4vh" : "6vh",
                  }}
                  transition={{ duration: 1, ease: "easeOut" }}
                >
                  <div className="animate-spin-slow absolute h-[360px] w-[360px] rounded-full border border-violet-500/25" />
                  <div className="absolute h-[300px] w-[300px] rounded-full bg-violet-600/25 blur-3xl" />
                  {/* light sweep */}
                  <motion.div
                    initial={{ x: "-120%" }}
                    animate={{ x: "120%" }}
                    transition={{ delay: 0.4, duration: 1.1, ease: "easeInOut" }}
                    className="pointer-events-none absolute z-20 h-[340px] w-24 -skew-x-12 bg-white/20 blur-md"
                  />
                  <motion.img
                    src={product.art || product.image}
                    alt={product.name}
                    onError={(e) => {
                      e.currentTarget.src = product.image;
                    }}
                    initial={{ filter: "brightness(0.2)" }}
                    animate={{ filter: "brightness(1)" }}
                    transition={{ duration: 1 }}
                    className="relative z-10 max-h-[46vh] w-auto rounded-2xl object-contain shadow-[0_30px_80px_rgba(124,58,237,0.4)]"
                  />
                  {product.off > 0 && (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 0.9, type: "spring" }}
                      className="absolute -right-3 -top-3 z-20 rounded-full bg-gradient-to-r from-amber-400 to-amber-500 px-3 py-1.5 text-sm font-bold text-black"
                    >
                      {product.off}% OFF
                    </motion.span>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* PHASE 2: buy panel */}
          <AnimatePresence>
            {phase >= 2 && (
              <motion.div
                initial={{ opacity: 0, y: 60 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
                className="absolute inset-x-0 bottom-[7%] z-40 mx-auto w-full max-w-3xl px-6"
              >
                <div className="glass rounded-3xl p-5 sm:p-6">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      {product.badge && (
                        <span className="mb-1 inline-block rounded-full border border-violet-400/40 bg-violet-600/20 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-violet-200">
                          {product.badge}
                        </span>
                      )}
                      <h3 className="font-head text-lg font-600 uppercase leading-tight text-white line-clamp-1">
                        {product.name}
                      </h3>
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        <div className="flex">
                          {[1, 2, 3, 4, 5].map((n) => (
                            <Star
                              key={n}
                              className={`h-3.5 w-3.5 ${
                                n <= Math.round(product.rating)
                                  ? "fill-amber-400 text-amber-400"
                                  : "text-white/25"
                              }`}
                            />
                          ))}
                        </div>
                        {Object.values(product.specs).map((v, i) => (
                          <span
                            key={i}
                            className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] text-violet-200"
                          >
                            {v}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="text-right">
                      {product.off > 0 && (
                        <p className="text-xs text-white/40 line-through">
                          {formatBRL(product.oldPrice)}
                        </p>
                      )}
                      <p className="font-display text-3xl text-gradient">
                        {formatBRL(product.price)}
                      </p>
                      <p className="text-[11px] text-white/50">
                        12x de {formatBRL(product.price / 12)}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
                    <div className="flex items-center justify-center rounded-full border border-white/15">
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
                    <a
                      href={`https://wa.me/${brand.whatsapp}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center justify-center gap-2 rounded-full border border-amber-400/40 px-6 py-3.5 font-head text-sm font-600 uppercase tracking-wider text-amber-300 transition-colors hover:bg-amber-400/10"
                    >
                      <Wind className="h-4 w-4" /> WhatsApp
                    </a>
                  </div>
                  <div className="mt-3">
                    <ShippingCalculator collapsible subtotal={product.price * qty} />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-4 text-[11px] text-white/50">
                    <span className="flex items-center gap-1.5">
                      <Truck className="h-3.5 w-3.5 text-emerald-400" /> Frete com desconto
                    </span>
                    <span className="flex items-center gap-1.5">
                      <ShieldCheck className="h-3.5 w-3.5 text-violet-300" /> Compra
                      segura
                    </span>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
