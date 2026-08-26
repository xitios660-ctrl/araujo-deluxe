import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Timer } from "lucide-react";

const calc = () => {
  const now = new Date();
  const end = new Date(now);
  end.setHours(23, 59, 59, 999);
  const diff = Math.max(0, end - now);
  return {
    h: Math.floor(diff / 3600000),
    m: Math.floor((diff % 3600000) / 60000),
    s: Math.floor((diff % 60000) / 1000),
  };
};

const pad = (n) => String(n).padStart(2, "0");

function Digit({ value, label }) {
  return (
    <div className="flex flex-col items-center">
      <div className="glass relative w-16 overflow-hidden rounded-xl border-amber-400/25 py-2.5 text-center sm:w-20">
        <motion.span
          key={value}
          initial={{ y: -14, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.25 }}
          className="block font-display text-3xl text-amber-300 sm:text-4xl"
        >
          {value}
        </motion.span>
        <div className="pointer-events-none absolute inset-x-0 top-1/2 h-px bg-white/10" />
      </div>
      <span className="mt-1.5 text-[9px] font-semibold uppercase tracking-[0.3em] text-white/40">
        {label}
      </span>
    </div>
  );
}

export default function PromoCountdown() {
  const [t, setT] = useState(calc());

  useEffect(() => {
    const id = setInterval(() => setT(calc()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: 0.3, duration: 0.6 }}
      data-testid="promo-countdown"
      className="mt-6 flex flex-col items-center"
    >
      <p className="mb-3 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.3em] text-amber-300">
        <Timer className="h-4 w-4 animate-pulse" /> A oferta termina em
      </p>
      <div className="flex items-start gap-2">
        <Digit value={pad(t.h)} label="Horas" />
        <span className="pt-3 font-display text-2xl text-amber-400/60 animate-pulse">:</span>
        <Digit value={pad(t.m)} label="Min" />
        <span className="pt-3 font-display text-2xl text-amber-400/60 animate-pulse">:</span>
        <Digit value={pad(t.s)} label="Seg" />
      </div>
    </motion.div>
  );
}
