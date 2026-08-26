import React from "react";
import { motion } from "framer-motion";
import { Wind, Zap, ArrowRight } from "lucide-react";
import { brand } from "../mock";

export default function CtaBanner() {
  return (
    <section className="relative z-10 mx-auto max-w-7xl px-4 py-10">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="relative overflow-hidden rounded-3xl border border-violet-500/30 bg-gradient-to-br from-violet-800/40 via-purple-900/30 to-[#0b0817] p-8 sm:p-12"
      >
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-violet-600/30 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-20 left-10 h-56 w-56 rounded-full bg-amber-500/10 blur-3xl" />
        <div className="relative grid grid-cols-1 items-center gap-8 lg:grid-cols-2">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full bg-amber-400/15 px-4 py-1.5 text-[11px] font-bold uppercase tracking-widest text-amber-300">
              <Zap className="h-3.5 w-3.5" /> Cartão recusado? Sem estresse
            </span>
            <h3 className="mt-5 font-display text-4xl leading-[0.95] text-white sm:text-5xl">
              NÃO PERCA <span className="text-gradient">SUA COMPRA</span>
            </h3>
            <p className="mt-4 max-w-md text-white/70">
              Problema no pagamento? A gente finaliza seu pedido na hora pelo
              WhatsApp. Atendimento humano, resposta imediata e sem burocracia.
            </p>
          </div>
          <div className="flex flex-col items-start gap-4 lg:items-end">
            <a
              href={`https://wa.me/${brand.whatsapp}`}
              target="_blank"
              rel="noreferrer"
              className="group inline-flex items-center gap-3 rounded-full bg-gradient-to-r from-emerald-500 to-green-600 px-8 py-4 font-head text-base font-600 uppercase tracking-wider text-white shadow-xl shadow-emerald-900/40 transition-transform hover:scale-105"
            >
              <Wind className="h-5 w-5" />
              Finalizar pelo WhatsApp
              <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
            </a>
            <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs font-semibold uppercase tracking-wide text-white/60 lg:justify-end">
              <span>• Atendimento humano</span>
              <span>• Resposta imediata</span>
              <span>• Sem burocracia</span>
            </div>
          </div>
        </div>
      </motion.div>
    </section>
  );
}
