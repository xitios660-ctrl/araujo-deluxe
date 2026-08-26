import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence, useMotionValue, useSpring } from "framer-motion";
import { ArrowRight, ChevronLeft, ChevronRight, Wind, Sparkles } from "lucide-react";
import { heroSlides, brand } from "../mock";

export default function Hero() {
  const [index, setIndex] = useState(0);
  const containerRef = useRef(null);

  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const sx = useSpring(mx, { stiffness: 60, damping: 20 });
  const sy = useSpring(my, { stiffness: 60, damping: 20 });

  useEffect(() => {
    const t = setInterval(
      () => setIndex((i) => (i + 1) % heroSlides.length),
      6000
    );
    return () => clearInterval(t);
  }, []);

  const onMove = (e) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    mx.set(x * 30);
    my.set(y * 30);
  };

  const slide = heroSlides[index];
  const go = (dir) =>
    setIndex((i) => (i + dir + heroSlides.length) % heroSlides.length);

  return (
    <section
      id="inicio"
      ref={containerRef}
      onMouseMove={onMove}
      className="cinema-bg relative flex min-h-[86vh] items-center overflow-hidden"
    >
      {/* Orbiting decorative rings */}
      <motion.div
        style={{ x: sx, y: sy }}
        className="pointer-events-none absolute -right-40 top-1/2 -translate-y-1/2"
      >
        <div className="animate-spin-slow relative h-[620px] w-[620px] rounded-full border border-violet-500/20">
          <div className="absolute inset-10 rounded-full border border-violet-500/15" />
          <div className="absolute inset-24 rounded-full border border-amber-400/15" />
          <div className="absolute left-1/2 top-0 h-3 w-3 -translate-x-1/2 rounded-full bg-amber-400 shadow-[0_0_20px_6px_rgba(251,191,36,0.6)]" />
          <div className="absolute bottom-8 right-16 h-2 w-2 rounded-full bg-violet-400 shadow-[0_0_18px_6px_rgba(139,92,246,0.7)]" />
        </div>
      </motion.div>

      {/* Big ghost typography */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center opacity-[0.04]">
        <span className="font-display text-[26vw] leading-none text-white">
          COBRA
        </span>
      </div>

      <div className="relative z-10 mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-10 px-4 py-16 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <AnimatePresence mode="wait">
            <motion.div
              key={slide.id}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            >
              <span className="inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-600/10 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.25em] text-violet-200">
                <Sparkles className="h-3.5 w-3.5 text-amber-300" />
                {slide.kicker}
              </span>
              <h1 className="mt-6 font-display text-6xl leading-[0.9] text-white sm:text-7xl md:text-8xl">
                <span className="glow-purple">{slide.title}</span>
                <br />
                <span className="text-gradient">{slide.highlight}</span>
              </h1>
              <p className="mt-6 max-w-xl text-base text-white/70 sm:text-lg">
                {slide.desc}
              </p>
            </motion.div>
          </AnimatePresence>

          <div className="mt-9 flex flex-wrap items-center gap-4">
            <a
              href={slide.ctaHref}
              className="group inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-violet-600 to-purple-500 px-7 py-3.5 font-head text-sm font-600 uppercase tracking-wider text-white shadow-lg shadow-violet-900/40 transition-all hover:shadow-violet-700/60"
            >
              {slide.cta}
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </a>
            <a
              href={`https://wa.me/${brand.whatsapp}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-full border border-amber-400/40 px-7 py-3.5 font-head text-sm font-600 uppercase tracking-wider text-amber-300 transition-colors hover:bg-amber-400/10"
            >
              <Wind className="h-4 w-4" />
              Falar no WhatsApp
            </a>
          </div>

          {/* Controls */}
          <div className="mt-12 flex items-center gap-4">
            <button
              onClick={() => go(-1)}
              className="flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white/70 transition-colors hover:border-violet-500/50 hover:text-white"
              aria-label="Anterior"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <div className="flex gap-2">
              {heroSlides.map((s, i) => (
                <button
                  key={s.id}
                  onClick={() => setIndex(i)}
                  className={`h-1.5 rounded-full transition-all ${
                    i === index ? "w-8 bg-amber-400" : "w-3 bg-white/20"
                  }`}
                  aria-label={`Slide ${i + 1}`}
                />
              ))}
            </div>
            <button
              onClick={() => go(1)}
              className="flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white/70 transition-colors hover:border-violet-500/50 hover:text-white"
              aria-label="Próximo"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Cinematic stat panel */}
        <motion.div
          style={{ x: sx, y: sy }}
          className="lg:col-span-5"
        >
          <div className="glass animate-floaty relative mx-auto max-w-sm rounded-3xl p-7">
            <div className="absolute -top-3 left-7 rounded-full bg-amber-400 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-black">
              {brand.tagline}
            </div>
            <div className="grid grid-cols-2 gap-5">
              {[
                { k: "+12K", v: "Pipeiros na quebrada" },
                { k: "4.9\u2605", v: "Avaliação média" },
                { k: "24h", v: "Envio expresso" },
                { k: "5P", v: "Blindada premium" },
              ].map((stat) => (
                <div key={stat.v} className="rounded-2xl bg-white/5 p-4">
                  <p className="font-display text-3xl text-gradient">{stat.k}</p>
                  <p className="mt-1 text-xs text-white/60">{stat.v}</p>
                </div>
              ))}
            </div>
            <div className="mt-5 flex items-center gap-3 rounded-2xl border border-amber-400/20 bg-amber-400/5 p-4">
              <Wind className="h-6 w-6 shrink-0 text-amber-300" />
              <p className="text-xs text-white/70">
                Cortante testado em campo por quem vive o céu todo fim de semana.
              </p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* bottom fade */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-[#08060f] to-transparent" />
    </section>
  );
}
