import React from "react";
import { motion } from "framer-motion";
import ProductCard from "./ProductCard";
import PromoCountdown from "./PromoCountdown";

export default function ProductSection({ id, eyebrow, title, subtitle, products, onOpen, accent = "violet", scene, countdown = false }) {
  return (
    <section id={id} className="relative z-10 mx-auto max-w-7xl px-4 py-14 sm:py-20">
      <div className="mb-10 flex flex-col items-center text-center">
        {scene && (
          <div className="mb-4 flex w-full max-w-md items-center gap-3">
            <motion.span
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.9, ease: "easeInOut" }}
              className="h-px flex-1 origin-right bg-gradient-to-l from-white/25 to-transparent"
            />
            <motion.span
              initial={{ opacity: 0, letterSpacing: "0.2em" }}
              whileInView={{ opacity: 1, letterSpacing: "0.5em" }}
              viewport={{ once: true }}
              transition={{ duration: 1 }}
              className="font-head text-[10px] font-600 uppercase text-white/40"
            >
              Cena {scene}
            </motion.span>
            <motion.span
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.9, ease: "easeInOut" }}
              className="h-px flex-1 origin-left bg-gradient-to-r from-white/25 to-transparent"
            />
          </div>
        )}
        <motion.span
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className={`mb-3 inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.28em] ${
            accent === "gold"
              ? "border-amber-400/30 bg-amber-400/10 text-amber-300"
              : "border-violet-500/30 bg-violet-600/10 text-violet-200"
          }`}
        >
          {eyebrow}
        </motion.span>
        <h2 className="flex flex-wrap justify-center gap-x-4 font-display text-4xl leading-none text-white sm:text-5xl md:text-6xl">
          {title.split(" ").map((w, i) => (
            <motion.span
              key={i}
              initial={{ opacity: 0, y: 46, filter: "blur(14px)" }}
              whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ delay: 0.15 + i * 0.16, duration: 0.7 }}
              className={accent === "gold" ? "glow-gold inline-block" : "glow-purple inline-block"}
            >
              {w}
            </motion.span>
          ))}
        </h2>
        {subtitle && (
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.4, duration: 0.6 }}
            className="mt-4 max-w-2xl text-sm text-white/60 sm:text-base"
          >
            {subtitle}
          </motion.p>
        )}
        <motion.div
          initial={{ scaleX: 0, opacity: 0 }}
          whileInView={{ scaleX: 1, opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.5, duration: 0.7, ease: "easeOut" }}
          className={`mt-5 h-1 w-24 rounded-full ${
            accent === "gold"
              ? "bg-gradient-to-r from-transparent via-amber-400 to-transparent"
              : "bg-gradient-to-r from-transparent via-violet-500 to-transparent"
          }`}
        />
        {countdown && <PromoCountdown />}
      </div>

      <div className="grid grid-cols-2 gap-4 sm:gap-5 md:grid-cols-3 lg:grid-cols-4">
        {products.map((p, i) => (
          <ProductCard key={p.id} product={p} index={i} onOpen={onOpen} />
        ))}
      </div>
    </section>
  );
}
