import React from "react";
import { motion } from "framer-motion";
import { Star, Quote } from "lucide-react";
import { testimonials } from "../mock";

function Card({ t }) {
  return (
    <div className="mx-3 w-[320px] shrink-0 rounded-2xl border border-white/10 bg-card p-6">
      <Quote className="h-7 w-7 text-violet-500/40" />
      <div className="mt-3 flex">
        {Array.from({ length: t.rating }).map((_, i) => (
          <Star key={i} className="h-4 w-4 fill-amber-400 text-amber-400" />
        ))}
      </div>
      <p className="mt-3 text-sm leading-relaxed text-white/80">“{t.text}”</p>
      <div className="mt-5 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-violet-600 to-purple-800 font-head text-sm font-600 text-white">
          {t.name.charAt(0)}
        </span>
        <div>
          <p className="text-sm font-600 text-white">{t.name}</p>
          <p className="text-xs text-white/40">{t.handle}</p>
        </div>
      </div>
    </div>
  );
}

export default function Testimonials() {
  const loop = [...testimonials, ...testimonials];
  return (
    <section className="relative z-10 overflow-hidden py-16 sm:py-24">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="mb-12 text-center"
      >
        <span className="mb-3 inline-block rounded-full border border-violet-500/30 bg-violet-600/10 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.28em] text-violet-200">
          A quebrada aprova
        </span>
        <h2 className="font-display text-4xl leading-none text-white sm:text-5xl md:text-6xl">
          <span className="glow-purple">QUEM TESTOU, RECOMENDA</span>
        </h2>
      </motion.div>

      <div className="relative">
        <div className="pointer-events-none absolute left-0 top-0 z-10 h-full w-24 bg-gradient-to-r from-[#08060f] to-transparent" />
        <div className="pointer-events-none absolute right-0 top-0 z-10 h-full w-24 bg-gradient-to-l from-[#08060f] to-transparent" />
        <div className="flex w-max animate-marquee">
          {loop.map((t, i) => (
            <Card key={i} t={t} />
          ))}
        </div>
      </div>
    </section>
  );
}
