import React, { useState } from "react";
import { motion } from "framer-motion";
import { Mail, Send, Instagram, Check } from "lucide-react";
import { brand, instagramShots } from "../mock";

export default function Newsletter() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);

  const submit = (e) => {
    e.preventDefault();
    if (!email) return;
    setDone(true);
    setEmail("");
    setTimeout(() => setDone(false), 3500);
  };

  return (
    <section id="contato" className="relative z-10 mx-auto max-w-7xl px-4 py-16">
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Newsletter */}
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="glass flex flex-col justify-center rounded-3xl p-8"
        >
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-600/20 text-violet-300">
            <Mail className="h-6 w-6" />
          </span>
          <h3 className="mt-5 font-display text-3xl text-white">
            RECEBA AS PROMOÇÕES
          </h3>
          <p className="mt-2 text-sm text-white/60">
            Cadastre-se e seja o primeiro a saber das ofertas e lançamentos
            cortantes.
          </p>
          <form onSubmit={submit} className="mt-6 flex gap-2">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Seu melhor e-mail"
              className="h-12 flex-1 rounded-full border border-violet-500/20 bg-white/5 px-5 text-sm text-white placeholder:text-white/40 focus:border-violet-500/60 focus:outline-none focus:ring-2 focus:ring-violet-600/30"
            />
            <button
              type="submit"
              className="flex h-12 items-center gap-2 rounded-full bg-gradient-to-r from-violet-600 to-purple-500 px-6 font-head text-sm font-600 uppercase tracking-wider text-white transition-transform hover:scale-105"
            >
              {done ? <Check className="h-4 w-4" /> : <Send className="h-4 w-4" />}
              {done ? "Feito" : "Enviar"}
            </button>
          </form>
          {done && (
            <p className="mt-3 text-xs text-emerald-400">
              Show! Você entrou na lista das promoções. 🚀
            </p>
          )}
        </motion.div>

        {/* Instagram */}
        <motion.div
          initial={{ opacity: 0, x: 30 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="rounded-3xl border border-white/10 bg-card p-8"
        >
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-display text-2xl text-white">NO INSTAGRAM</h3>
              <p className="text-sm text-violet-300">@{brand.instagram}</p>
            </div>
            <a
              href={brand.instagramUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 rounded-full bg-gradient-to-r from-fuchsia-600 to-violet-500 px-4 py-2 text-xs font-600 uppercase tracking-wide text-white transition-transform hover:scale-105"
            >
              <Instagram className="h-4 w-4" /> Seguir
            </a>
          </div>
          <div className="mt-5 grid grid-cols-3 gap-2">
            {instagramShots.map((src, i) => (
              <a
                key={i}
                href={brand.instagramUrl}
                target="_blank"
                rel="noreferrer"
                className="group relative aspect-square overflow-hidden rounded-xl"
              >
                <img
                  src={src}
                  alt={`Post ${i + 1}`}
                  loading="lazy"
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
                  <Instagram className="h-6 w-6 text-white" />
                </div>
              </a>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
